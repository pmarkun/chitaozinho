from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Job

LOGGER = logging.getLogger("chitaozinho.request")
WORKER_LOGGER = logging.getLogger("chitaozinho.worker")
METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
JOB_STATUSES = ("pending", "running", "failed", "completed")


def configure_operational_logging() -> None:
    logging.disable(logging.NOTSET)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    LOGGER.setLevel(logging.INFO)
    LOGGER.disabled = False
    LOGGER.propagate = True
    WORKER_LOGGER.setLevel(logging.INFO)
    WORKER_LOGGER.disabled = False
    WORKER_LOGGER.propagate = True


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


def render_job_metrics(
    database: Session,
    *,
    worker_stale_seconds: int,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(UTC)
    counts = dict(
        database.execute(
            select(Job.status, func.count(Job.id))
            .where(Job.status.in_(JOB_STATUSES))
            .group_by(Job.status)
        ).all()
    )
    ready = (
        database.scalar(
            select(func.count(Job.id)).where(
                Job.status.in_(["pending", "failed"]),
                Job.available_at <= now,
            )
        )
        or 0
    )
    stale_running = (
        database.scalar(
            select(func.count(Job.id)).where(
                Job.status == "running",
                Job.updated_at < now - timedelta(seconds=worker_stale_seconds),
            )
        )
        or 0
    )
    lines = [
        "# HELP chitaozinho_jobs Current durable jobs by state.",
        "# TYPE chitaozinho_jobs gauge",
        *[
            f'chitaozinho_jobs{{status="{status}"}} {counts.get(status, 0)}'
            for status in JOB_STATUSES
        ],
        "# HELP chitaozinho_jobs_ready Jobs eligible for immediate processing.",
        "# TYPE chitaozinho_jobs_ready gauge",
        f"chitaozinho_jobs_ready {ready}",
        "# HELP chitaozinho_jobs_stale_running Running jobs past the recovery threshold.",
        "# TYPE chitaozinho_jobs_stale_running gauge",
        f"chitaozinho_jobs_stale_running {stale_running}",
    ]
    return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
