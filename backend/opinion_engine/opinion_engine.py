"""
ECHO — Multi-Dimensional Opinion Space (MDOS) Engine
=====================================================

Production-ready, vectorized opinion dynamics simulation engine implementing:
  • Continuous bounded confidence intervals (Deffuant model)
  • Categorical homophily via social distance metric
  • Backfire repulsion for out-group interactions
  • Scale-Free (Barabási–Albert) and Small-World (Watts–Strogatz) topologies
  • Real-time polarization telemetry and influencer detection

Spec Source: Social Model.pdf — ECHO Documentation Suite
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import networkx as nx
import numpy as np

# ---------------------------------------------------------------------------
# Constants & Agent Matrix Column Indices (7D Vector)
# ---------------------------------------------------------------------------

COL_POLITICAL = 0    # P_i ∈ [-1.0, 1.0] (Ideology: Left to Right)
COL_ECONOMIC = 1     # E_i ∈ [ 0.0, 1.0] (Class: Poor to Rich)
COL_RELIGION = 2     # R_i ∈ ℤ⁺          (Categorical Identity Group)
COL_BELIEF = 3       # O_i ∈ [-1.0, 1.0] (Dynamic Narrative Opinion)
COL_GULLIBILITY = 4  # μ_i ∈ [0.01, 0.4] (Individual Learning Rate)
COL_AROUSAL = 5      # A_i ∈ [ 0.0, 1.0] (Dynamic Emotional State)
COL_LITERACY = 6     # S_i ∈ [ 0.0, 1.0] (Skepticism/Media Literacy)
COL_IS_BOT = 7       # B_i ∈ {0.0, 1.0}  (Bot status)
COL_IS_CLERIC = 8    # C_i ∈ {0.0, 1.0}  (Religious Authority Anchor)

INFLUENCER_PERCENTILE = 0.15  # Top 15% by belief delta magnitude
FATIGUE_LIMIT = 10            # Consecutive backfires before unfollowing

logger = logging.getLogger("echo.opinion_engine")


class Topology(Enum):
    """Supported network topology archetypes."""
    SCALE_FREE = "scale_free"         # Barabási–Albert (Influencer Dynamics)
    SMALL_WORLD = "small_world"       # Watts–Strogatz (Echo Chamber Dynamics)
    STOCHASTIC_BLOCK = "stochastic_block" # Stochastic Block Model


@dataclass
class TopologyParams:
    """Parameters for network generation."""
    m: int = 3       # Scale-Free: edges to attach from a new node to existing nodes
    k: int = 6       # Small-World: k nearest neighbors in a ring
    p: float = 0.3   # Small-World: probability of rewiring each edge
    sbm_blocks: int = 3      # SBM: Number of blocks
    sbm_p_in: float = 0.3    # SBM: In-block edge probability
    sbm_p_out: float = 0.01  # SBM: Out-block edge probability


MAX_HISTORY_TICKS = 1000  # Memory cap: ~16MB at 1000 agents × 1000 ticks

@dataclass
class TickTelemetry:
    """Telemetry snapshot for a single simulation tick."""
    tick: int
    polarization: float        # σ(beliefs) — standard deviation
    avg_belief: float          # μ(beliefs) — mean network belief
    edges_severed: int         # Cumulative total of unfollows/blocks
    edges_formed: int          # Cumulative total of new homophilic connections formed
    active_influencers: list[int] = field(default_factory=list)
    belief_snapshot: list[float] = field(default_factory=list)   # Full per-agent belief distribution
    arousal_snapshot: list[float] = field(default_factory=list)  # Full per-agent arousal distribution
    edge_count: int = 0                                           # Live edge count this tick


class OpinionEngine:
    """
    Multi-Dimensional Opinion Space (MDOS) simulation engine.

    Manages an N-agent network where each agent is represented by a 7D
    attribute vector. Agents update beliefs each tick via bounded confidence 
    convergence (in-group) or backfire repulsion (out-group), governed by a 
    pairwise social distance metric, individual gullibility, and emotional arousal.

    Parameters
    ----------
    n_agents : int
        Total number of agents in the network.
    topology : Topology
        Network structure archetype.
    w_pol : float
        Weight coefficient for political distance.
    w_econ : float
        Weight coefficient for economic distance.
    w_rel : float
        Weight coefficient for religious identity match.
    d_tolerance : float
        Base bounded confidence threshold. Scales dynamically with Arousal.
    gamma : float
        Backfire / polarization repulsion coefficient.
    topology_params : TopologyParams, optional
        Parameters specific to the chosen topology archetype.
    n_religious_groups : int
        Number of distinct religious/cultural groups.
    seed : int, optional
    """

    def __init__(
        self,
        n_agents: int = 500,
        topology: Topology = Topology.SMALL_WORLD,
        w_pol: float = 0.4,
        w_econ: float = 0.2,
        w_rel: float = 0.4,
        d_tolerance: float = 0.5,
        gamma: float = 0.1,
        topology_params: Optional[TopologyParams] = None,
        n_religious_groups: int = 3,
        seed: Optional[int] = None,
        fatigue_limit: int = 10,
        p_fact_checkers: float = 0.05,
        p_bots: float = 0.0,
        custom_edges: Optional[list[list[int]]] = None,
        arousal_decay: float = 0.8,
        extremism_threshold: float = 0.8,
        skepticism_threshold: float = 0.6,
        fatigue_cooldown: float = 0.2,
        belief_dist: str = "uniform",
        custom_agents_matrix: Optional[np.ndarray] = None,
        custom_adjacency: Optional[np.ndarray] = None,
        custom_anchors: Optional[list[int]] = None,
        religion_registry: Optional[Any] = None,
        narrative_profile: Optional[Any] = None,
    ) -> None:
        # Configuration
        self.n_agents = n_agents if custom_agents_matrix is None else custom_agents_matrix.shape[0]
        self.topology_type = topology
        self.w_pol = w_pol
        self.w_econ = w_econ
        self.w_rel = w_rel
        self.d_tolerance = d_tolerance
        self.gamma = gamma
        self.topology_params = topology_params or TopologyParams()
        self.n_religious_groups = n_religious_groups
        self.seed = seed
        self.fatigue_limit = fatigue_limit
        self.p_fact_checkers = p_fact_checkers
        self.p_bots = p_bots
        self.custom_edges = custom_edges
        self.arousal_decay = arousal_decay
        self.extremism_threshold = extremism_threshold
        self.skepticism_threshold = skepticism_threshold
        self.fatigue_cooldown = fatigue_cooldown
        self.belief_dist = belief_dist
        
        self.religion_registry = religion_registry
        self.narrative_profile = narrative_profile

        # Engine State
        self.algorithm_active = False
        self.custom_update_logic: Optional[callable] = None

        # Internal state & telemetry
        self._tick: int = 0
        self._history: list[TickTelemetry] = []
        self._last_belief_delta: np.ndarray = np.zeros(n_agents, dtype=np.float64)
        self._rng = np.random.default_rng(seed)

        # Initialize the data matrices
        if custom_agents_matrix is not None:
            self._agents = custom_agents_matrix.copy()
        else:
            self._agents = self._init_agents()
            
        self._baseline_beliefs = self._agents[:, COL_BELIEF].copy()
        
        if custom_adjacency is not None:
            self._adjacency = custom_adjacency.copy()
            self._graph = nx.from_numpy_array(self._adjacency)
        else:
            self._graph, self._adjacency = self._init_network()
            
        self.anchors = custom_anchors or []
        
        # Structural state (Connection Fatigue)
        self._fatigue = np.zeros((self.n_agents, self.n_agents), dtype=np.float64)
        self._severed_edges = np.zeros((self.n_agents, self.n_agents), dtype=bool)
        self._total_edges_severed = 0
        self._total_edges_formed = 0

        logger.info(
            "OpinionEngine initialized: %d agents, topology=%s",
            self.n_agents, topology.value,
        )

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _init_agents(self) -> np.ndarray:
        """Create the N×9 agent attribute matrix with random distributions."""
        agents = np.empty((self.n_agents, 9), dtype=np.float64)

        # Sociological Anchors
        agents[:, COL_POLITICAL] = self._rng.uniform(-1.0, 1.0, self.n_agents)
        agents[:, COL_ECONOMIC] = self._rng.uniform(0.0, 1.0, self.n_agents)
        
        if self.religion_registry:
            agents[:, COL_RELIGION] = self._rng.choice(
                self.religion_registry.n_religions,
                size=self.n_agents,
                p=self.religion_registry.demographic_weights
            ).astype(np.float64)
        else:
            agents[:, COL_RELIGION] = self._rng.integers(1, self.n_religious_groups + 1, self.n_agents).astype(np.float64)
        
        # Dynamic State
        if self.belief_dist == "normal":
            agents[:, COL_BELIEF] = np.clip(self._rng.normal(0.0, 0.3, self.n_agents), -1.0, 1.0)
        elif self.belief_dist == "bimodal":
            mask = self._rng.choice([True, False], size=self.n_agents)
            left_peak = self._rng.normal(-0.6, 0.2, self.n_agents)
            right_peak = self._rng.normal(0.6, 0.2, self.n_agents)
            beliefs = np.where(mask, left_peak, right_peak)
            agents[:, COL_BELIEF] = np.clip(beliefs, -1.0, 1.0)
        else: # uniform
            agents[:, COL_BELIEF] = self._rng.uniform(-1.0, 1.0, self.n_agents)
        
        # Psychological Traits
        agents[:, COL_GULLIBILITY] = self._rng.uniform(0.01, 0.4, self.n_agents)
        
        if self.religion_registry:
            for r_id in range(self.religion_registry.n_religions):
                mask = agents[:, COL_RELIGION] == r_id
                r_range = self.religion_registry.profiles[r_id].base_gullibility_range
                agents[mask, COL_GULLIBILITY] = self._rng.uniform(r_range[0], r_range[1], mask.sum())

        agents[:, COL_AROUSAL] = 0.0
        if self.narrative_profile and self.religion_registry:
            for r_id, name in enumerate(self.religion_registry.names):
                mask = agents[:, COL_RELIGION] == r_id
                sens = self.narrative_profile.group_sensitivity.get(name, 0.3)
                agents[mask, COL_AROUSAL] = sens * self.narrative_profile.initial_arousal_spike
                
        agents[:, COL_LITERACY] = self._rng.uniform(0.0, 1.0, self.n_agents)

        # Default all to not bot and not cleric
        agents[:, COL_IS_BOT] = 0.0
        agents[:, COL_IS_CLERIC] = 0.0
        
        # Assign Clerics
        if self.religion_registry:
            for r_id in range(self.religion_registry.n_religions):
                candidates = np.where(agents[:, COL_RELIGION] == r_id)[0]
                if len(candidates) > 0:
                    cleric_id = self._rng.choice(candidates)
                    agents[cleric_id, COL_IS_CLERIC] = 1.0
                    agents[cleric_id, COL_GULLIBILITY] = 0.0

        # Apply Fact-Checkers
        n_fact_checkers = int(self.n_agents * self.p_fact_checkers)
        if n_fact_checkers > 0:
            fc_indices = self._rng.choice(self.n_agents, n_fact_checkers, replace=False)
            agents[fc_indices, COL_LITERACY] = 1.0
            agents[fc_indices, COL_GULLIBILITY] = 0.01
            agents[fc_indices, COL_BELIEF] = 0.0

        # Apply Bots
        n_bots = int(self.n_agents * self.p_bots)
        if n_bots > 0:
            non_fc_indices = np.setdiff1d(np.arange(self.n_agents), fc_indices if n_fact_checkers > 0 else [])
            bot_indices = self._rng.choice(non_fc_indices, min(n_bots, len(non_fc_indices)), replace=False)
            agents[bot_indices, COL_IS_BOT] = 1.0
            agents[bot_indices, COL_LITERACY] = 0.0
            agents[bot_indices, COL_GULLIBILITY] = 0.0 
            half_bots = len(bot_indices) // 2
            agents[bot_indices[:half_bots], COL_BELIEF] = 1.0
            agents[bot_indices[half_bots:], COL_BELIEF] = -1.0

        return agents

    def _init_network(self) -> tuple[nx.Graph, np.ndarray]:
        """Generate the network graph and its adjacency matrix."""
        n = self.n_agents
        params = self.topology_params

        if self.custom_edges is not None:
            graph = nx.Graph()
            graph.add_nodes_from(range(n))
            graph.add_edges_from(self.custom_edges)
        elif self.topology_type == Topology.SCALE_FREE:
            graph = nx.barabasi_albert_graph(n, params.m, seed=self.seed)
        elif self.topology_type == Topology.SMALL_WORLD:
            k = max(2, params.k if params.k % 2 == 0 else params.k + 1)
            graph = nx.watts_strogatz_graph(n, k, params.p, seed=self.seed)
        elif self.topology_type == Topology.STOCHASTIC_BLOCK:
            sizes = [n // params.sbm_blocks] * params.sbm_blocks
            sizes[-1] += n % params.sbm_blocks
            p_matrix = [[params.sbm_p_in if i == j else params.sbm_p_out for j in range(params.sbm_blocks)] for i in range(params.sbm_blocks)]
            graph = nx.stochastic_block_model(sizes, p_matrix, seed=self.seed)
        else:
            raise ValueError(f"Unsupported topology: {self.topology_type}")

        adjacency = nx.to_numpy_array(graph, dtype=np.float64)
        return graph, adjacency

    # ------------------------------------------------------------------
    # Distance Computation
    # ------------------------------------------------------------------

    def _compute_social_distance_matrix(self) -> np.ndarray:
        """Compute the N×N social distance matrix D(i,j) via broadcasting."""
        P = self._agents[:, COL_POLITICAL]
        E = self._agents[:, COL_ECONOMIC]
        R = self._agents[:, COL_RELIGION].astype(np.int32)

        pol_dist = np.abs(P[:, None] - P[None, :])
        econ_dist = np.abs(E[:, None] - E[None, :])
        rel_match = (R[:, None] == R[None, :]).astype(np.float64)

        base_dist = self.w_pol * pol_dist + self.w_econ * econ_dist - self.w_rel * rel_match
        
        if self.religion_registry:
            friction = self.religion_registry.friction_matrix[R[:, None], R[None, :]]
            return base_dist + friction
        else:
            return base_dist

    def get_social_distance_matrix(self) -> np.ndarray:
        """
        Calculates and returns the social distance matrix D between all agents
        based on their political, economic, and religious profiles.
        """
        return self._compute_social_distance_matrix()

    # ------------------------------------------------------------------
    # Core Physics Loop
    # ------------------------------------------------------------------

    def step(self) -> dict[str, Any]:
        """Advance the simulation by one tick and process 9D dynamics."""
        self._tick += 1
        self._agents[:, COL_AROUSAL] *= self.arousal_decay
        
        old_beliefs = self._agents[:, COL_BELIEF].copy()
        D = self.get_social_distance_matrix()

        if self.custom_update_logic is not None:
            try:
                new_beliefs, top_influencers = self.custom_update_logic(old_beliefs.copy(), self._adjacency.copy())
            except Exception as e:
                logger.error(f"Custom algorithm failed: {e}. Falling back to default.")
                new_beliefs, top_influencers = self._apply_opinion_dynamics(D, old_beliefs)
        else:
            new_beliefs, top_influencers = self._apply_opinion_dynamics(D, old_beliefs)

        self._agents[:, COL_BELIEF] = new_beliefs
        self._last_belief_delta = np.abs(new_beliefs - old_beliefs)

        polarization = float(np.std(new_beliefs))
        avg_belief = float(np.mean(new_beliefs))
        active_influencers = self.get_active_influencers().tolist()
        live_edge_count = int(self._adjacency.sum() / 2)

        telemetry = TickTelemetry(
            tick=self._tick,
            polarization=polarization,
            avg_belief=avg_belief,
            edges_severed=self._total_edges_severed,
            edges_formed=self._total_edges_formed,
            active_influencers=active_influencers,
            belief_snapshot=new_beliefs.tolist(),
            arousal_snapshot=self._agents[:, COL_AROUSAL].tolist(),
            edge_count=live_edge_count,
        )

        if len(self._history) >= MAX_HISTORY_TICKS:
            self._history.pop(0)
        self._history.append(telemetry)

        return {
            "tick": self._tick,
            "polarization": polarization,
            "avg_belief": avg_belief,
            "edges_severed": self._total_edges_severed,
            "edges_formed": self._total_edges_formed,
            "active_influencers": active_influencers,
            "top_influencers": top_influencers.tolist()
        }

    def _apply_opinion_dynamics(self, D: np.ndarray, beliefs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Apply Convergence, Backfire, Literacy limits, and Structural Fatigue."""
        adj = self._adjacency
        gullibility = self._agents[:, COL_GULLIBILITY] 
        arousal = self._agents[:, COL_AROUSAL]         
        base_literacy = self._agents[:, COL_LITERACY]       

        extremism = np.abs(beliefs)
        literacy = base_literacy * (1.0 - extremism)
        
        eff_tolerance = self.d_tolerance * (1.0 - arousal) * (1.0 - extremism * 0.5)
        
        if self.religion_registry and self.narrative_profile:
            r_ids = self._agents[:, COL_RELIGION].astype(int)
            dogma_scores = self.religion_registry.dogma_matrix[r_ids, self.narrative_profile.topic_index]
            eff_tolerance *= (1.0 - dogma_scores)
            
        eff_tolerance_matrix = np.maximum(0.01, eff_tolerance[:, None])
        belief_diff = beliefs[None, :] - beliefs[:, None]

        extreme_post = np.abs(beliefs[None, :]) > self.extremism_threshold
        skeptic_mask = (literacy[:, None] > self.skepticism_threshold) & extreme_post
        
        converge_mask = (adj > 0) & (D <= eff_tolerance_matrix) & ~skeptic_mask
        
        # Incorporate Cleric Authority Multipliers
        authority_mult = np.ones_like(adj)
        if self.religion_registry:
            cleric_mask = self._agents[:, COL_IS_CLERIC] == 1.0
            for i in range(self.n_agents):
                if cleric_mask[i]:
                    r_i = int(self._agents[i, COL_RELIGION])
                    # Boost for own religion, penalty for others
                    same_rel = self._agents[:, COL_RELIGION] == r_i
                    authority_mult[i, same_rel] = self.religion_registry.authority_multipliers[r_i]
                    authority_mult[i, ~same_rel] = -1.0
        
        converge_delta = gullibility[:, None] * (1.0 - D) * belief_diff * authority_mult
        converge_delta *= converge_mask

        sign_i = np.sign(beliefs)[:, None]
        sign_j = np.sign(beliefs)[None, :]
        sign_mismatch = sign_i != sign_j

        backfire_mask = (adj > 0) & (D > eff_tolerance_matrix) & sign_mismatch
        backfire_delta = -self.gamma * D * np.sign(belief_diff)
        backfire_delta *= backfire_mask

        backfire_counts = backfire_mask.sum(axis=1)
        self._agents[:, COL_AROUSAL] = np.clip(arousal + (backfire_counts * 0.1), 0.0, 1.0)

        self._fatigue[backfire_mask] += 1
        self._fatigue[converge_mask] = 0
        self._fatigue = np.maximum(0.0, self._fatigue - self.fatigue_cooldown)

        sever_mask = self._fatigue >= self.fatigue_limit
        if np.any(sever_mask):
            severed_count = np.sum(adj[sever_mask] > 0)
            self._total_edges_severed += int(severed_count)
            self._adjacency[sever_mask] = 0
            self._adjacency[sever_mask.T] = 0 
            self._severed_edges[sever_mask] = True
            self._severed_edges[sever_mask.T] = True

        heal_mask = self._severed_edges & (self._fatigue == 0.0) & (adj == 0)
        heal_prob_mask = self._rng.random((self.n_agents, self.n_agents)) < 0.05
        active_heals = heal_mask & heal_prob_mask
        active_heals = active_heals | active_heals.T

        if np.any(active_heals):
            self._total_edges_formed += int(np.sum(active_heals) // 2)
            self._adjacency[active_heals] = 1.0
            self._severed_edges[active_heals] = False

        unconnected_mask = (adj == 0) & (np.eye(self.n_agents) == 0)
        homophily_mask = unconnected_mask & (np.abs(belief_diff) < 0.1)
        form_prob = 0.05 if self.algorithm_active else 0.001
        form_prob_mask = self._rng.random((self.n_agents, self.n_agents)) < form_prob
        new_edges_mask = homophily_mask & form_prob_mask
        new_edges_mask = new_edges_mask | new_edges_mask.T
        
        if np.any(new_edges_mask):
            self._total_edges_formed += int(np.sum(new_edges_mask) // 2)
            self._adjacency[new_edges_mask] = 1.0
            self._fatigue[new_edges_mask] = 0

        total_delta = converge_delta + backfire_delta
        active_neighbors = np.maximum((converge_mask | backfire_mask).sum(axis=1), 1.0)
        mean_delta = total_delta.sum(axis=1) / active_neighbors
        abs_delta = np.abs(total_delta)
        top_influencers = np.argsort(abs_delta, axis=1)[:, -3:][:, ::-1]

        return np.clip(beliefs + mean_delta, -1.0, 1.0), top_influencers

    # ------------------------------------------------------------------
    # API Hooks
    # ------------------------------------------------------------------

    def get_active_influencers(self) -> np.ndarray:
        n_influencers = max(1, int(np.ceil(self.n_agents * INFLUENCER_PERCENTILE)))
        top_indices = np.argpartition(self._last_belief_delta, -n_influencers)[-n_influencers:]
        sorted_order = np.argsort(self._last_belief_delta[top_indices])[::-1]
        return top_indices[sorted_order]

    def get_telemetry(self) -> dict[str, Any]:
        if not self._history:
            beliefs = self._agents[:, COL_BELIEF]
            return {
                "current_tick": 0,
                "polarization": float(np.std(beliefs)),
                "avg_belief": float(np.mean(beliefs)),
                "edges_severed": 0,
                "edges_formed": 0,
                "history": [],
            }
        latest = self._history[-1]
        return {
            "current_tick": latest.tick,
            "polarization": latest.polarization,
            "avg_belief": latest.avg_belief,
            "edges_severed": latest.edges_severed,
            "edges_formed": latest.edges_formed,
            "history": [
                {
                    "tick": t.tick,
                    "polarization": t.polarization,
                    "avg_belief": t.avg_belief,
                    "edges_severed": t.edges_severed,
                    "edges_formed": t.edges_formed,
                    "n_influencers": len(t.active_influencers),
                }
                for t in self._history
            ],
        }

    def get_agent_stubbornness(self, agent_id: int) -> float:
        """Stubbornness trait is 1.0 minus gullibility."""
        return float(1.0 - self._agents[agent_id, COL_GULLIBILITY])

    def get_agent_baseline_belief(self, agent_id: int) -> float:
        """Return the baseline belief at tick 0 for the agent."""
        return float(self._baseline_beliefs[agent_id])

    def get_agent_belief(self, agent_id: int) -> float:
        """Return the current belief of the agent."""
        return float(self._agents[agent_id, COL_BELIEF])

    def get_agent_detail(self, agent_id: int) -> dict[str, Any]:
        """Return the full 7D attribute detail for a single agent."""
        row = self._agents[agent_id]
        return {
            "agent_id": agent_id,
            "political": float(row[COL_POLITICAL]),
            "economic": float(row[COL_ECONOMIC]),
            "religion": int(row[COL_RELIGION]),
            "belief": float(row[COL_BELIEF]),
            "gullibility": float(row[COL_GULLIBILITY]),
            "arousal": float(row[COL_AROUSAL]),
            "literacy": float(row[COL_LITERACY]),
            "is_bot": bool(row[COL_IS_BOT] > 0.5),
            "last_belief_delta": float(self._last_belief_delta[agent_id]),
            "is_anchor": agent_id in self.anchors,
        }

    def get_agent_states(self) -> np.ndarray:
        return self._agents.copy()

    def get_adjacency(self) -> np.ndarray:
        return self._adjacency.copy()

    def get_graph(self) -> nx.Graph:
        # Re-build graph from current adjacency to reflect severed edges
        return nx.from_numpy_array(self._adjacency)

    def force_edge(self, u: int, v: int) -> None:
        """Manually form an edge between two agents."""
        if 0 <= u < self.n_agents and 0 <= v < self.n_agents and u != v:
            self._adjacency[u, v] = 1.0
            self._adjacency[v, u] = 1.0
            self._fatigue[u, v] = 0.0
            self._fatigue[v, u] = 0.0
            self._severed_edges[u, v] = False
            self._severed_edges[v, u] = False

    def inject_narrative(self, agent_id: int, belief_score: float) -> None:
        """Force an agent to adopt a specific belief score (Patient Zero)."""
        belief_score = np.clip(belief_score, -1.0, 1.0)
        self._agents[agent_id, COL_BELIEF] = belief_score

    def global_broadcast(self, belief_shift: float, arousal_shift: float) -> None:
        """Applies a system-wide exogenous shock to all agents."""
        new_beliefs = self._agents[:, COL_BELIEF] + belief_shift
        self._agents[:, COL_BELIEF] = np.clip(new_beliefs, -1.0, 1.0)
        
        new_arousal = self._agents[:, COL_AROUSAL] + arousal_shift
        self._agents[:, COL_AROUSAL] = np.clip(new_arousal, 0.0, 1.0)

    def export_state_log(self, filepath: str | Path) -> None:
        """Export tick history to a JSONL file."""
        with open(Path(filepath), "w", encoding="utf-8") as f:
            for record in self._history:
                entry = {
                    "tick": record.tick,
                    "polarization": record.polarization,
                    "avg_belief": record.avg_belief,
                    "edges_severed": record.edges_severed,
                    "edges_formed": record.edges_formed,
                    "active_influencers": record.active_influencers,
                }
                f.write(json.dumps(entry) + "\n")

    @property
    def tick(self) -> int:
        return self._tick

    def __repr__(self) -> str:
        beliefs = self._agents[:, COL_BELIEF]
        return (
            f"OpinionEngine(n={self.n_agents}, tick={self._tick}, "
            f"polarization={np.std(beliefs):.4f}, "
            f"severed_edges={self._total_edges_severed}, "
            f"formed_edges={self._total_edges_formed})"
        )