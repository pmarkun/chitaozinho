from __future__ import annotations

import json
import runpy
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest


def test_object_lock_report_is_private_exclusive_and_atomically_updated(
    tmp_path: Path,
) -> None:
    script = runpy.run_path("scripts/test-s3-object-lock")
    create_report = cast(
        Callable[[Path, dict[str, Any]], None],
        script["create_report"],
    )
    replace_report = cast(
        Callable[[Path, dict[str, Any]], bytes],
        script["replace_report"],
    )
    report_path = tmp_path / "report.json"

    create_report(report_path, {"status": "started"})
    assert stat.S_IMODE(report_path.stat().st_mode) == 0o600
    assert json.loads(report_path.read_text()) == {"status": "started"}

    with pytest.raises(FileExistsError):
        create_report(report_path, {"status": "unexpected-overwrite"})

    encoded = replace_report(
        report_path,
        {
            "objects": [{"key": "acceptance/run/manifest.json"}],
            "status": "retaining",
        },
    )
    assert report_path.read_bytes() == encoded
    assert json.loads(encoded)["status"] == "retaining"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_object_lock_acceptance_requires_an_https_ceph_origin() -> None:
    script = runpy.run_path("scripts/test-s3-object-lock")
    validate_endpoint = cast(
        Callable[[str], str],
        script["validate_ceph_endpoint"],
    )

    assert validate_endpoint("https://rgw.example.test/") == ("https://rgw.example.test")
    for invalid in (
        "http://rgw.example.test",
        "https://user:secret@rgw.example.test",
        "https://rgw.example.test/path",
        "https://rgw.example.test?query=1",
    ):
        with pytest.raises(ValueError, match="HTTPS origin"):
            validate_endpoint(invalid)
