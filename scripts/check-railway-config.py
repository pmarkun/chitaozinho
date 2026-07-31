#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
API_PATH = ROOT / "infra" / "railway" / "api.json"
WORKER_PATH = ROOT / "infra" / "railway" / "worker.json"
SCHEMA = "https://railway.com/railway.schema.json"
BUILD = {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile",
}
RESTART = {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 5,
}


def load(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if not isinstance(document, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return document


def validate_configs(
    api: dict[str, Any],
    worker: dict[str, Any],
) -> None:
    validate_common("api", api)
    validate_common("worker", worker)

    api_deploy = require_mapping(api, "deploy", "api")
    worker_deploy = require_mapping(worker, "deploy", "worker")
    if api_deploy.get("preDeployCommand") != ["alembic upgrade head"]:
        raise ValueError("api must apply the exact forward migration before deploy")
    api_start = api_deploy.get("startCommand")
    if (
        not isinstance(api_start, str)
        or "chitaozinho_api.main:create_app" not in api_start
        or "--factory" not in api_start
        or "--host 0.0.0.0" not in api_start
        or "--port $PORT" not in api_start
        or "--no-access-log" not in api_start
    ):
        raise ValueError("api start command violates the public runtime contract")
    if api_deploy.get("healthcheckPath") != "/readyz":
        raise ValueError("api deploy health check must use dependency-aware /readyz")
    timeout = api_deploy.get("healthcheckTimeout")
    if not isinstance(timeout, int) or not 10 <= timeout <= 60:
        raise ValueError("api health check timeout must be between 10 and 60 seconds")

    if "preDeployCommand" in worker_deploy:
        raise ValueError("worker must not race the api migration during deploy")
    if "healthcheckPath" in worker_deploy:
        raise ValueError("worker must not advertise an HTTP readiness endpoint")
    worker_start = worker_deploy.get("startCommand")
    if worker_start != "python -m chitaozinho_api.worker":
        raise ValueError("worker start command violates the runtime contract")
    if api_start == worker_start:
        raise ValueError("api and worker processes must remain separate")


def validate_common(name: str, document: dict[str, Any]) -> None:
    if document.get("$schema") != SCHEMA:
        raise ValueError(f"{name} must declare the Railway schema")
    if document.get("build") != BUILD:
        raise ValueError(f"{name} must build the repository Dockerfile")
    deploy = require_mapping(document, "deploy", name)
    for key, expected in RESTART.items():
        if deploy.get(key) != expected:
            raise ValueError(f"{name} must use the bounded restart policy")
    reject_forbidden_keys(document, name=name)


def require_mapping(
    document: dict[str, Any],
    key: str,
    name: str,
) -> dict[str, Any]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{name}.{key} must be an object")
    return value


def reject_forbidden_keys(value: object, *, name: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in {"volume", "volumes", "volumemounts"}:
                raise ValueError(
                    f"{name} must not declare Railway volumes for evidence"
                )
            reject_forbidden_keys(nested, name=name)
    elif isinstance(value, list):
        for nested in value:
            reject_forbidden_keys(nested, name=name)


def main() -> None:
    validate_configs(load(API_PATH), load(WORKER_PATH))
    print("Railway configuration valid: isolated api and worker contracts")


if __name__ == "__main__":
    main()
