from __future__ import annotations
from pathlib import Path
import numpy as np
from scipy import sparse


class FlyWireReservoir:
    """Fixed sparse FAFB reservoir with independent state per tracked token/key.

    The topology and input projection are shared, but recurrent state is NOT shared across
    unrelated tokens. This prevents one token's event sequence from contaminating another
    token's FlyWire features during replay/PAPER.
    """

    def __init__(
        self,
        artifact_dir: str | Path,
        enabled: bool = False,
        state_dim: int = 64,
        alpha: float = 0.9,
        input_dim: int = 16,
        seed: int = 783,
        variant: str = 'FLY_REAL',
        max_states: int = 4096,
    ) -> None:
        self.enabled = enabled
        self.artifact_dir = Path(artifact_dir)
        self.alpha = float(alpha)
        self.input_dim = int(input_dim)
        self._loaded = False
        self.W = None
        self.B = None
        self.seed = int(seed)
        self.variant = variant
        self.max_states = max(16, int(max_states))
        self.states: dict[str, np.ndarray] = {}
        self._state_order: list[str] = []

    def _load(self) -> None:
        if self._loaded or not self.enabled:
            return
        files = {
            'FLY_REAL': 'adjacency.npz',
            'FLY_SHUFFLED_WEIGHTS': 'fly_shuffled_weights.npz',
            'FLY_REWIRED': 'fly_rewired.npz',
            'FLY_DEGREE_PRESERVED': 'fly_degree_preserved.npz',
            'RANDOM_RESERVOIR': 'random_reservoir.npz',
        }
        wpath = self.artifact_dir / files.get(self.variant, 'adjacency.npz')
        if not wpath.exists():
            self.enabled = False
            return
        self.W = sparse.load_npz(wpath).tocsr().astype(np.float32)
        n = self.W.shape[0]
        rowsum = np.asarray(np.abs(self.W).sum(axis=1)).reshape(-1)
        scale = max(float(rowsum.max()) if len(rowsum) else 1.0, 1.0)
        self.W = self.W / scale
        rng = np.random.default_rng(self.seed)
        self.B = rng.normal(0, 0.15, (n, self.input_dim)).astype(np.float32)
        self._loaded = True

    def _state_for(self, key: str) -> np.ndarray:
        assert self.W is not None
        state = self.states.get(key)
        if state is None:
            state = np.zeros(self.W.shape[0], dtype=np.float32)
            self.states[key] = state
            self._state_order.append(key)
            if len(self._state_order) > self.max_states:
                evicted = self._state_order.pop(0)
                self.states.pop(evicted, None)
        return state

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self.states.clear()
            self._state_order.clear()
            return
        self.states.pop(key, None)
        try:
            self._state_order.remove(key)
        except ValueError:
            pass

    def step(self, z: np.ndarray, key: str = "__global__") -> dict[str, float | str]:
        zero = {
            'fly_state_mean': 0.0,
            'fly_state_std': 0.0,
            'fly_state_change': 0.0,
            'fly_anomaly': 0.0,
            'fly_variant': self.variant,
            'fly_status': 'DISABLED' if not self.enabled else 'WAITING_ARTIFACT',
        }
        if not self.enabled:
            return zero
        self._load()
        if not self.enabled or self.W is None or self.B is None:
            return zero

        z = np.asarray(z, dtype=np.float32).reshape(-1)[:self.input_dim]
        if len(z) < self.input_dim:
            z = np.pad(z, (0, self.input_dim - len(z)))

        key = str(key or "__global__")
        prev = self._state_for(key)
        recurrent = self.W.dot(prev)
        inp = self.B.dot(z)
        state = np.tanh(self.alpha * recurrent + inp).astype(np.float32)
        delta = state - prev
        self.states[key] = state
        return {
            'fly_state_mean': float(state.mean()),
            'fly_state_std': float(state.std()),
            'fly_state_change': float(np.linalg.norm(delta) / max(np.sqrt(len(delta)), 1)),
            'fly_anomaly': float(np.max(np.abs(delta))),
            'fly_variant': self.variant,
            'fly_status': 'ACTIVE',
        }
