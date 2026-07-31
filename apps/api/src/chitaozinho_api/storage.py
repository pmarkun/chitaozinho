from __future__ import annotations

import base64
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path
from re import fullmatch

import boto3
from botocore.exceptions import ClientError

from .config import Settings


def validate_storage_identifier(value: str, label: str) -> None:
    if fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is None or value in {".", ".."}:
        raise ValueError(f"invalid {label}")


@dataclass(frozen=True)
class FinalStorageResult:
    key: str
    status: str
    version_id: str | None
    retain_until: datetime | None


class LocalDurableStorage:
    def __init__(
        self,
        root: Path,
        max_read_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self.root = root
        self.max_read_bytes = max_read_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    def check_ready(self) -> None:
        if not self.root.is_dir() or not os.access(self.root, os.R_OK | os.W_OK):
            raise RuntimeError("local storage is unavailable")

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
        with self.resolve(storage_key).open("rb") as source:
            data = source.read(self.max_read_bytes + 1)
        if len(data) > self.max_read_bytes:
            raise ValueError("stored part exceeds configured read limit")
        return data

    def resolve(self, storage_key: str) -> Path:
        relative = Path(storage_key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("invalid storage key")
        root = self.root.resolve()
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise ValueError("storage key escapes storage root") from error
        return candidate

    def package_path(self, session_id: str) -> Path:
        validate_storage_identifier(session_id, "session id")
        return self.root / "packages" / f"{session_id}.zip"

    def protect_final(
        self,
        session_id: str,
        name: str,
        source: Path,
        digest: str,
        retain_until: datetime,
    ) -> FinalStorageResult:
        validate_storage_identifier(session_id, "session id")
        validate_final_name(name)
        if sha256_identifier(source) != digest:
            raise ValueError("final object digest does not match source")
        return FinalStorageResult(
            key=str(source),
            status="stored",
            version_id=None,
            retain_until=None,
        )


class S3DurableStorage:
    def __init__(self, settings: Settings) -> None:
        if settings.s3_access_key_id is None or settings.s3_secret_access_key is None:
            raise ValueError("S3 credentials are required")
        self.root = settings.storage_path
        self.bucket = settings.s3_bucket
        self.kms_key_id = settings.s3_kms_key_id
        self.max_read_bytes = settings.max_part_size
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def check_ready(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)

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
        encryption: dict[str, str] = {}
        if self.kms_key_id is not None:
            encryption = {
                "ServerSideEncryption": "aws:kms",
                "SSEKMSKeyId": self.kms_key_id,
            }
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentLength=len(data),
            **encryption,
        )
        return key

    def read(self, storage_key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=storage_key)
        length = response.get("ContentLength")
        body = response["Body"]
        try:
            if not isinstance(length, int) or length < 0 or length > self.max_read_bytes:
                raise ValueError("stored part exceeds configured read limit")
            data = body.read(self.max_read_bytes + 1)
        finally:
            body.close()
        if len(data) != length or len(data) > self.max_read_bytes:
            raise ValueError("stored part length does not match storage metadata")
        return data

    def package_path(self, session_id: str) -> Path:
        validate_storage_identifier(session_id, "session id")
        return self.root / "packages" / f"{session_id}.zip"

    def protect_final(
        self,
        session_id: str,
        name: str,
        source: Path,
        digest: str,
        retain_until: datetime,
    ) -> FinalStorageResult:
        validate_storage_identifier(session_id, "session id")
        validate_final_name(name)
        digest_hex = digest.removeprefix("sha256:")
        if (
            len(digest_hex) != 64
            or fullmatch(r"[0-9a-f]{64}", digest_hex) is None
            or sha256_identifier(source) != digest
        ):
            raise ValueError("final object digest does not match source")
        key = f"final/{session_id}/{name}/{digest_hex}"
        head = self._head_final(key)
        if head is None:
            encryption: dict[str, str] = {"ServerSideEncryption": "AES256"}
            if self.kms_key_id is not None:
                encryption = {
                    "ServerSideEncryption": "aws:kms",
                    "SSEKMSKeyId": self.kms_key_id,
                }
            try:
                with source.open("rb") as body:
                    self.client.put_object(
                        Bucket=self.bucket,
                        Key=key,
                        Body=body,
                        ContentLength=source.stat().st_size,
                        ChecksumSHA256=base64.b64encode(bytes.fromhex(digest_hex)).decode("ascii"),
                        Metadata={"sha256": digest},
                        ObjectLockMode="COMPLIANCE",
                        ObjectLockRetainUntilDate=retain_until,
                        IfNoneMatch="*",
                        **encryption,
                    )
            except ClientError as error:
                code = str(error.response.get("Error", {}).get("Code", ""))
                if code not in {"PreconditionFailed", "412"}:
                    raise
            head = self._head_final(key)
        if head is None:
            raise RuntimeError("final object is missing after upload")
        stored_until = head.get("ObjectLockRetainUntilDate")
        if (
            head.get("Metadata", {}).get("sha256") != digest
            or head.get("ContentLength") != source.stat().st_size
            or head.get("ObjectLockMode") != "COMPLIANCE"
            or not isinstance(stored_until, datetime)
            or stored_until < retain_until
            or head.get("ServerSideEncryption") not in {"AES256", "aws:kms"}
            or (
                self.kms_key_id is not None
                and (
                    head.get("ServerSideEncryption") != "aws:kms"
                    or head.get("SSEKMSKeyId") != self.kms_key_id
                )
            )
            or not head.get("VersionId")
        ):
            raise RuntimeError("final object retention could not be verified")
        return FinalStorageResult(
            key=key,
            status="locked",
            version_id=str(head["VersionId"]),
            retain_until=stored_until,
        )

    def _head_final(self, key: str) -> dict | None:
        try:
            return self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise


DurableStorage = LocalDurableStorage | S3DurableStorage


def create_storage(settings: Settings) -> DurableStorage:
    if settings.storage_backend == "local":
        return LocalDurableStorage(
            settings.storage_path,
            max_read_bytes=settings.max_part_size,
        )
    if settings.storage_backend == "s3":
        return S3DurableStorage(settings)
    raise ValueError(f"unsupported storage backend: {settings.storage_backend}")


def validate_final_name(value: str) -> None:
    if fullmatch(r"[a-z0-9][a-z0-9.-]{0,127}", value) is None:
        raise ValueError("invalid final object name")


def sha256_identifier(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
