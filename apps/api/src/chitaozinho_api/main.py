from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime
from functools import partial
from hashlib import sha256
from pathlib import PurePosixPath

from chitaozinho_protocol import (
    DOMAINS,
    base64url_decode,
    base64url_encode,
    canonical_bytes,
    sha256_identifier,
    verify_canonical,
)
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .database import create_database_engine, session_dependency
from .models import (
    Artifact,
    ArtifactPart,
    Attestation,
    Base,
    CaptureSession,
    ChainEntry,
    Incident,
    MerkleBatch,
    OtsComplement,
    Receipt,
)
from .packaging import ensure_package
from .proof_service import create_merkle_batch, timestamp_capture, upgrade_merkle_batch
from .schemas import (
    ArtifactCompleteRequest,
    ArtifactCompleteResponse,
    AttestationResponse,
    CreateSessionResponse,
    EntryRequest,
    EntryResponse,
    FinalizeRequest,
    FinalizeResponse,
    MerkleBatchRequest,
    MerkleBatchResponse,
    OtsComplementResponse,
    PartResponse,
    RegisterKeyRequest,
    SessionStatusResponse,
)
from .security import ServerSigner
from .storage import DurableStorage, create_storage


def create_app(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
    storage: DurableStorage | None = None,
    create_tables: bool = False,
) -> FastAPI:
    settings = settings or Settings()
    engine = engine or create_database_engine(settings)
    storage = storage or create_storage(settings)
    signer = ServerSigner.from_settings(settings)
    factory = sessionmaker(engine, expire_on_commit=False)
    if create_tables:
        Base.metadata.create_all(engine)

    app = FastAPI(title="Chitãozinho API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=[
            "Content-Type",
            "Idempotency-Key",
            "X-Entry-Json",
            "X-Entry-Hash",
            "X-Entry-Signature",
        ],
        expose_headers=["X-Package-SHA256", "Content-Disposition"],
        max_age=600,
    )
    app.state.session_factory = factory
    get_session = partial(session_dependency, factory)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/v1/sessions",
        response_model=CreateSessionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_capture_session(
        database: Session = Depends(get_session),
    ) -> CreateSessionResponse:
        active_signer = require_signer(signer)
        now = datetime.now(UTC)
        capture_session = CaptureSession(
            id=uuid.uuid4().hex,
            server_challenge=base64url_encode(secrets.token_bytes(32)),
            status="created",
            next_sequence=0,
            created_at=now,
            updated_at=now,
        )
        database.add(capture_session)
        database.commit()
        return CreateSessionResponse(
            session_id=capture_session.id,
            server_challenge=capture_session.server_challenge,
            server_time=now,
            upload_policy={"max_part_size": settings.max_part_size},
            retention_policy={"mode": "development", "days": None},
            server_public_key_id=active_signer.key_id,
            next_sequence=0,
        )

    @app.post(
        "/v1/sessions/{session_id}/keys",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def register_session_key(
        session_id: str,
        body: RegisterKeyRequest,
        database: Session = Depends(get_session),
    ) -> Response:
        capture_session = require_capture_session(database, session_id)
        if capture_session.status != "created":
            raise HTTPException(status.HTTP_409_CONFLICT, "session key already registered")
        try:
            public_key = base64url_decode(body.public_key)
        except ValueError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
        if len(public_key) != 32:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Ed25519 public key must contain 32 bytes",
            )
        capture_session.client_key_id = body.key_id
        capture_session.client_public_key = public_key
        capture_session.status = "key_registered"
        capture_session.updated_at = datetime.now(UTC)
        database.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post(
        "/v1/sessions/{session_id}/events",
        response_model=EntryResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_event(
        session_id: str,
        body: EntryRequest,
        response: Response,
        idempotency_key: str = Header(min_length=1, max_length=128),
        database: Session = Depends(get_session),
    ) -> EntryResponse:
        capture_session = require_ready_session(database, session_id)
        existing = database.scalar(
            select(ChainEntry).where(
                ChainEntry.session_id == session_id,
                ChainEntry.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if (
                existing.entry_hash != body.entry_hash
                or existing.payload != body.entry
                or existing.signature_hex != body.signature_hex
            ):
                record_incident(
                    database,
                    session_id,
                    "event_idempotency_conflict",
                    {"idempotency_key": idempotency_key},
                )
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "idempotency key reused with divergent content",
                )
            response.status_code = status.HTTP_200_OK
            return entry_response(existing, "already_recorded")

        validate_entry(database, capture_session, body)
        entry = ChainEntry(
            session_id=session_id,
            sequence=capture_session.next_sequence,
            entry_type=str(body.entry["entry_type"]),
            entry_hash=body.entry_hash,
            payload=body.entry,
            signature_hex=body.signature_hex,
            idempotency_key=idempotency_key,
            created_at=datetime.now(UTC),
        )
        database.add(entry)
        capture_session.next_sequence += 1
        capture_session.status = "capturing"
        capture_session.updated_at = datetime.now(UTC)
        try:
            database.commit()
        except IntegrityError as error:
            database.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "entry sequence conflict") from error
        return entry_response(entry, "recorded")

    @app.put(
        "/v1/sessions/{session_id}/artifacts/{artifact_id}/parts/{part_number}",
        response_model=PartResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_part(
        session_id: str,
        artifact_id: str,
        part_number: int,
        request: Request,
        response: Response,
        idempotency_key: str = Header(min_length=1, max_length=128),
        content_length: int = Header(ge=0),
        x_entry_json: str = Header(),
        x_entry_hash: str = Header(pattern=r"^sha256:[0-9a-f]{64}$"),
        x_entry_signature: str = Header(pattern=r"^[0-9a-f]{128}$"),
        database: Session = Depends(get_session),
    ) -> PartResponse:
        validate_identifier(artifact_id, "artifact id")
        if part_number < 0 or part_number >= settings.max_artifact_parts:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid part number")
        active_signer = require_signer(signer)
        capture_session = require_ready_session(database, session_id)
        chunks: list[bytes] = []
        total_size = 0
        async for chunk in request.stream():
            total_size += len(chunk)
            if total_size > settings.max_part_size:
                raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "part exceeds size limit")
            chunks.append(chunk)
        data = b"".join(chunks)
        if total_size != content_length:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "declared part size does not match received bytes",
            )
        expected_part_hash = sha256_identifier(data)
        existing = database.scalar(
            select(ArtifactPart).where(
                ArtifactPart.session_id == session_id,
                ArtifactPart.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            original_entry = database.scalar(
                select(ChainEntry).where(
                    ChainEntry.session_id == session_id,
                    ChainEntry.idempotency_key == f"entry:{idempotency_key}",
                )
            )
            receipt = (
                database.scalar(
                    select(Receipt).where(
                        Receipt.session_id == session_id,
                        Receipt.sequence == original_entry.sequence,
                    )
                )
                if original_entry is not None
                else None
            )
            try:
                replay_payload = json.loads(base64url_decode(x_entry_json))
            except (ValueError, json.JSONDecodeError) as error:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "invalid entry JSON",
                ) from error
            if (
                existing.artifact_id != artifact_id
                or existing.part_number != part_number
                or existing.part_hash != expected_part_hash
                or original_entry is None
                or replay_payload != original_entry.payload
                or x_entry_hash != original_entry.entry_hash
                or x_entry_signature != original_entry.signature_hex
                or receipt is None
            ):
                record_incident(
                    database,
                    session_id,
                    "part_idempotency_conflict",
                    {
                        "idempotency_key": idempotency_key,
                        "artifact_id": artifact_id,
                        "part_number": part_number,
                    },
                )
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "idempotency key reused with divergent content",
                )
            response.status_code = status.HTTP_200_OK
            return part_response(existing, receipt)

        try:
            entry_payload = json.loads(base64url_decode(x_entry_json))
        except (ValueError, json.JSONDecodeError) as error:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "invalid entry JSON",
            ) from error
        body = EntryRequest(
            entry=entry_payload,
            entry_hash=x_entry_hash,
            signature_hex=x_entry_signature,
        )
        validate_entry(database, capture_session, body)
        if (
            entry_payload.get("artifact_id") != artifact_id
            or entry_payload.get("part_number") != part_number
            or entry_payload.get("part_hash") != expected_part_hash
        ):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "entry does not describe uploaded part",
            )

        try:
            storage_key = storage.put_part(session_id, artifact_id, part_number, data)
        except FileExistsError as error:
            record_incident(
                database,
                session_id,
                "part_storage_conflict",
                {"artifact_id": artifact_id, "part_number": part_number},
            )
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "part number already contains different bytes",
            ) from error
        entry = ChainEntry(
            session_id=session_id,
            sequence=capture_session.next_sequence,
            entry_type="artifact_part",
            entry_hash=x_entry_hash,
            payload=entry_payload,
            signature_hex=x_entry_signature,
            idempotency_key=f"entry:{idempotency_key}",
            created_at=datetime.now(UTC),
        )
        part = ArtifactPart(
            session_id=session_id,
            artifact_id=artifact_id,
            part_number=part_number,
            part_hash=expected_part_hash,
            size=len(data),
            storage_key=storage_key,
            persistence_state="durable_staging",
            idempotency_key=idempotency_key,
        )
        receipt_payload = {
            "protocol_version": "0.1.0",
            "session_id": session_id,
            "sequence": capture_session.next_sequence,
            "entry_hash": x_entry_hash,
            "artifact_id": artifact_id,
            "part_number": part_number,
            "part_hash": expected_part_hash,
            "previous_receipt_hash": capture_session.last_receipt_hash,
            "server_time": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "persistence_state": "durable_staging",
        }
        receipt_hash = sha256_identifier(canonical_bytes(receipt_payload))
        receipt = Receipt(
            session_id=session_id,
            sequence=capture_session.next_sequence,
            receipt_hash=receipt_hash,
            payload=receipt_payload,
            signature_hex=active_signer.sign(DOMAINS["receipt"], receipt_payload),
        )
        database.add_all([entry, part, receipt])
        capture_session.next_sequence += 1
        capture_session.last_receipt_hash = receipt_hash
        capture_session.status = "uploading"
        capture_session.updated_at = datetime.now(UTC)
        try:
            database.commit()
        except IntegrityError as error:
            database.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "part or sequence conflict") from error
        return part_response(part, receipt)

    @app.post(
        "/v1/sessions/{session_id}/artifacts/{artifact_id}/complete",
        response_model=ArtifactCompleteResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def complete_artifact(
        session_id: str,
        artifact_id: str,
        body: ArtifactCompleteRequest,
        response: Response,
        database: Session = Depends(get_session),
    ) -> ArtifactCompleteResponse:
        validate_identifier(artifact_id, "artifact id")
        capture_session = require_ready_session(database, session_id)
        existing = database.scalar(
            select(Artifact).where(
                Artifact.session_id == session_id,
                Artifact.artifact_id == artifact_id,
            )
        )
        if existing is not None:
            if not artifact_matches_request(existing, body):
                record_incident(
                    database,
                    session_id,
                    "artifact_completion_conflict",
                    {"artifact_id": artifact_id},
                )
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "artifact completion conflicts with immutable result",
                )
            response.status_code = status.HTTP_200_OK
            return artifact_response(existing)

        validate_entry(database, capture_session, body.entry)
        entry_payload = body.entry.entry
        if (
            entry_payload.get("entry_type") != "artifact_completed"
            or entry_payload.get("artifact_id") != artifact_id
            or entry_payload.get("artifact_hash") != body.artifact_hash
        ):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "entry does not describe completed artifact",
            )
        parts = list(
            database.scalars(
                select(ArtifactPart)
                .where(
                    ArtifactPart.session_id == session_id,
                    ArtifactPart.artifact_id == artifact_id,
                )
                .order_by(ArtifactPart.part_number)
            )
        )
        if len(parts) != body.part_count or [part.part_number for part in parts] != list(
            range(body.part_count)
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "artifact parts are missing or non-contiguous",
            )
        digest = sha256()
        actual_size = 0
        for part in parts:
            part_bytes = storage.read(part.storage_key)
            digest.update(part_bytes)
            actual_size += len(part_bytes)
        actual_hash = f"sha256:{digest.hexdigest()}"
        if actual_size != body.size or actual_hash != body.artifact_hash:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "reconstructed artifact size or hash mismatch",
            )
        artifact = Artifact(
            session_id=session_id,
            artifact_id=artifact_id,
            path=validate_artifact_path(body.path),
            size=body.size,
            part_count=body.part_count,
            artifact_hash=body.artifact_hash,
            media_type=body.media_type,
            status="captured",
            method=body.method,
            provenance=body.provenance,
            completed_entry_hash=body.entry.entry_hash,
        )
        entry = ChainEntry(
            session_id=session_id,
            sequence=capture_session.next_sequence,
            entry_type="artifact_completed",
            entry_hash=body.entry.entry_hash,
            payload=entry_payload,
            signature_hex=body.entry.signature_hex,
            idempotency_key=f"artifact-complete:{artifact_id}",
            created_at=datetime.now(UTC),
        )
        database.add_all([artifact, entry])
        capture_session.next_sequence += 1
        capture_session.status = "capturing"
        capture_session.updated_at = datetime.now(UTC)
        try:
            database.commit()
        except IntegrityError as error:
            database.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "artifact completion conflict",
            ) from error
        return artifact_response(artifact)

    @app.post(
        "/v1/sessions/{session_id}/finalize",
        response_model=FinalizeResponse,
    )
    def finalize_session(
        session_id: str,
        body: FinalizeRequest,
        database: Session = Depends(get_session),
    ) -> FinalizeResponse:
        active_signer = require_signer(signer)
        capture_session = require_capture_session(database, session_id)
        if capture_session.manifest is not None:
            if (
                capture_session.capture_close != body.capture_close
                or capture_session.capture_close_signature_hex != body.signature_hex
            ):
                record_incident(
                    database,
                    session_id,
                    "finalization_conflict",
                    {"manifest_hash": capture_session.manifest_hash},
                )
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "session already finalized with different declaration",
                )
            return finalize_response(capture_session)
        capture_session = require_ready_session(database, session_id)
        entries = list(
            database.scalars(
                select(ChainEntry)
                .where(ChainEntry.session_id == session_id)
                .order_by(ChainEntry.sequence)
            )
        )
        artifacts = list(
            database.scalars(
                select(Artifact)
                .where(Artifact.session_id == session_id)
                .order_by(Artifact.artifact_id)
            )
        )
        validate_capture_close(capture_session, entries, artifacts, body)
        now = datetime.now(UTC)
        capture_status = (
            "incomplete"
            if body.capture_close["known_gaps"]
            or any(artifact.status != "captured" for artifact in artifacts)
            else "complete"
        )
        manifest = build_manifest(
            settings,
            capture_session,
            entries,
            artifacts,
            body.capture_close,
            capture_status,
            now,
        )
        manifest_hash = sha256_identifier(canonical_bytes(manifest))
        capture_session.capture_close = body.capture_close
        capture_session.capture_close_signature_hex = body.signature_hex
        capture_session.manifest = manifest
        capture_session.manifest_hash = manifest_hash
        capture_session.manifest_signature_hex = active_signer.sign(
            DOMAINS["manifest"], manifest
        )
        capture_session.server_key_id = active_signer.key_id
        capture_session.status = capture_status
        capture_session.ended_at = now
        capture_session.updated_at = now
        database.commit()
        return finalize_response(capture_session)

    @app.get("/v1/sessions/{session_id}/package")
    def download_package(
        session_id: str,
        database: Session = Depends(get_session),
    ) -> FileResponse:
        active_signer = require_signer(signer)
        capture_session = require_capture_session(database, session_id)
        if capture_session.manifest is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "session must be finalized before packaging",
            )
        try:
            package_path, package_hash = ensure_package(
                database,
                storage,
                active_signer,
                capture_session,
            )
        except (OSError, ValueError) as error:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "package generation failed",
            ) from error
        return FileResponse(
            package_path,
            media_type="application/zip",
            filename=f"chitaozinho-{session_id}.zip",
            headers={"X-Package-SHA256": package_hash},
        )

    @app.post(
        "/v1/sessions/{session_id}/timestamp",
        response_model=AttestationResponse,
    )
    def timestamp_session(
        session_id: str,
        database: Session = Depends(get_session),
    ) -> AttestationResponse:
        active_signer = require_signer(signer)
        capture_session = require_capture_session(database, session_id)
        if capture_session.manifest is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "session must be finalized before timestamping",
            )
        attestation = timestamp_capture(
            database,
            settings,
            active_signer,
            capture_session,
        )
        return attestation_response(attestation)

    @app.post(
        "/v1/merkle-batches",
        response_model=MerkleBatchResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_batch(
        body: MerkleBatchRequest,
        database: Session = Depends(get_session),
    ) -> MerkleBatchResponse:
        active_signer = require_signer(signer)
        try:
            batch = create_merkle_batch(
                database,
                settings,
                active_signer,
                body.session_ids,
                submit_ots=body.submit_ots,
            )
        except ValueError as error:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                str(error),
            ) from error
        return MerkleBatchResponse(
            batch_id=batch.id,
            root_hash=batch.root_hash,
            status=batch.status,
            session_count=len(body.session_ids),
        )

    @app.post(
        "/v1/merkle-batches/{batch_id}/upgrade",
        response_model=OtsComplementResponse,
    )
    def upgrade_batch(
        batch_id: str,
        database: Session = Depends(get_session),
    ) -> OtsComplementResponse:
        active_signer = require_signer(signer)
        batch = database.get(MerkleBatch, batch_id)
        if batch is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Merkle batch not found")
        try:
            complement = upgrade_merkle_batch(
                database,
                settings,
                active_signer,
                batch,
            )
        except ValueError as error:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                str(error),
            ) from error
        return ots_complement_response(complement)

    @app.get(
        "/v1/sessions/{session_id}/attestations",
        response_model=list[AttestationResponse],
    )
    def get_attestations(
        session_id: str,
        database: Session = Depends(get_session),
    ) -> list[AttestationResponse]:
        require_capture_session(database, session_id)
        attestations = database.scalars(
            select(Attestation)
            .where(Attestation.session_id == session_id)
            .order_by(Attestation.sequence)
        )
        return [attestation_response(value) for value in attestations]

    @app.get(
        "/v1/sessions/{session_id}",
        response_model=SessionStatusResponse,
    )
    def get_capture_session(
        session_id: str,
        database: Session = Depends(get_session),
    ) -> SessionStatusResponse:
        capture_session = require_capture_session(database, session_id)
        package_available = storage.package_path(session_id).exists()
        return SessionStatusResponse(
            session_id=session_id,
            capture_status=capture_session.status,
            package_status="available" if package_available else capture_session.package_status,
            timestamp_status=capture_session.timestamp_status,
            blockchain_status=capture_session.blockchain_status,
            storage_status=capture_session.storage_status,
            next_sequence=capture_session.next_sequence,
            manifest_hash=capture_session.manifest_hash,
        )

    return app


