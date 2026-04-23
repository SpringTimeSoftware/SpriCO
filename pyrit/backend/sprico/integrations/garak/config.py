"""garak scan configuration models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class GarakGeneratorConfig:
    type: str
    name: str
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GarakScanConfig:
    scan_id: str
    target_id: str
    generator: GarakGeneratorConfig
    policy_id: str | None = None
    scan_profile: str = "quick_baseline"
    vulnerability_categories: list[str] = field(default_factory=list)
    target_name: str | None = None
    target_type: str | None = None
    probes: list[str] = field(default_factory=list)
    detectors: list[str] = field(default_factory=list)
    extended_detectors: bool = False
    buffs: list[str] = field(default_factory=list)
    generations: int = 1
    max_attempts: int = 1
    seed: int | None = None
    parallel_requests: int = 1
    parallel_attempts: int = 1
    timeout_seconds: int = 3600
    budget: dict[str, Any] = field(default_factory=dict)
    permission_attestation: bool = False
    judge_settings: dict[str, Any] = field(default_factory=dict)
    policy_context: dict[str, Any] = field(default_factory=dict)
    profile_resolution: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["generator"] = self.generator.to_dict()
        return payload
