"""Exercise API-generated synthetic packages across independent verifiers."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-engines", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="chitaozinho-adversarial-") as directory:
        fixture = Path(directory)
        environment = {**os.environ, "HASH_ONLY_TEST_OUTPUT": directory}
        subprocess.run(
            ["uv", "run", "pytest", "apps/api/tests/test_hash_only.py", "-q"],
            cwd=ROOT,
            env=environment,
            check=True,
        )
        template = json.loads((fixture / "template.json").read_text())
        with (
            ZipFile(fixture / "evidence.zip") as source,
            ZipFile(fixture / "duplicate-index.zip", "w") as target,
        ):
            for entry in source.infolist():
                data = source.read(entry)
                if entry.filename == "package-index.json":
                    data = b'{"session_id":"forged-first-value",' + data[1:]
                target.writestr(entry, data)
        for name in ["evidence.zip", "duplicate-index.zip"]:
            result = subprocess.run(
                [
                    "cargo",
                    "run",
                    "--quiet",
                    "-p",
                    "chitaozinho-verifier",
                    "--",
                    "verify",
                    str(fixture / name),
                    "--trusted-server-key-hex",
                    template["server_key"],
                    "--json",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if name == "evidence.zip":
                if result.returncode or json.loads(result.stdout)["result"] != "integral":
                    raise RuntimeError("Valid synthetic package rejected: " + result.stderr)
            elif result.returncode == 0 or "duplicate JSON key" not in result.stderr:
                raise RuntimeError("Ambiguous index was not rejected for the expected reason")
            print(f"CLI: {name} {'accepted' if result.returncode == 0 else 'rejected'}")
        engines = ["chromium", "firefox", "webkit"] if args.all_engines else ["chromium"]
        browser_environment = dict(os.environ)
        for variable in [
            "CHITAOZINHO_WEB_BASE_URL",
            "CHITAOZINHO_WEB_TEST_PACKAGE",
            "CHITAOZINHO_WEB_TEST_CHECKSUM",
        ]:
            browser_environment.pop(variable, None)
        for engine in engines:
            command = ["pnpm", "--filter", "@chitaozinho/verifier-web", "test:e2e"]
            if engine != "chromium":
                command.extend(["--grep", "adversarial ZIP"])
            subprocess.run(
                command,
                cwd=ROOT,
                env={
                    **browser_environment,
                    "CHITAOZINHO_ADVERSARIAL_FIXTURE_DIR": directory,
                    "CHITAOZINHO_WEB_BROWSER": engine,
                },
                check=True,
            )


if __name__ == "__main__":
    main()