def require_signer(signer: ServerSigner | None) -> ServerSigner:
    if signer is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "server signing key is not configured",
        )
    return signer


def record_incident(
    database: Session,
    session_id: str,
    kind: str,
    details: dict,
) -> None:
    database.add(
        Incident(
            session_id=session_id,
            kind=kind,
            details=details,
            created_at=datetime.now(UTC),
        )
    )
    database.commit()


def require_capture_session(database: Session, session_id: str) -> CaptureSession:
    capture_session = database.get(CaptureSession, session_id)
    if capture_session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    return capture_session


def require_ready_session(database: Session, session_id: str) -> CaptureSession:
    capture_session = require_capture_session(database, session_id)
    if capture_session.client_public_key is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "session key is not registered")
    if capture_session.status in {"complete", "incomplete", "invalid_chain"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "session is already closed")
    return capture_session


ENTRY_TYPES = {
    "capture_started",
    "artifact_part",
    "artifact_completed",
    "navigation",
    "scroll",
    "marker",
    "clock_restarted",
    "capture_finished",
}
ENTRY_FIELDS = {
    "protocol_version",
    "entry_type",
    "session_id",
    "sequence",
    "artifact_id",
    "part_number",
    "part_hash",
    "artifact_hash",
    "previous_entry_hash",
    "client_clock_id",
    "client_monotonic_time",
    "client_wall_time",
    "server_challenge",
    "event_data",
}


