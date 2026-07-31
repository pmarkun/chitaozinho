from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from chitaozinho_api.config import Settings
from chitaozinho_api.models import AuditEvent, Base, CaptureSession
from chitaozinho_api.retention import protect_final_artifact, retention_deadline
from chitaozinho_api.storage import LocalDurableStorage, S3DurableStorage
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


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


def test_local_storage_read_cannot_escape_storage_root(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"private server data")
    storage = LocalDurableStorage(root)

    with pytest.raises(ValueError, match="invalid storage key"):
        storage.read("../outside")
    with pytest.raises(ValueError, match="invalid storage key"):
        storage.read(str(outside))

    (root / "link").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes storage root"):
        storage.read("link")


def test_storage_reads_enforce_size_and_metadata_limits(tmp_path: Path) -> None:
    local = LocalDurableStorage(tmp_path / "local", max_read_bytes=4)
    oversized = local.root / "oversized.part"
    oversized.write_bytes(b"12345")
    with pytest.raises(ValueError, match="read limit"):
        local.read("oversized.part")

    s3 = S3DurableStorage.__new__(S3DurableStorage)
    s3.bucket = "evidence-test"
    s3.max_read_bytes = 4
    s3.client = FakeReadClient(b"12345", reported_length=5)
    with pytest.raises(ValueError, match="read limit"):
        s3.read("oversized.part")

    s3.client = FakeReadClient(b"1234", reported_length=3)
    with pytest.raises(ValueError, match="does not match"):
        s3.read("mismatched.part")


def test_local_final_artifact_is_stored_but_not_claimed_as_locked(
    tmp_path: Path,
) -> None:
    source = tmp_path / "package.zip"
    source.write_bytes(b"synthetic package")
    digest = f"sha256:{sha256(source.read_bytes()).hexdigest()}"
    result = LocalDurableStorage(tmp_path).protect_final(
        "session",
        "evidence-package.zip",
        source,
        digest,
        datetime.now(UTC) + timedelta(days=1),
    )
    assert result.status == "stored"
    assert result.version_id is None
    assert result.retain_until is None


def test_s3_final_artifact_requires_verified_compliance_retention(
    tmp_path: Path,
) -> None:
    source = tmp_path / "package.zip"
    content = b"synthetic package"
    source.write_bytes(content)
    digest = f"sha256:{sha256(content).hexdigest()}"
    retain_until = datetime.now(UTC) + timedelta(days=1)
    client = FakeObjectLockClient(content, digest, retain_until)
    storage = S3DurableStorage.__new__(S3DurableStorage)
    storage.root = tmp_path
    storage.bucket = "evidence-test"
    storage.kms_key_id = None
    storage.client = client

    result = storage.protect_final(
        "session",
        "evidence-package.zip",
        source,
        digest,
        retain_until,
    )
    assert result.status == "locked"
    assert result.version_id == "version-1"
    assert client.put_arguments["ObjectLockMode"] == "COMPLIANCE"
    assert client.put_arguments["IfNoneMatch"] == "*"
    assert client.put_arguments["ServerSideEncryption"] == "AES256"
    assert client.uploaded == content

    client.head_response["ObjectLockMode"] = "GOVERNANCE"
    with pytest.raises(RuntimeError, match="retention could not be verified"):
        storage.protect_final(
            "another-session",
            "evidence-package.zip",
            source,
            digest,
            retain_until,
        )


def test_s3_final_artifact_uses_and_verifies_configured_kms_key(
    tmp_path: Path,
) -> None:
    source = tmp_path / "package.zip"
    content = b"synthetic KMS package"
    source.write_bytes(content)
    digest = f"sha256:{sha256(content).hexdigest()}"
    retain_until = datetime.now(UTC) + timedelta(days=1)
    kms_key_id = "arn:aws:kms:sa-east-1:123456789012:key/test-key"
    client = FakeObjectLockClient(content, digest, retain_until)
    client.head_response.update(
        {
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": kms_key_id,
        }
    )
    storage = S3DurableStorage.__new__(S3DurableStorage)
    storage.root = tmp_path
    storage.bucket = "evidence-test"
    storage.kms_key_id = kms_key_id
    storage.client = client

    result = storage.protect_final(
        "session",
        "evidence-package.zip",
        source,
        digest,
        retain_until,
    )

    assert result.status == "locked"
    assert client.put_arguments["ServerSideEncryption"] == "aws:kms"
    assert client.put_arguments["SSEKMSKeyId"] == kms_key_id

    client.head_response["SSEKMSKeyId"] = "arn:aws:kms:sa-east-1:other:key/wrong"
    with pytest.raises(RuntimeError, match="retention could not be verified"):
        storage.protect_final(
            "another-session",
            "evidence-package.zip",
            source,
            digest,
            retain_until,
        )


