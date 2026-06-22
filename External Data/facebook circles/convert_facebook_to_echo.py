import gzip
import json
import random
import math
from collections import deque
from pathlib import Path

# ECHO Simulation Constraints
TARGET_NODES = 500

def run_conversion():
    print("Loading Facebook Ego Networks dataset...")
    
    # 1. Load Edges from gzip
    edges_file = Path("facebook_combined.txt.gz")
    if not edges_file.exists():
        print(f"Error: {edges_file} not found.")
        return

    adj_list = {}
    with gzip.open(edges_file, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                u = int(parts[0])
                v = int(parts[1])
                if u not in adj_list: adj_list[u] = []
                if v not in adj_list: adj_list[v] = []
                adj_list[u].append(v)
                adj_list[v].append(u)

    print(f"Loaded graph with {len(adj_list)} total nodes.")

    # 2. Extract a connected subgraph of TARGET_NODES using BFS
    # Facebook is highly clustered (homophily). We start from a random highly connected node.
    start_node = max(adj_list.keys(), key=lambda k: len(adj_list[k]))
    
    visited = set()
    queue = deque([start_node])
    subgraph_nodes = set()

    print(f"Extracting dense subgraph of {TARGET_NODES} nodes starting from Node {start_node}...")
    while queue and len(subgraph_nodes) < TARGET_NODES:
        curr = queue.popleft()
        if curr not in visited:
            visited.add(curr)
            subgraph_nodes.add(curr)
            # Add neighbors to queue
            for neighbor in adj_list.get(curr, []):
                if neighbor not in visited:
                    queue.append(neighbor)

    # 3. Create a mapping from FB ID to ECHO ID (0 to 499)
    node_mapping = {old_id: new_id for new_id, old_id in enumerate(list(subgraph_nodes))}

    # 4. Build ECHO Agent Array
    echo_agents = []
    
    # Calculate max degree (friends) for normalizing "economic" height
    degrees = {nid: len([v for v in adj_list.get(nid, []) if v in subgraph_nodes]) for nid in subgraph_nodes}
    max_degree = max(degrees.values()) if degrees else 1
    max_log_degree = math.log(max_degree + 1)

    for old_id in subgraph_nodes:
        new_id = node_mapping[old_id]
        
        # We don't have explicit features in the combined file, so we infer them from network topology
        degree = degrees[old_id]
        
        # Economic (Height): Based on number of friends (log scale)
        economic = math.log(degree + 1) / max_log_degree if max_log_degree > 0 else 0.1
        
        # Belief: Randomly assign to create natural starting polarization
        belief = random.uniform(-0.8, 0.8)
        
        # Literacy: Random distribution
        literacy = random.uniform(0.2, 0.9)
        
        # Bots: Make 5% of the least connected nodes into bots
        is_bot = (degree <= 2 and random.random() < 0.2)

        agent = {
            "agent_id": new_id,
            "political": belief,
            "economic": economic,
            "religion": 1 if belief > 0 else 0, # Map right-leaning to religion=1
            "belief": belief,
            "gullibility": max(0.01, 0.5 - (literacy * 0.4)), # More literate = less gullible
            "arousal": 0.05,
            "literacy": literacy,
            "is_bot": is_bot,
            "last_belief_delta": 0.0
        }
        echo_agents.append(agent)

    # Sort array by agent_id to ensure index matching
    echo_agents.sort(key=lambda x: x["agent_id"])

    # 5. Build ECHO Edges Array (only keeping edges within the subgraph)
    echo_edges = []
    seen_edges = set()
    
    for u in subgraph_nodes:
        for v in adj_list.get(u, []):
            if v in subgraph_nodes:
                new_u = node_mapping[u]
                new_v = node_mapping[v]
                
                # Ensure undirected edges aren't duplicated
                edge = tuple(sorted([new_u, new_v]))
                if edge not in seen_edges:
                    seen_edges.add(edge)
                    echo_edges.append(list(edge))

    print(f"Generated ECHO graph: {len(echo_agents)} Agents, {len(echo_edges)} Edges.")

    # 6. Package and Export JSON
    session_data = {
        "total_ticks": 0,
        "final_polarization": 0.0,
        "agents": echo_agents,
        "edges": echo_edges,
        "history": [],
        "narrative_logs": [
            {
                "tick": 0,
                "agent_id": -1,
                "message": "[SYSTEM] Successfully imported Facebook Social Circles empirical dataset.",
                "bias": 0.0,
                "provider": "system"
            }
        ]
    }

    output_path = Path("facebook_echo_session.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2)

    print(f"Success! Saved ECHO session file to: {output_path.absolute()}")
    print("You can now click the 'Upload' icon in your Dashboard to load this network.")

if __name__ == "__main__":
    run_conversion()
