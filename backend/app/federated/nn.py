"""A dependency-free multi-layer perceptron used by federated client trainers.

The model is a small fully-connected network implemented in NumPy so that local
training runs fast and deterministically anywhere (no CUDA/GPU required). Weights
can be flattened/unflattened for aggregation and encrypted exchange.

This mirrors how Flower/FedML client trainers behave: a client loads its private
dataset, runs several local epochs, and reports a weight *delta*.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)


def _relu_grad(x: np.ndarray) -> np.ndarray:
    return (x > 0).astype(float)


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


@dataclass
class MLP:
    """Fully-connected network with ReLU hidden layers and softmax output."""

    input_dim: int
    hidden_layers: List[int] = field(default_factory=lambda: [16, 8])
    output_dim: int = 2
    seed: int = 42
    _weights: Optional[List[np.ndarray]] = None
    _biases: Optional[List[np.ndarray]] = None

    def __post_init__(self) -> None:
        if self._weights is None:
            self.reset()

    def reset(self) -> None:
        rng = np.random.default_rng(self.seed)
        dims = [self.input_dim, *self.hidden_layers, self.output_dim]
        self._weights, self._biases = [], []
        for i in range(len(dims) - 1):
            fan_in = dims[i]
            # He initialization
            scale = math.sqrt(2.0 / fan_in)
            self._weights.append(rng.standard_normal((dims[i + 1], dims[i])) * scale)
            self._biases.append(np.zeros(dims[i + 1]))

    # -- serialization -----------------------------------------------------
    def param_count(self) -> int:
        return sum(w.size + b.size for w, b in zip(self._weights, self._biases))

    def flatten(self) -> np.ndarray:
        return np.concatenate([w.ravel() for w in self._weights] + [b.ravel() for b in self._biases])

    def load_flattened(self, flat: np.ndarray) -> None:
        """Rebuild weights/biases from a flat vector. Layout must match
        `flatten()`: all weight matrices first (row-major), then all biases."""
        self._weights, self._biases = [], []
        idx = 0
        dims = [self.input_dim, *self.hidden_layers, self.output_dim]
        for i in range(len(dims) - 1):
            n_w = dims[i + 1] * dims[i]
            self._weights.append(flat[idx : idx + n_w].reshape(dims[i + 1], dims[i]))
            idx += n_w
        for i in range(len(dims) - 1):
            n_b = dims[i + 1]
            self._biases.append(flat[idx : idx + n_b])
            idx += n_b

    # -- forward / predict --------------------------------------------------
    def forward(self, X: np.ndarray) -> Tuple[List[np.ndarray], List[np.ndarray], np.ndarray]:
        acts = [X]
        preacts = []
        H = X
        for i, W in enumerate(self._weights):
            Z = H @ W.T + self._biases[i]
            preacts.append(Z)
            H = _relu(Z) if i < len(self._weights) - 1 else Z
            acts.append(H)
        return acts, preacts, _softmax(acts[-1])

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        _, _, proba = self.forward(X)
        return proba

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.predict_proba(X).argmax(axis=1)

    # -- local training ------------------------------------------------------
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        epochs: int = 1,
        batch_size: int = 32,
        lr: float = 0.01,
        mu: float = 0.0,
        global_weights: Optional[np.ndarray] = None,
        momentum: float = 0.0,
        rng_seed: Optional[int] = None,
    ) -> dict:
        """Run local SGD. Returns final metrics and the weight *delta*.

        - mu > 0 implements the FedProx proximal term: local loss is augmented
          with (mu / 2) * ||w - w_global||^2.
        - momentum > 0 implements SGD with momentum (used by FedAdam clients).
        """
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.int64)
        n = X.shape[0]
        rng = np.random.default_rng(rng_seed if rng_seed is not None else 7)
        start_weights = self.flatten()

        # One-hot target
        Y = np.zeros((n, self.output_dim))
        Y[np.arange(n), y] = 1.0

        # Momentum buffers (per parameter tensor, mirroring weight shapes)
        velocities = [np.zeros_like(w) for w in self._weights] + [np.zeros_like(b) for b in self._biases]

        for epoch in range(epochs):
            perm = rng.permutation(n)
            for i in range(0, n, batch_size):
                idx = perm[i : i + batch_size]
                Xb, Yb = X[idx], Y[idx]
                acts, preacts, proba = self.forward(Xb)

                dZ = proba - Yb  # softmax cross-entropy gradient
                grad_weights: List[np.ndarray] = []
                grad_biases: List[np.ndarray] = []
                for layer in range(len(self._weights) - 1, -1, -1):
                    grad_weights.append(dZ.T @ acts[layer] / Xb.shape[0])
                    grad_biases.append(dZ.mean(axis=0))
                    if layer > 0:
                        dH = dZ @ self._weights[layer]
                        dZ = dH * _relu_grad(preacts[layer - 1])
                grad_weights.reverse()
                grad_biases.reverse()

                params = self._weights + self._biases
                grads = grad_weights + grad_biases
                flat_idx = 0
                flat_grads = []
                flat_params = []
                for p, g in zip(params, grads):
                    flat_grads.append(g.ravel())
                    flat_params.append(p.ravel())
                fgrad = np.concatenate(flat_grads)
                fparam = np.concatenate(flat_params)

                if mu > 0.0 and global_weights is not None:
                    # FedProx proximal regularization
                    fgrad = fgrad + mu * (fparam - global_weights)

                # update with optional momentum
                flat_velocity = np.concatenate([v.ravel() for v in velocities])
                flat_velocity = momentum * flat_velocity + fgrad
                new_param = fparam - lr * flat_velocity

                # write back
                idx_ = 0
                for i_layer, p in enumerate(params):
                    size = p.size
                    p.flat[:] = new_param[idx_ : idx_ + size]
                    velocities[i_layer].flat[:] = flat_velocity[idx_ : idx_ + size]
                    idx_ += size

        end_weights = self.flatten()
        delta = end_weights - start_weights

        # evaluate on full local set
        proba_all = self.predict_proba(X)
        preds = proba_all.argmax(axis=1)
        acc = float((preds == y).mean())
        loss = float(-np.log(proba_all[np.arange(n), y] + 1e-9).mean())
        return {
            "accuracy": round(acc, 4),
            "loss": round(loss, 4),
            "delta": delta,
            "weights": end_weights,
        }
