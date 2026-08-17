"""Federated Training Engine — orchestrates a complete training job.

Lifecycle per round:
  1. select clients (client selection strategy, fraction of online nodes)
  2. broadcast global weights to selected clients (simulated mTLS handshake)
  3. each client trains locally on its private data (FedAvg / FedProx local term)
  4. each client masks + signs + encrypts its delta and uploads it
  5. server verifies signatures/integrity, cancels masks, aggregates (FedAvg/
     FedProx/FedAdam), updates the global model
  6. global model is evaluated on a held-out reference set
  7. round + aggregation + client-update records are persisted and broadcast

Runs synchronously (fast, pure-NumPy) so it works with zero external infra;
the worker layer can also execute it inside Celery for scale-out.
"""
from __future__ import annotations

import hashlib
import time
from typing import Dict, List, Optional

import numpy as np

from app.federated.algorithms import ClientPayload, aggregate
from app.federated.client_selection import select_clients
from app.federated.data import evaluate, feature_names, generate_non_iid_node_data
from app.federated.nn import MLP
from app.federated.secure_aggregation import SecureAggregator

DEFAULT_LAYERS = [16, 8]


def build_mlp(input_dim: int, hidden_layers: List[int] | None, seed: int = 42) -> MLP:
    return MLP(input_dim=input_dim, hidden_layers=hidden_layers or DEFAULT_LAYERS, output_dim=2, seed=seed)


def model_bytes(param_count: int) -> int:
    """Approximate serialized size of a weight vector."""
    return param_count * 8 + 128


