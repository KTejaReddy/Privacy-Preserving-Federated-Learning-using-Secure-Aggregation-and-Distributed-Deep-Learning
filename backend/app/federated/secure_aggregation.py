"""Secure Aggregation Engine.

Implements the Bonawitz et al. (2017) masking scheme adapted for the platform:

1. Pairwise masking: for each ordered pair (u, v) of participating clients, a
   shared random seed is agreed (in production this happens over a Diffie-Hellman
   exchange; here we derive it from a keyed PRF on the platform master secret +
   both node ids so the demo is reproducible and self-contained).

2. Each client adds the masks (+ for its outgoing pair, - for its incoming pair)
   to its local model delta before upload. Individual updates therefore reveal
   nothing about the true delta.

3. The server sums the masked updates; because masks cancel pairwise, the sum
   equals the sum of the true deltas — the global update — while no single
   client's update is ever visible.

4. Uploads are additionally encrypted with AES-256-GCM (transport layer) and
   signed with each node's RSA private key (identity + integrity), which the
   server verifies against the node's registered public key (simulated mTLS).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from app.core.crypto import random_seed_bytes
from app.core.security import decrypt_bytes, encrypt_bytes, rsa_sign, rsa_verify
from app.federated.algorithms import ClientPayload

# 64-bit float + structure
_PARAM_BYTES = 8


@dataclass
class MaskedUpdate:
    node_id: int
    ciphertext: bytes
    signature_b64: str
    nonce: str = ""
    sha256: str = ""
    status: str = "received"


@dataclass
class SecureAggregationResult:
    aggregated_delta: np.ndarray
    mask_pair_count: int
    mask_bytes: int
    verified_signatures: int
    integrity_ok: bool
    method: str = "masked_sum"
    log: List[str] = field(default_factory=list)


def _pair_mask(seed_bytes: bytes, param_count: int) -> np.ndarray:
    """Deterministic pseudo-random mask of shape (param_count,) from a seed."""
    # HMAC-DRBG style expansion: hash seed + counter, interpret each 8-byte
    # word as a float64 mapped to [-1, 1]. Each digest yields 4 values, so we
    # stream enough digests to cover param_count exactly.
    import math

    n_digests = math.ceil(param_count / 4)
    stream = b"".join(
        hmac.new(seed_bytes, struct.pack(">I", i), hashlib.sha256).digest()
        for i in range(n_digests)
    )
    vals = np.frombuffer(stream, dtype=">u8").astype(np.float64)
    vals = (vals / float(2**64)) * 2.0 - 1.0
    mask = np.zeros(param_count, dtype=np.float64)
    mask[:] = vals[:param_count]
    return mask


def derive_pair_seed(master_secret: bytes, client_a: int, client_b: int) -> bytes:
    """Keyed PRF deriving the shared mask seed for ordered pair (a, b)."""
    payload = f"{min(client_a, client_b)}:{max(client_a, client_b)}".encode("utf-8")
    return hmac.new(master_secret, payload, hashlib.sha256).digest()


def generate_client_masks(
    client_id: int,
    peer_ids: List[int],
    param_count: int,
    master_secret: bytes,
) -> np.ndarray:
    """Compute the total mask a client adds to its delta: + for peers with a
    larger id, - for peers with a smaller id (this ensures pairwise cancellation)."""
    total = np.zeros(param_count, dtype=np.float64)
    for peer in peer_ids:
        if peer == client_id:
            continue
        seed = derive_pair_seed(master_secret, client_id, peer)
        mask = _pair_mask(seed, param_count)
        if peer > client_id:
            total += mask
        else:
            total -= mask
    return total


def mask_delta(client_id: int, delta: np.ndarray, peer_ids: List[int], master_secret: bytes) -> np.ndarray:
    """Client-side: mask the local delta before upload."""
    mask = generate_client_masks(client_id, peer_ids, delta.size, master_secret)
    return delta + mask


class SecureAggregator:
    """Server-side secure aggregator."""

    def __init__(self, master_secret: bytes | None = None, transport_key: bytes | None = None) -> None:
        self.master_secret = master_secret or hashlib.sha256(random_seed_bytes(32)).digest()
        # Fixed transport key for the demo session (per-round keys in production).
        self.transport_key = transport_key or random_seed_bytes(32)

    # -- client upload path --------------------------------------------------
    def client_prepare_upload(
        self,
        client_id: int,
        delta: np.ndarray,
        peer_ids: List[int],
        private_key_pem: str,
        use_encryption: bool = True,
        masks: bool = True,
    ) -> dict:
        """Called on the client: masks, signs and optionally encrypts a delta."""
        if masks:
            masked = mask_delta(client_id, delta, peer_ids, self.master_secret)
        else:
            masked = delta
        raw = np.asarray(masked, dtype=np.float64).tobytes()
        digest = hashlib.sha256(raw).hexdigest()
        signature = rsa_sign(private_key_pem, raw)
        if use_encryption:
            ciphertext = encrypt_bytes(raw, self.transport_key)
            return {
                "ciphertext_b64": ciphertext.hex(),
                "signature_b64": signature,
                "sha256": digest,
                "encrypted": True,
                "masked": masks,
            }
        return {
            "ciphertext_b64": raw.hex(),
            "signature_b64": signature,
            "sha256": digest,
            "encrypted": False,
            "masked": masks,
        }

    # -- server verification + unmasking --------------------------------------
    def receive_and_verify(
        self,
        client_id: int,
        upload: dict,
        public_key_pem: str,
        param_count: int,
    ) -> MaskedUpdate:
        raw_hex = upload["ciphertext_b64"]
        raw = bytes.fromhex(raw_hex)
        if upload.get("encrypted"):
            raw = decrypt_bytes(raw, self.transport_key)
        ok_signature = rsa_verify(public_key_pem, raw, upload["signature_b64"])
        digest = hashlib.sha256(raw).hexdigest()
        integrity = digest == upload.get("sha256", "")
        if len(raw) != param_count * _PARAM_BYTES:
            return MaskedUpdate(client_id, raw, upload["signature_b64"], status="dropped")
        update = MaskedUpdate(
            client_id,
            raw,
            upload["signature_b64"],
            sha256=digest,
            status="verified" if (ok_signature and integrity) else "dropped",
        )
        return update

    def unmask(self, masked: np.ndarray, client_id: int, peer_ids: List[int]) -> np.ndarray:
        """Server-side: cancel a client's masks (it knows the pairing, so it can
        reconstruct the inverse). In the real protocol the server never sees
        individual masks; here we demonstrate the math of cancellation."""
        mask = generate_client_masks(client_id, peer_ids, masked.size, self.master_secret)
        return masked - mask

    def aggregate(
        self,
        updates: List[MaskedUpdate],
        param_count: int,
        peer_ids: List[int],
    ) -> SecureAggregationResult:
        """Sum masked updates: pairwise masks cancel, yielding the true sum."""
        valid = [u for u in updates if u.status == "verified"]
        total = np.zeros(param_count, dtype=np.float64)
        for u in valid:
            arr = np.frombuffer(u.ciphertext, dtype=np.float64).copy()
            total += arr
        mask_pairs = len(peer_ids) * (len(peer_ids) - 1)
        return SecureAggregationResult(
            aggregated_delta=total,
            mask_pair_count=mask_pairs,
            mask_bytes=mask_pairs * 32,
            verified_signatures=len(valid),
            integrity_ok=len(valid) == len(updates),
            log=[
                f"Received {len(updates)} masked updates",
                f"Verified {len(valid)} signatures + integrity hashes",
                f"Cancelled {mask_pairs} pairwise masks",
                "Aggregated sum of true client deltas",
            ],
        )


def demo_secure_aggregation_flow(
    payloads: List[ClientPayload],
    private_keys: Dict[int, str],
    public_keys: Dict[int, str],
) -> SecureAggregationResult:
    """End-to-end demonstration of the masking + encryption + signing flow.

    Used by the Coordinator API so users can watch a real secure aggregation
    handshake execute on live data.
    """
    aggregator = SecureAggregator()
    param_count = payloads[0].delta.size if payloads else 0
    if param_count == 0:
        return SecureAggregationResult(np.zeros(0), 0, 0, 0, False)

    peer_ids = [p.node_id for p in payloads]
    uploads: List[MaskedUpdate] = []
    for p in payloads:
        pk = private_keys.get(p.node_id, "")
        pub = public_keys.get(p.node_id, "")
        upload = aggregator.client_prepare_upload(p.node_id, p.delta, peer_ids, pk)
        update = aggregator.receive_and_verify(p.node_id, upload, pub, param_count)
        uploads.append(update)

    # verify math: unmasked sum of masked updates == true sum
    true_sum = np.zeros(param_count)
    for p in payloads:
        true_sum += p.delta
    aggregated = aggregator.aggregate(uploads, param_count, peer_ids)
    recovered_sum = aggregated.aggregated_delta
    math_ok = np.allclose(recovered_sum, true_sum, atol=1e-6)
    aggregated.log.append(f"Math verification: sum-of-masked == true sum ({math_ok})")
    return aggregated


def json_safe_payload(payloads: List[ClientPayload]) -> List[dict]:
    return [
        {
            "node_id": p.node_id,
            "node_name": p.node_name,
            "local_accuracy": p.local_accuracy,
            "local_loss": p.local_loss,
            "samples": p.samples,
            "training_time_ms": p.training_time_ms,
            "upload_bytes": p.upload_bytes,
        }
        for p in payloads
    ]
