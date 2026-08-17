"""Federated aggregation algorithms.

FedAvg   — weighted average of client deltas (McMahan et al., 2017).
FedProx  — adds a proximal term during local training; aggregation is still a
           weighted average (Li et al., 2020). Handled in the trainer via mu.
FedAdam  — server-side Adam optimizer over the aggregated pseudo-gradient
           (Reddi et al., 2021).

Each algorithm returns updated global weights, a communication cost estimate and
algorithm-specific metadata for the aggregation log.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np


@dataclass
class ClientPayload:
    node_id: int
    node_name: str
    delta: np.ndarray
    local_accuracy: float
    local_loss: float
    samples: int = 1000
    training_time_ms: int = 0
    upload_bytes: int = 0


@dataclass
class AggregationResult:
    new_weights: np.ndarray
    algorithm: str
    client_weights: List[float]
    weighted_avg: float
    communication_bytes: int
    details: Dict = field(default_factory=dict)


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


def fedavg(payloads: List[ClientPayload], global_weights: np.ndarray, **_) -> AggregationResult:
    weights = np.array([max(p.samples, 1) for p in payloads], dtype=float)
    weights = weights / weights.sum()
    aggregated = np.zeros_like(global_weights)
    for w, p in zip(weights, payloads):
        aggregated += w * p.delta
    new_weights = global_weights + aggregated
    comm = sum(p.upload_bytes for p in payloads)
    return AggregationResult(
        new_weights=new_weights,
        algorithm="fedavg",
        client_weights=[round(float(w), 4) for w in weights],
        weighted_avg=float(np.mean(np.abs(aggregated))),
        communication_bytes=comm,
        details={"scheme": "weighted-average-of-deltas"},
    )


def fedprox(payloads: List[ClientPayload], global_weights: np.ndarray, **_) -> AggregationResult:
    # Aggregation identical to FedAvg; the proximal term was applied locally.
    result = fedavg(payloads, global_weights)
    result.algorithm = "fedprox"
    result.details = {"scheme": "fedavg-aggregation + proximal local term"}
    return result


class AdamServerState:
    """Server-side Adam optimizer state used by FedAdam."""

    def __init__(self, param_count: int, beta1: float = 0.9, beta2: float = 0.999, eps: float = 1e-8) -> None:
        self.m = np.zeros(param_count)
        self.v = np.zeros(param_count)
        self.t = 0
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps

    def step(self, pseudo_gradient: np.ndarray, lr: float = 0.01) -> np.ndarray:
        self.t += 1
        self.m = self.beta1 * self.m + (1 - self.beta1) * pseudo_gradient
        self.v = self.beta2 * self.v + (1 - self.beta2) * (pseudo_gradient**2)
        m_hat = self.m / (1 - self.beta1**self.t)
        v_hat = self.v / (1 - self.beta2**self.t)
        return lr * m_hat / (np.sqrt(v_hat) + self.eps)


def fedadam(
    payloads: List[ClientPayload],
    global_weights: np.ndarray,
    server_state: AdamServerState | None = None,
    server_lr: float = 0.01,
    **kwargs,
) -> AggregationResult:
    weights = np.array([max(p.samples, 1) for p in payloads], dtype=float)
    weights = weights / weights.sum()
    pseudo_gradient = np.zeros_like(global_weights)
    for w, p in zip(weights, payloads):
        pseudo_gradient += w * p.delta
    if server_state is None:
        server_state = AdamServerState(global_weights.size)
    update = server_state.step(pseudo_gradient, lr=server_lr)
    new_weights = global_weights + update
    comm = sum(p.upload_bytes for p in payloads)
    return AggregationResult(
        new_weights=new_weights,
        algorithm="fedadam",
        client_weights=[round(float(w), 4) for w in weights],
        weighted_avg=float(np.mean(np.abs(update))),
        communication_bytes=comm,
        details={
            "scheme": "server-side-adam",
            "server_lr": server_lr,
            "adam_step": server_state.t,
        },
    )


ALGORITHMS = {
    "fedavg": fedavg,
    "fedprox": fedprox,
    "fedadam": fedadam,
}


def aggregate(
    algorithm: str,
    payloads: List[ClientPayload],
    global_weights: np.ndarray,
    **kwargs,
) -> AggregationResult:
    fn = ALGORITHMS.get(algorithm, fedavg)
    return fn(payloads, global_weights, **kwargs)
