# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""API routes for version information."""

import json
import logging
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

import pyrit
from pyrit.memory import CentralMemory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/version", tags=["version"])
BACKEND_STARTUP_TIMESTAMP = datetime.now(timezone.utc).isoformat()


class VersionResponse(BaseModel):
    """Version information response model."""

    version: str
    source: Optional[str] = None
    commit: Optional[str] = None
    commit_hash: Optional[str] = None
    modified: Optional[bool] = None
    build_timestamp: Optional[str] = None
    backend_startup_timestamp: str
    display: str
    database_info: Optional[str] = None
    default_labels: Optional[dict[str, str]] = None


@router.get("", response_model=VersionResponse)
async def get_version_async(request: Request) -> VersionResponse:
    """
    Get version information for the PyRIT installation.

    Returns version from pyrit.__version__ and additional build info
    if running in Docker (from /app/build_info.json).

    Returns:
        VersionResponse: Version information including build metadata.
    """
    version = pyrit.__version__
    display = version
    source = None
    commit = os.getenv("SPRICO_COMMIT_SHA") or os.getenv("GIT_COMMIT")
    build_timestamp = os.getenv("SPRICO_BUILD_TIMESTAMP")
    modified = None

    # Try to load build info from Docker
    build_info_path = Path("/app/build_info.json")
    if build_info_path.exists():
        try:
            with open(build_info_path) as f:
                build_info = json.load(f)
                source = build_info.get("source")
                commit = build_info.get("commit") or commit
                modified = build_info.get("modified")
                build_timestamp = build_info.get("build_timestamp") or build_info.get("timestamp") or build_timestamp
                display = build_info.get("display", version)
        except Exception as e:
            logger.warning(f"Failed to load build info: {e}")

    if not commit:
        commit = _git_commit()

    # Detect current database backend
    database_info: Optional[str] = None
    try:
        memory = CentralMemory.get_memory_instance()
        db_type = type(memory).__name__
        db_name = None
        if memory.engine.url.database:
            db_name = memory.engine.url.database.split("?")[0]
        database_info = f"{db_type} ({db_name})" if db_name else f"{db_type} (None)"
    except Exception as e:
        logger.debug(f"Could not detect database info: {e}")

    # Read default labels from app state (set by pyrit_backend CLI)
    default_labels: Optional[dict[str, str]] = getattr(request.app.state, "default_labels", None) or None

    return VersionResponse(
        version=version,
        source=source,
        commit=commit,
        commit_hash=commit,
        modified=modified,
        build_timestamp=build_timestamp,
        backend_startup_timestamp=BACKEND_STARTUP_TIMESTAMP,
        display=display,
        database_info=database_info,
        default_labels=default_labels,
    )


def _git_commit() -> Optional[str]:
    try:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        value = completed.stdout.strip()
        return value or None
    except Exception:
        return None
