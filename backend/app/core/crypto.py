"""Cryptographic toolkit used by the Secure Aggregation engine.

Provides deterministic PRNG seeds (for pairwise masking), key generation, and
optional homomorphic-encryption detection (TenSEAL) when heavy deps are enabled.
"""
from __future__ import annotations

import os
from typing import Optional

from app.core.config import settings

try:  # optional heavy dependency
    import tenseal  # type: ignore

    TENSEAL_AVAILABLE = True
except ImportError:
    tenseal = None
    TENSEAL_AVAILABLE = False


def random_seed_bytes(n: Optional[int] = None) -> bytes:
    return os.urandom(n or settings.MASK_KEY_BYTES)


def random_int_seed() -> int:
    return int.from_bytes(os.urandom(8), "big")


def he_available() -> bool:
    return TENSEAL_AVAILABLE and settings.ENABLE_HEAVY_DEPS
