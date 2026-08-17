"""Pydantic schemas (request/response contracts) for the API surface."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------- auth
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2)
    role: str = "ml_engineer"
    organization_id: Optional[int] = None
    title: str = ""


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserOut"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    organization_id: Optional[int] = None
    organization_name: Optional[str] = None
    title: str
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    user: UserOut
    permissions: List[str]
    role_label: str
    feature_flags: Dict[str, bool]


# ---------------------------------------------------------------- orgs
class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    industry: str = "Technology"
    country: str = ""
    description: str = ""
    compliance_level: str = "GDPR + HIPAA aligned"
    data_guardian_enabled: bool = True


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    compliance_level: Optional[str] = None
    data_guardian_enabled: Optional[bool] = None


class OrganizationOut(BaseModel):
    id: int
    name: str
    slug: str
    industry: str
    country: str
    description: str
    status: str
    compliance_level: str
    data_guardian_enabled: bool
    created_at: datetime
    node_count: int = 0
    dataset_count: int = 0
    user_count: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- nodes
class NodeCreate(BaseModel):
    organization_id: int
    name: str
    endpoint: str = ""
    device_type: str = "server"
    cpu_cores: int = 8
    gpu_name: str = ""
    ram_gb: float = 16
    bandwidth_mbps: float = 100
    latency_ms: float = 12


class NodeUpdate(BaseModel):
    name: Optional[str] = None
    endpoint: Optional[str] = None
    status: Optional[str] = None
    bandwidth_mbps: Optional[float] = None
    latency_ms: Optional[float] = None
    trust_score: Optional[float] = None


class NodeOut(BaseModel):
    id: int
    organization_id: int
    organization_name: Optional[str] = None
    name: str
    endpoint: str
    status: str
    device_type: str
    cpu_cores: int
    gpu_name: str
    ram_gb: float
    bandwidth_mbps: float
    latency_ms: float
    last_heartbeat: Optional[datetime] = None
    mTLS_verified: bool
    trust_score: float
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- datasets
class DatasetCreate(BaseModel):
    organization_id: int
    name: str
    description: str = ""
    data_type: str = "tabular"
    feature_count: int = 8
    sample_count: int = 1000
    positive_ratio: float = 0.5
    noise: float = 0.15


class DatasetOut(BaseModel):
    id: int
    organization_id: int
    organization_name: Optional[str] = None
    name: str
    description: str
    data_type: str
    feature_count: int
    sample_count: int
    positive_ratio: float
    noise: float
    privacy_controls: Dict[str, Any]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- training
class TrainingJobCreate(BaseModel):
    name: str
    description: str = ""
    algorithm: str = "fedavg"
    model_architecture: str = "mlp"
    hidden_layers: List[int] = [16, 8]
    total_rounds: int = Field(default=5, ge=1, le=100)
    client_fraction: float = Field(default=0.6, ge=0.1, le=1.0)
    learning_rate: float = Field(default=0.01, gt=0)
    batch_size: int = Field(default=32, ge=1)
    local_epochs: int = Field(default=1, ge=1, le=50)
    mu: float = 0.0
    server_momentum: float = 0.9
    secure_aggregation: bool = True
    privacy_budget_per_round: float = 0.5
    use_encryption: bool = True
    dataset_ids: List[int] = []
    selected_node_ids: List[int] = []
    data_distribution: str = "non_iid"
    local_samples: int = 900
    noise: float = 0.15
    input_dim: int = 8
    seed: int = 42
    organization_id: Optional[int] = None

    @field_validator("algorithm")
    @classmethod
    def valid_algorithm(cls, v: str) -> str:
        if v not in ("fedavg", "fedprox", "fedadam"):
            raise ValueError("algorithm must be fedavg, fedprox or fedadam")
        return v


class JobAction(BaseModel):
    action: str  # start | pause | resume | cancel | approve | reject
    notes: str = ""


class RoundOut(BaseModel):
    id: int
    round_number: int
    status: str
    participated_count: int
    avg_loss: Optional[float]
    accuracy: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    f1: Optional[float]
    communication_bytes: int
    aggregation_time_ms: int
    privacy_budget_used: float
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TrainingJobOut(BaseModel):
    id: int
    name: str
    description: str
    status: str
    algorithm: str
    model_architecture: str
    total_rounds: int
    current_round: int
    client_fraction: float
    learning_rate: float
    local_epochs: int
    secure_aggregation: bool
    privacy_budget_per_round: float
    metrics_json: Dict[str, Any]
    created_by: int
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- models
class ModelVersionOut(BaseModel):
    id: int
    job_id: int
    job_name: Optional[str] = None
    version: int
    status: str
    accuracy: Optional[float]
    loss: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    f1: Optional[float]
    metrics_json: Dict[str, Any]
    parent_version: Optional[int]
    approval_notes: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelApprove(BaseModel):
    notes: str = ""


class ModelInferenceRequest(BaseModel):
    features: List[float] = Field(min_length=1)
    feature_names: Optional[List[str]] = None
    version_id: Optional[int] = None


class ModelInferenceResponse(BaseModel):
    version_id: int
    version: int
    model_name: str
    prediction: int
    probability: float
    confidence: float
    explanation: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------- ai
class ProviderCreate(BaseModel):
    name: str
    provider_type: str
    base_url: str = ""
    api_key: str = ""
    models: List[str] = []
    temperature_default: float = 0.3


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    models: Optional[List[str]] = None
    temperature_default: Optional[float] = None


class ProviderOut(BaseModel):
    id: int
    name: str
    provider_type: str
    base_url: str
    key_mask: str
    models: List[str]
    temperature_default: float
    status: str
    latency_ms: float
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    provider_id: int
    model: str = ""
    messages: List[Dict[str, str]] = Field(min_length=1)
    temperature: Optional[float] = None


class ChatResponse(BaseModel):
    provider_id: int
    provider_name: str
    model: str
    content: str
    tokens: int
    latency_ms: int
    status: str
    error: str = ""


class PromptTemplateCreate(BaseModel):
    name: str
    provider_id: Optional[int] = None
    model: str = ""
    system_prompt: str = ""
    user_prompt: str = ""
    temperature: float = 0.3
    variables: List[str] = []


class PromptTemplateOut(BaseModel):
    id: int
    name: str
    provider_id: Optional[int]
    model: str
    system_prompt: str
    user_prompt: str
    temperature: float
    variables: List[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- misc
class LabExperimentCreate(BaseModel):
    name: str
    description: str = ""
    algorithm: str = "fedavg"
    clients: int = Field(default=5, ge=2, le=50)
    rounds: int = Field(default=10, ge=1, le=100)
    data_distribution: str = "non_iid"
    node_failure_rate: float = Field(default=0.0, ge=0.0, le=0.9)


class FeatureFlagUpdate(BaseModel):
    enabled: bool
    description: str = ""


class SettingUpdate(BaseModel):
    value: str


class AuditVerifyOut(BaseModel):
    ok: bool
    message: str


class AggregationDemoResponse(BaseModel):
    job_name: str
    round_number: int
    clients: List[dict]
    method: str
    mask_pairs: int
    verified_signatures: int
    math_ok: bool
    privacy_budget_used: float
    log: List[str]


class DatasetSummary(BaseModel):
    total_datasets: int
    total_samples: int
    by_industry: Dict[str, int]


class MessageOut(BaseModel):
    message: str
    ok: bool = True


# re-export forward ref
TokenResponse.model_rebuild()
