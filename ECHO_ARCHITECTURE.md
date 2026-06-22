# ECHO Simulation Architecture & Design Documentation

This document outlines the core architectural decisions, the mathematical reasoning behind the "magic numbers," the frontend-backend communication flow, and the distinctions between the two primary network topology models in the ECHO Multi-Dimensional Opinion Space (MDOS) Simulation.

---

## 1. The "Magic Numbers": Mathematical & Behavioral Reasoning

The simulation relies on specific constants and thresholds to maintain a stable, realistic, and performant model of human opinion dynamics without devolving into chaos or stagnation.

### Network & Opinion Dynamics Bounds
* **`COL_GULLIBILITY` bounds `[0.01, 0.4]`**: This acts as the individual learning rate. By capping the maximum gullibility at 0.4 (40%), it prevents agents from radically flipping their beliefs entirely in a single tick. This simulates that even highly impressionable individuals change their core beliefs gradually over time rather than instantaneously.
* **`d_tolerance = 0.5` (Base)**: This is the bounded confidence threshold. Agents only converge in belief if their social distance is below 0.5. It ensures that agents who are fundamentally opposed (e.g., opposite ends of the political spectrum) experience backfire/repulsion rather than convergence.

### Psychological & Structural Mechanics
* **`INFLUENCER_PERCENTILE = 0.15` (15%)**: The engine flags the top 15% of agents (by the magnitude of their belief change in a single tick) as "active influencers." This strikes a balance between capturing significant narrative shifts in the network and optimizing performance by not overwhelming the LLM generation API with hundreds of requests.
* **`FATIGUE_LIMIT = 10` (or 5 via config)**: Defines how many consecutive negative (backfire) interactions an agent can tolerate before they sever ties (unfollow) a connection. This models the psychological toll of constant disagreement and drives the mechanical formation of Echo Chambers.
* **`arousal_decay = 0.8`**: After every tick, agent arousal is multiplied by 0.8 (decaying by 20%). This simulates the natural cooling of emotions over time if no new triggering interactions occur.
* **`extremism_threshold = 0.8` & `skepticism_threshold = 0.6`**: If an agent's absolute belief exceeds 0.8, they are considered "extreme." If an agent's media literacy is above 0.6, they act as skeptics. The engine uses these to dynamically lower media literacy when an agent becomes extreme (Confirmation Bias), locking them deeper into their echo chamber.

---

## 2. System Architecture

ECHO follows a decoupled Client-Server architecture utilizing a Python/FastAPI backend and a React/Zustand frontend. 

### Backend: Vectorized Physics Engine (`opinion_engine.py`)
The backend is not just an API; it is a high-performance simulation engine built using **NumPy** and **NetworkX**.
* **8D Agent Matrix**: Instead of looping over object-oriented classes, all agents are stored as a 2D NumPy array (`N x 8` columns, including the bot flag). This allows the use of vectorized operations (broadcasting) to calculate the social distance matrix `D(i,j)` for all agents simultaneously in massive parallel.
* **Core Loop (`step`)**: Each tick, the engine computes:
  1. Social Distance & Tolerance bounds (modified by Arousal & Extremism).
  2. **Bounded Convergence**: Pulling similar agents together.
  3. **Backfire Repulsion**: Pushing dissimilar agents apart.
  4. **Structural Updates**: Incrementing fatigue, severing ties, and forming new homophilic links.
* **LLM Integration (`server.py` & `llm_client.py`)**: After the physical tick, the top 3 influencers are evaluated via an LLM. The LLM reads the incoming narrative and mutates the text based on the influencer's current belief and stubbornness, driving the qualitative evolution of the simulation.

### Why Matrices over Objects (Data-Oriented Design)?
ECHO consciously avoids standard Object-Oriented Programming (e.g., an `Agent` class) for its core engine loop in favor of Data-Oriented Design (DOD). 
* **Speed of Vectorization**: Python loops carry significant interpreter overhead. Updating thousands of agents requires intensive mathematical operations per tick. By using NumPy matrices, the math is executed simultaneously in highly optimized C code via "broadcasting", completely avoiding the slow "Python Tax" of `for` loops.
* **Memory Locality**: Python objects are scattered across RAM, causing slow CPU cache misses during intensive iterations. A NumPy array is a single, continuous block of memory, allowing the CPU to load the network into ultra-fast L1/L2 cache and process the simulation near-instantly.

---

## 3. Frontend-Backend Communication

The application uses standard RESTful JSON API endpoints handled by FastAPI on the backend and `fetch` via Zustand actions on the frontend.

