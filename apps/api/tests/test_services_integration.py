from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from chitaozinho_api.config import Settings
from chitaozinho_api.database import create_database_engine
from chitaozinho_api.models import Base, CaptureSession
from chitaozinho_api.storage import S3DurableStorage
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    os.getenv("CHITAOZINHO_RUN_SERVICE_INTEGRATION") != "1",
    reason="local PostgreSQL and Garage integration is opt-in",
)


def test_postgres_and_garage_persist_without_overwrite() -> None:
    settings = Settings()
    assert settings.database_url.startswith("postgresql")
    assert settings.storage_backend == "s3"

    engine = create_database_engine(settings)
    Base.metadata.create_all(engine)
    session_id = uuid.uuid4().hex
    now = datetime.now(UTC)
    with Session(engine) as database:
        database.add(
            CaptureSession(
                id=session_id,
                server_challenge="integration-test",
                status="created",
                next_sequence=0,
                created_at=now,
                updated_at=now,
            )
        )
        database.commit()
        assert database.scalar(
            select(CaptureSession).where(CaptureSession.id == session_id)
        )

    storage = S3DurableStorage(settings)
    original = b"garage integration bytes"
    key = storage.put_part(session_id, "integration", 0, original)
    assert storage.read(key) == original
    assert storage.put_part(session_id, "integration", 0, original) == key
    with pytest.raises(FileExistsError):
        storage.put_part(session_id, "integration", 0, b"divergent")
    assert storage.read(key) == original
