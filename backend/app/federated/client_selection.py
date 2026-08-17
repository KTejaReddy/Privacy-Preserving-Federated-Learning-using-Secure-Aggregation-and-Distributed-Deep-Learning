"""Client selection strategies for federated rounds.

Supported strategies:
  - random:          uniform random sample of eligible (online) nodes.
  - random_seeded:   deterministic random sample (reproducible experiments).
  - top_health:      select nodes with the highest trust scores.
  - round_robin:     rotate through the eligible set across rounds.
"""
from __future__ import annotations

import random
from typing import List


def select_clients(
    strategy: str,
    nodes: List[dict],
    fraction: float,
    round_number: int = 0,
    rng_seed: int = 0,
) -> List[dict]:
    """Select a subset of eligible nodes. `nodes` is a list of dicts with at
    least: id, name, status (online), trust_score."""
    eligible = [n for n in nodes if n.get("status") == "online"]
    if not eligible:
        eligible = list(nodes)
    k = max(1, int(round(len(eligible) * fraction)))
    k = min(k, len(eligible))

    if strategy == "top_health":
        ranked = sorted(eligible, key=lambda n: n.get("trust_score", 0), reverse=True)
        return ranked[:k]

    if strategy == "round_robin":
        ranked = sorted(eligible, key=lambda n: n.get("id", 0))
        start = (round_number * k) % max(len(ranked), 1)
        picked = []
        for i in range(k):
            picked.append(ranked[(start + i) % len(ranked)])
        return picked

    # random / random_seeded
    rng = random.Random(rng_seed if strategy == "random_seeded" else None)
    return rng.sample(eligible, k)
