from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
SCRIPT = ROOT / "scripts" / "check-railway-config.py"
SPEC = importlib.util.spec_from_file_location("check_railway_config", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
railway = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(railway)


def configs() -> tuple[dict, dict, dict]:
    return (
        railway.load(railway.API_PATH),
        railway.load(railway.WORKER_PATH),
        railway.load(railway.VERIFIER_WEB_PATH),
    )


def test_committed_railway_configs_satisfy_runtime_contract() -> None:
    api, worker, verifier_web = configs()
    railway.validate_configs(api, worker, verifier_web)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("preDeployCommand", [], "forward migration"),
        ("healthcheckPath", "/healthz", "dependency-aware"),
        (
            "startCommand",
            "uvicorn chitaozinho_api.main:create_app --factory",
            "runtime contract",
        ),
    ],
)
def test_api_contract_rejects_unsafe_deploy_changes(
    field: str,
    value: object,
    message: str,
) -> None:
    api, worker, verifier_web = configs()
    api["deploy"][field] = value
    with pytest.raises(ValueError, match=message):
        railway.validate_configs(api, worker, verifier_web)


def test_worker_cannot_run_migrations_or_mount_evidence_volume() -> None:
    api, worker, verifier_web = configs()
    worker_with_migration = copy.deepcopy(worker)
    worker_with_migration["deploy"]["preDeployCommand"] = ["alembic upgrade head"]
    with pytest.raises(ValueError, match="must not race"):
        railway.validate_configs(api, worker_with_migration, verifier_web)

    worker["deploy"]["volumes"] = [{"mountPath": "/app/data"}]
    with pytest.raises(ValueError, match="must not declare Railway volumes"):
        railway.validate_configs(api, worker, verifier_web)


def test_verifier_uses_static_container_contract() -> None:
    api, worker, verifier_web = configs()
    verifier_web["deploy"]["startCommand"] = "pnpm dev"
    with pytest.raises(ValueError, match="immutable container command"):
        railway.validate_configs(api, worker, verifier_web)