def validate_entry(
    database: Session,
    capture_session: CaptureSession,
    body: EntryRequest,
) -> None:
    entry = body.entry
    required_fields = {
        "protocol_version",
        "entry_type",
        "session_id",
        "sequence",
        "previous_entry_hash",
        "client_clock_id",
        "client_monotonic_time",
        "client_wall_time",
        "server_challenge",
    }
    if missing := required_fields.difference(entry):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"entry is missing required fields: {', '.join(sorted(missing))}",
        )
    if unknown := set(entry).difference(ENTRY_FIELDS):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"entry contains unknown fields: {', '.join(sorted(unknown))}",
        )
    if entry["protocol_version"] != "0.1.0":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unsupported protocol version")
    if entry["entry_type"] not in ENTRY_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "entry type is invalid")
    if not isinstance(entry["sequence"], int) or isinstance(entry["sequence"], bool):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "entry sequence is invalid")
    if (
        not isinstance(entry["client_monotonic_time"], int)
        or isinstance(entry["client_monotonic_time"], bool)
        or entry["client_monotonic_time"] < 0
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "monotonic time is invalid")
    if entry.get("session_id") != capture_session.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "entry session id mismatch")
    if entry.get("sequence") != capture_session.next_sequence:
        raise HTTPException(status.HTTP_409_CONFLICT, "entry sequence is not the next sequence")
    if capture_session.next_sequence == 0 and entry["entry_type"] != "capture_started":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "the genesis entry must be capture_started",
        )
    if entry.get("server_challenge") != capture_session.server_challenge:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "server challenge mismatch")
    try:
        wall_time = datetime.fromisoformat(str(entry["client_wall_time"]).replace("Z", "+00:00"))
    except ValueError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "client wall time is not RFC 3339",
        ) from error
    if wall_time.tzinfo is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "client wall time must have an explicit offset",
        )
    if entry["entry_type"] == "artifact_part" and not {
        "artifact_id",
        "part_number",
        "part_hash",
    }.issubset(entry):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "artifact part entry is incomplete",
        )
    if entry["entry_type"] == "artifact_completed" and not {
        "artifact_id",
        "artifact_hash",
    }.issubset(entry):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "artifact completion entry is incomplete",
        )
    expected_previous = None
    if capture_session.next_sequence > 0:
        previous_entry = database.scalar(
            select(ChainEntry).where(
                ChainEntry.session_id == capture_session.id,
                ChainEntry.sequence == capture_session.next_sequence - 1,
            )
        )
        if previous_entry is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "previous entry is missing")
        expected_previous = previous_entry.entry_hash
        if (
            previous_entry.payload["client_clock_id"] != entry["client_clock_id"]
            and entry["entry_type"] != "clock_restarted"
        ):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "a new client clock must begin with clock_restarted",
            )
        previous_same_clock = database.scalar(
            select(ChainEntry)
            .where(
                ChainEntry.session_id == capture_session.id,
                ChainEntry.payload["client_clock_id"].as_string()
                == entry["client_clock_id"],
            )
            .order_by(ChainEntry.sequence.desc())
        )
        if (
            previous_same_clock is not None
            and entry["client_monotonic_time"]
            < previous_same_clock.payload["client_monotonic_time"]
        ):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "monotonic time moved backwards within the same clock",
            )
    if entry.get("previous_entry_hash") != expected_previous:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "previous entry hash mismatch")
    actual_hash = sha256_identifier(canonical_bytes(entry))
    if body.entry_hash != actual_hash:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "entry hash mismatch")
    signature = bytes.fromhex(body.signature_hex)
    if not verify_canonical(
        DOMAINS["entry"],
        entry,
        signature,
        capture_session.client_public_key or b"",
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "entry signature invalid")


