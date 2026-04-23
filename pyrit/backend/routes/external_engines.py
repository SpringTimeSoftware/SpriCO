"""External attack/evidence engine metadata APIs."""

from __future__ import annotations

from fastapi import APIRouter

from pyrit.backend.sprico.external_engines import external_engine_matrix

router = APIRouter(tags=["external-engines"])


@router.get("/external-engines")
async def external_engines() -> dict:
    return external_engine_matrix()
