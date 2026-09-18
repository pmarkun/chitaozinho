from __future__ import annotations

import os
import tempfile
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path, PurePosixPath

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .config import Settings
from .storage import validate_storage_identifier

MAX_PROOF_BYTES = 16 * 1024 * 1024


def validate_proof_key(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"invalid proof key: {value}")
    return path.as_posix()


class LocalProofStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put_once(self, key: str, data: bytes) -> None:
        key = validate_proof_key(key)
        if len(data) > MAX_PROOF_BYTES:
            raise ValueError("proof exceeds configured size limit")
        target = self.root.joinpath(*PurePosixPath(key).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=".proof-",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                if not compare_digest(self.read(key), data):
                    raise
        finally:
            temporary.unlink(missing_ok=True)

    def read(self, key: str) -> bytes:
        key = validate_proof_key(key)
        target = self.root.joinpath(*PurePosixPath(key).parts)
        data = target.read_bytes()
        if len(data) > MAX_PROOF_BYTES:
            raise ValueError("proof exceeds configured size limit")
        return data

    def delete_scope(self, kind: str, identifier: str) -> None:
        prefix = proof_scope(kind, identifier)
        target = self.root.joinpath(prefix)
        target.resolve().relative_to(self.root.resolve())
        if target.is_symlink():
            raise ValueError("proof scope must not be a symlink")
        if target.exists():
            import shutil

            shutil.rmtree(target)
        if target.exists():
            raise RuntimeError("proof scope still exists")


class S3ProofStorage:
    def __init__(self, settings: Settings) -> None:
        if settings.s3_access_key_id is None or settings.s3_secret_access_key is None:
            raise ValueError("S3 credentials are required")
        self.bucket = settings.s3_bucket
        client_arguments = dict(
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            verify=(str(settings.s3_ca_bundle) if settings.s3_ca_bundle is not None else True),
        )
        if settings.storage_provider == "railway":
            client_arguments["config"] = Config(s3={"addressing_style": "virtual"})
        self.client = boto3.client("s3", **client_arguments)

    def put_once(self, key: str, data: bytes) -> None:
        key = self._object_key(key)
        if len(data) > MAX_PROOF_BYTES:
            raise ValueError("proof exceeds configured size limit")
        digest = f"sha256:{sha256(data).hexdigest()}"
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentLength=len(data),
                Metadata={"sha256": digest},
                IfNoneMatch="*",
            )
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code", ""))
            if code not in {"PreconditionFailed", "412"}:
                raise
        head = self.client.head_object(Bucket=self.bucket, Key=key)
        if (
            head.get("ContentLength") != len(data)
            or head.get("Metadata", {}).get("sha256") != digest
        ):
            raise RuntimeError("stored proof integrity could not be verified")

    def read(self, key: str) -> bytes:
        response = self.client.get_object(
            Bucket=self.bucket,
            Key=self._object_key(key),
        )
        length = response.get("ContentLength")
        expected_digest = response.get("Metadata", {}).get("sha256")
        body = response["Body"]
        try:
            if not isinstance(length, int) or length < 0 or length > MAX_PROOF_BYTES:
                raise ValueError("proof exceeds configured size limit")
            data = body.read(MAX_PROOF_BYTES + 1)
        finally:
            body.close()
        actual_digest = f"sha256:{sha256(data).hexdigest()}"
        if (
            len(data) != length
            or len(data) > MAX_PROOF_BYTES
            or not isinstance(expected_digest, str)
            or not compare_digest(expected_digest, actual_digest)
        ):
            raise ValueError("stored proof integrity does not match metadata")
        return data

    @staticmethod
    def _object_key(key: str) -> str:
        return f"proofs/{validate_proof_key(key)}"

    def delete_scope(self, kind: str, identifier: str) -> None:
        prefix = f"proofs/{proof_scope(kind, identifier)}/"
        # Relist from the beginning after each page: safe if deletion changes pagination.
        previous_keys: list[str] | None = None
        while True:
            objects = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            keys = [item["Key"] for item in objects.get("Contents", [])]
            if not keys:
                return
            if keys == previous_keys:
                raise RuntimeError("proof deletion made no progress")
            previous_keys = keys
            if any(not key.startswith(prefix) for key in keys):
                raise RuntimeError("proof listing escaped deletion scope")
            result = self.client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": key} for key in keys]},
            )
            if result.get("Errors"):
                raise RuntimeError("partial proof deletion; retry required")


def proof_scope(kind: str, identifier: str) -> str:
    if kind not in {"sessions", "merkle"}:
        raise ValueError("unsupported proof scope")
    validate_storage_identifier(identifier, "proof scope")
    return f"{kind}/{identifier}"


ProofStorage = LocalProofStorage | S3ProofStorage


def create_proof_storage(settings: Settings) -> ProofStorage:
    if settings.storage_backend == "s3":
        return S3ProofStorage(settings)
    return LocalProofStorage(settings.proofs_path)
