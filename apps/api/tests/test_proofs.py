from __future__ import annotations

import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import chitaozinho_api.proofs as proofs
import pytest
from chitaozinho_api.proofs import (
    MerkleLeaf,
    MerkleProof,
    MerkleStep,
    build_merkle_proofs,
    create_rfc3161_query,
    inspect_ots,
    parse_openssl_time,
    stamp_ots,
    upgrade_ots,
    verify_merkle_proof,
    verify_rfc3161_response,
)
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def test_rfc3161_query_contains_exact_manifest_digest(tmp_path: Path) -> None:
    manifest_hash = "sha256:" + ("42" * 32)
    query = tmp_path / "manifest.tsq"
    create_rfc3161_query(manifest_hash, query)
    inspected = subprocess.run(
        ["openssl", "ts", "-query", "-in", str(query), "-text"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    message_data = inspected.split("Message data:", 1)[1].split("Policy OID:", 1)[0]
    assert len(re.findall(r"\b42\b", message_data.lower())) == 32
    assert "sha256" in inspected


def test_merkle_proofs_verify_and_hide_unsalted_manifest_hashes() -> None:
    leaves = [
        MerkleLeaf("sha256:" + (f"{index:02x}" * 32), f"{index + 10:02x}" * 32)
        for index in range(3)
    ]
    proofs = build_merkle_proofs(leaves)
    assert len({proof.root_hash for proof in proofs}) == 1
    assert all(verify_merkle_proof(proof) for proof in proofs)
    assert all(
        proof.leaf.commitment() != bytes.fromhex(proof.leaf.manifest_hash[7:]) for proof in proofs
    )


def test_merkle_proof_detects_tampering() -> None:
    proof = build_merkle_proofs(
        [
            MerkleLeaf("sha256:" + ("01" * 32), "10" * 32),
            MerkleLeaf("sha256:" + ("02" * 32), "20" * 32),
        ]
    )[0]
    tampered = MerkleProof(
        leaf=proof.leaf,
        root_hash=proof.root_hash,
        steps=(MerkleStep("right", "ff" * 32),),
    )
    assert not verify_merkle_proof(tampered)


def test_openssl_timestamp_is_normalized_to_rfc3339() -> None:
    assert parse_openssl_time("Jul 30 19:43:49 2026 GMT") == "2026-07-30T19:43:49Z"


def test_ots_stamp_requires_two_responses_from_public_calendars(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        source = Path(command[-1])
        source.with_name(source.name + ".ots").write_bytes(b"pending-proof")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(proofs, "run_checked", fake_run)
    root = tmp_path / "root.bin"
    proof = tmp_path / "proof.ots"
    calendars = [
        "https://alice.btc.calendar.opentimestamps.org",
        "https://bob.btc.calendar.opentimestamps.org",
        "https://finney.calendar.eternitywall.com",
        "https://ots.btc.catallaxy.com",
    ]
    stamp_ots("sha256:" + ("42" * 32), root, proof, calendars)

    assert proof.read_bytes() == b"pending-proof"
    assert calls[0][:6] == ["ots", "--no-cache", "stamp", "-m", "2", "--calendar"]
    assert sum(value == "--calendar" for value in calls[0]) == 4

    with pytest.raises(ValueError, match="at least two"):
        stamp_ots("sha256:" + ("43" * 32), tmp_path / "other", proof, calendars[:1])


@pytest.mark.parametrize(
    ("inspection", "expected"),
    [
        ("verify PendingAttestation('https://calendar')", "pending_confirmation"),
        ("verify BitcoinBlockHeaderAttestation(900000)", "bitcoin_attestation_available"),
        ("unknown", "verification_failed"),
    ],
)
def test_ots_inspection_distinguishes_proof_from_node_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inspection: str,
    expected: str,
) -> None:
    monkeypatch.setattr(
        proofs,
        "run_checked",
        lambda command: subprocess.CompletedProcess(
            command,
            0,
            stdout=inspection,
            stderr="",
        ),
    )
    assert inspect_ots(tmp_path / "proof.ots") == expected


def test_ots_upgrade_treats_pending_calendar_confirmation_as_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = tmp_path / "original.ots"
    complement = tmp_path / "complement.ots"
    original.write_bytes(b"pending-proof")

    def pending(command: list[str]) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(
            1,
            command,
            stderr="Calendar: Pending confirmation in Bitcoin blockchain\n"
            "Failed! Timestamp not complete",
        )

    monkeypatch.setattr(proofs, "run_checked", pending)

    assert upgrade_ots(original, complement) is False
    assert complement.read_bytes() == original.read_bytes()


def test_ots_upgrade_does_not_hide_unexpected_client_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = tmp_path / "original.ots"
    original.write_bytes(b"pending-proof")
    monkeypatch.setattr(
        proofs,
        "run_checked",
        lambda command: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, command, stderr="network failure")
        ),
    )

    with pytest.raises(subprocess.CalledProcessError, match="returned non-zero"):
        upgrade_ots(original, tmp_path / "complement.ots")


