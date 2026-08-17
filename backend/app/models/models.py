"""SQLAlchemy ORM models for the entire Federated AI Platform."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    industry: Mapped[str] = mapped_column(String(120), default="Technology")
    country: Mapped[str] = mapped_column(String(80), default="—")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | suspended | pending
    compliance_level: Mapped[str] = mapped_column(String(64), default="GDPR + HIPAA aligned")
    data_guardian_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="organization")
    nodes: Mapped[list["FederatedNode"]] = relationship(back_populates="organization")
    datasets: Mapped[list["Dataset"]] = relationship(back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), index=True, default="ml_engineer")
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    organization: Mapped[Organization | None] = relationship(back_populates="users")


class FederatedNode(Base):
    __tablename__ = "federated_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    endpoint: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="unknown")  # online | offline | degraded | unknown
    device_type: Mapped[str] = mapped_column(String(64), default="server")  # server | gpu | edge | mobile
    cpu_cores: Mapped[int] = mapped_column(Integer, default=8)
    gpu_name: Mapped[str] = mapped_column(String(120), default="None")
    ram_gb: Mapped[float] = mapped_column(Float, default=16)
    bandwidth_mbps: Mapped[float] = mapped_column(Float, default=100)
    latency_ms: Mapped[float] = mapped_column(Float, default=12)
    client_fraction_cap: Mapped[float] = mapped_column(Float, default=1.0)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    public_key: Mapped[str] = mapped_column(Text, default="")
    cert_serial: Mapped[str] = mapped_column(String(120), default="")
    mTLS_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    trust_score: Mapped[float] = mapped_column(Float, default=0.95)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="nodes")


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    data_type: Mapped[str] = mapped_column(String(64), default="tabular")  # tabular | image | text | time_series
    feature_count: Mapped[int] = mapped_column(Integer, default=8)
    sample_count: Mapped[int] = mapped_column(Integer, default=1000)
    positive_ratio: Mapped[float] = mapped_column(Float, default=0.5)
    noise: Mapped[float] = mapped_column(Float, default=0.15)
    privacy_controls: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="registered")  # registered | validated | quarantined
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="datasets")


class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft | pending_approval | approved | running | paused | completed | failed | cancelled
    algorithm: Mapped[str] = mapped_column(String(32), default="fedavg")  # fedavg | fedprox | fedadam
    model_architecture: Mapped[str] = mapped_column(String(64), default="mlp")
    hidden_layers: Mapped[list] = mapped_column(JSON, default=list)
    total_rounds: Mapped[int] = mapped_column(Integer, default=10)
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    client_fraction: Mapped[float] = mapped_column(Float, default=0.6)
    learning_rate: Mapped[float] = mapped_column(Float, default=0.01)
    batch_size: Mapped[int] = mapped_column(Integer, default=32)
    local_epochs: Mapped[int] = mapped_column(Integer, default=1)
    mu: Mapped[float] = mapped_column(Float, default=0.0)  # FedProx proximal term
    server_momentum: Mapped[float] = mapped_column(Float, default=0.9)  # FedAdam
    aggregation_method: Mapped[str] = mapped_column(String(32), default="secure_masking")
    secure_aggregation: Mapped[bool] = mapped_column(Boolean, default=True)
    privacy_budget_per_round: Mapped[float] = mapped_column(Float, default=0.5)
    use_encryption: Mapped[bool] = mapped_column(Boolean, default=True)
    dataset_ids: Mapped[list] = mapped_column(JSON, default=list)
    selected_node_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    rounds: Mapped[list["FederatedRound"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    versions: Mapped[list["ModelVersion"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class FederatedRound(Base):
    __tablename__ = "federated_rounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("training_jobs.id"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | selecting | training | aggregating | completed | failed
    selected_client_ids: Mapped[list] = mapped_column(JSON, default=list)
    participated_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    f1: Mapped[float | None] = mapped_column(Float, nullable=True)
    communication_bytes: Mapped[int] = mapped_column(Integer, default=0)
    aggregation_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    client_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    privacy_budget_used: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    job: Mapped[TrainingJob] = relationship(back_populates="rounds")
    client_updates: Mapped[list["ClientUpdate"]] = relationship(back_populates="round", cascade="all, delete-orphan")


class ClientUpdate(Base):
    __tablename__ = "client_updates"

    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("federated_rounds.id"), index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("federated_nodes.id"))
    status: Mapped[str] = mapped_column(String(32), default="received")  # received | verified | aggregated | dropped
    masked_update: Mapped[dict] = mapped_column(JSON, default=dict)
    local_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    local_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    upload_bytes: Mapped[int] = mapped_column(Integer, default=0)
    contribution_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    round: Mapped[FederatedRound] = relationship(back_populates="client_updates")
    node: Mapped[FederatedNode] = relationship()


class AggregationLog(Base):
    __tablename__ = "aggregation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("federated_rounds.id"), index=True)
    method: Mapped[str] = mapped_column(String(64), default="masked_sum")
    client_count: Mapped[int] = mapped_column(Integer, default=0)
    masked_upload_count: Mapped[int] = mapped_column(Integer, default=0)
    masks_cancelled: Mapped[bool] = mapped_column(Boolean, default=True)
    signature_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    integrity_hash: Mapped[str] = mapped_column(String(128), default="")
    privacy_budget_consumed: Mapped[float] = mapped_column(Float, default=0.0)
    encryption_alg: Mapped[str] = mapped_column(String(64), default="AES-256-GCM")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("training_jobs.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | approved | rejected | deployed | archived
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    f1: Mapped[float | None] = mapped_column(Float, nullable=True)
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    parent_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approval_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    job: Mapped[TrainingJob] = relationship(back_populates="versions")


class XAIExplanation(Base):
    __tablename__ = "xai_explanations"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"), index=True)
    method: Mapped[str] = mapped_column(String(64), default="kernel_shap")
    feature_names: Mapped[list] = mapped_column(JSON, default=list)
    shap_values: Mapped[list] = mapped_column(JSON, default=list)
    base_value: Mapped[float] = mapped_column(Float, default=0.0)
    prediction: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    sample_index: Mapped[int] = mapped_column(Integer, default=0)
    explanation_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class NodeEvent(Base):
    __tablename__ = "node_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("federated_nodes.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64))  # heartbeat | round_start | training | upload | failure | recovery
    message: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), default="info")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_email: Mapped[str] = mapped_column(String(255), default="system")
    action: Mapped[str] = mapped_column(String(200), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), default="")
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")
    severity: Mapped[str] = mapped_column(String(16), default="info")
    chain_hash: Mapped[str] = mapped_column(String(128))
    previous_hash: Mapped[str] = mapped_column(String(128), default="GENESIS")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AIProvider(Base):
    __tablename__ = "ai_providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    provider_type: Mapped[str] = mapped_column(String(64))  # openai | anthropic | gemini | groq | deepseek | openrouter | mistral | ollama | azure_openai | openai_compatible
    base_url: Mapped[str] = mapped_column(String(255), default="")
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="")
    key_mask: Mapped[str] = mapped_column(String(64), default="")
    models: Mapped[list] = mapped_column(JSON, default=list)
    temperature_default: Mapped[float] = mapped_column(Float, default=0.3)
    status: Mapped[str] = mapped_column(String(32), default="configured")  # configured | tested | unreachable
    latency_ms: Mapped[float] = mapped_column(Float, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("ai_providers.id"), nullable=True)
    model: Mapped[str] = mapped_column(String(120), default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    user_prompt: Mapped[str] = mapped_column(Text, default="")
    temperature: Mapped[float] = mapped_column(Float, default=0.3)
    variables: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class InferenceLog(Base):
    __tablename__ = "inference_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("ai_providers.id"), index=True)
    provider_name: Mapped[str] = mapped_column(String(120), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    prompt_preview: Mapped[str] = mapped_column(Text, default="")
    response_preview: Mapped[str] = mapped_column(Text, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="ok")
    error: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LabExperiment(Base):
    __tablename__ = "lab_experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    algorithm: Mapped[str] = mapped_column(String(32), default="fedavg")
    clients: Mapped[int] = mapped_column(Integer, default=5)
    rounds: Mapped[int] = mapped_column(Integer, default=10)
    data_distribution: Mapped[str] = mapped_column(String(32), default="iid")  # iid | non_iid | pathological
    node_failure_rate: Mapped[float] = mapped_column(Float, default=0.0)
    results_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(Text, default="")
