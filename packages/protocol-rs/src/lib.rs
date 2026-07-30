use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use serde::Serialize;
use sha2::{Digest, Sha256};

pub const ENTRY_DOMAIN: &[u8] = b"CHITAOZINHO/ENTRY/v1";
pub const RECEIPT_DOMAIN: &[u8] = b"CHITAOZINHO/RECEIPT/v1";
pub const CAPTURE_CLOSE_DOMAIN: &[u8] = b"CHITAOZINHO/CAPTURE_CLOSE/v1";
pub const MANIFEST_DOMAIN: &[u8] = b"CHITAOZINHO/MANIFEST/v1";
pub const PACKAGE_INDEX_DOMAIN: &[u8] = b"CHITAOZINHO/PACKAGE_INDEX/v1";
pub const ATTESTATION_DOMAIN: &[u8] = b"CHITAOZINHO/ATTESTATION/v1";

#[derive(Debug, thiserror::Error)]
pub enum ProtocolError {
    #[error("canonical JSON serialization failed: {0}")]
    Canonicalization(#[from] serde_json::Error),
    #[error("invalid Ed25519 signature")]
    InvalidSignature,
}

pub fn canonical_bytes<T: Serialize>(value: &T) -> Result<Vec<u8>, ProtocolError> {
    Ok(serde_jcs::to_vec(value)?)
}

pub fn sha256_bytes(data: &[u8]) -> [u8; 32] {
    Sha256::digest(data).into()
}

pub fn sha256_identifier(data: &[u8]) -> String {
    format!("sha256:{}", hex::encode(sha256_bytes(data)))
}

pub fn hash_canonical<T: Serialize>(value: &T) -> Result<[u8; 32], ProtocolError> {
    Ok(sha256_bytes(&canonical_bytes(value)?))
}

pub fn sign_canonical<T: Serialize>(
    domain: &[u8],
    value: &T,
    private_seed: &[u8; 32],
) -> Result<[u8; 64], ProtocolError> {
    let mut message = Vec::with_capacity(domain.len() + 32);
    message.extend_from_slice(domain);
    message.extend_from_slice(&hash_canonical(value)?);
    Ok(SigningKey::from_bytes(private_seed)
        .sign(&message)
        .to_bytes())
}

pub fn verify_canonical<T: Serialize>(
    domain: &[u8],
    value: &T,
    signature: &[u8; 64],
    public_key: &[u8; 32],
) -> Result<(), ProtocolError> {
    let mut message = Vec::with_capacity(domain.len() + 32);
    message.extend_from_slice(domain);
    message.extend_from_slice(&hash_canonical(value)?);
    VerifyingKey::from_bytes(public_key)
        .map_err(|_| ProtocolError::InvalidSignature)?
        .verify(&message, &Signature::from_bytes(signature))
        .map_err(|_| ProtocolError::InvalidSignature)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::Deserialize;
    use serde_json::Value;

    #[derive(Deserialize)]
    struct Vector {
        entry: Value,
        canonical_json: String,
        sha256: String,
        private_seed_hex: String,
        public_key_hex: String,
        signature_hex: String,
    }

    fn vector() -> Vector {
        serde_json::from_str(include_str!("../../../test-vectors/protocol-v0.1.json")).unwrap()
    }

    fn array_from_hex<const N: usize>(value: &str) -> [u8; N] {
        hex::decode(value).unwrap().try_into().unwrap()
    }

    #[test]
    fn canonicalizes_and_hashes_identically() {
        let vector = vector();
        let canonical = canonical_bytes(&vector.entry).unwrap();
        assert_eq!(
            String::from_utf8(canonical.clone()).unwrap(),
            vector.canonical_json
        );
        assert_eq!(sha256_identifier(&canonical), vector.sha256);
    }

    #[test]
    fn signs_and_verifies_identically() {
        let vector = vector();
        let private_seed = array_from_hex(&vector.private_seed_hex);
        let public_key = array_from_hex(&vector.public_key_hex);
        let expected_signature = array_from_hex(&vector.signature_hex);
        let signature = sign_canonical(ENTRY_DOMAIN, &vector.entry, &private_seed).unwrap();
        assert_eq!(signature, expected_signature);
        verify_canonical(ENTRY_DOMAIN, &vector.entry, &signature, &public_key).unwrap();
    }

    #[test]
    fn rejects_altered_content_domain_and_signature() {
        let vector = vector();
        let public_key = array_from_hex(&vector.public_key_hex);
        let mut signature: [u8; 64] = array_from_hex(&vector.signature_hex);
        let mut altered = vector.entry.clone();
        altered["sequence"] = serde_json::json!(2);
        assert!(verify_canonical(ENTRY_DOMAIN, &altered, &signature, &public_key).is_err());
        assert!(verify_canonical(RECEIPT_DOMAIN, &vector.entry, &signature, &public_key).is_err());
        signature[0] ^= 1;
        assert!(verify_canonical(ENTRY_DOMAIN, &vector.entry, &signature, &public_key).is_err());
    }
}
