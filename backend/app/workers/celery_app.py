"""Celery application for background jobs.

Celery is used in docker-compose deployments (Redis broker). For zero-infra
local runs the platform falls back to an in-process thread pool so every
feature works out of the box.
"""
from __future__ import annotations

import os

from app.core.config import settings

USE_CELERY = os.environ.get("FL_USE_CELERY", "0") == "1"

celery_app = None
if USE_CELERY:
    from celery import Celery

    celery_app = Celery(
        "federated_platform",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=["app.workers.tasks"],
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        worker_max_tasks_per_child=50,
    )
