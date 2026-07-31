from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

CPU_DELTA_LIMIT = 25.0
RSS_DELTA_LIMIT_MIB = 250.0
WRITE_DELTA_LIMIT_MIB_PER_MINUTE = 100.0


@dataclass(frozen=True)
class PhaseStats:
    samples: int
    duration_seconds: float
    average_cpu_percent: float
    peak_rss_mib: float
    read_mib_per_minute: float
    write_mib_per_minute: float


def phase_stats(rows: list[dict[str, str]], phase: str) -> PhaseStats:
    selected = [row for row in rows if row["phase"] == phase]
    if not selected:
        raise ValueError(f"phase has no samples: {phase}")
    timestamps = [datetime.fromisoformat(row["timestamp"]) for row in selected]
    intervals = [
        (current - previous).total_seconds()
        for previous, current in zip(timestamps, timestamps[1:], strict=False)
    ]
    if any(interval <= 0 for interval in intervals):
        raise ValueError(f"phase timestamps are not increasing: {phase}")
    sample_interval = statistics.median(intervals) if intervals else 1.0
    duration = max(
        1.0,
        (timestamps[-1] - timestamps[0]).total_seconds() + sample_interval,
    )
    return PhaseStats(
        samples=len(selected),
        duration_seconds=round(duration, 3),
        average_cpu_percent=round(
            statistics.fmean(float(row["cpu_percent"]) for row in selected),
            3,
        ),
        peak_rss_mib=round(max(float(row["rss_mib"]) for row in selected), 3),
        read_mib_per_minute=round(
            float(selected[-1]["read_mib"]) * 60 / duration,
            3,
        ),
        write_mib_per_minute=round(
            float(selected[-1]["write_mib"]) * 60 / duration,
            3,
        ),
    )


def analyze(path: Path, *, minimum_samples: int = 20) -> dict:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    expected_columns = {
        "timestamp",
        "phase",
        "chrome_processes",
        "cpu_percent",
        "rss_mib",
        "read_mib",
        "write_mib",
    }
    if not rows or set(rows[0]) != expected_columns:
        raise ValueError("unexpected browser resource CSV columns")
    if any(int(row["chrome_processes"]) <= 0 for row in rows):
        raise ValueError("browser resource sample has no Chrome processes")
    if any(
        float(row[column]) < 0
        for row in rows
        for column in ("cpu_percent", "read_mib", "write_mib")
    ):
        raise ValueError("browser resource sample contains a negative counter")
    baseline = phase_stats(rows, "baseline")
    capture = phase_stats(rows, "capture")
    if baseline.samples < minimum_samples or capture.samples < minimum_samples:
        raise ValueError(
            f"each phase requires at least {minimum_samples} samples"
        )
    deltas = {
        "average_cpu_percentage_points": round(
            capture.average_cpu_percent - baseline.average_cpu_percent,
            3,
        ),
        "peak_rss_mib": round(capture.peak_rss_mib - baseline.peak_rss_mib, 3),
        "write_mib_per_minute": round(
            capture.write_mib_per_minute - baseline.write_mib_per_minute,
            3,
        ),
    }
    checks = {
        "average_cpu": deltas["average_cpu_percentage_points"] <= CPU_DELTA_LIMIT,
        "peak_rss": deltas["peak_rss_mib"] <= RSS_DELTA_LIMIT_MIB,
        "write_rate": (
            deltas["write_mib_per_minute"]
            <= WRITE_DELTA_LIMIT_MIB_PER_MINUTE
        ),
    }
    return {
        "schema_version": "0.1.0",
        "csv_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "baseline": asdict(baseline),
        "capture": asdict(capture),
        "deltas": deltas,
        "limits": {
            "average_cpu_percentage_points": CPU_DELTA_LIMIT,
            "peak_rss_mib": RSS_DELTA_LIMIT_MIB,
            "write_mib_per_minute": WRITE_DELTA_LIMIT_MIB_PER_MINUTE,
        },
        "checks": checks,
        "resource_gate_passed": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--minimum-samples", type=int, default=20)
    args = parser.parse_args()
    if args.minimum_samples <= 0:
        parser.error("--minimum-samples must be positive")
    try:
        report = analyze(args.csv, minimum_samples=args.minimum_samples)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    serialized = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    if args.output is not None:
        args.output.write_text(serialized + "\n")
    print(serialized)
    if not report["resource_gate_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
