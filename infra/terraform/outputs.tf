output "evidence_bucket_name" {
  value = aws_s3_bucket.evidence.id
}

output "evidence_bucket_region" {
  value = var.aws_region
}
