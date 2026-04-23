"""Compatibility API for SpriCO's PyRIT adapter surface."""

from __future__ import annotations

from fastapi import APIRouter

from pyrit.backend.sprico.pyrit_adapter.compatibility import load_compatibility_matrix

router = APIRouter(tags=["pyrit"])


@router.get("/pyrit/compatibility")
async def get_pyrit_compatibility() -> dict:
    return load_compatibility_matrix()