def test_rfc3161_chain_is_verified_at_signed_generation_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    reply_text = "\n".join(
        [
            "Policy OID: 1.2.3.4",
            "Serial number: 0x01",
            "Time stamp: Jul 30 19:43:49 2026 GMT",
        ]
    )

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=reply_text if "-reply" in command else "",
            stderr="",
        )

    monkeypatch.setattr(proofs, "run_checked", fake_run)
    result = verify_rfc3161_response(
        tmp_path / "manifest.tsq",
        tmp_path / "manifest.tsr",
        tmp_path / "ca.pem",
        untrusted_chain=tmp_path / "chain.pem",
    )

    expected_epoch = int(datetime(2026, 7, 30, 19, 43, 49, tzinfo=UTC).timestamp())
    verify_command = next(command for command in calls if "-verify" in command)
    assert verify_command[verify_command.index("-attime") + 1] == str(expected_epoch)
    assert "-x509_strict" in verify_command
    assert "-crl_check_all" in verify_command
    assert result == {
        "gen_time": "2026-07-30T19:43:49Z",
        "policy": "1.2.3.4",
        "serial": "0x01",
    }


def test_real_rfc3161_rejects_hash_chain_and_validity_divergence(
    tmp_path: Path,
) -> None:
    valid = create_test_tsa(tmp_path / "valid")
    verified = verify_rfc3161_response(
        valid["query"],
        valid["response"],
        valid["root_certificate"],
        crl_check=False,
    )
    assert verified["gen_time"].endswith("Z")

    altered_query = tmp_path / "altered.tsq"
    create_rfc3161_query("sha256:" + ("43" * 32), altered_query)
    with pytest.raises(subprocess.CalledProcessError):
        verify_rfc3161_response(
            altered_query,
            valid["response"],
            valid["root_certificate"],
            crl_check=False,
        )

    with pytest.raises(subprocess.CalledProcessError):
        verify_rfc3161_response(
            valid["query"],
            valid["response"],
            create_test_tsa(tmp_path / "other")["root_certificate"],
            crl_check=False,
        )

    expired = create_test_tsa(tmp_path / "expired", expired=True)
    with pytest.raises(subprocess.CalledProcessError):
        verify_rfc3161_response(
            expired["query"],
            expired["response"],
            expired["root_certificate"],
            crl_check=False,
        )


def create_test_tsa(root: Path, *, expired: bool = False) -> dict[str, Path]:
    root.mkdir(parents=True)
    now = datetime.now(UTC)
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Root")])
    root_certificate = (
        x509.CertificateBuilder()
        .subject_name(root_name)
        .issuer_name(root_name)
        .public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=30))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()),
            critical=False,
        )
        .sign(root_key, hashes.SHA256())
    )
    tsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tsa_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test TSA")])
    tsa_certificate = (
        x509.CertificateBuilder()
        .subject_name(tsa_name)
        .issuer_name(root_name)
        .public_key(tsa_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=2))
        .not_valid_after(now - timedelta(days=1) if expired else now + timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.TIME_STAMPING]),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(tsa_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()),
            critical=False,
        )
        .sign(root_key, hashes.SHA256())
    )
    root_path = root / "root.pem"
    tsa_path = root / "tsa.pem"
    key_path = root / "tsa.key"
    root_path.write_bytes(root_certificate.public_bytes(serialization.Encoding.PEM))
    tsa_path.write_bytes(tsa_certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        tsa_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    serial_path = root / "serial"
    serial_path.write_text("01\n")
    config_path = root / "tsa.cnf"
    config_path.write_text(
        "\n".join(
            [
                "[tsa]",
                "default_tsa = tsa_config",
                "[tsa_config]",
                f"serial = {serial_path}",
                "crypto_device = builtin",
                f"signer_cert = {tsa_path}",
                f"certs = {root_path}",
                f"signer_key = {key_path}",
                "signer_digest = sha256",
                "default_policy = 1.2.3.4.1",
                "other_policies = 1.2.3.4.2",
                "digests = sha256",
                "accuracy = secs:1",
                "ordering = yes",
                "tsa_name = yes",
                "ess_cert_id_chain = yes",
                "ess_cert_id_alg = sha256",
            ]
        )
        + "\n"
    )
    query_path = root / "manifest.tsq"
    response_path = root / "manifest.tsr"
    create_rfc3161_query("sha256:" + ("42" * 32), query_path)
    subprocess.run(
        [
            "openssl",
            "ts",
            "-reply",
            "-config",
            str(config_path),
            "-section",
            "tsa_config",
            "-queryfile",
            str(query_path),
            "-out",
            str(response_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        "query": query_path,
        "response": response_path,
        "root_certificate": root_path,
    }