### The API Flow
1. **`POST /api/initialize`**: The user configures the simulation parameters (agent count, topology, topic) on the UI. The frontend sends this to the backend. The backend creates the NumPy matrix, generates the NetworkX graph, calculates static 3D layout coordinates (`X`, `Z`), generates the initial "Patient Zero" LLM post, and returns the entire starting state.
2. **`POST /api/step`**: Triggered automatically by a `setInterval` loop in the frontend (1 tick per second). The backend processes the matrix math, queries the LLM for the top 3 influencers, and returns the updated belief arrays, arousal arrays, updated edge lists (for severed/formed connections), and narrative logs.
3. **`POST /api/inject`**: Triggered when a user clicks an agent in the 3D canvas and manually injects a belief, allowing for interactive "God-mode" manipulation.

---

## 4. How the Frontend Works

The frontend is built with React, utilizing **Zustand** for global state management and **Web Audio API** for procedural sound design.

### State Management (`useSimulationStore.js`)
* The store acts as the single source of truth, holding the `agents` array, active `edges`, `positions`, and simulation `telemetry`.
* **The Animation Loop**: When the user hits play, `startSimulationLoop` initializes a `setInterval` that fires every 1 second. Each interval calls `stepSimulation()`, hitting the backend `/api/step` endpoint.
* **Reactivity**: As the store updates `agents` and `edges`, the React components (specifically the `VoxelCanvas` WebGL view) automatically re-render. Belief maps to color (Blue to Red), Arousal maps to vertical height (Y-axis jumping), and the line segments update as connections sever and heal.
* **Audio Feedback**: The store generates procedural, synthesizer-based audio. A soft pop plays for every tick, a sharp snap plays when edges are severed, and a digital chime plays on manual narrative injection.

---

## 5. Distribution Models & Network Topologies

The simulation relies on distribution models and graph topologies to define the starting state of the agents and how they are connected. While the engine uses specific defaults, its architecture allows for highly flexible substitutions.

### Agent Attribute Distributions
Currently, agent traits (Ideology, Wealth, Belief) are generated using a **Uniform Distribution** (e.g., `np.random.uniform`), meaning every value across the spectrum has an equal chance of being assigned. The architecture easily supports swapping these distributions to model different populations:
* **Normal (Gaussian) Distribution**: Using `np.random.normal()`, you could simulate a population where most people are moderate (centered around 0.0), with very few extremists. This models realistic general populations.
* **Bimodal Distribution**: Sampling from two separate Normal distributions (e.g., centered at -0.7 and +0.7) simulates a population that is *already deeply polarized* at the start, skipping natural echo chamber formation.
* **Pareto Distribution**: Using `np.random.pareto()` models the 80/20 rule, useful for concentrating wealth (`COL_ECONOMIC`) or skepticism into a tiny fraction of the population.

### Network Topology Models
The simulation currently offers two fundamentally different mathematical graph models using `NetworkX`, though many others can be plugged in.

#### 1. Small-World Topology (Watts-Strogatz Model)
* **How it works**: Agents are arranged in a ring and connected to their `k` nearest neighbors. Then, with a probability `p`, edges are randomly "rewired" to distant nodes.
* **Real-World Equivalent**: Real-life friend groups, Facebook, or local communities.
* **Simulation Effect**: It features high local clustering (cliques) but short average path lengths. This model is exceptional at demonstrating the formation of **tight-knit Echo Chambers**, as local clusters easily converge, but the few bridging connections to other clusters are highly susceptible to backfire and severing (fatigue).

#### 2. Scale-Free Topology (Barabási-Albert Model)
* **How it works**: Uses "preferential attachment." As new nodes are added to the network during generation, they are mathematically more likely to connect to nodes that *already* have a high number of connections.
* **Real-World Equivalent**: Twitter (X), Instagram, or the broader Internet.
* **Simulation Effect**: Results in a network dominated by a few massive "Hubs" (Mega-influencers) and many nodes with very few connections. In this model, narratives spread rapidly from the center outwards. Echo chambers are less about local cliques and more about massive orbital factions revolving around polarized influencer hubs.

#### Alternative Topologies (Extensibility)
Because the backend uses `NetworkX`, it is trivial to inject other topologies:
* **Erdős-Rényi (Random Graph)**: A completely random network serving as a control model.
* **Stochastic Block Model (SBM)**: Explicitly creates isolated "communities" to test narrative jumps across completely segregated cultural blocks.
