use std::collections::{BTreeMap, BTreeSet};
use std::fs::{self, File};
use std::io::{self, BufRead, BufReader, BufWriter, Read, Write};
use std::path::{Component, Path, PathBuf};
use std::process::Command;

use anyhow::{Context, Result, anyhow, bail, ensure};
use chitaozinho_protocol::{
    ATTESTATION_DOMAIN, CAPTURE_CLOSE_DOMAIN, ENTRY_DOMAIN, MANIFEST_DOMAIN, PACKAGE_INDEX_DOMAIN,
    PROOF_BUNDLE_INDEX_DOMAIN, RECEIPT_DOMAIN, canonical_bytes, sha256_identifier, sign_canonical,
    verify_canonical,
};
use chrono::{SecondsFormat, Utc};
use ed25519_dalek::SigningKey;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tempfile::TempDir;
use walkdir::WalkDir;
use zip::write::SimpleFileOptions;
use zip::{CompressionMethod, ZipArchive, ZipWriter};

const PACKAGE_INDEX_PATH: &str = "package-index.json";
const PACKAGE_INDEX_SIGNATURE_PATH: &str = "signatures/package-index.server.sig";
const MANIFEST_PATH: &str = "capture-manifest.json";
const MANIFEST_SIGNATURE_PATH: &str = "signatures/capture-manifest.server.sig";
const PUBLIC_KEYS_PATH: &str = "signatures/public-keys.json";
const ENTRIES_PATH: &str = "chain/entries.jsonl";
const RECEIPTS_PATH: &str = "chain/receipts.jsonl";
const PROOF_BUNDLE_INDEX_PATH: &str = "proof-bundle-index.json";
const PROOF_BUNDLE_INDEX_SIGNATURE_PATH: &str = "signatures/proof-bundle-index.server.sig";
const ATTESTATIONS_PATH: &str = "attestations.jsonl";
const MAX_ENTRIES: usize = 10_000;
const MAX_FILE_SIZE: u64 = 2 * 1024 * 1024 * 1024;
const MAX_TOTAL_SIZE: u64 = 5 * 1024 * 1024 * 1024;
const MAX_COMPRESSION_RATIO: u64 = 1_000;
const MAX_METADATA_FILE_SIZE: u64 = 16 * 1024 * 1024;

#[derive(Debug)]
pub struct PackResult {
    pub package_path: PathBuf,
    pub hash_path: PathBuf,
    pub sha256: String,
}

#[derive(Debug, Serialize)]
pub struct VerificationReport {
    pub result: &'static str,
    pub session_id: String,
    pub members_verified: usize,
    pub checks: Vec<&'static str>,
    pub temporal_proof: &'static str,
    pub attestations_verified: usize,
}

pub fn write_html_report(report: &VerificationReport, path: &Path) -> Result<()> {
    let checks = report
        .checks
        .iter()
        .map(|check| format!("<li><code>{}</code>: válido</li>", escape_html(check)))
        .collect::<String>();
    let html = format!(
        concat!(
            "<!doctype html><html lang=\"pt-BR\"><meta charset=\"utf-8\">",
            "<title>Verificação Chitãozinho</title>",
            "<h1>Relatório de verificação</h1>",
            "<dl><dt>Resultado</dt><dd>{}</dd>",
            "<dt>Sessão</dt><dd><code>{}</code></dd>",
            "<dt>Membros verificados</dt><dd>{}</dd>",
            "<dt>Prova temporal</dt><dd>{}</dd>",
            "<dt>Attestations verificadas</dt><dd>{}</dd></dl>",
            "<h2>Verificações</h2><ul>{}</ul>",
            "<h2>Limitações</h2>",
            "<p>Este pacote demonstra a integridade e a rastreabilidade técnica ",
            "dos artefatos a partir do momento em que foram processados pelo sistema.</p>",
            "<p>O relatório não comprova autoria, veracidade material ou validade jurídica definitiva.</p>",
            "</html>"
        ),
        escape_html(result_label(report.result)),
        escape_html(&report.session_id),
        report.members_verified,
        escape_html(report.temporal_proof),
        report.attestations_verified,
        checks
    );
    if let Some(parent) = path.parent().filter(|value| !value.as_os_str().is_empty()) {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, html)?;
    Ok(())
}

