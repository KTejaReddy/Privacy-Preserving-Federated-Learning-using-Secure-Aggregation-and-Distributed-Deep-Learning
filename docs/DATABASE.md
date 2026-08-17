# Database Documentation

SQLAlchemy 2.0 ORM, `DeclarativeBase`. Runs on **SQLite** (default, zero-config) or **PostgreSQL** (`DATABASE_URL`). JSON columns store semi-structured payloads (config, metrics, privacy controls). All timestamps are UTC.

## Entity Relationship Overview

```
organizations ─┬─< users
               ├─< federated_nodes ─< client_updates >─ federated_rounds >─< training_jobs
               └─< datasets          node_events ──────────┘                      │
                                                                └─< model_versions >─< xai_explanations
                                                                                        aggregated in aggregation_logs
audit_logs (standalone, hash-chained)
ai_providers ─< inference_logs · prompt_templates (standalone)
lab_experiments · settings · feature_flags (standalone)
```

## Tables

### `organizations`
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| name / slug | str | slug unique, indexed |
| industry, country | str | e.g. "Health & Care", "Switzerland" |
| description | text | |
| status | str | `active` / `suspended` / `pending` |
| compliance_level | str | e.g. "GDPR + HIPAA aligned" |
| data_guardian_enabled | bool | Data Guardian fingerprinting |
| created_at | datetime | |

### `users`
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| email | str | unique, lower-cased |
| full_name | str | |
| password_hash | str | bcrypt |
| role | str | `admin` / `coordinator` / `org_admin` / `ml_engineer` / `research_scientist` |
| organization_id | FK→organizations | nullable |
| title, is_active, mfa_enabled | | |
| created_at, last_login | datetime | |

### `federated_nodes`
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| organization_id | FK→organizations | |
| name, endpoint | str | endpoint like `mtls://<name>.internal:8443` |
| status | str | `online` / `degraded` / `offline` / `unknown` (simulator updates) |
| device_type | str | `server` / `gpu` / `edge` / `mobile` |
| cpu_cores, gpu_name, ram_gb | | compute spec |
| bandwidth_mbps, latency_ms | float | realtime telemetry |
| client_fraction_cap | float | max selection share |
| last_heartbeat | datetime | |
| public_key | text | RSA identity |
| cert_serial | str | simulated mTLS certificate |
| mTLS_verified, trust_score | bool/float | |

### `datasets`
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| organization_id | FK→organizations | |
| name, description | | |
| data_type | str | `tabular` / `image` / `text` / `time_series` |
| feature_count, sample_count | int | |
| positive_ratio, noise | float | synthetic data params |
| privacy_controls | JSON | fingerprint, raw_data_exposure=false, pii_detected, encryption, retention |
| status | str | `registered` / `validated` / `quarantined` |

**Privacy invariant:** only metadata lives here — the raw data stays on-premise.

### `training_jobs`
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| name, description | | |
| status | str | `draft` → `approved` → `running` → `completed` / `failed` / `cancelled`; `paused` |
| algorithm | str | `fedavg` / `fedprox` / `fedadam` |
| model_architecture, hidden_layers | str / JSON | MLP config |
| total_rounds, current_round | int | |
| client_fraction, learning_rate, batch_size, local_epochs | | hyperparameters |
| mu | float | FedProx proximal term |
| server_momentum | float | FedAdam β |
| aggregation_method | str | `secure_masking` |
| secure_aggregation, use_encryption | bool | |
| privacy_budget_per_round | float | ε per round |
| dataset_ids, selected_node_ids | JSON | |
| created_by (FK users), organization_id (FK) | | |
| metrics_json | JSON | seed, input_dim, distribution, final metrics |
| created_at, started_at, finished_at | datetime | |

### `federated_rounds`
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| job_id | FK→training_jobs | cascade delete |
| round_number | int | |
| status | str | `completed` etc. |
| selected_client_ids | JSON | sampled clients |
| participated_count | int | |
| avg_loss, accuracy, precision, recall, f1 | float nullable | global eval metrics |
| communication_bytes | int | payload accounting |
| aggregation_time_ms | int | |
| client_metrics | JSON | per-client {accuracy, loss, training_time_ms, …} |
| privacy_budget_used | float | ε consumed |
| started_at, finished_at | datetime | |

### `client_updates`
Per-participant record per round: `round_id` FK, `node_id` FK, `status` (`received`/`verified`/`aggregated`/`dropped`), `masked_update` JSON, `local_accuracy`, `local_loss`, `training_time_ms`, `upload_bytes`, `contribution_score`.

### `aggregation_logs`
`round_id` FK, `method`, `client_count`, `masked_upload_count`, `masks_cancelled`, `signature_verified`, `integrity_hash`, `privacy_budget_consumed`, `encryption_alg` (AES-256-GCM), `details` JSON (engine agg record), `created_at`.

### `model_versions`
`job_id` FK, `version` int, `status` (`pending`/`approved`/`rejected`/`deployed`/`archived`), metrics (accuracy, loss, precision, recall, f1), `params_json` (serialized weights for inference), `metrics_json` (full round history), `parent_version` (rollback chain), `created_by`, `approved_by`, `approval_notes`.

### `xai_explanations`
`model_version_id` FK, `method` (kernel_shap), `feature_names`, `shap_values`, `base_value`, `prediction`, `confidence`, `sample_index`, `explanation_text`.

### `node_events`
`node_id` FK, `event_type` (`heartbeat`/`round_start`/`training`/`upload`/`failure`/`recovery`), `message`, `severity`, `created_at`. Powers the Communication Monitor timeline.

### `audit_logs`
`actor_id`, `actor_email`, `action`, `entity_type`, `entity_id`, `details` JSON, `ip`, `severity`, **`chain_hash`**, `previous_hash`, `created_at`. The hash chain: `chain_hash = SHA256(previous_hash | canonical_payload)`. Append-only — no update/delete API exists.

### `ai_providers`
`name`, `provider_type`, `base_url`, **`api_key_encrypted`** (AES-256-GCM), `key_mask` (e.g. `sk-…wxyz`), `models` JSON, `temperature_default`, `status` (`configured`/`tested`/`unreachable`), `latency_ms`, `created_by`.

### `prompt_templates`, `inference_logs`
Prompt Studio templates (`system_prompt`, `user_prompt`, `variables`, `temperature`) and AI usage logs (`provider_id`, `prompt_preview`, `response_preview`, `latency_ms`, `tokens`, `status`, `error`).

### `lab_experiments`
`name`, `description`, `algorithm`, `clients`, `rounds`, `data_distribution` (`iid`/`non_iid`/`pathological`), `node_failure_rate`, `results_json` (accuracy curve, communication bytes, elapsed ms), `created_by`.

### `settings`, `feature_flags`
Key/value pairs for platform settings and toggleable feature flags.

## Indexes & cascade rules

- FK columns are indexed (`organization_id`, `job_id`, `round_id`, `node_id`, `model_version_id`, `provider_id`).
- `FederatedRound` and `ModelVersion` cascade-delete with their job.
- `ClientUpdate` cascades with its round.
- `email` and `organization.slug` are unique.

## Migrations

For SQLite dev, tables are created via `Base.metadata.create_all` on boot. For PostgreSQL production upgrades, point Alembic at `app.models.models:Base.metadata` (not yet generated — see Developer Guide for the module checklist).
