"""Allowlisted garak scan profiles for SpriCO scanner execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class GarakScanProfile:
    id: str
    label: str
    categories: tuple[str, ...]
    probes: tuple[str, ...] = field(default_factory=tuple)
    detectors: tuple[str, ...] = field(default_factory=tuple)
    buffs: tuple[str, ...] = field(default_factory=tuple)
    generations: int = 1
    timeout_seconds: int = 300


SCAN_PROFILES: dict[str, GarakScanProfile] = {
    "quick_baseline": GarakScanProfile(
        id="quick_baseline",
        label="Quick baseline",
        categories=("Privacy & Data Leakage", "Prompt Injection & Jailbreaks"),
        probes=("leakreplay.GuardianComplete", "promptinject.HijackHateHumans"),
        generations=1,
        timeout_seconds=180,
    ),
    "privacy_and_prompt_injection": GarakScanProfile(
        id="privacy_and_prompt_injection",
        label="Privacy and prompt injection",
        categories=("Privacy & Data Leakage", "Prompt Injection & Jailbreaks", "System Prompt Extraction"),
        probes=("leakreplay.GuardianComplete", "promptinject.HijackHateHumans", "encoding.InjectBase64"),
        generations=1,
        timeout_seconds=300,
    ),
    "deep_llm_security": GarakScanProfile(
        id="deep_llm_security",
        label="Deep LLM security",
        categories=(
            "Privacy & Data Leakage",
            "Prompt Injection & Jailbreaks",
            "System Prompt Extraction",
            "RAG Poisoning",
            "Agent / Tool Misuse",
            "Unsafe Medical Advice",
            "Hallucination / Unsupported Claims",
            "Authorization Boundary Bypass",
        ),
        probes=(
            "leakreplay.GuardianComplete",
            "promptinject.HijackHateHumans",
            "encoding.InjectBase64",
            "dan.DanInTheWild",
            "packagehallucination.Python",
            "doctor.Doctor",
        ),
        generations=2,
        timeout_seconds=600,
    ),
}

_CATEGORY_PROBES: dict[str, tuple[str, ...]] = {
    "Privacy & Data Leakage": ("leakreplay.GuardianComplete", "apikey.GCGCached"),
    "Prompt Injection & Jailbreaks": ("promptinject.HijackHateHumans", "dan.DanInTheWild"),
    "System Prompt Extraction": ("leakreplay.GuardianComplete",),
    "RAG Poisoning": ("web_injection.DocumentExfiltration", "latentinjection.LatentInjectionFactSnippetEiffel"),
    "Agent / Tool Misuse": ("exploitation.Exploitation",),
    "Unsafe Medical Advice": ("doctor.Doctor",),
    "Hallucination / Unsupported Claims": ("packagehallucination.Python", "snowball.GraphConnectivity"),
    "Authorization Boundary Bypass": ("promptinject.HijackHateHumans",),
}


def get_scan_profiles() -> list[dict[str, Any]]:
    return [
        {
            "id": profile.id,
            "label": profile.label,
            "categories": list(profile.categories),
            "probes": list(profile.probes),
            "detectors": list(profile.detectors),
            "generations": profile.generations,
            "timeout_seconds": profile.timeout_seconds,
        }
        for profile in SCAN_PROFILES.values()
    ]


def resolve_scan_profile(
    *,
    scan_profile: str,
    vulnerability_categories: list[str],
    available_plugins: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Resolve profile/category selection to allowlisted garak options.

    The frontend never sends raw garak CLI arguments. This function is the
    allowlist boundary. When garak plugin discovery is available, unavailable
    probes/detectors are skipped and reported instead of being passed through.
    """

    profile_key = (scan_profile or "quick_baseline").strip()
    if profile_key not in SCAN_PROFILES:
        raise ValueError(f"Unsupported scan_profile '{scan_profile}'.")

    profile = SCAN_PROFILES[profile_key]
    selected_categories = list(vulnerability_categories or profile.categories)
    probes = list(profile.probes)
    detectors = list(profile.detectors)
    buffs = list(profile.buffs)

    for category in selected_categories:
        for probe in _CATEGORY_PROBES.get(category, ()):
            if probe not in probes:
                probes.append(probe)

    skipped: dict[str, list[str]] = {"probes": [], "detectors": [], "buffs": []}
    if available_plugins:
        probes, skipped["probes"] = _filter_available(probes, available_plugins.get("probes") or [])
        detectors, skipped["detectors"] = _filter_available(detectors, available_plugins.get("detectors") or [])
        buffs, skipped["buffs"] = _filter_available(buffs, available_plugins.get("buffs") or [])

    return {
        "scan_profile": profile.id,
        "profile_label": profile.label,
        "categories": selected_categories,
        "probes": probes,
        "detectors": detectors,
        "buffs": buffs,
        "skipped": {key: value for key, value in skipped.items() if value},
        "default_generations": profile.generations,
        "default_timeout_seconds": profile.timeout_seconds,
    }


def _filter_available(values: list[str], available: list[str]) -> tuple[list[str], list[str]]:
    if not available:
        return values, []
    available_set = {item.lower() for item in available}
    selected: list[str] = []
    skipped: list[str] = []
    for value in values:
        if value.lower() in available_set:
            selected.append(value)
        else:
            skipped.append(value)
    return selected, skipped
