#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

CONFIG_PATH = (
    Path(__file__).parents[1]
    / "infra"
    / "monitoring"
    / "alerts.rules.json"
)
EXPECTED_ALERTS = {
    "ChitaozinhoApiUnavailable",
    "ChitaozinhoHighMeanRequestLatency",
    "ChitaozinhoHighServerErrorRatio",
    "ChitaozinhoReadyJobsBacklogged",
    "ChitaozinhoStaleRunningJobs",
}


def main() -> None:
    document = json.loads(CONFIG_PATH.read_text())
    groups = document.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("monitoring configuration requires alert groups")
    names: set[str] = set()
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("name"), str):
            raise ValueError("invalid alert group")
        rules = group.get("rules")
        if not isinstance(rules, list) or not rules:
            raise ValueError("alert group requires rules")
        for rule in rules:
            validate_rule(rule)
            name = rule["alert"]
            if name in names:
                raise ValueError(f"duplicate alert: {name}")
            names.add(name)
    if names != EXPECTED_ALERTS:
        missing = sorted(EXPECTED_ALERTS - names)
        unexpected = sorted(names - EXPECTED_ALERTS)
        raise ValueError(
            f"alert contract changed; missing={missing}, unexpected={unexpected}"
        )
    print(f"Monitoring configuration valid: {len(names)} alerts")


def validate_rule(rule: object) -> None:
    if not isinstance(rule, dict):
        raise ValueError("alert rule must be an object")
    name = rule.get("alert")
    expression = rule.get("expr")
    duration = rule.get("for")
    labels = rule.get("labels")
    annotations = rule.get("annotations")
    if not isinstance(name, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9]+", name) is None:
        raise ValueError("invalid alert name")
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError(f"{name} requires an expression")
    if any(value in expression for value in ("session_id", "job_id", "subject_id")):
        raise ValueError(f"{name} uses a high-cardinality identifier")
    if not isinstance(duration, str) or re.fullmatch(r"[1-9][0-9]*[smhd]", duration) is None:
        raise ValueError(f"{name} requires a bounded duration")
    if (
        not isinstance(labels, dict)
        or labels.get("severity") not in {"warning", "critical"}
    ):
        raise ValueError(f"{name} requires an approved severity")
    if (
        not isinstance(annotations, dict)
        or not isinstance(annotations.get("summary"), str)
        or not isinstance(annotations.get("description"), str)
    ):
        raise ValueError(f"{name} requires summary and description")


if __name__ == "__main__":
    main()