def test_s3_parts_request_configured_kms_key() -> None:
    kms_key_id = "arn:aws:kms:sa-east-1:123456789012:key/test-key"
    client = FakePartClient()
    storage = S3DurableStorage.__new__(S3DurableStorage)
    storage.bucket = "evidence-test"
    storage.kms_key_id = kms_key_id
    storage.client = client

    storage.put_part("session", "recording", 0, b"synthetic part")

    assert client.put_arguments["ServerSideEncryption"] == "aws:kms"
    assert client.put_arguments["SSEKMSKeyId"] == kms_key_id


def test_retention_deadline_never_loses_time_before_delayed_storage() -> None:
    protected_at = datetime(2026, 7, 30, 12, tzinfo=UTC)
    capture = CaptureSession(
        id="delayed-session",
        server_challenge="challenge",
        status="complete",
        next_sequence=0,
        created_at=protected_at - timedelta(days=30),
        updated_at=protected_at - timedelta(days=30),
        ended_at=protected_at - timedelta(days=30),
    )

    assert retention_deadline(
        capture,
        90,
        protected_at=protected_at,
    ) == protected_at + timedelta(days=90)


def test_retention_failure_is_explicit_and_audited(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'retention.db'}")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    capture = CaptureSession(
        id="session",
        server_challenge="challenge",
        status="complete",
        next_sequence=0,
        created_at=now,
        updated_at=now,
        ended_at=now,
    )
    source = tmp_path / "package.zip"
    source.write_bytes(b"synthetic package")
    digest = f"sha256:{sha256(source.read_bytes()).hexdigest()}"
    with Session(engine) as database:
        database.add(capture)
        database.commit()
        status = protect_final_artifact(
            database,
            Settings(storage_path=tmp_path),
            FailingFinalStorage(tmp_path),
            capture,
            name="evidence-package.zip",
            path=source,
            digest=digest,
        )
        assert status == "retention_failed"
        assert capture.storage_status == "retention_failed"
        event = database.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "evidence_retention_evaluated")
        )
        assert event is not None
        assert event.details["storage_status"] == "retention_failed"
        assert event.details["error_type"] == "RuntimeError"


class FailingFinalStorage(LocalDurableStorage):
    def protect_final(self, *arguments, **keyword_arguments):
        raise RuntimeError("synthetic storage failure")


class FakeObjectLockClient:
    def __init__(
        self,
        content: bytes,
        digest: str,
        retain_until: datetime,
    ) -> None:
        self.uploaded = b""
        self.put_arguments: dict = {}
        self.head_response = {
            "Metadata": {"sha256": digest},
            "ContentLength": len(content),
            "ObjectLockMode": "COMPLIANCE",
            "ObjectLockRetainUntilDate": retain_until,
            "ServerSideEncryption": "AES256",
            "VersionId": "version-1",
        }
        self.missing = True

    def head_object(self, **_arguments) -> dict:
        if self.missing:
            self.missing = False
            raise ClientError(
                {"Error": {"Code": "404", "Message": "not found"}},
                "HeadObject",
            )
        return self.head_response

    def put_object(self, **arguments) -> dict:
        self.put_arguments = arguments
        self.uploaded = arguments["Body"].read()
        return {"VersionId": "version-1"}


class FakePartClient:
    def __init__(self) -> None:
        self.put_arguments: dict = {}

    def list_objects_v2(self, **_arguments) -> dict:
        return {"Contents": []}

    def put_object(self, **arguments) -> dict:
        self.put_arguments = arguments
        return {}


class FakeReadClient:
    def __init__(self, content: bytes, reported_length: int) -> None:
        self.content = content
        self.reported_length = reported_length

    def get_object(self, **_arguments) -> dict:
        return {
            "Body": BytesIO(self.content),
            "ContentLength": self.reported_length,
        }
