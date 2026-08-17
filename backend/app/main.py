"""Federated AI Platform — FastAPI application entrypoint.

Wires every module router, CORS, rate limiting, health checks and startup
initialization (DB creation + simulator + seed when FL_SEED=1).
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import init_db

API_PREFIX = settings.API_V1_PREFIX


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # seed demo data on first boot if enabled
    if settings.ENV != "production":
        try:
            from app.seed import seed_demo_data

            seed_demo_data()
        except Exception:  # noqa: BLE001
            pass
    # start the realtime node simulator
    try:
        from app.workers.tasks import start_simulator

        start_simulator(ticks=1_000_000, interval_s=3.0)
    except Exception:  # noqa: BLE001
        pass
    yield


app = FastAPI(
    title="Federated AI Platform",
    description="Privacy-Preserving Federated Learning using Secure Aggregation and Distributed Deep Learning",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple in-memory token bucket per client IP."""
    from app.core.ratelimit import limiter

    allowed, retry_after = limiter.check(str(request.client.host if request.client else "unknown"))
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "retry_after": retry_after},
        )
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(int((time.time() - start) * 1000))
    return response


# ------------------------------------------------------------------- routers
from app.api.routers import (  # noqa: E402
    admin,
    ai,
    analytics,
    assistant,
    audit,
    auth,
    coordinator,
    dashboard,
    datasets,
    evaluation,
    explainability,
    lab,
    models,
    monitor,
    nodes,
    organizations,
    reports,
    training,
    usersettings,
)

for r in (
    auth.router,
    dashboard.router,
    organizations.router,
    nodes.router,
    datasets.router,
    training.router,
    coordinator.router,
    models.router,
    evaluation.router,
    explainability.router,
    monitor.router,
    analytics.router,
    reports.router,
    audit.router,
    assistant.router,
    ai.router,
    admin.router,
    usersettings.router,
    lab.router,
):
    app.include_router(r, prefix=API_PREFIX)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}


@app.get("/")
def root():
    return {"name": settings.APP_NAME, "version": "1.0.0", "docs": "/docs", "health": "/health"}
