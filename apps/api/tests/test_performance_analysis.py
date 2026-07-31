from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HEADER = (
    "timestamp,phase,chrome_processes,cpu_percent,rss_mib,"
    "read_mib,write_mib\n"
)
SCRIPT = Path(__file__).parents[3] / "scripts" / "analyze_browser_resources.py"


def test_browser_resource_report_compares_normalized_phases(
    tmp_path: Path,
) -> None:
    path = tmp_path / "resources.csv"
    path.write_text(
        HEADER
        + "2026-07-30T12:00:00-03:00,baseline,10,5,1000,0,0\n"
        + "2026-07-30T12:00:02-03:00,baseline,10,7,1010,1,2\n"
        + "2026-07-30T12:01:00-03:00,capture,11,15,1100,0,0\n"
        + "2026-07-30T12:01:02-03:00,capture,11,17,1120,2,4\n"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(path),
            "--minimum-samples",
            "2",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)

    assert report["baseline"]["duration_seconds"] == 4
    assert report["capture"]["duration_seconds"] == 4
    assert report["deltas"] == {
        "average_cpu_percentage_points": 10.0,
        "peak_rss_mib": 110.0,
        "write_mib_per_minute": 30.0,
    }
    assert report["resource_gate_passed"] is True
    assert len(report["csv_sha256"]) == 64


def test_browser_resource_report_rejects_thresholds_and_missing_samples(
    tmp_path: Path,
) -> None:
    path = tmp_path / "resources.csv"
    path.write_text(
        HEADER
        + "2026-07-30T12:00:00Z,baseline,10,1,100,0,0\n"
        + "2026-07-30T12:00:01Z,capture,10,50,500,0,10\n"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(path),
            "--minimum-samples",
            "1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert report["resource_gate_passed"] is False
    assert report["checks"] == {
        "average_cpu": False,
        "peak_rss": False,
        "write_rate": False,
    }
    missing = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(path),
            "--minimum-samples",
            "2",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert missing.returncode == 2
    assert "at least 2 samples" in missing.stderr
