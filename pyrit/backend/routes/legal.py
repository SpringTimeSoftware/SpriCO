"""Legal and open-source component metadata APIs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse

from pyrit.backend.sprico.external_engines import (
    get_open_source_component,
    list_open_source_components,
    read_component_file,
)

router = APIRouter(tags=["legal"])


@router.get("/legal/open-source-components")
async def open_source_components() -> list[dict]:
    return list_open_source_components()


@router.get("/legal/open-source-components/{component_id}")
async def open_source_component(component_id: str) -> dict:
    component = get_open_source_component(component_id)
    if component is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown open-source component '{component_id}'")
    return component


@router.get("/legal/open-source-components/{component_id}/license", response_class=PlainTextResponse)
async def open_source_component_license(component_id: str) -> str:
    return _known_component_file(component_id, "license")


@router.get("/legal/open-source-components/{component_id}/source", response_class=PlainTextResponse)
async def open_source_component_source(component_id: str) -> str:
    return _known_component_file(component_id, "source")


@router.get("/legal/open-source-components/{component_id}/version", response_class=PlainTextResponse)
async def open_source_component_version(component_id: str) -> str:
    return _known_component_file(component_id, "version")


def _known_component_file(component_id: str, file_kind: str) -> str:
    content = read_component_file(component_id, file_kind)
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown open-source component '{component_id}'")
    if content == "":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{file_kind} file for open-source component '{component_id}' was not found",
        )
    return content
