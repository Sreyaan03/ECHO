import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("echo.contagion_manager")

@dataclass
class ContagionTopic:
    topic_id: int
    topic_name: str
    narrative_profile: any  # NarrativeProfile
    beliefs: np.ndarray
    baseline_beliefs: np.ndarray
    influencer_memory: Dict[int, List[str]] = field(default_factory=dict)
    
class ContagionManager:
    """
    Manages multi-topic contagion, allowing secondary and tertiary narratives
    to propagate through the ECHO network using the primary engine's topology.
    
    All beliefs are independent per-topic arrays. The primary engine's adjacency
    matrix and religion registry are reused for physics — making the secondary
    topic fully religion-aware, just like the primary topic.
    """
    def __init__(self):
        self.topics: Dict[int, ContagionTopic] = {}
        
    def add_topic(
        self,
        topic_id: int,
        topic_name: str,
        narrative_profile,
        num_agents: int,
        belief_dist: str = 'uniform',
        engine=None,           # pass the engine so we can apply religion-aware init
    ):
        """Initializes a new topic with its own independent belief array.
        
        If `engine` is supplied and the narrative_profile has group_sensitivity,
        initial arousal is seeded per religious group — identical to how the
        primary engine does it in _init_agents().
        """
        rng = np.random.default_rng()
        
        if belief_dist == 'uniform':
            beliefs = rng.uniform(-1.0, 1.0, num_agents)
        elif belief_dist == 'normal':
            beliefs = np.clip(rng.normal(0, 0.4, num_agents), -1.0, 1.0)
        elif belief_dist == 'bimodal':
            mask = rng.choice([True, False], size=num_agents)
            left  = np.clip(rng.normal(-0.6, 0.2, num_agents), -1, 0)
            right = np.clip(rng.normal( 0.6, 0.2, num_agents),  0, 1)
            beliefs = np.where(mask, right, left)
        else:
            beliefs = np.zeros(num_agents)

        # ── Religion-aware belief seeding ──────────────────────────────────
        # If the narrative_profile carries an initial_belief_valence,
        # shift each agent's starting belief toward that valence weighted
        # by their religious group's sensitivity — matching primary engine logic.
        if engine is not None and engine.religion_registry and narrative_profile:
            r_ids = engine._agents[:, 2].astype(int)   # COL_RELIGION = 2
            registry = engine.religion_registry
            for r_id, name in enumerate(registry.names):
                mask = r_ids == r_id
                sens = narrative_profile.group_sensitivity.get(name, 0.3)
                valence = narrative_profile.initial_belief_valence
                # Pull beliefs toward valence proportional to sensitivity
                beliefs[mask] = np.clip(
                    beliefs[mask] * (1.0 - sens) + valence * sens,
                    -1.0, 1.0
                )
                
        baseline_beliefs = beliefs.copy()
        
        self.topics[topic_id] = ContagionTopic(
            topic_id=topic_id,
            topic_name=topic_name,
            narrative_profile=narrative_profile,
            beliefs=beliefs,
            baseline_beliefs=baseline_beliefs
        )
        logger.info(f"Added secondary topic {topic_id}: {topic_name} (religion-aware: {engine is not None})")
        
    def get_topic(self, topic_id: int) -> Optional[ContagionTopic]:
        return self.topics.get(topic_id)
        
    def step(self, engine, topic_id: int):
        """
        Runs one step of Deffuant bounded confidence on the specified topic,
        using the main engine's adjacency matrix and religion-aware tolerance.
        
        Mirrors _apply_opinion_dynamics() logic from OpinionEngine:
          - effective tolerance is modulated by dogma score on the classified topic
          - gullibility determines convergence rate
        """
        topic = self.get_topic(topic_id)
        if not topic:
            return

        # ── Use _adjacency (numpy array), NOT .A ───────────────────────────
        adj = engine._adjacency          # shape (N, N), float64
        N   = engine.n_agents
        registry = engine.religion_registry
        profile  = topic.narrative_profile

        beliefs     = topic.beliefs                            # shape (N,)
        gullibility = engine._agents[:, 4]                    # COL_GULLIBILITY
        arousal     = engine._agents[:, 5]                    # COL_AROUSAL

        # ── Religion-aware effective tolerance ────────────────────────────
        # Default to engine's d_tolerance, then modulate by dogma if available
        eff_tolerance = engine.d_tolerance * np.ones(N)
        if registry and profile:
            r_ids = engine._agents[:, 2].astype(int)          # COL_RELIGION
            # dogma_matrix shape: (n_religions, n_topics)
            dogma_scores = registry.dogma_matrix[r_ids, profile.topic_index]
            eff_tolerance *= (1.0 - dogma_scores)

        # Also reduce tolerance when agents are highly aroused (same as primary)
        eff_tolerance *= (1.0 - arousal)
        eff_tolerance  = np.maximum(0.01, eff_tolerance)

        # ── Vectorised social distance (reuse engine's method) ─────────────
        D = engine.get_social_distance_matrix()               # shape (N, N)

        # Build convergence mask: must be connected AND social-distance in range
        eff_tol_matrix = eff_tolerance[:, None]               # (N,1) broadcast
        converge_mask  = (adj > 0) & (D <= eff_tol_matrix)    # (N, N)

        if not converge_mask.any():
            return

        # ── Vectorised Deffuant update ─────────────────────────────────────
        belief_diff = beliefs[None, :] - beliefs[:, None]     # (N, N)
        mu          = gullibility[:, None]                     # learning rate

        # Each agent shifts toward neighbours within tolerance
        delta = np.where(converge_mask, mu * belief_diff, 0.0)
        topic.beliefs = np.clip(beliefs + delta.sum(axis=1) / (N ** 0.5), -1.0, 1.0)
        
    def detect_bridging_agents(self, engine, topic_id_b: int, threshold: float = 0.6) -> List[int]:
        """
        Returns agent indices that are highly polarized on BOTH topics simultaneously.
        These agents are the 'bridging' nodes that conflate the two narratives.
        """
        topic_b = self.get_topic(topic_id_b)
        if not topic_b:
            return []
            
        belief_a = engine._agents[:, 3]   # COL_BELIEF
        belief_b = topic_b.beliefs
        
        mask = (np.abs(belief_a) > threshold) & (np.abs(belief_b) > threshold)
        return np.where(mask)[0].tolist()
        
    def inject_topic(self, agent_id: int, topic_id: int, belief_score: float):
        """Manually set a specific agent's belief on a secondary topic."""
        topic = self.get_topic(topic_id)
        if topic:
            topic.beliefs[agent_id] = np.clip(belief_score, -1.0, 1.0)
