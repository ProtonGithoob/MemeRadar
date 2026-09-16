#!/usr/bin/env python3
"""Poll an already-running read-only stack without changing its state."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
_MODES = {
    "analysis_only": True,
    "paper_trading": True,
    "manual_execution": False,
    "auto_execution": False,
}
_ENDPOINTS = (
    ("live", "/health/live", False),
    ("ready", "/health/ready", False),
    ("readiness", "/v1/readiness", True),
    ("operations", "/v1/operations/overview", True),
    ("providers", "/v1/providers/health?limit=50", True),
)


@dataclass(frozen=True, slots=True)
class HttpResult:
    status: int
    body: object
    latency_ms: float


RequestFunction = Callable[[str, dict[str, str]], HttpResult]
Clock = Callable[[], datetime]
RuntimeSnapshotFunction = Callable[[Sequence[str]], Mapping[str, Mapping[str, object]]]
_MEMORY_USAGE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([kmgtpe]?i?b)\s*/", re.IGNORECASE)
_MEMORY_UNITS = {
    "b": 1,
    "kb": 1000,
    "mb": 1000**2,
    "gb": 1000**3,
    "tb": 1000**4,
    "pb": 1000**5,
    "kib": 1024,
    "mib": 1024**2,
    "gib": 1024**3,
    "tib": 1024**4,
    "pib": 1024**5,
}


def _request_json(url: str, headers: dict[str, str]) -> HttpResult:
    started = time.perf_counter()
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - operator-supplied read URL
            raw = response.read()
            status = int(response.status)
    except HTTPError as exc:
        raw = exc.read()
        status = int(exc.code)
    except (OSError, TimeoutError, URLError):
        raise
    try:
        body: object = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        body = {"malformed_response": True}
    return HttpResult(status, body, round((time.perf_counter() - started) * 1000, 3))


def _bounded_iterations(value: int) -> int:
    if isinstance(value, bool) or not 1 <= value <= 100_000:
        raise ValueError("iterations must be between 1 and 100000")
    return value


def _bounded_interval(value: float) -> float:
    if isinstance(value, bool) or not 0 <= value <= 3600:
        raise ValueError("interval_seconds must be between 0 and 3600")
    return float(value)


def _git_sha() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--verify", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _memory_bytes(value: str) -> int | None:
    match = _MEMORY_USAGE.match(value)
    if match is None:
        return None
    unit = match.group(2).lower()
    multiplier = _MEMORY_UNITS.get(unit)
    return None if multiplier is None else round(float(match.group(1)) * multiplier)


def _docker_snapshot(names: Sequence[str]) -> Mapping[str, Mapping[str, object]]:
    """Capture bounded container liveness, restart and memory evidence."""

    inspect = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Status}}\t{{.RestartCount}}",
            *names,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    inspected = [line.split("\t", 1) for line in inspect.stdout.splitlines() if line.strip()]
    if len(inspected) != len(names) or any(len(line) != 2 for line in inspected):
        raise ValueError("docker inspect returned an incomplete container snapshot")
    stats = subprocess.run(
        [
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "{{.Name}}\t{{.MemUsage}}",
            *names,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    memory: dict[str, int | None] = {}
    for line in stats.stdout.splitlines():
        name, separator, usage = line.partition("\t")
        if separator:
            memory[name] = _memory_bytes(usage)
    return {
        name: {
            "status": state,
            "restart_count": int(restarts),
            "memory_usage_bytes": memory.get(name),
        }
        for name, (state, restarts) in zip(names, inspected, strict=True)
    }


def _container_runtime(
    names: Sequence[str],
    initial: Mapping[str, Mapping[str, object]] | None,
    final: Mapping[str, Mapping[str, object]] | None,
) -> dict[str, object]:
    if not names or initial is None or final is None:
        return {
            "measurement_method": "NOT_CONFIGURED",
            "worker_liveness": "NOT_MEASURED",
            "process_container_restarts": "NOT_MEASURED",
            "memory_usage_bytes": "NOT_MEASURED",
        }
    services: dict[str, dict[str, object]] = {}
    restarts: dict[str, int] = {}
    memory_usage: dict[str, dict[str, int | None]] = {}
    for name in names:
        before = initial.get(name, {})
        after = final.get(name, {})
        before_restart = before.get("restart_count")
        after_restart = after.get("restart_count")
        if not isinstance(before_restart, int) or isinstance(before_restart, bool):
            raise ValueError("container restart count is invalid")
        if not isinstance(after_restart, int) or isinstance(after_restart, bool):
            raise ValueError("container restart count is invalid")
        before_memory = before.get("memory_usage_bytes")
        after_memory = after.get("memory_usage_bytes")
        if before_memory is not None and (
            not isinstance(before_memory, int) or isinstance(before_memory, bool)
        ):
            raise ValueError("container memory usage is invalid")
        if after_memory is not None and (
            not isinstance(after_memory, int) or isinstance(after_memory, bool)
        ):
            raise ValueError("container memory usage is invalid")
        services[name] = {
            "status": after.get("status"),
            "restart_count": after_restart,
        }
        restarts[name] = max(0, after_restart - before_restart)
        memory_usage[name] = {
            "initial": before_memory,
            "final": after_memory,
            "growth": (
                None
                if before_memory is None or after_memory is None
                else after_memory - before_memory
            ),
        }
    worker_names = [name for name in names if "worker" in name.lower()]
    worker_liveness = (
        "PASS"
        if worker_names and all(services[name]["status"] == "running" for name in worker_names)
        else "FAIL"
    )
    return {
        "measurement_method": "docker_inspect_and_stats",
        "services": services,
        "worker_liveness": worker_liveness,
        "process_container_restarts": restarts,
        "memory_usage_bytes": memory_usage,
    }


def _real_observation_count(body: object) -> int | None:
    if not isinstance(body, Mapping):
        return None
    for key in ("gmgn_alpha_validation", "alpha_validation"):
        candidate = body.get(key)
        if isinstance(candidate, Mapping):
            value = candidate.get("real_observation_count")
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
    value = body.get("real_observation_count")
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _counter(body: object, name: str) -> int | None:
    if not isinstance(body, Mapping):
        return None
    metrics = body.get("metrics")
    if not isinstance(metrics, Mapping):
        return None
    counters = metrics.get("counters")
    if not isinstance(counters, Mapping):
        return None
    value = counters.get(name)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _modes(body: object) -> dict[str, bool] | None:
    if not isinstance(body, Mapping):
        return None
    for key in ("protected_modes", "modes"):
        value = body.get(key)
        if isinstance(value, Mapping):
            result = {name: value.get(name) for name in _MODES}
            if all(isinstance(item, bool) for item in result.values()):
                return result  # type: ignore[return-value]
    return None


def _dependency_interruptions(body: object) -> dict[str, int]:
    result = {"database": 0, "redis": 0}
    if not isinstance(body, Mapping):
        return result
    dependencies = body.get("dependencies")
    if not isinstance(dependencies, Mapping):
        return result
    for name in result:
        item = dependencies.get(name)
        if (
            isinstance(item, Mapping)
            and item.get("required") is True
            and item.get("state") != "reachable"
        ):
            result[name] += 1
    return result


def _digest(report: Mapping[str, object]) -> str:
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def run_stack_soak(
    base_url: str,
    viewer_token: str | None,
    *,
    iterations: int = 100,
    interval_seconds: float = 1.0,
    request: RequestFunction = _request_json,
    clock: Clock | None = None,
    container_names: Sequence[str] = (),
    container_snapshot: RuntimeSnapshotFunction | None = None,
) -> dict[str, object]:
    """Collect bounded HTTP/readiness evidence from an existing stack."""

    if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
        raise ValueError("base_url must be an HTTP(S) URL")
    count = _bounded_iterations(iterations)
    interval = _bounded_interval(interval_seconds)
    if viewer_token is None or not isinstance(viewer_token, str) or not viewer_token:
        report: dict[str, object] = {
            "schema_version": "production-stack-soak-v1",
            "measurement_method": "production_like_http_stack",
            "status": "BLOCKED_EXTERNAL",
            "reason": "MEMERADAR_STACK_VIEWER_API_TOKEN is required",
            "request_count": 0,
            "error_count": 0,
            "readiness_failures": 0,
        }
        report["artifact_digest"] = _digest(report)
        return report

    now = clock or (lambda: datetime.now(UTC))
    started_at = now()
    request_count = 0
    error_count = 0
    readiness_failures = 0
    dependency_interruptions = {"database": 0, "redis": 0}
    latencies: list[float] = []
    statuses: dict[str, int] = {}
    initial_observations: int | None = None
    final_observations: int | None = None
    observed_modes: dict[str, bool] | None = None
    execution_eligible: bool | None = None
    failures: list[str] = []
    normalized_container_names = tuple(
        name.strip() for name in container_names if isinstance(name, str) and name.strip()
    )
    initial_container_runtime = (
        None
        if not normalized_container_names
        else (container_snapshot or _docker_snapshot)(normalized_container_names)
    )
    initial_duplicate_events: int | None = None
    final_duplicate_events: int | None = None

    for iteration in range(count):
        for name, path, authenticated in _ENDPOINTS:
            headers = {"Authorization": f"Bearer {viewer_token}"} if authenticated else {}
            request_count += 1
            try:
                result = request(f"{base_url.rstrip('/')}{path}", headers)
            except (OSError, TimeoutError, URLError) as exc:
                error_count += 1
                failures.append(f"{name}:{type(exc).__name__}")
                continue
            latencies.append(result.latency_ms)
            statuses[str(result.status)] = statuses.get(str(result.status), 0) + 1
            if not 200 <= result.status < 300:
                error_count += 1
                failures.append(f"{name}:HTTP_{result.status}")
            if name == "ready":
                if result.status != 200:
                    readiness_failures += 1
                for dependency, amount in _dependency_interruptions(result.body).items():
                    dependency_interruptions[dependency] += amount
            if name == "readiness":
                observations = _real_observation_count(result.body)
                if observations is not None:
                    if initial_observations is None:
                        initial_observations = observations
                    final_observations = observations
                modes = _modes(result.body)
                if modes is not None:
                    observed_modes = modes
                if isinstance(result.body, Mapping):
                    live_money = result.body.get("live_money")
                    if isinstance(live_money, Mapping) and isinstance(
                        live_money.get("execution_eligible"), bool
                    ):
                        execution_eligible = live_money["execution_eligible"]
            if name == "operations" and isinstance(result.body, Mapping):
                duplicate_events = _counter(result.body, "duplicate_events")
                if duplicate_events is not None:
                    if initial_duplicate_events is None:
                        initial_duplicate_events = duplicate_events
                    final_duplicate_events = duplicate_events
                modes = _modes(result.body)
                if modes is not None:
                    observed_modes = modes
                if isinstance(result.body.get("execution_eligible"), bool):
                    execution_eligible = result.body["execution_eligible"]
        if iteration + 1 < count and interval:
            time.sleep(interval)

    final_container_runtime = (
        None
        if not normalized_container_names
        else (container_snapshot or _docker_snapshot)(normalized_container_names)
    )
    ended_at = now()
    duration = max(0.0, (ended_at - started_at).total_seconds())
    mode_ok = observed_modes == _MODES
    execution_ok = execution_eligible is False
    container_runtime = _container_runtime(
        normalized_container_names,
        initial_container_runtime,
        final_container_runtime,
    )
    container_ok = container_runtime["worker_liveness"] in {"PASS", "NOT_MEASURED"}
    status = (
        "PASS"
        if error_count == 0 and mode_ok and execution_ok and container_ok
        else "DEGRADED"
    )
    duplicate_delta = (
        None
        if initial_duplicate_events is None or final_duplicate_events is None
        else max(0, final_duplicate_events - initial_duplicate_events)
    )
    report = {
        "schema_version": "production-stack-soak-v1",
        "measurement_method": "production_like_http_stack",
        "git_sha": _git_sha(),
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_seconds": round(duration, 3),
        "iterations": count,
        "request_count": request_count,
        "error_count": error_count,
        "readiness_failures": readiness_failures,
        "http_status_counts": statuses,
        "latency_ms": {
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
            "average": round(sum(latencies) / len(latencies), 3) if latencies else None,
        },
        "dependency_interruptions": dependency_interruptions,
        "persistence": {
            "initial_real_observation_count": initial_observations,
            "final_real_observation_count": final_observations,
            "real_observation_delta": (
                None
                if initial_observations is None or final_observations is None
                else final_observations - initial_observations
            ),
        },
        "duplicate_accounting": {
            "initial_duplicate_events": initial_duplicate_events,
            "final_duplicate_events": final_duplicate_events,
            "duplicate_event_delta": duplicate_delta,
            "duplicate_rate_per_request": (
                None
                if duplicate_delta is None
                else round(duplicate_delta / max(request_count, 1), 6)
            ),
        },
        "container_runtime": container_runtime,
        "protected_modes": observed_modes,
        "execution_eligible": execution_eligible,
        "failures": failures[:32],
        "status": status,
    }
    report["artifact_digest"] = _digest(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MEMERADAR_STACK_API_BASE_URL", "http://127.0.0.1:18000"),
    )
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run_stack_soak(
            args.base_url,
            os.environ.get("MEMERADAR_STACK_VIEWER_API_TOKEN"),
            iterations=args.iterations,
            interval_seconds=args.interval_seconds,
            container_names=tuple(
                name.strip()
                for name in os.environ.get("MEMERADAR_STACK_CONTAINER_NAMES", "").split(",")
                if name.strip()
            ),
        )
        encoded = json.dumps(report, sort_keys=True, indent=2) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        else:
            sys.stdout.write(encoded)
    except (OSError, TypeError, ValueError, subprocess.CalledProcessError) as exc:
        del exc
        print("production stack soak failed: INVALID_INPUT_OR_UNAVAILABLE_STACK", file=sys.stderr)
        return 2
    status = report["status"]
    return 0 if status == "PASS" else 2 if status == "BLOCKED_EXTERNAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
