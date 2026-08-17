"""Enterprise Role-Based Access Control.

Roles:
  - admin                  Platform administrator: full control.
  - coordinator            Federated Coordinator: manages rounds, orgs, approvals.
  - org_admin              Organization Admin: manages local datasets, launches local training.
  - ml_engineer            ML Engineer: model development, evaluation, explainability, tuning.
  - research_scientist     Research Scientist: federated lab, experiments, read-only datasets.
"""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    COORDINATOR = "coordinator"
    ORG_ADMIN = "org_admin"
    ML_ENGINEER = "ml_engineer"
    RESEARCH_SCIENTIST = "research_scientist"


ROLE_LABELS = {
    Role.ADMIN: "Platform Admin",
    Role.COORDINATOR: "Federated Coordinator",
    Role.ORG_ADMIN: "Organization Admin",
    Role.ML_ENGINEER: "ML Engineer",
    Role.RESEARCH_SCIENTIST: "Research Scientist",
}


class Permission(str, Enum):
    # platform
    MANAGE_PLATFORM = "platform:manage"
    MANAGE_ROLES = "platform:roles"
    MANAGE_FEATURE_FLAGS = "platform:feature_flags"
    # organizations
    VIEW_ORGS = "orgs:view"
    MANAGE_ORGS = "orgs:manage"
    # nodes
    VIEW_NODES = "nodes:view"
    MANAGE_NODES = "nodes:manage"
    # datasets
    VIEW_DATASETS = "datasets:view"
    CREATE_DATASETS = "datasets:create"
    MANAGE_DATASETS = "datasets:manage"
    # training
    VIEW_TRAINING = "training:view"
    CREATE_TRAINING = "training:create"
    MANAGE_TRAINING = "training:manage"
    APPROVE_TRAINING = "training:approve"
    RUN_TRAINING = "training:run"
    # models
    VIEW_MODELS = "models:view"
    MANAGE_MODELS = "models:manage"
    DEPLOY_MODELS = "models:deploy"
    # evaluation / xai
    VIEW_EVALUATION = "evaluation:view"
    VIEW_XAI = "xai:view"
    # monitoring / analytics
    VIEW_MONITOR = "monitor:view"
    VIEW_ANALYTICS = "analytics:view"
    VIEW_REPORTS = "reports:view"
    # audit
    VIEW_AUDIT = "audit:view"
    # ai integrations
    MANAGE_AI = "ai:manage"
    USE_AI = "ai:use"
    # admin panel
    VIEW_ADMIN = "admin:view"
    # lab
    VIEW_LAB = "lab:view"
    # settings
    MANAGE_SETTINGS = "settings:manage"


# Permission matrix
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),
    Role.COORDINATOR: {
        Permission.VIEW_ORGS, Permission.MANAGE_ORGS,
        Permission.VIEW_NODES, Permission.MANAGE_NODES,
        Permission.VIEW_DATASETS,
        Permission.VIEW_TRAINING, Permission.CREATE_TRAINING, Permission.MANAGE_TRAINING,
        Permission.APPROVE_TRAINING, Permission.RUN_TRAINING,
        Permission.VIEW_MODELS, Permission.MANAGE_MODELS,
        Permission.VIEW_EVALUATION, Permission.VIEW_XAI,
        Permission.VIEW_MONITOR, Permission.VIEW_ANALYTICS, Permission.VIEW_REPORTS,
        Permission.VIEW_AUDIT,
        Permission.USE_AI, Permission.VIEW_LAB,
    },
    Role.ORG_ADMIN: {
        Permission.VIEW_ORGS,
        Permission.VIEW_NODES, Permission.MANAGE_NODES,
        Permission.VIEW_DATASETS, Permission.CREATE_DATASETS, Permission.MANAGE_DATASETS,
        Permission.VIEW_TRAINING, Permission.CREATE_TRAINING, Permission.MANAGE_TRAINING,
        Permission.RUN_TRAINING,
        Permission.VIEW_MODELS, Permission.MANAGE_MODELS,
        Permission.VIEW_EVALUATION, Permission.VIEW_XAI,
        Permission.VIEW_MONITOR, Permission.VIEW_ANALYTICS, Permission.VIEW_REPORTS,
        Permission.USE_AI, Permission.VIEW_LAB,
    },
    Role.ML_ENGINEER: {
        Permission.VIEW_ORGS,
        Permission.VIEW_NODES,
        Permission.VIEW_DATASETS, Permission.CREATE_DATASETS,
        Permission.VIEW_TRAINING, Permission.CREATE_TRAINING,
        Permission.VIEW_MODELS, Permission.MANAGE_MODELS,
        Permission.VIEW_EVALUATION, Permission.VIEW_XAI,
        Permission.VIEW_MONITOR, Permission.VIEW_ANALYTICS, Permission.VIEW_REPORTS,
        Permission.USE_AI, Permission.VIEW_LAB,
    },
    Role.RESEARCH_SCIENTIST: {
        Permission.VIEW_ORGS,
        Permission.VIEW_NODES,
        Permission.VIEW_DATASETS,
        Permission.VIEW_TRAINING,
        Permission.VIEW_MODELS,
        Permission.VIEW_EVALUATION, Permission.VIEW_XAI,
        Permission.VIEW_MONITOR, Permission.VIEW_ANALYTICS,
        Permission.USE_AI, Permission.VIEW_LAB,
    },
}


def role_permissions(role: str) -> set[str]:
    try:
        return {p.value for p in ROLE_PERMISSIONS[Role(role)]}
    except (KeyError, ValueError):
        return set()


def role_label(role: str) -> str:
    try:
        return ROLE_LABELS[Role(role)]
    except (KeyError, ValueError):
        return role.title()


def has_permission(role: str, permission: str | Permission) -> bool:
    perm = permission.value if isinstance(permission, Permission) else permission
    return perm in role_permissions(role)


ALL_ROLES = [r.value for r in Role]