def validate_identifier(value: str, label: str) -> None:
    if (
        not value
        or len(value) > 128
        or value in {".", ".."}
        or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
               for character in value)
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"invalid {label}")


def validate_artifact_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or not path.parts
        or "\\" in value
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "artifact path must be a safe relative POSIX path",
        )
    return value


def artifact_matches_request(artifact: Artifact, body: ArtifactCompleteRequest) -> bool:
    return (
        artifact.part_count == body.part_count
        and artifact.size == body.size
        and artifact.artifact_hash == body.artifact_hash
        and artifact.path == body.path
        and artifact.media_type == body.media_type
        and artifact.method == body.method
        and artifact.provenance == body.provenance
        and artifact.completed_entry_hash == body.entry.entry_hash
    )


def artifact_response(artifact: Artifact) -> ArtifactCompleteResponse:
    return ArtifactCompleteResponse(
        session_id=artifact.session_id,
        artifact_id=artifact.artifact_id,
        part_count=artifact.part_count,
        size=artifact.size,
        artifact_hash=artifact.artifact_hash,
        status=artifact.status,
    )


def validate_capture_close(
    capture_session: CaptureSession,
    entries: list[ChainEntry],
    artifacts: list[Artifact],
    body: FinalizeRequest,
) -> None:
    close = body.capture_close
    required = {
        "protocol_version",
        "session_id",
        "session_root",
        "last_entry_hash",
        "entry_count",
        "artifacts",
        "known_gaps",
        "client_key_id",
        "client_public_key",
    }
    if set(close) != required:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "capture close fields do not match protocol schema",
        )
    if not entries or entries[-1].entry_type != "capture_finished":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "capture_finished must be the final chain entry",
        )
    if [entry.sequence for entry in entries] != list(range(len(entries))):
        raise HTTPException(status.HTTP_409_CONFLICT, "entry chain contains sequence gaps")
    last_hash = entries[-1].entry_hash
    if (
        close["protocol_version"] != "0.1.0"
        or close["session_id"] != capture_session.id
        or close["session_root"] != last_hash
        or close["last_entry_hash"] != last_hash
        or close["entry_count"] != len(entries)
        or close["client_key_id"] != capture_session.client_key_id
        or close["client_public_key"]
        != base64url_encode(capture_session.client_public_key or b"")
        or not isinstance(close["known_gaps"], list)
        or any(not isinstance(gap, str) for gap in close["known_gaps"])
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "capture close does not match persisted session",
        )
    expected_artifacts = [
        {
            "artifact_id": artifact.artifact_id,
            "path": artifact.path,
            "size": artifact.size,
            "status": artifact.status,
            "artifact_hash": artifact.artifact_hash,
        }
        for artifact in artifacts
    ]
    if close["artifacts"] != expected_artifacts:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "capture close artifacts do not match completed artifacts",
        )
    if not verify_canonical(
        DOMAINS["capture_close"],
        close,
        bytes.fromhex(body.signature_hex),
        capture_session.client_public_key or b"",
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "capture close signature invalid",
        )


