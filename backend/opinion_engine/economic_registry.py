import json
import logging
import os
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np

logger = logging.getLogger("echo.economic_registry")


@dataclass
class EconomicClass:
    id: int
    name: str
    demographic_weight: float
    economic_anxiety_multiplier: float
    base_literacy_range: Tuple[float, float]
    political_lean_bias: float
    authority_figure: str


class EconomicRegistry:
    """
    Loads and compiles economics.json into NumPy matrices for the OpinionEngine.

    Designed to be fully model-agnostic: the number of classes and the
    conditional probability matrices are read dynamically from the JSON file.
    Swapping between economic models (Precariat, Neo-Marxist, SES Quintile,
    or any custom model) requires only editing economics.json — no code changes.

    JSON keys ending in '_note' are documentation strings and are ignored
    by the loader, so they can be freely added or modified without breaking
    anything.

    Parameters
    ----------
    data : dict
        Parsed content of economics.json.
    n_religions : int
        Number of religion IDs loaded from the active religions.json.
        Used to validate the religion_conditional_matrix column count.
    """

    def __init__(self, data: dict, n_religions: int = 0):
        self.data = data
        self.version = data.get("version", "1.0")
        self.region = data.get("region", "Unknown")
        self.model_name = data.get("model", "Unknown")

        # --- Parse class profiles ------------------------------------------
        self.profiles: List[EconomicClass] = []
        for c in data.get("classes", []):
            self.profiles.append(EconomicClass(
                id=c["id"],
                name=c["name"],
                demographic_weight=c["demographic_weight"],
                economic_anxiety_multiplier=c["economic_anxiety_multiplier"],
                base_literacy_range=tuple(c["base_literacy_range"]),
                political_lean_bias=c["political_lean_bias"],
                authority_figure=c.get("authority_figure", ""),
            ))

        # Validate sequential IDs starting from 0
        self.profiles.sort(key=lambda p: p.id)
        for i, p in enumerate(self.profiles):
            if p.id != i:
                raise ValueError(
                    f"Economic class IDs must be sequential starting from 0. "
                    f"Found id={p.id} at index {i}."
                )

        self.n_classes = len(self.profiles)
        self.names = [p.name for p in self.profiles]

        if self.n_classes == 0:
            raise ValueError("economics.json must define at least one class.")

        # --- Demographic weights -------------------------------------------
        weights = [p.demographic_weight for p in self.profiles]
        total = sum(weights)
        if not np.isclose(total, 1.0):
            logger.warning(
                f"Economic class demographic_weights sum to {total:.4f}, not 1.0. "
                f"Auto-normalizing."
            )
            self.demographic_weights = np.array(weights) / total
        else:
            self.demographic_weights = np.array(weights)

        # --- Derived arrays ------------------------------------------------
        self.anxiety_multipliers = np.array(
            [p.economic_anxiety_multiplier for p in self.profiles]
        )
        self.literacy_ranges = np.array(
            [list(p.base_literacy_range) for p in self.profiles]
        )  # shape: (C, 2)
        self.political_lean_biases = np.array(
            [p.political_lean_bias for p in self.profiles]
        )

        # --- Friction matrix -----------------------------------------------
        friction_raw = data.get("friction_matrix", [])
        if len(friction_raw) != self.n_classes:
            raise ValueError(
                f"friction_matrix must have {self.n_classes} rows "
                f"(one per class), got {len(friction_raw)}."
            )
        self.friction_matrix = np.array(friction_raw, dtype=np.float64)
        if self.friction_matrix.shape != (self.n_classes, self.n_classes):
            raise ValueError(
                f"friction_matrix must be square ({self.n_classes}×{self.n_classes})."
            )
        # Warn if diagonal is not zero (it should be — no self-friction)
        if not np.all(np.diag(self.friction_matrix) == 0.0):
            logger.warning(
                "friction_matrix diagonal contains non-zero values. "
                "Self-friction is unusual — check economics.json."
            )

        # --- Religion conditional matrix -----------------------------------
        # Shape: (C, R) — P(Religion | Class)
        rcm_raw = data.get("religion_conditional_matrix", [])
        if len(rcm_raw) != self.n_classes:
            raise ValueError(
                f"religion_conditional_matrix must have {self.n_classes} rows "
                f"(one per class), got {len(rcm_raw)}."
            )

        rcm = np.array(rcm_raw, dtype=np.float64)

        # Validate column count matches n_religions if provided
        if n_religions > 0 and rcm.shape[1] != n_religions:
            raise ValueError(
                f"religion_conditional_matrix has {rcm.shape[1]} columns but "
                f"religions.json defines {n_religions} religions. "
                f"These must match."
            )

        # Normalize each row to sum to 1.0 (with warning if needed)
        row_sums = rcm.sum(axis=1)
        for i, s in enumerate(row_sums):
            if not np.isclose(s, 1.0):
                logger.warning(
                    f"religion_conditional_matrix row {i} ({self.names[i]}) "
                    f"sums to {s:.4f}, not 1.0. Auto-normalizing."
                )
        self.religion_conditional_matrix = rcm / row_sums[:, None]

        logger.info(
            f"EconomicRegistry loaded: model='{self.model_name}', "
            f"region='{self.region}', classes={self.names}"
        )

    # -----------------------------------------------------------------------
    # Class-level helpers
    # -----------------------------------------------------------------------

    def get_class_name(self, class_id: int) -> str:
        """Return the human-readable name for a class ID."""
        if 0 <= class_id < self.n_classes:
            return self.names[class_id]
        return f"Class({class_id})"

    def get_religion_weights_for_class(self, class_id: int) -> np.ndarray:
        """
        Return the conditional religion probability weights for a given class.
        Shape: (R,) where R = number of religions in religions.json.
        """
        return self.religion_conditional_matrix[class_id]

    def get_literacy_range(self, class_id: int) -> Tuple[float, float]:
        """Return the (min, max) literacy range for a given class."""
        return tuple(self.literacy_ranges[class_id])

    def get_anxiety_multiplier(self, class_id: int) -> float:
        """Return the economic anxiety multiplier for a given class."""
        return float(self.anxiety_multipliers[class_id])

    def get_political_bias(self, class_id: int) -> float:
        """Return the political lean bias for a given class."""
        return float(self.political_lean_biases[class_id])

    # -----------------------------------------------------------------------
    # Loader
    # -----------------------------------------------------------------------

    @classmethod
    def load(cls, filepath: str, n_religions: int = 0) -> "EconomicRegistry":
        """
        Load an EconomicRegistry from a JSON file.

        Parameters
        ----------
        filepath : str
            Path to economics.json. Falls back to the directory of this
            module if the path does not exist.
        n_religions : int
            Number of religion entries in the active religions.json.
            If provided, validates the column count of religion_conditional_matrix.
        """
        if not os.path.exists(filepath):
            # Fallback: look for the file in data/india/ relative to this module
            fallback = os.path.join(os.path.dirname(__file__), "data", "india", "economics.json")
            if os.path.exists(fallback):
                filepath = fallback
            else:
                raise FileNotFoundError(
                    f"Could not find economics.json at '{filepath}' or '{fallback}'."
                )

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls(data, n_religions=n_religions)
