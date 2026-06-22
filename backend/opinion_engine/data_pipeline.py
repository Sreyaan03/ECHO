import json
import networkx as nx
import numpy as np
from .llm_client import EchoLLMClient

# Constants corresponding to opinion_engine.py
COL_POLITICAL = 0
COL_ECONOMIC = 1
COL_RELIGION = 2
COL_BELIEF = 3
COL_GULLIBILITY = 4
COL_AROUSAL = 5
COL_LITERACY = 6
COL_IS_BOT = 7

class OSINTDataPipeline:
    def __init__(self, llm_client: EchoLLMClient = None):
        self.llm_client = llm_client or EchoLLMClient()

    def load_topology(self, json_filepath: str):
        """
        Loads a JSON file representing the social network.
        Expected format:
        {
          "nodes": [ {"id": "user1", "bio": "Crypto enthusiast..."}, ... ],
          "edges": [ {"source": "user1", "target": "user2"}, ... ]
        }
        """
        with open(json_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return self.process_osint_graph(data)

    def process_osint_graph(self, data: dict):
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        
        G = nx.Graph()
        
        # Add nodes with data
        for i, node in enumerate(nodes):
            G.add_node(i, id=node.get("id", str(i)), bio=node.get("bio", ""))
            
        # Map string IDs to integer indices for edges
        id_to_idx = {node.get("id", str(i)): i for i, node in enumerate(nodes)}
        
        for edge in edges:
            src = id_to_idx.get(edge.get("source"))
            tgt = id_to_idx.get(edge.get("target"))
            if src is not None and tgt is not None and src != tgt:
                G.add_edge(src, tgt)

        # 1. Identify isolated nodes and inject "Ambient Cultural Node"
        isolated_nodes = list(nx.isolates(G))
        if isolated_nodes:
            ambient_node_idx = len(nodes)
            G.add_node(ambient_node_idx, id="ambient_culture", bio="General internet background noise")
            for node_idx in isolated_nodes:
                # Connect isolated nodes to the ambient node
                G.add_edge(node_idx, ambient_node_idx, weight=0.01)
        
        n_agents = len(G.nodes)
        agents_matrix = np.zeros((n_agents, 8), dtype=np.float64)
        
        # 2. Eigenvector Centrality to find Top 10% Anchors
        try:
            centrality = nx.eigenvector_centrality_numpy(G)
        except:
            centrality = nx.degree_centrality(G)
            
        # Sort nodes by centrality
        sorted_nodes = sorted(centrality.keys(), key=lambda k: centrality[k], reverse=True)
        top_10_percent_count = max(1, int(n_agents * 0.10))
        anchors = sorted_nodes[:top_10_percent_count]
        
        anchor_set = set(anchors)
        
        # 3. LLM Profiling for Anchors
        # We process anchors and then use LPA for the rest.
        # Since LPA is usually for labels, for continuous values we just average neighbors.
        for anchor in anchors:
            bio = G.nodes[anchor].get("bio", "")
            if bio.strip():
                # Extract using LLM
                pol, econ, rel, lit = self._extract_traits_from_bio(bio)
            else:
                pol, econ, rel, lit = (np.random.uniform(-1, 1), np.random.uniform(0, 1), 1, np.random.uniform(0.2, 0.8))
                
            agents_matrix[anchor, COL_POLITICAL] = pol
            agents_matrix[anchor, COL_ECONOMIC] = econ
            agents_matrix[anchor, COL_RELIGION] = rel
            agents_matrix[anchor, COL_BELIEF] = pol # Initial belief mirrors political ideology
            agents_matrix[anchor, COL_GULLIBILITY] = np.random.uniform(0.01, 0.4)
            agents_matrix[anchor, COL_AROUSAL] = 0.0
            agents_matrix[anchor, COL_LITERACY] = lit
            agents_matrix[anchor, COL_IS_BOT] = 0.0
            
        # 4. Label Propagation (Continuous Average) for the rest
        # Initialize the non-anchors randomly first
        for i in range(n_agents):
            if i not in anchor_set:
                agents_matrix[i, COL_POLITICAL] = np.random.uniform(-1, 1)
                agents_matrix[i, COL_ECONOMIC] = np.random.uniform(0, 1)
                agents_matrix[i, COL_RELIGION] = np.random.randint(1, 4)
                agents_matrix[i, COL_BELIEF] = agents_matrix[i, COL_POLITICAL]
                agents_matrix[i, COL_GULLIBILITY] = np.random.uniform(0.01, 0.4)
                agents_matrix[i, COL_AROUSAL] = 0.0
                agents_matrix[i, COL_LITERACY] = np.random.uniform(0.0, 1.0)
                agents_matrix[i, COL_IS_BOT] = 0.0

        # Run 5 iterations of averaging from neighbors to smooth out non-anchors
        for _ in range(5):
            new_matrix = agents_matrix.copy()
            for i in range(n_agents):
                if i not in anchor_set:
                    neighbors = list(G.neighbors(i))
                    if neighbors:
                        # Average Political and Economic
                        new_matrix[i, COL_POLITICAL] = np.mean([agents_matrix[n, COL_POLITICAL] for n in neighbors])
                        new_matrix[i, COL_ECONOMIC] = np.mean([agents_matrix[n, COL_ECONOMIC] for n in neighbors])
                        new_matrix[i, COL_BELIEF] = new_matrix[i, COL_POLITICAL]
            agents_matrix = new_matrix

        # Generate Adjacency Matrix
        adj_matrix = nx.to_numpy_array(G)
        
        return agents_matrix, adj_matrix, list(G.edges), anchors

    def _extract_traits_from_bio(self, bio: str):
        """
        Uses the LLM client to translate a bio into numeric values.
        Returns (Political, Economic, Religion_Group, Literacy)
        """
        prompt = (
            f"Analyze this user bio: '{bio}'.\n"
            "Output exactly a JSON object with four keys and numeric values. No other text.\n"
            "{\n"
            "  \"political\": (float between -1.0 for far-left and 1.0 for far-right),\n"
            "  \"economic\": (float between 0.0 for poor/working class and 1.0 for wealthy),\n"
            "  \"religion\": (integer 1, 2, or 3 representing primary cultural group),\n"
            "  \"literacy\": (float between 0.0 for highly gullible/uneducated and 1.0 for highly media literate)\n"
            "}"
        )
        try:
            # We bypass the standard evaluate_message and do a direct Groq/Gemini call if needed,
            # or just use a placeholder text generation. Since llm_client currently returns strings,
            # we will parse the JSON.
            # _call_groq expects (system_prompt, user_prompt)
            response_text = self.llm_client._call_groq(
                system_prompt="You are an OSINT analyzer.",
                user_prompt=prompt
            )
            
            import re
            json_match = re.search(r'\{.*\}', response_text.replace('\n', ''))
            if json_match:
                data = json.loads(json_match.group())
                pol = float(data.get("political", 0.0))
                econ = float(data.get("economic", 0.5))
                rel = int(data.get("religion", 1))
                lit = float(data.get("literacy", 0.5))
                return pol, econ, rel, lit
            else:
                return (0.0, 0.5, 1, 0.5)
        except Exception as e:
            print(f"OSINT Extraction Error: {e}")
            return (0.0, 0.5, 1, 0.5)
