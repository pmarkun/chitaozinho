from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path


def digest_bytes(identifier: str) -> bytes:
    prefix, separator, value = identifier.partition(":")
    if prefix != "sha256" or separator != ":" or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("expected a lowercase sha256 identifier")
    return bytes.fromhex(value)


def create_rfc3161_query(manifest_hash: str, output: Path) -> bytes:
    output.parent.mkdir(parents=True, exist_ok=True)
    run_checked(
        [
            "openssl",
            "ts",
            "-query",
            "-digest",
            digest_bytes(manifest_hash).hex(),
            "-sha256",
            "-cert",
            "-out",
            str(output),
        ]
    )
    return output.read_bytes()


def request_rfc3161_timestamp(url: str, query: bytes, output: Path) -> bytes:
    request = urllib.request.Request(
        url,
        data=query,
        headers={
            "Content-Type": "application/timestamp-query",
            "Accept": "application/timestamp-reply",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.headers.get_content_type() != "application/timestamp-reply":
            raise ValueError("TSA returned an unexpected content type")
        body = response.read(16 * 1024 * 1024 + 1)
    if len(body) > 16 * 1024 * 1024:
        raise ValueError("TSA response exceeds size limit")
    write_new(output, body)
    return body


def verify_rfc3161_response(
    query: Path,
    response: Path,
    ca_bundle: Path,
    *,
    untrusted_chain: Path | None = None,
    crl_check: bool = True,
) -> dict[str, str]:
    text = run_checked(["openssl", "ts", "-reply", "-in", str(response), "-text"]).stdout
    gen_time = parse_openssl_time(extract_field(text, "Time stamp"))
    verification_time = int(datetime.fromisoformat(gen_time.replace("Z", "+00:00")).timestamp())
    command = [
        "openssl",
        "ts",
        "-verify",
        "-queryfile",
        str(query),
        "-in",
        str(response),
        "-CAfile",
        str(ca_bundle),
        "-purpose",
        "timestampsign",
        "-attime",
        str(verification_time),
        "-x509_strict",
    ]
    if untrusted_chain is not None:
        command.extend(["-untrusted", str(untrusted_chain)])
    if crl_check:
        command.append("-crl_check_all")
    run_checked(command)
    return {
        "gen_time": gen_time,
        "policy": extract_field(text, "Policy OID"),
        "serial": extract_field(text, "Serial number"),
    }


def extract_rfc3161_chain(response: Path, output: Path) -> None:
    token = response.with_suffix(".token.der")
    try:
        run_checked(
            [
                "openssl",
                "ts",
                "-reply",
                "-in",
                str(response),
                "-token_out",
                "-out",
                str(token),
            ]
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        run_checked(
            [
                "openssl",
                "pkcs7",
                "-inform",
                "DER",
                "-in",
                str(token),
                "-print_certs",
                "-out",
                str(output),
            ]
        )
    finally:
        token.unlink(missing_ok=True)


@dataclass(frozen=True)
class MerkleLeaf:
    manifest_hash: str
    salt_hex: str

    def commitment(self) -> bytes:
        salt = bytes.fromhex(self.salt_hex)
        if len(salt) != 32:
            raise ValueError("Merkle salt must contain 32 bytes")
        return sha256(b"\x00" + salt + digest_bytes(self.manifest_hash)).digest()


@dataclass(frozen=True)
class MerkleStep:
    side: str
    hash_hex: str


@dataclass(frozen=True)
class MerkleProof:
    leaf: MerkleLeaf
    root_hash: str
    steps: tuple[MerkleStep, ...]

    def as_dict(self) -> dict:
        return {
            "schema_version": "0.1.0",
            "algorithm": "sha256-domain-separated-v1",
            "manifest_hash": self.leaf.manifest_hash,
            "salt_hex": self.leaf.salt_hex,
            "root_hash": self.root_hash,
            "steps": [
                {"side": step.side, "hash": f"sha256:{step.hash_hex}"} for step in self.steps
            ],
        }


def build_merkle_proofs(leaves: list[MerkleLeaf]) -> list[MerkleProof]:
    if not leaves:
        raise ValueError("Merkle batch cannot be empty")
    level = [leaf.commitment() for leaf in leaves]
    paths: list[list[MerkleStep]] = [[] for _leaf in leaves]
    memberships = [[index] for index in range(len(leaves))]
    while len(level) > 1:
        next_level: list[bytes] = []
        next_memberships: list[list[int]] = []
        for offset in range(0, len(level), 2):
            left = level[offset]
            right = level[offset + 1] if offset + 1 < len(level) else left
            left_members = memberships[offset]
            right_members = (
                memberships[offset + 1] if offset + 1 < len(memberships) else left_members
            )
            for index in left_members:
                paths[index].append(MerkleStep("right", right.hex()))
            if offset + 1 < len(level):
                for index in right_members:
                    paths[index].append(MerkleStep("left", left.hex()))
            next_level.append(sha256(b"\x01" + left + right).digest())
            next_memberships.append(sorted(set(left_members + right_members)))
        level = next_level
        memberships = next_memberships
    root_hash = f"sha256:{level[0].hex()}"
    return [
        MerkleProof(leaf=leaf, root_hash=root_hash, steps=tuple(paths[index]))
        for index, leaf in enumerate(leaves)
    ]


def verify_merkle_proof(proof: MerkleProof) -> bool:
    current = proof.leaf.commitment()
    for step in proof.steps:
        sibling = bytes.fromhex(step.hash_hex)
        if len(sibling) != 32:
            return False
        if step.side == "left":
            current = sha256(b"\x01" + sibling + current).digest()
        elif step.side == "right":
            current = sha256(b"\x01" + current + sibling).digest()
        else:
            return False
    return f"sha256:{current.hex()}" == proof.root_hash


def write_merkle_proof(proof: MerkleProof, output: Path) -> None:
    write_new(
        output,
        json.dumps(proof.as_dict(), sort_keys=True, separators=(",", ":")).encode() + b"\n",
    )


def stamp_ots(root_hash: str, root_file: Path, proof_file: Path, calendars: list[str]) -> None:
    write_new(root_file, digest_bytes(root_hash))
    if len(calendars) < 2:
        raise ValueError("OpenTimestamps requires at least two public calendars")
    command = ["ots", "--no-cache", "stamp", "-m", "2"]
    for calendar in calendars:
        command.extend(["--calendar", calendar])
    command.append(str(root_file))
    run_checked(command)
    generated = root_file.with_name(root_file.name + ".ots")
    if generated != proof_file:
        proof_file.parent.mkdir(parents=True, exist_ok=True)
        generated.rename(proof_file)


def upgrade_ots(original: Path, complement: Path) -> bool:
    if complement.exists():
        raise FileExistsError(complement)
    complement.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original, complement)
    try:
        before = complement.read_bytes()
        try:
            run_checked(["ots", "--no-cache", "upgrade", str(complement)])
        except subprocess.CalledProcessError as error:
            output = f"{error.stdout or ''}\n{error.stderr or ''}".lower()
            if "pending confirmation" not in output and "timestamp not complete" not in output:
                raise
            shutil.copyfile(original, complement)
            return False
        return complement.read_bytes() != before
    finally:
        complement.with_name(complement.name + ".bak").unlink(missing_ok=True)


def inspect_ots(proof_file: Path) -> str:
    result = run_checked(["ots", "info", str(proof_file)])
    output = f"{result.stdout}\n{result.stderr}"
    if "BitcoinBlockHeaderAttestation" in output:
        return "bitcoin_attestation_available"
    if "PendingAttestation" in output:
        return "pending_confirmation"
    return "verification_failed"


def verify_ots(
    root_file: Path,
    proof_file: Path,
    bitcoin_node_url: str | None = None,
) -> str:
    command = ["ots"]
    if bitcoin_node_url is not None:
        command.extend(["--bitcoin-node", bitcoin_node_url])
    command.extend(["verify", "-f", str(root_file), str(proof_file)])
    result = run_checked(command)
    output = f"{result.stdout}\n{result.stderr}".lower()
    if "pending" in output:
        return "pending_confirmation"
    if "success" in output:
        return "confirmed"
    return "verification_failed"


def write_new(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(content)


def extract_field(text: str, label: str) -> str:
    match = re.search(rf"^{re.escape(label)}:\s*(.+)$", text, re.MULTILINE)
    if match is None:
        raise ValueError(f"RFC 3161 response is missing {label}")
    return match.group(1).strip()


def parse_openssl_time(value: str) -> str:
    parsed = datetime.strptime(value, "%b %d %H:%M:%S %Y GMT").replace(tzinfo=UTC)
    return parsed.isoformat().replace("+00:00", "Z")


def run_checked(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
