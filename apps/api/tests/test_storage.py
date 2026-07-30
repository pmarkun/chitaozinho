from pathlib import Path

import pytest
from chitaozinho_api.storage import LocalDurableStorage


def test_storage_never_overwrites_part(tmp_path: Path) -> None:
    storage = LocalDurableStorage(tmp_path)
    key = storage.put_part("session", "recording", 0, b"original")
    assert storage.read(key) == b"original"

    replayed_key = storage.put_part("session", "recording", 0, b"original")
    assert replayed_key == key

    with pytest.raises(FileExistsError):
        storage.put_part("session", "recording", 0, b"changed")
    assert storage.read(key) == b"original"


@pytest.mark.parametrize("identifier", ["..", ".", "with/slash", ""])
def test_storage_rejects_unsafe_identifiers(tmp_path: Path, identifier: str) -> None:
    storage = LocalDurableStorage(tmp_path)
    session_id = "session" if identifier else identifier
    with pytest.raises(ValueError, match="invalid"):
        storage.put_part(session_id, identifier, 0, b"x")
