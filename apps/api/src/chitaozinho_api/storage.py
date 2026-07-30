from __future__ import annotations

import os
import tempfile
from hmac import compare_digest
from pathlib import Path
from re import fullmatch


def validate_storage_identifier(value: str, label: str) -> None:
    if fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is None or value in {".", ".."}:
        raise ValueError(f"invalid {label}")


class LocalDurableStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put_part(
        self,
        session_id: str,
        artifact_id: str,
        part_number: int,
        data: bytes,
    ) -> str:
        validate_storage_identifier(session_id, "session id")
        validate_storage_identifier(artifact_id, "artifact id")
        if part_number < 0:
            raise ValueError("invalid part number")
        relative = Path(session_id) / artifact_id / f"{part_number:08d}.part"
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=".upload-",
        )
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            try:
                os.link(temporary_name, target)
            except FileExistsError:
                if not compare_digest(target.read_bytes(), data):
                    raise
            finally:
                Path(temporary_name).unlink(missing_ok=True)
            directory_descriptor = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except BaseException:
            Path(temporary_name).unlink(missing_ok=True)
            raise
        return relative.as_posix()

    def read(self, storage_key: str) -> bytes:
        return (self.root / storage_key).read_bytes()
