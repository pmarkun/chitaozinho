from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateSessionResponse(StrictModel):
    session_id: str
    server_challenge: str
    server_time: datetime
    upload_policy: dict[str, Any]
    retention_policy: dict[str, Any]
    server_public_key_id: str
    next_sequence: int


class RegisterKeyRequest(StrictModel):
    key_id: str = Field(min_length=1, max_length=128)
    public_key: str = Field(pattern=r"^[A-Za-z0-9_-]+$")


class EntryRequest(StrictModel):
    entry: dict[str, Any]
    entry_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    signature_hex: str = Field(pattern=r"^[0-9a-f]{128}$")


class EntryResponse(StrictModel):
    session_id: str
    sequence: int
    entry_hash: str
    status: str


class PartResponse(StrictModel):
    session_id: str
    sequence: int
    artifact_id: str
    part_number: int
    part_hash: str
    persistence_state: str
    receipt_hash: str
    receipt_signature_hex: str
    receipt: dict[str, Any]


class ArtifactCompleteRequest(StrictModel):
    entry: EntryRequest
    part_count: int = Field(ge=1)
    size: int = Field(ge=0)
    artifact_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    path: str = Field(min_length=1, max_length=1024)
    media_type: str = Field(min_length=1, max_length=255)
    method: str = Field(min_length=1, max_length=128)
    provenance: str = Field(
        pattern=r"^(client_reported|server_observed|externally_attested)$"
    )


class ArtifactCompleteResponse(StrictModel):
    session_id: str
    artifact_id: str
    part_count: int
    size: int
    artifact_hash: str
    status: str


class FinalizeRequest(StrictModel):
    capture_close: dict[str, Any]
    signature_hex: str = Field(pattern=r"^[0-9a-f]{128}$")


class FinalizeResponse(StrictModel):
    session_id: str
    status: str
    manifest_hash: str
    manifest_signature_hex: str
    server_key_id: str
    manifest: dict[str, Any]


class SessionStatusResponse(StrictModel):
    session_id: str
    capture_status: str
    package_status: str
    timestamp_status: str
    blockchain_status: str
    storage_status: str
    next_sequence: int
    manifest_hash: str | None = None
