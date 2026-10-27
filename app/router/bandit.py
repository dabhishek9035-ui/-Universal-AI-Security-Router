"""LinUCB contextual bandit (disjoint model per arm).

Context = feature vector, arms = detector subsets. Reward = correctness
- cost-weight - latency-weight. State persists to data/bandit_state.npz.
"""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np


class LinUCB:
    def __init__(self, dim: int, alpha: float = 0.3):
        self.dim = dim
        self.alpha = alpha
        self.arms: dict[str, dict[str, np.ndarray]] = {}
        self._lock = threading.Lock()

    def _ensure_arm(self, arm_id: str) -> dict[str, np.ndarray]:
        arm = self.arms.get(arm_id)
        if arm is None:
            arm = {
                "A": np.eye(self.dim),
                "b": np.zeros(self.dim),
            }
            self.arms[arm_id] = arm
        return arm

    def select(self, context: np.ndarray, arm_ids: list[str]) -> tuple[str, dict[str, float]]:
        """UCB scores per arm; returns (best_arm, {arm: ucb})."""
        x = np.asarray(context, dtype=float)
        scores: dict[str, float] = {}
        with self._lock:
            for arm_id in arm_ids:
                arm = self._ensure_arm(arm_id)
                A_inv = np.linalg.inv(arm["A"])
                theta = A_inv @ arm["b"]
                exploit = float(theta @ x)
                explore = self.alpha * float(np.sqrt(x @ A_inv @ x))
                scores[arm_id] = exploit + explore
        best = max(scores, key=scores.get)
        return best, scores

    def update(self, arm_id: str, context: np.ndarray, reward: float) -> None:
        x = np.asarray(context, dtype=float)
        with self._lock:
            arm = self._ensure_arm(arm_id)
            arm["A"] += np.outer(x, x)
            arm["b"] += reward * x

    def save(self, path: Path) -> None:
        with self._lock:
            if not self.arms:
                return
            arm_ids = sorted(self.arms)
            np.savez(
                path,
                dim=self.dim,
                alpha=self.alpha,
                arm_ids=np.array(arm_ids),
                **{f"A_{a}": self.arms[a]["A"] for a in arm_ids},
                **{f"b_{a}": self.arms[a]["b"] for a in arm_ids},
            )

    @classmethod
    def load(cls, path: Path) -> "LinUCB | None":
        try:
            data = np.load(path, allow_pickle=False)
            router = cls(dim=int(data["dim"]), alpha=float(data["alpha"]))
            for arm_id in data["arm_ids"]:
                arm_id = str(arm_id)
                router.arms[arm_id] = {
                    "A": np.array(data[f"A_{arm_id}"]),
                    "b": np.array(data[f"b_{arm_id}"]),
                }
            return router
        except Exception:
            return None
