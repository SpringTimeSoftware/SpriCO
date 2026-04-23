# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
FastAPI application entry point for PyRIT backend.
"""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import pyrit
from pyrit.backend.middleware import RequestIdMiddleware, register_error_handlers
from pyrit.backend.routes import activity, attacks, audit, conditions, converters, evidence, external_engines, garak, health, judge, labels, legal, media, policies, projects, pyrit_compatibility, red, scoring, shield, storage, targets, version
from pyrit.backend.services.target_service import get_target_service
from pyrit.memory import CentralMemory, SQLiteMemory

# Check for development mode from environment variable
DEV_MODE = os.getenv("PYRIT_DEV_MODE", "false").lower() == "true"

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    # Initialization is handled by the pyrit_backend CLI before uvicorn starts.
    # Running 'uvicorn pyrit.backend.main:app' directly is not supported;
    # use 'pyrit_backend' instead.
    try:
        CentralMemory.get_memory_instance()
    except ValueError:
        logger.warning(
            "CentralMemory is not initialized. "
            "Falling back to SQLiteMemory for backend availability. "
            "Prefer starting via 'pyrit_backend' CLI for full initialization."
        )
        CentralMemory.set_memory_instance(SQLiteMemory())
    get_target_service().initialize_persistent_targets()
    yield


app = FastAPI(
    title="SpriCo AI Audit Platform API",
    description="Structured AI audit platform built on PyRIT and SQLite - REST API",
    version=pyrit.__version__,
    lifespan=lifespan,
)

# Register RFC 7807 error handlers
register_error_handlers(app)

# Attach X-Request-ID to every request/response for log correlation
app.add_middleware(RequestIdMiddleware)


# Configure CORS
_default_origins = "http://localhost:3000,http://localhost:5173"
_cors_origins = [o.strip() for o in os.getenv("PYRIT_CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routes
app.include_router(attacks.router, prefix="/api", tags=["attacks"])
app.include_router(activity.router, prefix="/api", tags=["activity"])
app.include_router(targets.router, prefix="/api", tags=["targets"])
app.include_router(converters.router, prefix="/api", tags=["converters"])
app.include_router(conditions.router, prefix="/api", tags=["conditions"])
app.include_router(labels.router, prefix="/api", tags=["labels"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(media.router, prefix="/api", tags=["media"])
app.include_router(scoring.router, prefix="/api", tags=["scoring"])
app.include_router(audit.router, prefix="/api", tags=["audit"])
app.include_router(pyrit_compatibility.router, prefix="/api", tags=["pyrit"])
app.include_router(garak.router, prefix="/api", tags=["garak"])
app.include_router(judge.router, prefix="/api", tags=["judge"])
app.include_router(external_engines.router, prefix="/api", tags=["external-engines"])
app.include_router(legal.router, prefix="/api", tags=["legal"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(policies.router, prefix="/api", tags=["policies"])
app.include_router(shield.router, prefix="/api", tags=["shield"])
app.include_router(red.router, prefix="/api", tags=["red"])
app.include_router(evidence.router, prefix="/api", tags=["evidence"])
app.include_router(storage.router, prefix="/api", tags=["storage"])
app.include_router(version.router, tags=["version"])


def setup_frontend() -> None:
    """Set up frontend static file serving."""
    frontend_path = Path(__file__).parent / "frontend"

    if DEV_MODE:
        # Development mode: frontend served separately by Vite
        print("[dev] Running in DEVELOPMENT mode - frontend should be running on port 3000")
    elif frontend_path.exists():
        # Production mode: serve bundled frontend
        print(f"[ok] Serving frontend from {frontend_path}")
        app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
    else:
        # Production mode but no frontend found - warn but don't exit
        # This allows API-only usage
        print("[warning] Frontend not found!")
        print(f"   Expected location: {frontend_path}")
        print("   The frontend must be built and included in the package.")
        print("   Run: python build_scripts/prepare_package.py")
        print("   API endpoints will still work but the UI won't be available.")


# Set up frontend at module load time (needed when running via uvicorn)
setup_frontend()
