from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

LOGGER = logging.getLogger("chitaozinho.request")
WORKER_LOGGER = logging.getLogger("chitaozinho.worker")
METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def configure_operational_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    LOGGER.setLevel(logging.INFO)
    WORKER_LOGGER.setLevel(logging.INFO)


def emit_request_log(
    *,
    request_id: str,
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    level = logging.ERROR if status_code >= 500 else logging.INFO
    LOGGER.log(
        level,
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": logging.getLevelName(level).lower(),
                "event": "http_request",
                "request_id": request_id,
                "method": method,
                "route": route,
                "status_code": status_code,
                "duration_ms": round(duration_seconds * 1_000, 3),
            },
            separators=(",", ":"),
        ),
    )


def emit_worker_log(
    *,
    event: str,
    job_id: str,
    job_kind: str,
    status: str,
    attempts: int,
    subject_id: str | None,
    error_type: str | None = None,
) -> None:
    level = logging.ERROR if status == "failed" else logging.INFO
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": logging.getLevelName(level).lower(),
        "event": event,
        "job_id": job_id,
        "job_kind": job_kind,
        "status": status,
        "attempts": attempts,
        "subject_id": subject_id,
    }
    if error_type is not None:
        record["error_type"] = error_type
    WORKER_LOGGER.log(
        level,
        json.dumps(record, separators=(",", ":")),
    )


@dataclass
class RequestMetrics:
    _requests: Counter[tuple[str, str, int]] = field(default_factory=Counter)
    _duration: Counter[tuple[str, str]] = field(default_factory=Counter)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def observe(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        with self._lock:
            self._requests[(method, route, status_code)] += 1
            self._duration[(method, route)] += duration_seconds

    def render(self) -> str:
        lines = [
            "# HELP chitaozinho_http_requests_total HTTP requests handled.",
            "# TYPE chitaozinho_http_requests_total counter",
        ]
        with self._lock:
            for (method, route, status_code), count in sorted(self._requests.items()):
                labels = (
                    f'method="{_escape(method)}",'
                    f'route="{_escape(route)}",'
                    f'status="{status_code}"'
                )
                lines.append(f"chitaozinho_http_requests_total{{{labels}}} {count}")
            lines.extend(
                [
                    "# HELP chitaozinho_http_request_duration_seconds_sum "
                    "Total HTTP request duration.",
                    "# TYPE chitaozinho_http_request_duration_seconds_sum counter",
                ]
            )
            for (method, route), duration in sorted(self._duration.items()):
                labels = f'method="{_escape(method)}",route="{_escape(route)}"'
                lines.append(
                    "chitaozinho_http_request_duration_seconds_sum"
                    f"{{{labels}}} {duration:.9f}"
                )
        return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
