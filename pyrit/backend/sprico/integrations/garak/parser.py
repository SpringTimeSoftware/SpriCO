"""Parse garak JSONL and hit-log artifacts into raw scanner findings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RawScannerFinding:
    engine: str = "garak"
    engine_version: str | None = None
    probe_id: str | None = None
    detector_id: str | None = None
    generator_id: str | None = None
    prompt: str | None = None
    response: str | None = None
    attempt_id: str | None = None
    generation_id: str | None = None
    detector_result: Any = None
    pass_fail: str | None = None
    failure_rate: float | None = None
    raw_json: dict[str, Any] = field(default_factory=dict)
    artifact_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_artifacts(*, scan_dir: Path, engine_version: str | None = None) -> list[RawScannerFinding]:
    findings: list[RawScannerFinding] = []
    for path in _jsonl_paths(scan_dir):
        findings.extend(parse_jsonl_file(path=path, engine_version=engine_version))
    return findings


def parse_jsonl_file(*, path: Path, engine_version: str | None = None) -> list[RawScannerFinding]:
    findings: list[RawScannerFinding] = []
    if not path.exists():
        return findings
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                findings.append(
                    RawScannerFinding(
                        engine_version=engine_version,
                        raw_json={"unparsed_line": text, "line_no": line_no},
                        artifact_refs=[str(path)],
                    )
                )
                continue
            finding = parse_json_record(payload=payload, engine_version=engine_version, artifact_ref=str(path))
            if finding:
                findings.append(finding)
    return findings


def parse_json_record(*, payload: dict[str, Any], engine_version: str | None = None, artifact_ref: str | None = None) -> RawScannerFinding | None:
    if not isinstance(payload, dict):
        return None
    artifact_refs = [artifact_ref] if artifact_ref else []
    detector_result = _pick(payload, "detector_result", "detector_results", "score", "scores", "result", "passed", "hit")
    pass_fail = _pick(payload, "pass_fail", "status", "outcome", "hit", "passed", "detected")
    failure_rate = _float_or_none(_pick(payload, "failure_rate", "fail_rate", "score", "failure", "rate"))
    return RawScannerFinding(
        engine_version=engine_version or _pick(payload, "garak_version", "version"),
        probe_id=_string_or_none(_pick(payload, "probe", "probe_id", "probe_classname", "probe_name", "probe.name", "probe.module")),
        detector_id=_string_or_none(_pick(payload, "detector", "detector_id", "detector_classname", "detector_name", "detector.name", "detector.module")),
        generator_id=_string_or_none(_pick(payload, "generator", "generator_id", "model", "target", "target_name", "generator.name")),
        prompt=_string_or_none(_pick(payload, "prompt", "mutated_prompt", "input", "attack_prompt", "prompt_text", "request")),
        response=_string_or_none(_pick(payload, "response", "output", "generation", "target_output", "generated_text", "model_output")),
        attempt_id=str(_pick(payload, "attempt_id", "attempt", "uuid", "id") or ""),
        generation_id=str(_pick(payload, "generation_id", "generation_id", "sample_id", "sample") or ""),
        detector_result=detector_result,
        pass_fail=str(pass_fail) if pass_fail is not None else None,
        failure_rate=failure_rate,
        raw_json=payload,
        artifact_refs=artifact_refs,
    )


def _jsonl_paths(scan_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for pattern in ("*.jsonl", "*.hitlog", "*hitlog*.jsonl", "*hits*.jsonl"):
        paths.extend(scan_dir.glob(pattern))
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _pick(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = _pick_path(payload, key)
        if value not in (None, ""):
            return value
    return None


def _pick_path(payload: dict[str, Any], key: str) -> Any:
    if "." not in key:
        return payload.get(key)
    current: Any = payload
    for part in key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("name", "module", "id", "class", "classname"):
            if value.get(key):
                return str(value[key])
    return str(value)


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
