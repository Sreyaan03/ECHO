import csv
import json
import random
import math
from collections import deque
from pathlib import Path

# ECHO Simulation Constraints
TARGET_NODES = 500

def run_conversion():
    print("Loading Twitch Gamers dataset...")
    
    # 1. Load Edges into an adjacency list
    edges_file = Path("large_twitch_edges.csv")
    if not edges_file.exists():
        print(f"Error: {edges_file} not found.")
        return

    adj_list = {}
    with open(edges_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            u = int(row["numeric_id_1"])
            v = int(row["numeric_id_2"])
            if u not in adj_list: adj_list[u] = []
            if v not in adj_list: adj_list[v] = []
            adj_list[u].append(v)
            adj_list[v].append(u)

    print(f"Loaded graph with {len(adj_list)} total nodes.")

    # 2. Extract a connected subgraph of TARGET_NODES using BFS
    # Start from a node with a high degree to ensure a dense, interesting network
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

    # 3. Create a mapping from Twitch ID to ECHO ID (0 to 499)
    node_mapping = {old_id: new_id for new_id, old_id in enumerate(list(subgraph_nodes))}

    # 4. Load Features
    features_file = Path("large_twitch_features.csv")
    node_features = {}
    if features_file.exists():
        with open(features_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                nid = int(row["numeric_id"])
                if nid in subgraph_nodes:
                    node_features[nid] = row

    # 5. Build ECHO Agent Array
    echo_agents = []
    
    # Calculate max views for normalizing the "economic" height
    max_views = max([int(feat["views"]) for feat in node_features.values()] + [1])
    max_log_views = math.log(max_views + 1)

    for old_id in subgraph_nodes:
        new_id = node_mapping[old_id]
        feat = node_features.get(old_id, {})
        
        # Extract Twitch features
        views = int(feat.get("views", 0))
        mature = int(feat.get("mature", 0))
        life_time = int(feat.get("life_time", 1))
        dead_account = int(feat.get("dead_account", 0))

        # Map to ECHO physical dimensions
        # Economic (Height): Logarithmic mapping of view count
        economic = math.log(views + 1) / max_log_views if max_log_views > 0 else 0.1
        
        # Belief (Color): Let's map mature content streamers to the right (+1.0) and others slightly to the left
        # Add some noise so it's not perfectly binary
        base_belief = 0.6 if mature == 1 else -0.6
        belief = base_belief + random.uniform(-0.3, 0.3)
        belief = max(-1.0, min(1.0, belief))
        
        # Literacy: Based on account lifetime
        literacy = min(1.0, life_time / 3000.0)
        
        # Bots: Dead accounts become bots in the simulation
        is_bot = bool(dead_account == 1)

        agent = {
            "agent_id": new_id,
            "political": belief,
            "economic": economic,
            "religion": 1 if mature == 1 else 0, # Use religion block as mature status
            "belief": belief,
            "gullibility": max(0.01, 0.4 - (literacy * 0.3)), # More literate = less gullible
            "arousal": 0.1,
            "literacy": literacy,
            "is_bot": is_bot,
            "last_belief_delta": 0.0
        }
        echo_agents.append(agent)

    # Sort array by agent_id to ensure index matching
    echo_agents.sort(key=lambda x: x["agent_id"])

    # 6. Build ECHO Edges Array (only keeping edges within the subgraph)
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

    # 7. Package and Export JSON
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
                "message": "[SYSTEM] Successfully imported Twitch Gamers empirical dataset.",
                "bias": 0.0,
                "provider": "system"
            }
        ]
    }

    output_path = Path("twitch_echo_session.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2)

    print(f"Success! Saved ECHO session file to: {output_path.absolute()}")
    print("You can now click the 'Upload' icon in your Dashboard to load this network.")

if __name__ == "__main__":
    run_conversion()
