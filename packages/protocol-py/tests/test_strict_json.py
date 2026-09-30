import json
from pathlib import Path

import pytest
from chitaozinho_protocol import parse_strict_json

VECTORS = json.loads((Path(__file__).parents[3] / "test-vectors/strict-json.json").read_text())


@pytest.mark.parametrize("vector", VECTORS, ids=lambda vector: vector["name"])
def test_strict_json(vector: dict) -> None:
    if vector["valid"]:
        assert parse_strict_json(vector["json"]) == json.loads(vector["json"])
    else:
        with pytest.raises(ValueError):
            parse_strict_json(vector["json"])


def test_depth_limit() -> None:
    with pytest.raises(ValueError):
        parse_strict_json("[" * 65 + "0" + "]" * 65)
