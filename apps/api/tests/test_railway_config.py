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


def graph() -> dict:
    return railway.load_graph()


def resource(document: dict, name: str) -> dict:
    return next(value for value in document["resources"] if value["name"] == name)


def test_committed_railway_iac_satisfies_beta_runtime_contract() -> None:
    railway.validate_graph(graph())


def test_api_contract_rejects_unsafe_deploy_changes() -> None:
    document = graph()
    resource(document, "api")["deploy"]["healthcheckPath"] = "/healthz"
    with pytest.raises(ValueError, match="dependency-aware"):
        railway.validate_graph(document)


def test_worker_cannot_run_migrations_or_mount_evidence_volume() -> None:
    document = graph()
    resource(document, "worker")["deploy"]["preDeployCommand"] = [
        "alembic upgrade head"
    ]
    with pytest.raises(ValueError, match="must not race"):
        railway.validate_graph(document)

    document = graph()
    resource(document, "worker")["volumeAttachments"] = {
        "unsafe": {"mountPath": "/app/data"}
    }
    with pytest.raises(ValueError, match="must not use Railway volumes"):
        railway.validate_graph(document)


def test_openbao_must_be_private_and_persistent() -> None:
    document = graph()
    unsafe = copy.deepcopy(document)
    resource(unsafe, "openbao")["networking"] = {
        "serviceDomains": {"openbao.example.test": {}}
    }
    with pytest.raises(ValueError, match="must not be publicly exposed"):
        railway.validate_graph(unsafe)

    resource(document, "openbao")["volumeAttachments"] = {}
    with pytest.raises(ValueError, match="exactly one persistent volume"):
        railway.validate_graph(document)


def test_openbao_readiness_and_deploy_scope_cannot_drift() -> None:
    document = graph()
    openbao = resource(document, "openbao")
    openbao["deploy"]["healthcheckPath"] = "/v1/sys/health"
    with pytest.raises(ValueError, match="seal-aware readiness"):
        railway.validate_graph(document)

    document = graph()
    openbao = resource(document, "openbao")
    openbao["build"]["watchPatterns"].append("/**")
    with pytest.raises(ValueError, match="deploy scope"):
        railway.validate_graph(document)


def test_beta_storage_and_approle_guards_cannot_drift() -> None:
    document = graph()
    api = resource(document, "api")
    api["variables"]["CHITAOZINHO_STORAGE_PROVIDER"]["value"] = "ceph"
    with pytest.raises(ValueError, match="Railway Bucket"):
        railway.validate_graph(document)

    document = graph()
    api = resource(document, "api")
    api["variables"]["CHITAOZINHO_OPENBAO_TOKEN"] = {
        "type": "literal",
        "value": "unsafe",
    }
    with pytest.raises(ValueError, match="static OpenBao token"):
        railway.validate_graph(document)
