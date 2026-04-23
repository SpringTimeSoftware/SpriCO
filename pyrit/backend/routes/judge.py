"""Optional judge-model configuration APIs."""

from __future__ import annotations

from fastapi import APIRouter

from pyrit.backend.sprico.judge import get_judge_status

router = APIRouter(tags=["judge"])


@router.get("/judge/status")
async def judge_status() -> dict:
    return get_judge_status()
