from __future__ import annotations

import subprocess
from pathlib import Path

from chitaozinho_api.proofs import (
    MerkleLeaf,
    MerkleProof,
    MerkleStep,
    build_merkle_proofs,
    create_rfc3161_query,
    parse_openssl_time,
    verify_merkle_proof,
)


def test_rfc3161_query_contains_exact_manifest_digest(tmp_path: Path) -> None:
    manifest_hash = "sha256:" + ("42" * 32)
    query = tmp_path / "manifest.tsq"
    create_rfc3161_query(manifest_hash, query)
    inspected = subprocess.run(
        ["openssl", "ts", "-query", "-in", str(query), "-text"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.replace(":", "").lower()
    assert inspected.count("42") == 32
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
        proof.leaf.commitment() != bytes.fromhex(proof.leaf.manifest_hash[7:])
        for proof in proofs
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
