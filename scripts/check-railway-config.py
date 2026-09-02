#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
IAC_PATH = ROOT / ".railway" / "railway.ts"


def load_graph() -> dict[str, Any]:
    script = """
import config from './.railway/railway.ts';
import {createRailwayContext, project} from 'railway/iac';
const graph = await config(
  createRailwayContext({environment: 'staging', environmentName: 'staging'}),
  project,
);
process.stdout.write(JSON.stringify(graph));
"""
    result = subprocess.run(
        ["node", "--no-warnings", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    document = json.loads(result.stdout)
    if not isinstance(document, dict):
        raise ValueError("Railway IaC must compile to an object")
    return document


def validate_graph(graph: dict[str, Any]) -> None:
    resources = graph.get("resources")
    if not isinstance(resources, list):
        raise ValueError("Railway IaC must declare resources")
    by_name = {resource.get("name"): resource for resource in resources}
    expected = {
        "postgres",
        "chitaozinho-beta",
        "openbao-data",
        "api",
        "worker",
        "retention-cleanup",
        "ots-processor",
        "openbao",
        "verifier-web",
    }
    if set(by_name) != expected:
        raise ValueError("Railway beta topology is incomplete")

    api = by_name["api"]
    worker = by_name["worker"]
    cleanup = by_name["retention-cleanup"]
    ots_processor = by_name["ots-processor"]
    openbao = by_name["openbao"]
    verifier = by_name["verifier-web"]
    if api["deploy"].get("preDeployCommand") != ["alembic upgrade head"]:
        raise ValueError("api must apply the exact forward migration before deploy")
    if api["deploy"].get("healthcheckPath") != "/readyz":
        raise ValueError("api must use dependency-aware readiness")
    if worker["deploy"].get("startCommand") != "python -m chitaozinho_api.worker":
        raise ValueError("worker runtime contract changed")
    if worker["deploy"].get("preDeployCommand") is not None:
        raise ValueError("worker must not race the api migration")
    if cleanup["deploy"].get("cronSchedule") != "15 3 * * *":
        raise ValueError("retention cleanup schedule changed")
    if cleanup["deploy"].get("startCommand") != (
        "python -m chitaozinho_api.retention_cleanup"
    ):
        raise ValueError("retention cleanup runtime contract changed")
    if ots_processor["deploy"].get("cronSchedule") != "*/15 * * * *":
        raise ValueError("OpenTimestamps processor schedule changed")
    if ots_processor["deploy"].get("startCommand") != (
        "python -m chitaozinho_api.ots_processor"
    ):
        raise ValueError("OpenTimestamps processor runtime contract changed")
    if openbao.get("networking"):
        raise ValueError("OpenBao must not be publicly exposed")
    if openbao["deploy"].get("healthcheckPath") != "/healthz":
        raise ValueError("OpenBao must expose seal-aware readiness")
    if openbao["deploy"].get("healthcheckTimeout") != 600:
        raise ValueError("OpenBao readiness must leave time for manual unseal")
    attachments = openbao.get("volumeAttachments") or {}
    if set(attachments) != {"openbao-data"}:
        raise ValueError("OpenBao must have exactly one persistent volume")
    if attachments["openbao-data"].get("mountPath") != "/openbao/data":
        raise ValueError("OpenBao Raft volume must remain mounted at /openbao/data")
    for name in ("api", "worker", "retention-cleanup", "ots-processor"):
        if by_name[name].get("volumeAttachments"):
            raise ValueError("evidence services must not use Railway volumes")
    if verifier["deploy"].get("healthcheckPath") != "/health":
        raise ValueError("verifier healthcheck changed")

    expected_watch_patterns = {
        "api": {
            "/.dockerignore",
            "/Dockerfile",
            "/alembic.ini",
            "/pyproject.toml",
            "/uv.lock",
            "/apps/api/**",
            "/packages/protocol-py/**",
            "/infra/openbao/ca.crt",
        },
        "openbao": {
            "/.dockerignore",
            "/Dockerfile.openbao",
            "/infra/openbao/railway-entrypoint.sh",
            "/infra/openbao/readiness-server.sh",
        },
        "verifier-web": {
            "/.dockerignore",
            "/Dockerfile.verifier-web",
            "/package.json",
            "/pnpm-lock.yaml",
            "/pnpm-workspace.yaml",
            "/apps/verifier-web/**",
            "/packages/protocol-ts/**",
            "/infra/railway/verifier-web.Caddyfile",
        },
    }
    for name in ("worker", "retention-cleanup", "ots-processor"):
        expected_watch_patterns[name] = expected_watch_patterns["api"]
    for name, expected_patterns in expected_watch_patterns.items():
        actual_patterns = set((by_name[name].get("build") or {}).get("watchPatterns") or [])
        if actual_patterns != expected_patterns:
            raise ValueError(f"{name} deploy scope must match its runtime inputs")

    for name in ("api", "worker", "retention-cleanup", "ots-processor"):
        variables = by_name[name].get("variables") or {}

        def literal(key: str, service_variables: dict = variables) -> str | None:
            return service_variables.get(key, {}).get("value")

        if literal("CHITAOZINHO_ENV") != "beta":
            raise ValueError("backend service must run with beta safety policy")
        if literal("CHITAOZINHO_STORAGE_PROVIDER") != "railway":
            raise ValueError("backend service must use Railway Bucket")
        if literal("CHITAOZINHO_RETENTION_DAYS") != "30":
            raise ValueError("beta retention must remain 30 days")
        if literal("CHITAOZINHO_OTS_ENABLED") != "true":
            raise ValueError("OpenTimestamps must remain enabled in beta")
        if literal("CHITAOZINHO_EMAIL_PROVIDER") != "resend":
            raise ValueError("beta email must use the Resend HTTP API")

        def secret_is_wired(
            key: str,
            service_name: str = name,
            service_variables: dict = variables,
        ) -> bool:
            variable = service_variables.get(key, {})
            if service_name == "ots-processor":
                return variable == {
                    "type": "reference",
                    "resource": "service.worker",
                    "output": key,
                }
            return variable.get("type") == "preserve"

        for key in (
            "CHITAOZINHO_AUTH_TOKEN_PEPPER",
            "CHITAOZINHO_METRICS_TOKEN",
            "CHITAOZINHO_OPENBAO_ROLE_ID",
            "CHITAOZINHO_OPENBAO_SECRET_ID",
            "CHITAOZINHO_RESEND_API_KEY",
            "CHITAOZINHO_RESEND_FROM",
            "CHITAOZINHO_SERVER_CERTIFICATE_JSON",
            "CHITAOZINHO_SERVER_REVOCATION_LIST_JSON",
            "CHITAOZINHO_SERVER_ROOT_PUBLIC_JSON",
        ):
            if not secret_is_wired(key):
                raise ValueError(f"{name}.{key} must remain a secret or internal reference")
        if "CHITAOZINHO_OPENBAO_TOKEN" in variables:
            raise ValueError("static OpenBao token is forbidden")


def main() -> None:
    validate_graph(load_graph())
    print("Railway IaC valid: beta topology, storage, cron and OpenBao are isolated")


if __name__ == "__main__":
    main()