def build_manifest(
    settings: Settings,
    capture_session: CaptureSession,
    entries: list[ChainEntry],
    artifacts: list[Artifact],
    capture_close: dict,
    capture_status: str,
    ended_at: datetime,
) -> dict:
    return {
        "schema_version": "0.1.0",
        "session_id": capture_session.id,
        "status": capture_status,
        "capture": {
            "started_at_client": entries[0].payload["client_wall_time"],
            "ended_at_client": entries[-1].payload["client_wall_time"],
            "started_at_server": rfc3339(capture_session.created_at),
            "ended_at_server": rfc3339(ended_at),
            "software": {
                "name": settings.software_name,
                "version": settings.software_version,
                "commit": settings.software_commit,
                "build_hash": settings.software_build_hash,
            },
        },
        "artifacts": [
            {
                "artifact_id": artifact.artifact_id,
                "path": artifact.path,
                "size": artifact.size,
                "media_type": artifact.media_type,
                "status": artifact.status,
                "method": artifact.method,
                "provenance": artifact.provenance,
                "artifact_hash": artifact.artifact_hash,
            }
            for artifact in artifacts
        ],
        "chain": {
            "first_hash": entries[0].entry_hash,
            "last_hash": entries[-1].entry_hash,
            "entry_count": len(entries),
            "root_hash": entries[-1].entry_hash,
        },
        "capture_close": {
            "path": "chain/capture-close.json",
            "client_signature_path": "signatures/capture-close.client.sig",
        },
        "limitations": [
            "The package does not prove authorship of displayed content.",
            "The package does not prove that displayed content is factually true.",
        ],
    }


