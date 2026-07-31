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

output "runtime_iam_policy_json" {
  description = "Least-privilege policy for the Railway API and worker credentials."
  value       = data.aws_iam_policy_document.runtime.json
}
