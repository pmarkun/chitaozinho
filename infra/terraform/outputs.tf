output "evidence_bucket_name" {
  value = aws_s3_bucket.evidence.id
}

output "evidence_bucket_region" {
  value = var.aws_region
}

output "evidence_kms_key_arn" {
  value = aws_kms_key.evidence.arn
}

output "signing_envelope_kms_key_arn" {
  value = aws_kms_key.signing_envelope.arn
}
