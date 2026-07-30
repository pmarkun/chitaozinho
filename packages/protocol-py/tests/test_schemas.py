from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).parents[3]
SCHEMA_DIR = ROOT / "packages" / "schemas"
VECTOR_DIR = ROOT / "test-vectors"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def entry_validator() -> Draft202012Validator:
    return Draft202012Validator(
        load_json(SCHEMA_DIR / "entry.schema.json"),
        format_checker=FormatChecker(),
    )


@pytest.mark.parametrize("schema_path", sorted(SCHEMA_DIR.glob("*.schema.json")))
def test_schema_is_valid_draft_2020_12(schema_path: Path) -> None:
    Draft202012Validator.check_schema(load_json(schema_path))


def test_entry_vector_matches_schema() -> None:
    vector = load_json(VECTOR_DIR / "protocol-v0.1.json")
    entry_validator().validate(vector["entry"])


def test_invalid_hash_vector_is_rejected() -> None:
    vector = load_json(VECTOR_DIR / "protocol-v0.1-invalid.json")
    with pytest.raises(ValidationError):
        entry_validator().validate(vector["invalid_hash_format"])
