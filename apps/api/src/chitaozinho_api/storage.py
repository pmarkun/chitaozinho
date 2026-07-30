from __future__ import annotations

import os
import tempfile
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path
from re import fullmatch

import boto3

from .config import Settings


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

    def resolve(self, storage_key: str) -> Path:
        relative = Path(storage_key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("invalid storage key")
        return self.root / relative

    def package_path(self, session_id: str) -> Path:
        validate_storage_identifier(session_id, "session id")
        return self.root / "packages" / f"{session_id}.zip"


class S3DurableStorage:
    def __init__(self, settings: Settings) -> None:
        if settings.s3_access_key_id is None or settings.s3_secret_access_key is None:
            raise ValueError("S3 credentials are required")
        self.root = settings.storage_path
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

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
        digest = sha256(data).hexdigest()
        prefix = f"sessions/{session_id}/{artifact_id}/{part_number:08d}-"
        key = f"{prefix}{digest}.part"
        existing = self.client.list_objects_v2(
            Bucket=self.bucket,
            Prefix=prefix,
            MaxKeys=2,
        ).get("Contents", [])
        if existing:
            existing_keys = {item["Key"] for item in existing}
            if key not in existing_keys:
                raise FileExistsError(next(iter(existing_keys)))
            if not compare_digest(self.read(key), data):
                raise FileExistsError(key)
            return key
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentLength=len(data),
        )
        return key

    def read(self, storage_key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=storage_key)
        return response["Body"].read()

    def package_path(self, session_id: str) -> Path:
        validate_storage_identifier(session_id, "session id")
        return self.root / "packages" / f"{session_id}.zip"


DurableStorage = LocalDurableStorage | S3DurableStorage


def create_storage(settings: Settings) -> DurableStorage:
    if settings.storage_backend == "local":
        return LocalDurableStorage(settings.storage_path)
    if settings.storage_backend == "s3":
        return S3DurableStorage(settings)
    raise ValueError(f"unsupported storage backend: {settings.storage_backend}")