fn result_label(result: &str) -> &str {
    match result {
        "integral" => "íntegro",
        "integral_but_incomplete" => "íntegro, mas incompleto",
        "invalid" => "inválido",
        _ => "não verificável",
    }
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PackageIndex {
    schema_version: String,
    session_id: String,
    created_at: String,
    members: Vec<PackageMember>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PackageMember {
    path: String,
    size: u64,
    media_type: String,
    sha256: String,
}

#[derive(Debug, Deserialize)]
struct PublicKeys {
    schema_version: String,
    server: PublicKeyRecord,
    client: PublicKeyRecord,
}

#[derive(Debug, Deserialize)]
struct PublicKeyRecord {
    key_id: String,
    algorithm: String,
    public_key_hex: String,
}

#[derive(Debug, Deserialize)]
struct CaptureManifest {
    schema_version: String,
    session_id: String,
    status: String,
    artifacts: Vec<ManifestArtifact>,
    chain: ManifestChain,
    capture_close: CaptureCloseReference,
}

#[derive(Debug, Deserialize)]
struct ManifestChain {
    first_hash: String,
    last_hash: String,
    entry_count: u64,
    root_hash: String,
}

#[derive(Debug, Deserialize)]
struct ManifestArtifact {
    path: String,
    size: u64,
    status: String,
    artifact_hash: Option<String>,
}

#[derive(Debug, Deserialize)]
struct CaptureCloseReference {
    path: String,
    client_signature_path: String,
}

#[derive(Debug, Deserialize)]
struct CaptureCloseStatement {
    session_id: String,
    session_root: String,
    last_entry_hash: String,
    entry_count: u64,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct ChainRecord {
    entry: serde_json::Value,
    entry_hash: String,
    signature_hex: String,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct ReceiptRecord {
    receipt: serde_json::Value,
    receipt_hash: String,
    signature_hex: String,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct ProofBundleIndex {
    schema_version: String,
    session_id: String,
    manifest_hash: String,
    created_at: String,
    members: Vec<ProofBundleMember>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct ProofBundleMember {
    path: String,
    size: u64,
    sha256: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct AttestationRecord {
    document: serde_json::Value,
    document_hash: String,
    signature_hex: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct MerkleProofDocument {
    schema_version: String,
    algorithm: String,
    manifest_hash: String,
    salt_hex: String,
    root_hash: String,
    steps: Vec<MerkleProofStep>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct MerkleProofStep {
    side: String,
    hash: String,
}

pub fn pack(source: &Path, output: &Path, server_seed: &[u8; 32]) -> Result<PackResult> {
    ensure!(source.is_dir(), "source is not a directory");
    ensure!(
        !output.exists(),
        "output already exists: {}",
        output.display()
    );

    let temporary = tempfile::tempdir().context("create package staging directory")?;
    copy_source(source, temporary.path())?;

    let manifest_path = temporary.path().join(MANIFEST_PATH);
    let manifest_bytes = fs::read(&manifest_path)
        .with_context(|| format!("read required {}", manifest_path.display()))?;
    let manifest: CaptureManifest =
        serde_json::from_slice(&manifest_bytes).context("parse capture manifest")?;
    validate_manifest_header(&manifest)?;

    let public_keys_path = temporary.path().join(PUBLIC_KEYS_PATH);
    let public_keys: PublicKeys = read_json(&public_keys_path)?;
    validate_public_keys(&public_keys)?;
    let expected_server_key = SigningKey::from_bytes(server_seed)
        .verifying_key()
        .to_bytes();
    ensure!(
        decode_array::<32>(&public_keys.server.public_key_hex, "server public key")?
            == expected_server_key,
        "server seed does not match public-keys.json"
    );

    let canonical_manifest: serde_json::Value =
        serde_json::from_slice(&manifest_bytes).context("parse manifest for signing")?;
    let manifest_signature = sign_canonical(MANIFEST_DOMAIN, &canonical_manifest, server_seed)?;
    write_hex_file(
        &temporary.path().join(MANIFEST_SIGNATURE_PATH),
        &manifest_signature,
    )?;
    verify_manifest_artifacts(temporary.path(), &manifest)?;
    let entries = verify_chain(temporary.path(), &manifest, &public_keys)?;
    verify_receipts(temporary.path(), &entries, &public_keys)?;
    verify_capture_close(temporary.path(), &manifest, &public_keys)?;

    let members = collect_members(
        temporary.path(),
        &[PACKAGE_INDEX_PATH, PACKAGE_INDEX_SIGNATURE_PATH],
    )?;
    let package_index = PackageIndex {
        schema_version: "0.1.0".to_owned(),
        session_id: manifest.session_id.clone(),
        created_at: Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true),
        members,
    };
    let package_index_bytes = canonical_bytes(&package_index)?;
    fs::write(
        temporary.path().join(PACKAGE_INDEX_PATH),
        &package_index_bytes,
    )?;
    let index_signature = sign_canonical(PACKAGE_INDEX_DOMAIN, &package_index, server_seed)?;
    write_hex_file(
        &temporary.path().join(PACKAGE_INDEX_SIGNATURE_PATH),
        &index_signature,
    )?;

    if let Some(parent) = output.parent().filter(|path| !path.as_os_str().is_empty()) {
        fs::create_dir_all(parent)?;
    }
    create_zip(temporary.path(), output)?;
    let sha256 = hash_file(output)?;
    let hash_path = hash_path_for(output);
    fs::write(&hash_path, format!("{sha256}  {}\n", file_name(output)?))?;

    Ok(PackResult {
        package_path: output.to_path_buf(),
        hash_path,
        sha256,
    })
}

pub fn verify(package_path: &Path, trusted_server_key: &[u8; 32]) -> Result<VerificationReport> {
    verify_internal(package_path, None, trusted_server_key)
}

pub fn verify_with_proof_bundle_and_trust(
    package_path: &Path,
    proof_bundle_path: &Path,
    trusted_server_key: &[u8; 32],
    tsa_ca_bundle: Option<&Path>,
    tsa_crl_bundle: Option<&Path>,
) -> Result<VerificationReport> {
    verify_internal(
        package_path,
        Some((
            proof_bundle_path,
            TimestampTrust {
                ca_bundle: tsa_ca_bundle,
                crl_bundle: tsa_crl_bundle,
            },
        )),
        trusted_server_key,
    )
}

fn verify_internal(
    package_path: &Path,
    proof_bundle: Option<(&Path, TimestampTrust<'_>)>,
    trusted_server_key: &[u8; 32],
) -> Result<VerificationReport> {
    ensure!(package_path.is_file(), "package does not exist");
    let extracted = extract_safely(package_path)?;

    let index_path = extracted.path().join(PACKAGE_INDEX_PATH);
    let package_index: PackageIndex = read_json(&index_path)?;
    ensure!(
        package_index.schema_version == "0.1.0",
        "unsupported package index schema"
    );
    let index_signature =
        read_hex_array::<64>(&extracted.path().join(PACKAGE_INDEX_SIGNATURE_PATH))?;
    verify_canonical(
        PACKAGE_INDEX_DOMAIN,
        &package_index,
        &index_signature,
        trusted_server_key,
    )
    .context("invalid package index signature")?;

    verify_members(extracted.path(), &package_index)?;

    let public_keys: PublicKeys = read_json(&extracted.path().join(PUBLIC_KEYS_PATH))?;
    validate_public_keys(&public_keys)?;
    let packaged_server_key =
        decode_array::<32>(&public_keys.server.public_key_hex, "server public key")?;
    ensure!(
        packaged_server_key == *trusted_server_key,
        "packaged server key is not the trusted server key"
    );

    let manifest_path = extracted.path().join(MANIFEST_PATH);
    let manifest_value: serde_json::Value = read_json(&manifest_path)?;
    let manifest: CaptureManifest = read_json(&manifest_path)?;
    validate_manifest_header(&manifest)?;
    ensure!(
        manifest.session_id == package_index.session_id,
        "session id differs between manifest and package index"
    );
    let manifest_signature = read_hex_array::<64>(&extracted.path().join(MANIFEST_SIGNATURE_PATH))?;
    verify_canonical(
        MANIFEST_DOMAIN,
        &manifest_value,
        &manifest_signature,
        trusted_server_key,
    )
    .context("invalid capture manifest signature")?;

    verify_manifest_artifacts(extracted.path(), &manifest)?;
    let entries = verify_chain(extracted.path(), &manifest, &public_keys)?;
    verify_receipts(extracted.path(), &entries, &public_keys)?;
    verify_capture_close(extracted.path(), &manifest, &public_keys)?;
    let manifest_hash = sha256_identifier(&canonical_bytes(&manifest_value)?);
    let proof_result = proof_bundle
        .map(|(path, trust)| {
            verify_proof_bundle(
                path,
                &manifest.session_id,
                &manifest_hash,
                trusted_server_key,
                trust,
            )
        })
        .transpose()?;

    Ok(VerificationReport {
        result: if manifest.status == "complete" {
            "integral"
        } else {
            "integral_but_incomplete"
        },
        session_id: manifest.session_id,
        members_verified: package_index.members.len(),
        temporal_proof: proof_result
            .as_ref()
            .map_or("not_provided", |result| result.temporal_status),
        attestations_verified: proof_result
            .as_ref()
            .map_or(0, |result| result.attestations_verified),
        checks: vec![
            "safe_zip_structure",
            "package_index_signature",
            "member_hashes",
            "manifest_signature",
            "artifact_hashes",
            "entry_chain",
            "receipt_chain",
            "capture_close_signature",
            if proof_result.is_some() {
                "external_proof_bundle"
            } else {
                "external_proofs_not_provided"
            },
        ],
    })
}

struct ProofVerification {
    temporal_status: &'static str,
    attestations_verified: usize,
}

#[derive(Clone, Copy)]
struct TimestampTrust<'a> {
    ca_bundle: Option<&'a Path>,
    crl_bundle: Option<&'a Path>,
}

fn verify_proof_bundle(
    bundle_path: &Path,
    expected_session_id: &str,
    expected_manifest_hash: &str,
    trusted_server_key: &[u8; 32],
    timestamp_trust: TimestampTrust<'_>,
) -> Result<ProofVerification> {
    ensure!(bundle_path.is_file(), "proof bundle does not exist");
    let extracted = extract_safely(bundle_path)?;
    let index: ProofBundleIndex = read_json(&extracted.path().join(PROOF_BUNDLE_INDEX_PATH))?;
    ensure!(
        index.schema_version == "0.1.0",
        "unsupported proof bundle schema"
    );
    ensure!(
        index.session_id == expected_session_id,
        "proof bundle session id mismatch"
    );
    ensure!(
        index.manifest_hash == expected_manifest_hash,
        "proof bundle manifest hash mismatch"
    );
    ensure!(
        !index.created_at.is_empty(),
        "proof bundle created_at is empty"
    );
    let signature =
        read_hex_array::<64>(&extracted.path().join(PROOF_BUNDLE_INDEX_SIGNATURE_PATH))?;
    verify_canonical(
        PROOF_BUNDLE_INDEX_DOMAIN,
        &index,
        &signature,
        trusted_server_key,
    )
    .context("invalid proof bundle index signature")?;
    verify_proof_bundle_members(extracted.path(), &index)?;

    let records: Vec<AttestationRecord> =
        read_json_lines(&extracted.path().join(ATTESTATIONS_PATH))?;
    ensure!(!records.is_empty(), "proof bundle has no attestations");
    let mut previous: Option<String> = None;
    let mut temporal_status = "not_requested";
    for (sequence, record) in records.iter().enumerate() {
        ensure!(
            json_string(&record.document, "manifest_hash")? == expected_manifest_hash,
            "attestation manifest hash mismatch at sequence {sequence}"
        );
        match (&previous, record.document.get("previous_attestation_hash")) {
            (None, Some(serde_json::Value::Null)) => {}
            (Some(expected), Some(serde_json::Value::String(actual))) if expected == actual => {}
            _ => bail!("attestation chain mismatch at sequence {sequence}"),
        }
        let actual_hash = sha256_identifier(&canonical_bytes(&record.document)?);
        ensure!(
            record.document_hash == actual_hash,
            "attestation hash mismatch at sequence {sequence}"
        );
        let attestation_signature =
            decode_array::<64>(&record.signature_hex, "attestation signature")?;
        verify_canonical(
            ATTESTATION_DOMAIN,
            &record.document,
            &attestation_signature,
            trusted_server_key,
        )
        .with_context(|| format!("invalid attestation signature at sequence {sequence}"))?;
        verify_attestation_proofs(extracted.path(), &record.document, timestamp_trust)?;
        temporal_status = merge_temporal_status(temporal_status, &record.document)?;
        previous = Some(record.document_hash.clone());
    }
    Ok(ProofVerification {
        temporal_status,
        attestations_verified: records.len(),
    })
}

fn validate_manifest_header(manifest: &CaptureManifest) -> Result<()> {
    ensure!(
        manifest.schema_version == "0.1.0",
        "unsupported manifest schema"
    );
    ensure!(
        matches!(manifest.status.as_str(), "complete" | "incomplete"),
        "invalid capture status"
    );
    Ok(())
}

fn validate_public_keys(keys: &PublicKeys) -> Result<()> {
    ensure!(keys.schema_version == "0.1.0", "unsupported key schema");
    ensure!(
        keys.server.algorithm == "Ed25519" && keys.client.algorithm == "Ed25519",
        "unsupported public key algorithm"
    );
    ensure!(
        !keys.server.key_id.is_empty() && !keys.client.key_id.is_empty(),
        "key id cannot be empty"
    );
    Ok(())
}

fn verify_capture_close(
    root: &Path,
    manifest: &CaptureManifest,
    public_keys: &PublicKeys,
) -> Result<()> {
    let close_path = checked_join(root, &manifest.capture_close.path)?;
    let signature_path = checked_join(root, &manifest.capture_close.client_signature_path)?;
    let close_value: serde_json::Value = read_json(&close_path)?;
    let close: CaptureCloseStatement = read_json(&close_path)?;
    ensure!(
        close.session_id == manifest.session_id,
        "capture close session id mismatch"
    );
    ensure!(
        close.session_root == manifest.chain.root_hash
            && close.last_entry_hash == manifest.chain.last_hash
            && close.entry_count == manifest.chain.entry_count,
        "capture close does not match manifest chain"
    );
    let signature = read_hex_array::<64>(&signature_path)?;
    let public_key = decode_array::<32>(&public_keys.client.public_key_hex, "client public key")?;
    verify_canonical(CAPTURE_CLOSE_DOMAIN, &close_value, &signature, &public_key)
        .context("invalid capture close signature")
}

fn verify_chain(
    root: &Path,
    manifest: &CaptureManifest,
    public_keys: &PublicKeys,
) -> Result<BTreeMap<u64, String>> {
    let records: Vec<ChainRecord> = read_json_lines(&root.join(ENTRIES_PATH))?;
    ensure!(
        records.len() as u64 == manifest.chain.entry_count,
        "entry count differs from manifest"
    );
    ensure!(!records.is_empty(), "entry chain is empty");
    let client_key = decode_array::<32>(&public_keys.client.public_key_hex, "client public key")?;
    let mut previous: Option<String> = None;
    let mut by_sequence = BTreeMap::new();
    for (index, record) in records.iter().enumerate() {
        let sequence = json_u64(&record.entry, "sequence")?;
        ensure!(sequence == index as u64, "entry sequence has a gap");
        ensure!(
            json_string(&record.entry, "session_id")? == manifest.session_id,
            "entry session id mismatch"
        );
        match (&previous, record.entry.get("previous_entry_hash")) {
            (None, Some(serde_json::Value::Null)) => {}
            (Some(expected), Some(serde_json::Value::String(actual))) if expected == actual => {}
            _ => bail!("entry previous hash mismatch at sequence {sequence}"),
        }
        let actual_hash = sha256_identifier(&canonical_bytes(&record.entry)?);
        ensure!(
            record.entry_hash == actual_hash,
            "entry hash mismatch at sequence {sequence}"
        );
        let signature = decode_array::<64>(&record.signature_hex, "entry signature")?;
        verify_canonical(ENTRY_DOMAIN, &record.entry, &signature, &client_key)
            .with_context(|| format!("invalid entry signature at sequence {sequence}"))?;
        ensure!(
            by_sequence
                .insert(sequence, record.entry_hash.clone())
                .is_none(),
            "duplicate entry sequence"
        );
        previous = Some(record.entry_hash.clone());
    }
    let first = &records[0].entry_hash;
    let last = &records[records.len() - 1].entry_hash;
    ensure!(
        manifest.chain.first_hash == *first
            && manifest.chain.last_hash == *last
            && manifest.chain.root_hash == *last,
        "manifest chain hashes do not match entries"
    );
    Ok(by_sequence)
}

fn verify_receipts(
    root: &Path,
    entries: &BTreeMap<u64, String>,
    public_keys: &PublicKeys,
) -> Result<()> {
    let records: Vec<ReceiptRecord> = read_json_lines(&root.join(RECEIPTS_PATH))?;
    let server_key = decode_array::<32>(&public_keys.server.public_key_hex, "server public key")?;
    let mut previous: Option<String> = None;
    for record in records {
        let sequence = json_u64(&record.receipt, "sequence")?;
        let entry_hash = json_string(&record.receipt, "entry_hash")?;
        ensure!(
            entries.get(&sequence).map(String::as_str) == Some(entry_hash),
            "receipt references unknown entry"
        );
        match (&previous, record.receipt.get("previous_receipt_hash")) {
            (None, Some(serde_json::Value::Null)) => {}
            (Some(expected), Some(serde_json::Value::String(actual))) if expected == actual => {}
            _ => bail!("receipt previous hash mismatch at sequence {sequence}"),
        }
        let actual_hash = sha256_identifier(&canonical_bytes(&record.receipt)?);
        ensure!(
            record.receipt_hash == actual_hash,
            "receipt hash mismatch at sequence {sequence}"
        );
        let signature = decode_array::<64>(&record.signature_hex, "receipt signature")?;
        verify_canonical(RECEIPT_DOMAIN, &record.receipt, &signature, &server_key)
            .with_context(|| format!("invalid receipt signature at sequence {sequence}"))?;
        previous = Some(record.receipt_hash);
    }
    Ok(())
}

fn verify_manifest_artifacts(root: &Path, manifest: &CaptureManifest) -> Result<()> {
    for artifact in &manifest.artifacts {
        if artifact.status != "captured" {
            ensure!(
                artifact.artifact_hash.is_none(),
                "unavailable artifact cannot claim a hash"
            );
            continue;
        }
        let path = checked_join(root, &artifact.path)?;
        let metadata = fs::metadata(&path)
            .with_context(|| format!("missing captured artifact {}", artifact.path))?;
        ensure!(
            metadata.len() == artifact.size,
            "artifact size mismatch: {}",
            artifact.path
        );
        let actual_hash = hash_file(&path)?;
        ensure!(
            artifact.artifact_hash.as_deref() == Some(actual_hash.as_str()),
            "artifact hash mismatch: {}",
            artifact.path
        );
    }
    Ok(())
}

fn verify_members(root: &Path, index: &PackageIndex) -> Result<()> {
    let mut expected = BTreeMap::new();
    for member in &index.members {
        ensure!(
            expected.insert(member.path.as_str(), member).is_none(),
            "duplicate member in package index: {}",
            member.path
        );
    }
    let actual = collect_relative_files(root)?
        .into_iter()
        .filter(|path| path != PACKAGE_INDEX_PATH && path != PACKAGE_INDEX_SIGNATURE_PATH)
        .collect::<BTreeSet<_>>();
    let expected_paths = expected
        .keys()
        .map(|path| (*path).to_owned())
        .collect::<BTreeSet<_>>();
    ensure!(
        actual == expected_paths,
        "package members differ from signed index"
    );
    for (path, member) in expected {
        let full_path = checked_join(root, path)?;
        let metadata = fs::metadata(&full_path)?;
        ensure!(
            metadata.len() == member.size,
            "member size mismatch: {path}"
        );
        ensure!(
            hash_file(&full_path)? == member.sha256,
            "member hash mismatch: {path}"
        );
        ensure!(!member.media_type.is_empty(), "member media type is empty");
    }
    Ok(())
}

fn verify_proof_bundle_members(root: &Path, index: &ProofBundleIndex) -> Result<()> {
    let mut expected = BTreeMap::new();
    for member in &index.members {
        ensure!(
            expected.insert(member.path.as_str(), member).is_none(),
            "duplicate proof bundle member: {}",
            member.path
        );
    }
    let actual = collect_relative_files(root)?
        .into_iter()
        .filter(|path| path != PROOF_BUNDLE_INDEX_PATH && path != PROOF_BUNDLE_INDEX_SIGNATURE_PATH)
        .collect::<BTreeSet<_>>();
    let expected_paths = expected
        .keys()
        .map(|path| (*path).to_owned())
        .collect::<BTreeSet<_>>();
    ensure!(
        actual == expected_paths,
        "proof bundle members differ from signed index"
    );
    for (path, member) in expected {
        let full_path = checked_join(root, path)?;
        ensure!(
            fs::metadata(&full_path)?.len() == member.size,
            "proof member size mismatch: {path}"
        );
        ensure!(
            hash_file(&full_path)? == member.sha256,
            "proof member hash mismatch: {path}"
        );
    }
    Ok(())
}

fn verify_attestation_proofs(
    root: &Path,
    document: &serde_json::Value,
    timestamp_trust: TimestampTrust<'_>,
) -> Result<()> {
    if let Some(timestamp) = document.get("timestamp") {
        let request_path = json_string(timestamp, "request_path")?;
        verify_timestamp_query(
            &checked_join(root, request_path)?,
            json_string(document, "manifest_hash")?,
        )?;
        if json_string(document, "timestamp_status")? == "valid" {
            verify_timestamp_response(root, timestamp, timestamp_trust)?;
        }
    }
    if let Some(blockchain) = document.get("blockchain") {
        let merkle_path = json_string(blockchain, "merkle_proof_path")?;
        let proof: MerkleProofDocument = read_json(&checked_join(root, merkle_path)?)?;
        verify_merkle_document(&proof, json_string(document, "manifest_hash")?)?;
        if let Some(complement_path) = blockchain
            .get("ots_complement_path")
            .and_then(serde_json::Value::as_str)
        {
            let complement = checked_join(root, complement_path)?;
            ensure!(
                hash_file(&complement)? == json_string(blockchain, "ots_complement_hash")?,
                "OpenTimestamps complement hash mismatch"
            );
        }
        if let Some(ots_path) = blockchain
            .get("ots_proof_path")
            .and_then(serde_json::Value::as_str)
        {
            let original = checked_join(root, ots_path)?;
            let selected = blockchain
                .get("ots_complement_path")
                .and_then(serde_json::Value::as_str)
                .map(|path| checked_join(root, path))
                .transpose()?
                .unwrap_or(original);
            verify_ots_document(
                &proof.root_hash,
                &selected,
                json_string(document, "blockchain_status")?,
            )?;
        }
    }
    Ok(())
}

fn verify_timestamp_response(
    root: &Path,
    timestamp: &serde_json::Value,
    trust: TimestampTrust<'_>,
) -> Result<()> {
    let request = checked_join(root, json_string(timestamp, "request_path")?)?;
    let response = checked_join(root, json_string(timestamp, "response_path")?)?;
    let chain = checked_join(root, json_string(timestamp, "chain_path")?)?;
    let gen_time = json_string(timestamp, "gen_time")?;
    let policy = json_string(timestamp, "policy")?;
    let ca_bundle = trust
        .ca_bundle
        .ok_or_else(|| anyhow!("valid RFC 3161 proof requires --tsa-ca-bundle"))?;
    let crl_bundle = trust
        .crl_bundle
        .ok_or_else(|| anyhow!("valid RFC 3161 proof requires --tsa-crl-bundle"))?;
    let temporary = tempfile::tempdir().context("create RFC 3161 trust directory")?;
    let combined_trust = temporary.path().join("trust.pem");
    let mut trust_bytes = fs::read(ca_bundle).context("read TSA CA bundle")?;
    trust_bytes.push(b'\n');
    trust_bytes.extend(fs::read(crl_bundle).context("read TSA CRL bundle")?);
    fs::write(&combined_trust, trust_bytes)?;
    let verification = Command::new("openssl")
        .args(["ts", "-verify", "-queryfile"])
        .arg(&request)
        .args(["-in"])
        .arg(&response)
        .args(["-CAfile"])
        .arg(&combined_trust)
        .args(["-untrusted"])
        .arg(&chain)
        .args(["-purpose", "timestampsign", "-crl_check_all"])
        .output()
        .context("run RFC 3161 response verification")?;
    ensure!(
        verification.status.success(),
        "RFC 3161 response verification failed: {}",
        String::from_utf8_lossy(&verification.stderr)
    );
    let inspection = Command::new("openssl")
        .args(["ts", "-reply", "-in"])
        .arg(&response)
        .arg("-text")
        .output()
        .context("inspect RFC 3161 response")?;
    ensure!(inspection.status.success(), "invalid RFC 3161 response");
    let text = String::from_utf8_lossy(&inspection.stdout);
    ensure!(
        text.lines()
            .any(|line| line.trim() == format!("Policy OID: {policy}")),
        "RFC 3161 policy differs from attestation"
    );
    let parsed_time = chrono::DateTime::parse_from_rfc3339(gen_time)
        .context("attested RFC 3161 genTime is invalid")?
        .with_timezone(&Utc)
        .format("%b %e %H:%M:%S %Y GMT")
        .to_string();
    ensure!(
        text.lines()
            .any(|line| line.trim() == format!("Time stamp: {parsed_time}")),
        "RFC 3161 genTime differs from attestation"
    );
    Ok(())
}

fn verify_ots_document(root_hash: &str, proof_path: &Path, status: &str) -> Result<()> {
    let root_digest = decode_sha256_identifier(root_hash)?;
    let temporary = tempfile::tempdir().context("create OpenTimestamps verification directory")?;
    let root_file = temporary.path().join("root.bin");
    fs::write(&root_file, root_digest)?;
    match status {
        "pending_confirmation" | "submitted" => {
            let output = Command::new("ots")
                .arg("info")
                .arg(proof_path)
                .output()
                .context("run OpenTimestamps proof inspection")?;
            ensure!(
                output.status.success(),
                "invalid OpenTimestamps proof: {}",
                String::from_utf8_lossy(&output.stderr)
            );
            let text = format!(
                "{}\n{}",
                String::from_utf8_lossy(&output.stdout),
                String::from_utf8_lossy(&output.stderr)
            );
            ensure!(
                text.contains("PendingAttestation")
                    || text.contains("BitcoinBlockHeaderAttestation"),
                "OpenTimestamps proof has no recognized attestation"
            );
        }
        "confirmed" => {
            let output = Command::new("ots")
                .args(["verify", "-f"])
                .arg(&root_file)
                .arg(proof_path)
                .output()
                .context("run OpenTimestamps verification")?;
            ensure!(
                output.status.success(),
                "OpenTimestamps confirmation is invalid: {}",
                String::from_utf8_lossy(&output.stderr)
            );
        }
        "not_submitted" => {}
        "verification_failed" => bail!("attestation records an invalid OpenTimestamps proof"),
        other => bail!("unsupported blockchain status: {other}"),
    }
    Ok(())
}

fn verify_timestamp_query(path: &Path, expected_manifest_hash: &str) -> Result<()> {
    let output = Command::new("openssl")
        .args(["ts", "-query", "-in"])
        .arg(path)
        .arg("-text")
        .output()
        .context("run openssl timestamp query inspection")?;
    ensure!(
        output.status.success(),
        "invalid RFC 3161 timestamp query: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let normalized = String::from_utf8_lossy(&output.stdout)
        .chars()
        .filter(|character| character.is_ascii_hexdigit())
        .collect::<String>()
        .to_lowercase();
    ensure!(
        normalized.contains(expected_manifest_hash.trim_start_matches("sha256:")),
        "RFC 3161 query digest differs from manifest"
    );
    Ok(())
}

fn verify_merkle_document(proof: &MerkleProofDocument, expected_manifest_hash: &str) -> Result<()> {
    ensure!(
        proof.schema_version == "0.1.0" && proof.algorithm == "sha256-domain-separated-v1",
        "unsupported Merkle proof"
    );
    ensure!(
        proof.manifest_hash == expected_manifest_hash,
        "Merkle proof manifest hash mismatch"
    );
    let salt = decode_array::<32>(&proof.salt_hex, "Merkle salt")?;
    let manifest_digest = decode_sha256_identifier(&proof.manifest_hash)?;
    let mut leaf_hasher = Sha256::new();
    leaf_hasher.update([0_u8]);
    leaf_hasher.update(salt);
    leaf_hasher.update(manifest_digest);
    let mut current: [u8; 32] = leaf_hasher.finalize().into();
    for step in &proof.steps {
        let sibling = decode_sha256_identifier(&step.hash)?;
        let mut branch_hasher = Sha256::new();
        branch_hasher.update([1_u8]);
        match step.side.as_str() {
            "left" => {
                branch_hasher.update(sibling);
                branch_hasher.update(current);
            }
            "right" => {
                branch_hasher.update(current);
                branch_hasher.update(sibling);
            }
            _ => bail!("invalid Merkle proof side"),
        }
        current = branch_hasher.finalize().into();
    }
    ensure!(
        format!("sha256:{}", hex::encode(current)) == proof.root_hash,
        "Merkle proof root mismatch"
    );
    Ok(())
}

fn decode_sha256_identifier(value: &str) -> Result<[u8; 32]> {
    let digest = value
        .strip_prefix("sha256:")
        .ok_or_else(|| anyhow!("invalid SHA-256 identifier"))?;
    decode_array::<32>(digest, "SHA-256 digest")
}

fn merge_temporal_status(
    current: &'static str,
    document: &serde_json::Value,
) -> Result<&'static str> {
    let timestamp = json_string(document, "timestamp_status")?;
    let blockchain = json_string(document, "blockchain_status")?;
    if timestamp == "invalid" || blockchain == "verification_failed" {
        bail!("attestation records an invalid external proof");
    }
    if timestamp == "failed" {
        return Ok(if current == "not_requested" {
            "external_service_failed"
        } else {
            current
        });
    }
    if blockchain == "confirmed" {
        return Ok("confirmed");
    }
    if timestamp == "valid" {
        return Ok(if current == "confirmed" {
            "confirmed"
        } else {
            "timestamp_valid"
        });
    }
    if timestamp == "pending" || blockchain == "pending_confirmation" {
        return Ok(match current {
            "confirmed" => "confirmed",
            "timestamp_valid" => "timestamp_valid",
            _ => "pending",
        });
    }
    Ok(current)
}

fn extract_safely(package_path: &Path) -> Result<TempDir> {
    let temporary = tempfile::tempdir().context("create verifier temporary directory")?;
    let file = File::open(package_path)?;
    let mut archive = ZipArchive::new(BufReader::new(file)).context("open ZIP package")?;
    ensure!(
        archive.len() <= MAX_ENTRIES,
        "package exceeds maximum entry count"
    );

    let mut names = BTreeSet::new();
    let mut total_size = 0_u64;
    for index in 0..archive.len() {
        let mut entry = archive.by_index(index)?;
        let name = entry.name().to_owned();
        ensure!(names.insert(name.clone()), "duplicate ZIP member: {name}");
        ensure!(!entry.is_dir(), "directory ZIP entries are not allowed");
        ensure!(
            is_safe_relative_path(Path::new(&name)),
            "unsafe ZIP path: {name}"
        );
        if let Some(mode) = entry.unix_mode() {
            ensure!(
                mode & 0o170000 != 0o120000,
                "symlink is not allowed: {name}"
            );
        }
        ensure!(
            entry.size() <= MAX_FILE_SIZE,
            "ZIP member is too large: {name}"
        );
        if entry.compressed_size() > 0 {
            ensure!(
                entry.size()
                    <= entry
                        .compressed_size()
                        .saturating_mul(MAX_COMPRESSION_RATIO),
                "suspicious compression ratio: {name}"
            );
        }
        total_size = total_size
            .checked_add(entry.size())
            .ok_or_else(|| anyhow!("ZIP size overflow"))?;
        ensure!(
            total_size <= MAX_TOTAL_SIZE,
            "package exceeds maximum expanded size"
        );

        let target = checked_join(temporary.path(), &name)?;
        if let Some(parent) = target.parent() {
            fs::create_dir_all(parent)?;
        }
        let mut output = BufWriter::new(File::create(&target)?);
        let copied = io::copy(&mut entry.by_ref().take(MAX_FILE_SIZE + 1), &mut output)?;
        ensure!(
            copied == entry.size(),
            "ZIP member size changed while reading"
        );
        output.flush()?;
    }
    Ok(temporary)
}

fn copy_source(source: &Path, target: &Path) -> Result<()> {
    for entry in WalkDir::new(source).follow_links(false) {
        let entry = entry?;
        if entry.file_type().is_symlink() {
            bail!("source symlink is not allowed: {}", entry.path().display());
        }
        if !entry.file_type().is_file() {
            continue;
        }
        let relative = entry.path().strip_prefix(source)?;
        ensure!(is_safe_relative_path(relative), "unsafe source path");
        let destination = target.join(relative);
        if let Some(parent) = destination.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::copy(entry.path(), destination)?;
    }
    Ok(())
}

fn collect_members(root: &Path, excluded: &[&str]) -> Result<Vec<PackageMember>> {
    let excluded = excluded.iter().copied().collect::<BTreeSet<_>>();
    collect_relative_files(root)?
        .into_iter()
        .filter(|path| !excluded.contains(path.as_str()))
        .map(|path| {
            let full_path = checked_join(root, &path)?;
            let metadata = fs::metadata(&full_path)?;
            Ok(PackageMember {
                media_type: mime_guess::from_path(&path)
                    .first_or_octet_stream()
                    .essence_str()
                    .to_owned(),
                path,
                size: metadata.len(),
                sha256: hash_file(&full_path)?,
            })
        })
        .collect()
}

fn collect_relative_files(root: &Path) -> Result<Vec<String>> {
    let mut files = Vec::new();
    for entry in WalkDir::new(root).follow_links(false) {
        let entry = entry?;
        if entry.file_type().is_symlink() {
            bail!("symlink is not allowed: {}", entry.path().display());
        }
        if entry.file_type().is_file() {
            let relative = entry.path().strip_prefix(root)?;
            ensure!(is_safe_relative_path(relative), "unsafe package path");
            files.push(path_to_package_name(relative)?);
        }
    }
    files.sort();
    Ok(files)
}

fn create_zip(root: &Path, output: &Path) -> Result<()> {
    let file = File::create(output)?;
    let mut writer = ZipWriter::new(BufWriter::new(file));
    let options = SimpleFileOptions::default()
        .compression_method(CompressionMethod::Deflated)
        .unix_permissions(0o644);
    for relative in collect_relative_files(root)? {
        writer.start_file(&relative, options)?;
        let mut input = BufReader::new(File::open(checked_join(root, &relative)?)?);
        io::copy(&mut input, &mut writer)?;
    }
    writer.finish()?;
    Ok(())
}

fn read_json<T: for<'de> Deserialize<'de>>(path: &Path) -> Result<T> {
    ensure!(
        fs::metadata(path)?.len() <= MAX_METADATA_FILE_SIZE,
        "JSON metadata file is too large: {}",
        path.display()
    );
    let bytes = fs::read(path).with_context(|| format!("read {}", path.display()))?;
    serde_json::from_slice(&bytes).with_context(|| format!("parse {}", path.display()))
}

fn read_json_lines<T: for<'de> Deserialize<'de>>(path: &Path) -> Result<Vec<T>> {
    ensure!(
        fs::metadata(path)?.len() <= MAX_METADATA_FILE_SIZE,
        "JSONL metadata file is too large: {}",
        path.display()
    );
    let reader =
        BufReader::new(File::open(path).with_context(|| format!("read {}", path.display()))?);
    reader
        .lines()
        .enumerate()
        .map(|(index, line)| {
            let line = line?;
            ensure!(!line.trim().is_empty(), "blank JSONL line at {}", index + 1);
            serde_json::from_str(&line)
                .with_context(|| format!("parse {} line {}", path.display(), index + 1))
        })
        .collect()
}

fn json_u64(value: &serde_json::Value, field: &str) -> Result<u64> {
    value
        .get(field)
        .and_then(serde_json::Value::as_u64)
        .ok_or_else(|| anyhow!("missing or invalid {field}"))
}

fn json_string<'a>(value: &'a serde_json::Value, field: &str) -> Result<&'a str> {
    value
        .get(field)
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| anyhow!("missing or invalid {field}"))
}

fn write_hex_file(path: &Path, bytes: &[u8]) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, format!("{}\n", hex::encode(bytes)))?;
    Ok(())
}

fn read_hex_array<const N: usize>(path: &Path) -> Result<[u8; N]> {
    let value =
        fs::read_to_string(path).with_context(|| format!("read signature {}", path.display()))?;
    decode_array(value.trim(), "signature")
}

pub fn decode_array<const N: usize>(value: &str, label: &str) -> Result<[u8; N]> {
    let bytes = hex::decode(value).with_context(|| format!("invalid {label} hexadecimal"))?;
    bytes
        .try_into()
        .map_err(|_| anyhow!("{label} must contain {N} bytes"))
}

fn hash_file(path: &Path) -> Result<String> {
    let mut reader = BufReader::new(File::open(path)?);
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let read = reader.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(format!("sha256:{}", hex::encode(hasher.finalize())))
}

fn hash_path_for(package_path: &Path) -> PathBuf {
    let mut value = package_path.as_os_str().to_owned();
    value.push(".sha256");
    PathBuf::from(value)
}

fn file_name(path: &Path) -> Result<&str> {
    path.file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| anyhow!("output path has no UTF-8 filename"))
}

fn checked_join(root: &Path, relative: &str) -> Result<PathBuf> {
    let path = Path::new(relative);
    ensure!(
        is_safe_relative_path(path),
        "unsafe package path: {relative}"
    );
    Ok(root.join(path))
}

fn is_safe_relative_path(path: &Path) -> bool {
    !path.as_os_str().is_empty()
        && !path.is_absolute()
        && path
            .components()
            .all(|component| matches!(component, Component::Normal(_)))
}

fn path_to_package_name(path: &Path) -> Result<String> {
    let parts = path
        .components()
        .map(|component| match component {
            Component::Normal(value) => value
                .to_str()
                .map(ToOwned::to_owned)
                .ok_or_else(|| anyhow!("package path is not UTF-8")),
            _ => Err(anyhow!("unsafe package path")),
        })
        .collect::<Result<Vec<_>>>()?;
    Ok(parts.join("/"))
}

fn escape_html(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#39;")
}

#[cfg(test)]
mod tests {
    use super::*;
    use chitaozinho_protocol::{CAPTURE_CLOSE_DOMAIN, sha256_identifier, sign_canonical};
    use serde_json::json;

    #[test]
    fn path_validation_rejects_unsafe_names() {
        assert!(is_safe_relative_path(Path::new("capture/video.webm")));
        assert!(!is_safe_relative_path(Path::new("../secret")));
        assert!(!is_safe_relative_path(Path::new("/absolute")));
        assert!(!is_safe_relative_path(Path::new("capture/../secret")));
        assert!(!is_safe_relative_path(Path::new("")));
    }

    #[test]
    fn decoder_checks_size() {
        assert!(decode_array::<2>("aabb", "test").is_ok());
        assert!(decode_array::<2>("aa", "test").is_err());
        assert!(decode_array::<2>("not-hex", "test").is_err());
    }

    #[test]
    fn html_report_escapes_untrusted_session_id() {
        let temporary = tempfile::tempdir().unwrap();
        let report_path = temporary.path().join("report.html");
        let report = VerificationReport {
            result: "integral",
            session_id: "<script>alert(1)</script>".to_owned(),
            members_verified: 1,
            checks: vec!["member_hashes"],
            temporal_proof: "not_provided",
            attestations_verified: 0,
        };
        write_html_report(&report, &report_path).unwrap();
        let html = fs::read_to_string(report_path).unwrap();
        assert!(!html.contains("<script>"));
        assert!(html.contains("&lt;script&gt;"));
        assert!(html.contains("íntegro"));
        assert!(html.contains("não comprova autoria"));
    }

    #[test]
    fn package_round_trip_preserves_source() {
        let temporary = tempfile::tempdir().unwrap();
        let source = temporary.path().join("source");
        let package_path = temporary.path().join("evidence.zip");
        let seed = [7_u8; 32];
        let public_key = SigningKey::from_bytes(&seed).verifying_key().to_bytes();
        create_fixture(&source, &seed, &public_key);

        let result = pack(&source, &package_path, &seed).unwrap();
        assert!(result.package_path.is_file());
        assert!(result.hash_path.is_file());
        assert!(!source.join(PACKAGE_INDEX_PATH).exists());
        assert!(!source.join(MANIFEST_SIGNATURE_PATH).exists());

        let report = verify(&package_path, &public_key).unwrap();
        assert_eq!(report.result, "integral");
        assert_eq!(report.session_id, "session-test");
        assert!(report.members_verified >= 5);
    }

    #[test]
    fn verifies_signed_attestation_chain_and_merkle_proof_bundle() {
        let temporary = tempfile::tempdir().unwrap();
        let source = temporary.path().join("source");
        let package_path = temporary.path().join("evidence.zip");
        let proof_bundle_path = temporary.path().join("proofs.zip");
        let seed = [17_u8; 32];
        let public_key = SigningKey::from_bytes(&seed).verifying_key().to_bytes();
        create_fixture(&source, &seed, &public_key);
        pack(&source, &package_path, &seed).unwrap();
        create_proof_bundle_fixture(&source, &proof_bundle_path, &seed, false);

        let report = verify_with_proof_bundle_and_trust(
            &package_path,
            &proof_bundle_path,
            &public_key,
            None,
            None,
        )
        .unwrap();
        assert_eq!(report.attestations_verified, 1);
        assert_eq!(report.temporal_proof, "not_requested");
        assert!(report.checks.contains(&"external_proof_bundle"));
    }

    #[test]
    fn rejects_invalid_merkle_proof_in_signed_bundle() {
        let temporary = tempfile::tempdir().unwrap();
        let source = temporary.path().join("source");
        let package_path = temporary.path().join("evidence.zip");
        let proof_bundle_path = temporary.path().join("proofs.zip");
        let seed = [18_u8; 32];
        let public_key = SigningKey::from_bytes(&seed).verifying_key().to_bytes();
        create_fixture(&source, &seed, &public_key);
        pack(&source, &package_path, &seed).unwrap();
        create_proof_bundle_fixture(&source, &proof_bundle_path, &seed, true);

        let error = verify_with_proof_bundle_and_trust(
            &package_path,
            &proof_bundle_path,
            &public_key,
            None,
            None,
        )
        .unwrap_err()
        .to_string();
        assert!(error.contains("Merkle proof root mismatch"), "{error}");
    }

    #[test]
    fn detects_single_byte_artifact_change() {
        let temporary = tempfile::tempdir().unwrap();
        let source = temporary.path().join("source");
        let package_path = temporary.path().join("evidence.zip");
        let tampered_path = temporary.path().join("tampered.zip");
        let seed = [8_u8; 32];
        let public_key = SigningKey::from_bytes(&seed).verifying_key().to_bytes();
        create_fixture(&source, &seed, &public_key);
        pack(&source, &package_path, &seed).unwrap();
        rewrite_zip(
            &package_path,
            &tampered_path,
            Some("capture/recording.webm"),
        );

        let error = verify(&tampered_path, &public_key).unwrap_err().to_string();
        assert!(error.contains("member hash mismatch"), "{error}");
    }

    #[test]
    fn rejects_path_traversal_zip() {
        let temporary = tempfile::tempdir().unwrap();
        let package_path = temporary.path().join("unsafe.zip");
        let file = File::create(&package_path).unwrap();
        let mut writer = ZipWriter::new(file);
        writer
            .start_file("../escape", SimpleFileOptions::default())
            .unwrap();
        writer.write_all(b"unsafe").unwrap();
        writer.finish().unwrap();

        let error = verify(&package_path, &[0_u8; 32]).unwrap_err().to_string();
        assert!(error.contains("unsafe ZIP path"), "{error}");
        assert!(!temporary.path().join("escape").exists());
    }

    #[test]
    fn zip_builder_rejects_duplicate_members() {
        let temporary = tempfile::tempdir().unwrap();
        let package_path = temporary.path().join("duplicate.zip");
        let file = File::create(&package_path).unwrap();
        let mut writer = ZipWriter::new(file);
        writer
            .start_file("duplicate", SimpleFileOptions::default())
            .unwrap();
        writer.write_all(b"first").unwrap();
        let error = writer
            .start_file("duplicate", SimpleFileOptions::default())
            .unwrap_err()
            .to_string();
        assert!(error.contains("Duplicate filename"), "{error}");
    }

    #[test]
    fn packer_rejects_entry_sequence_gap() {
        let temporary = tempfile::tempdir().unwrap();
        let source = temporary.path().join("source");
        let package_path = temporary.path().join("evidence.zip");
        let seed = [9_u8; 32];
        let public_key = SigningKey::from_bytes(&seed).verifying_key().to_bytes();
        create_fixture(&source, &seed, &public_key);

        let mut record: ChainRecord = read_json_lines(&source.join(ENTRIES_PATH))
            .unwrap()
            .remove(0);
        record.entry["sequence"] = json!(1);
        record.entry_hash = sha256_identifier(&canonical_bytes(&record.entry).unwrap());
        record.signature_hex =
            hex::encode(sign_canonical(ENTRY_DOMAIN, &record.entry, &seed).unwrap());
        fs::write(
            source.join(ENTRIES_PATH),
            format!(
                "{}\n",
                String::from_utf8(canonical_bytes(&record).unwrap()).unwrap()
            ),
        )
        .unwrap();

        let error = pack(&source, &package_path, &seed).unwrap_err().to_string();
        assert!(error.contains("entry sequence has a gap"), "{error}");
    }

    fn create_fixture(source: &Path, seed: &[u8; 32], public_key: &[u8; 32]) {
        fs::create_dir_all(source.join("capture")).unwrap();
        fs::create_dir_all(source.join("chain")).unwrap();
        fs::create_dir_all(source.join("signatures")).unwrap();
        fs::write(source.join("capture/recording.webm"), b"original bytes").unwrap();

        let artifact_hash = sha256_identifier(b"original bytes");
        let entry = json!({
            "protocol_version": "0.1.0",
            "entry_type": "artifact_part",
            "session_id": "session-test",
            "sequence": 0,
            "artifact_id": "recording",
            "part_number": 0,
            "part_hash": artifact_hash,
            "previous_entry_hash": null,
            "client_clock_id": "clock-test",
            "client_monotonic_time": 1,
            "client_wall_time": "2026-07-30T15:00:00-03:00",
            "server_challenge": "AQID"
        });
        let entry_hash = sha256_identifier(&canonical_bytes(&entry).unwrap());
        let entry_signature = sign_canonical(ENTRY_DOMAIN, &entry, seed).unwrap();
        let chain_record = ChainRecord {
            entry,
            entry_hash: entry_hash.clone(),
            signature_hex: hex::encode(entry_signature),
        };
        fs::write(
            source.join(ENTRIES_PATH),
            format!(
                "{}\n",
                String::from_utf8(canonical_bytes(&chain_record).unwrap()).unwrap()
            ),
        )
        .unwrap();

        let receipt = json!({
            "protocol_version": "0.1.0",
            "session_id": "session-test",
            "sequence": 0,
            "entry_hash": entry_hash,
            "artifact_id": "recording",
            "part_number": 0,
            "part_hash": artifact_hash,
            "previous_receipt_hash": null,
            "server_time": "2026-07-30T18:00:01Z",
            "persistence_state": "durable_staging"
        });
        let receipt_hash = sha256_identifier(&canonical_bytes(&receipt).unwrap());
        let receipt_signature = sign_canonical(RECEIPT_DOMAIN, &receipt, seed).unwrap();
        let receipt_record = ReceiptRecord {
            receipt,
            receipt_hash,
            signature_hex: hex::encode(receipt_signature),
        };
        fs::write(
            source.join(RECEIPTS_PATH),
            format!(
                "{}\n",
                String::from_utf8(canonical_bytes(&receipt_record).unwrap()).unwrap()
            ),
        )
        .unwrap();

        let close = json!({
            "protocol_version": "0.1.0",
            "session_id": "session-test",
            "session_root": entry_hash,
            "last_entry_hash": entry_hash,
            "entry_count": 1,
            "artifacts": [{
                "artifact_id": "recording",
                "path": "capture/recording.webm",
                "size": 14,
                "status": "captured",
                "artifact_hash": artifact_hash
            }],
            "known_gaps": [],
            "client_key_id": "client-test",
            "client_public_key": "AQID"
        });
        fs::write(
            source.join("chain/capture-close.json"),
            canonical_bytes(&close).unwrap(),
        )
        .unwrap();
        let close_signature = sign_canonical(CAPTURE_CLOSE_DOMAIN, &close, seed).unwrap();
        write_hex_file(
            &source.join("signatures/capture-close.client.sig"),
            &close_signature,
        )
        .unwrap();

        let keys = json!({
            "schema_version": "0.1.0",
            "server": {
                "key_id": "server-test",
                "algorithm": "Ed25519",
                "public_key_hex": hex::encode(public_key)
            },
            "client": {
                "key_id": "client-test",
                "algorithm": "Ed25519",
                "public_key_hex": hex::encode(public_key)
            }
        });
        fs::write(
            source.join(PUBLIC_KEYS_PATH),
            canonical_bytes(&keys).unwrap(),
        )
        .unwrap();

        let manifest = json!({
            "schema_version": "0.1.0",
            "session_id": "session-test",
            "status": "complete",
            "capture": {
                "started_at_client": "2026-07-30T15:00:00-03:00",
                "ended_at_client": "2026-07-30T15:01:00-03:00",
                "started_at_server": "2026-07-30T18:00:00Z",
                "ended_at_server": "2026-07-30T18:01:00Z",
                "software": {
                    "name": "Chitãozinho Test",
                    "version": "0.1.0",
                    "commit": "test",
                    "build_hash": sha256_identifier(b"test-build")
                }
            },
            "artifacts": [{
                "artifact_id": "recording",
                "path": "capture/recording.webm",
                "size": 14,
                "media_type": "video/webm",
                "status": "captured",
                "method": "test",
                "provenance": "client_reported",
                "artifact_hash": artifact_hash
            }],
            "chain": {
                "first_hash": entry_hash,
                "last_hash": entry_hash,
                "entry_count": 1,
                "root_hash": entry_hash
            },
            "capture_close": {
                "path": "chain/capture-close.json",
                "client_signature_path": "signatures/capture-close.client.sig"
            },
            "limitations": [
                "Does not prove authorship.",
                "Does not prove material truth."
            ]
        });
        fs::write(
            source.join(MANIFEST_PATH),
            canonical_bytes(&manifest).unwrap(),
        )
        .unwrap();
    }

    fn create_proof_bundle_fixture(
        source: &Path,
        output: &Path,
        seed: &[u8; 32],
        invalid_root: bool,
    ) {
        let staging = tempfile::tempdir().unwrap();
        let manifest: serde_json::Value = read_json(&source.join(MANIFEST_PATH)).unwrap();
        let manifest_hash = sha256_identifier(&canonical_bytes(&manifest).unwrap());
        let salt = [23_u8; 32];
        let manifest_digest = decode_sha256_identifier(&manifest_hash).unwrap();
        let mut hasher = Sha256::new();
        hasher.update([0_u8]);
        hasher.update(salt);
        hasher.update(manifest_digest);
        let calculated_root: [u8; 32] = hasher.finalize().into();
        let root_hash = if invalid_root {
            format!("sha256:{}", "ff".repeat(32))
        } else {
            format!("sha256:{}", hex::encode(calculated_root))
        };
        let merkle_path = "merkle/session-test.proof.json";
        let proof = json!({
            "schema_version": "0.1.0",
            "algorithm": "sha256-domain-separated-v1",
            "manifest_hash": manifest_hash,
            "salt_hex": hex::encode(salt),
            "root_hash": root_hash,
            "steps": []
        });
        let proof_target = staging.path().join(merkle_path);
        fs::create_dir_all(proof_target.parent().unwrap()).unwrap();
        fs::write(&proof_target, canonical_bytes(&proof).unwrap()).unwrap();

        let document = json!({
            "schema_version": "0.1.0",
            "attestation_id": "session-test-0001",
            "previous_attestation_hash": null,
            "manifest_hash": manifest_hash,
            "created_at": "2026-07-30T18:02:00Z",
            "issuer_key_id": "server-test",
            "timestamp_status": "not_requested",
            "blockchain_status": "not_submitted",
            "blockchain": {
                "merkle_proof_path": merkle_path,
                "checked_at": "2026-07-30T18:02:00Z"
            }
        });
        let record = json!({
            "document_hash": sha256_identifier(&canonical_bytes(&document).unwrap()),
            "signature_hex": hex::encode(
                sign_canonical(ATTESTATION_DOMAIN, &document, seed).unwrap()
            ),
            "document": document
        });
        fs::write(
            staging.path().join(ATTESTATIONS_PATH),
            [canonical_bytes(&record).unwrap(), b"\n".to_vec()].concat(),
        )
        .unwrap();

        let members = [ATTESTATIONS_PATH, merkle_path]
            .into_iter()
            .map(|path| {
                let full_path = staging.path().join(path);
                ProofBundleMember {
                    path: path.to_owned(),
                    size: fs::metadata(&full_path).unwrap().len(),
                    sha256: hash_file(&full_path).unwrap(),
                }
            })
            .collect();
        let index = ProofBundleIndex {
            schema_version: "0.1.0".to_owned(),
            session_id: "session-test".to_owned(),
            manifest_hash,
            created_at: "2026-07-30T18:02:00Z".to_owned(),
            members,
        };
        fs::write(
            staging.path().join(PROOF_BUNDLE_INDEX_PATH),
            canonical_bytes(&index).unwrap(),
        )
        .unwrap();
        write_hex_file(
            &staging.path().join(PROOF_BUNDLE_INDEX_SIGNATURE_PATH),
            &sign_canonical(PROOF_BUNDLE_INDEX_DOMAIN, &index, seed).unwrap(),
        )
        .unwrap();
        create_zip(staging.path(), output).unwrap();
    }

    fn rewrite_zip(source: &Path, target: &Path, altered_path: Option<&str>) {
        let mut input = ZipArchive::new(File::open(source).unwrap()).unwrap();
        let mut writer = ZipWriter::new(File::create(target).unwrap());
        let options = SimpleFileOptions::default().compression_method(CompressionMethod::Deflated);
        for index in 0..input.len() {
            let mut entry = input.by_index(index).unwrap();
            let name = entry.name().to_owned();
            writer.start_file(&name, options).unwrap();
            if altered_path == Some(name.as_str()) {
                writer.write_all(b"Original bytes").unwrap();
            } else {
                io::copy(&mut entry, &mut writer).unwrap();
            }
        }
        writer.finish().unwrap();
    }
}
