import json
import logging
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
import os

logger = logging.getLogger("echo.religion_registry")

@dataclass
class ReligionProfile:
    id: int
    name: str
    demographic_weight: float
    dogma_vector: List[float]
    authority_multiplier: float
    base_gullibility_range: Tuple[float, float]

class ReligionRegistry:
    """
    Loads and compiles religions.json into NumPy matrices for the OpinionEngine.
    """
    def __init__(self, data: dict):
        self.data = data
        self.version = data.get("version", "1.0")
        self.topic_categories = data.get("topic_categories", [])
        
        # Parse religions
        self.profiles: List[ReligionProfile] = []
        for r in data.get("religions", []):
            self.profiles.append(ReligionProfile(
                id=r["id"],
                name=r["name"],
                demographic_weight=r["demographic_weight"],
                dogma_vector=r["dogma_vector"],
                authority_multiplier=r["authority_multiplier"],
                base_gullibility_range=tuple(r["base_gullibility_range"])
            ))
            
        # Validate sequential IDs
        self.profiles.sort(key=lambda p: p.id)
        for i, p in enumerate(self.profiles):
            if p.id != i:
                raise ValueError(f"Religion IDs must be sequential starting from 0. Found {p.id} at index {i}.")
                
        self.n_religions = len(self.profiles)
        self.names = [p.name for p in self.profiles]
        
        # Build matrices
        weights = [p.demographic_weight for p in self.profiles]
        total_weight = sum(weights)
        if not np.isclose(total_weight, 1.0):
            logger.warning(f"Demographic weights sum to {total_weight}, not 1.0. Normalizing...")
            self.demographic_weights = np.array(weights) / total_weight
        else:
            self.demographic_weights = np.array(weights)
            
        self.authority_multipliers = np.array([p.authority_multiplier for p in self.profiles])
        self.dogma_matrix = np.array([p.dogma_vector for p in self.profiles])
        
        # Parse friction matrix
        friction_list = data.get("friction_matrix", [])
        if len(friction_list) != self.n_religions:
            raise ValueError("Friction matrix dimensions must match number of religions.")
        self.friction_matrix = np.array(friction_list)
        if self.friction_matrix.shape != (self.n_religions, self.n_religions):
            raise ValueError("Friction matrix must be square (N x N).")
            
        logger.info(f"Loaded {self.n_religions} religions from registry: {self.names}")

    @classmethod
    def load(cls, filepath: str) -> 'ReligionRegistry':
        if not os.path.exists(filepath):
            # Fallback: look for the file in data/india/ relative to this module
            fallback = os.path.join(os.path.dirname(__file__), "data", "india", "religions.json")
            if os.path.exists(fallback):
                filepath = fallback
            else:
                raise FileNotFoundError(f"Could not find religions.json at {filepath} or {fallback}")
                
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)