def rfc3339(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def finalize_response(capture_session: CaptureSession) -> FinalizeResponse:
    return FinalizeResponse(
        session_id=capture_session.id,
        status=capture_session.status,
        manifest_hash=capture_session.manifest_hash or "",
        manifest_signature_hex=capture_session.manifest_signature_hex or "",
        server_key_id=capture_session.server_key_id or "",
        manifest=capture_session.manifest or {},
    )


def attestation_response(attestation: Attestation) -> AttestationResponse:
    return AttestationResponse(
        document=attestation.document,
        document_hash=attestation.document_hash,
        signature_hex=attestation.signature_hex,
    )


def ots_complement_response(complement: OtsComplement) -> OtsComplementResponse:
    return OtsComplementResponse(
        complement_id=complement.id,
        batch_id=complement.batch_id,
        proof_hash=complement.proof_hash,
        status=complement.status,
    )


def entry_response(entry: ChainEntry, state: str) -> EntryResponse:
    return EntryResponse(
        session_id=entry.session_id,
        sequence=entry.sequence,
        entry_hash=entry.entry_hash,
        status=state,
    )


def part_response(part: ArtifactPart, receipt: Receipt) -> PartResponse:
    return PartResponse(
        session_id=part.session_id,
        sequence=receipt.sequence,
        artifact_id=part.artifact_id,
        part_number=part.part_number,
        part_hash=part.part_hash,
        persistence_state=part.persistence_state,
        receipt_hash=receipt.receipt_hash,
        receipt_signature_hex=receipt.signature_hex,
        receipt=receipt.payload,
    )


app = create_app()