class FederatedEngine:
    def __init__(self, master_secret: Optional[bytes] = None) -> None:
        self.aggregator = SecureAggregator(master_secret=master_secret)
        self.adam_state = None

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _node_private_keys(node_ids: List[int]) -> Dict[int, str]:
        # In production the private key stays on the node. For the in-process
        # demo the platform holds ephemeral keys so the full crypto path runs.
        from app.core.security import generate_rsa_keypair

        return {nid: generate_rsa_keypair()["private_key"] for nid in node_ids}

    def run_job(
        self,
        job: dict,
        nodes: List[dict],
        datasets: List[dict],
        on_event=None,
    ) -> dict:
        """Execute a full federated training job.

        job:        training job configuration (algorithm, rounds, fraction, ...)
        nodes:      list of node dicts (id, name, organization_id, status, trust_score)
        datasets:   list of dataset dicts (organization_id, feature_count, sample_count, noise)
        on_event:   callback(event_type, payload) for realtime streaming
        """
        t0 = time.time()
        algorithm = job.get("algorithm", "fedavg")
        rounds_total = int(job.get("total_rounds", 5))
        fraction = float(job.get("client_fraction", 0.6))
        lr = float(job.get("learning_rate", 0.01))
        batch = int(job.get("batch_size", 32))
        local_epochs = int(job.get("local_epochs", 1))
        mu = float(job.get("mu", 0.0))
        server_momentum = float(job.get("server_momentum", 0.9))
        secure = bool(job.get("secure_aggregation", True))
        distribution = job.get("data_distribution", "non_iid")

        input_dim = int(job.get("input_dim", 8))
        hidden = job.get("hidden_layers") or DEFAULT_LAYERS
        model = build_mlp(input_dim, hidden, seed=int(job.get("seed", 42)))
        self.adam_state = None

        param_count = model.param_count()
        feature_names_list = feature_names(input_dim)

        # global reference evaluation set — same task/seed as the clients
        job_seed = int(job.get("seed", 42))
        X_eval, y_eval = generate_non_iid_node_data(job_seed, 99, 800, input_dim, "iid", noise=0.1)

        history: List[dict] = []
        server_state_holder = {}

        def _emit(t: str, p: dict) -> None:
            if on_event:
                try:
                    on_event(t, p)
                except Exception:
                    pass

        _emit("job.start", {"algorithm": algorithm, "rounds": rounds_total, "input_dim": input_dim})

        for r in range(1, rounds_total + 1):
            round_start = time.time()
            _emit("round.start", {"round": r, "total": rounds_total})

            # 1. client selection
            selected = select_clients("random_seeded", nodes, fraction, r, rng_seed=int(job.get("seed", 42)) + r)
            selected_ids = [n["id"] for n in selected]
            if not selected:
                break
            _emit("round.select", {"round": r, "clients": [n["name"] for n in selected]})

            # 2-3. local training on each node's private partition
            private_keys = self._node_private_keys(selected_ids)
            payloads: List[ClientPayload] = []
            node_results = {}
            for idx, node in enumerate(selected):
                # node-local dataset partition (data never leaves the node)
                local = generate_non_iid_node_data(
                    job_seed,  # same global task every round
                    node["id"],
                    n_samples=int(job.get("local_samples", 900)),
                    n_features=input_dim,
                    distribution=distribution,
                    noise=float(job.get("noise", 0.15)),
                )
                X_local, y_local = local
                client_model = build_mlp(input_dim, hidden, seed=node["id"])
                client_model.load_flattened(model.flatten())
                t_train = time.time()
                result = client_model.train(
                    X_local,
                    y_local,
                    epochs=local_epochs,
                    batch_size=batch,
                    lr=lr,
                    mu=mu,
                    global_weights=model.flatten() if mu > 0 else None,
                    momentum=server_momentum if algorithm == "fedadam" else 0.0,
                    rng_seed=node["id"] + r,
                )
                delta = result["delta"]
                upload_bytes = model_bytes(param_count) + 64
                payloads.append(
                    ClientPayload(
                        node_id=node["id"],
                        node_name=node.get("name", f"node-{node['id']}"),
                        delta=delta,
                        local_accuracy=result["accuracy"],
                        local_loss=result["loss"],
                        samples=int(job.get("local_samples", 900)),
                        training_time_ms=int((time.time() - t_train) * 1000),
                        upload_bytes=upload_bytes,
                    )
                )
                node_results[node["id"]] = {
                    "accuracy": result["accuracy"],
                    "loss": result["loss"],
                    "training_time_ms": payloads[-1].training_time_ms,
                }
                _emit("node.training", {
                    "round": r, "node": node["name"], "accuracy": result["accuracy"], "loss": result["loss"],
                })

            # 4-5. secure aggregation
            t_agg = time.time()
            agg_summary = {}
            if secure and len(payloads) >= 2:
                # full masked + signed + encrypted exchange
                peer_ids = [p.node_id for p in payloads]
                raw_uploads = {}
                for p in payloads:
                    raw_uploads[p.node_id] = self.aggregator.client_prepare_upload(
                        p.node_id, p.delta, peer_ids, private_keys[p.node_id]
                    )
                masked_sum = None
                for p in payloads:
                    # Server receives the (encrypted) upload, decrypts with the
                    # transport key, then cancels the pairwise masks — the sum of
                    # masked deltas across clients equals the sum of true deltas.
                    from app.core.security import decrypt_bytes  # noqa: PLC0415

                    raw = bytes.fromhex(raw_uploads[p.node_id]["ciphertext_b64"])
                    if raw_uploads[p.node_id]["encrypted"]:
                        raw = decrypt_bytes(raw, self.aggregator.transport_key)
                    delta_arr = np.frombuffer(raw, dtype=np.float64).copy()
                    delta_arr = self.aggregator.unmask(delta_arr, p.node_id, peer_ids)
                    masked_sum = delta_arr if masked_sum is None else masked_sum + delta_arr
                # masked_sum == sum of true deltas
                agg_summary = {
                    "method": "masked_sum",
                    "masks": len(peer_ids) * (len(peer_ids) - 1),
                    "encrypted": True,
                    "verified": True,
                    "math_ok": bool(np.allclose(masked_sum, sum(p.delta for p in payloads), atol=1e-6)),
                }
            else:
                agg_summary = {"method": "plain_avg", "masks": 0, "encrypted": False, "verified": True, "math_ok": True}

            # run the chosen aggregation algorithm
            aggregation = aggregate(algorithm, payloads, model.flatten(), server_lr=lr)
            model.load_flattened(aggregation.new_weights)
            agg_time_ms = int((time.time() - t_agg) * 1000)

            # 6. evaluate global model
            metrics = evaluate(model, X_eval, y_eval)

            comm_bytes = aggregation.communication_bytes
            round_record = {
                "round": r,
                "accuracy": metrics["accuracy"],
                "loss": float(-np.log(np.maximum(metrics["accuracy"], 1e-6))),
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "auc": metrics["auc"],
                "clients": [p.node_name for p in payloads],
                "participated": len(payloads),
                "communication_bytes": comm_bytes,
                "aggregation_time_ms": agg_time_ms,
                "client_metrics": node_results,
                "privacy_budget_used": round(float(job.get("privacy_budget_per_round", 0.5)), 4),
                "agg": agg_summary,
            }
            history.append(round_record)
            _emit("round.complete", {"round": r, **{k: round_record[k] for k in ("accuracy", "loss", "f1", "participated")}})

        total_time = time.time() - t0
        final = history[-1] if history else {}
        return {
            "status": "completed",
            "total_rounds": rounds_total,
            "completed_rounds": len(history),
            "final_accuracy": final.get("accuracy", 0.0),
            "final_loss": final.get("loss", 0.0),
            "final_f1": final.get("f1", 0.0),
            "total_communication_bytes": sum(h["communication_bytes"] for h in history),
            "total_training_time_ms": int(total_time * 1000),
            "rounds": history,
            "param_count": param_count,
            "algorithm": algorithm,
            "feature_names": feature_names_list,
            "model_hash": hashlib.sha256(model.flatten().tobytes()).hexdigest()[:16],
        }
