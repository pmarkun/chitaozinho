provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "evidence" {
  bucket              = var.bucket_name
  object_lock_enabled = true

  tags = {
    Application = "chitaozinho"
    Environment = var.environment
    DataClass   = "digital-evidence"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_object_lock_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = var.retention_days
    }
  }

  depends_on = [aws_s3_bucket_versioning.evidence]
}

resource "aws_kms_key" "evidence" {
  description             = "Chitaozinho immutable evidence encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Application = "chitaozinho"
    Environment = var.environment
    DataClass   = "digital-evidence"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_kms_alias" "evidence" {
  name          = "alias/chitaozinho-${var.environment}-evidence"
  target_key_id = aws_kms_key.evidence.key_id
}

resource "aws_kms_key" "signing_envelope" {
  description             = "Chitaozinho operational Ed25519 seed envelope"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Application = "chitaozinho"
    Environment = var.environment
    DataClass   = "signing-key-material"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_kms_alias" "signing_envelope" {
  name          = "alias/chitaozinho-${var.environment}-signing-envelope"
  target_key_id = aws_kms_key.signing_envelope.key_id
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.evidence.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "evidence_bucket" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["s3:*"]
    resources = [aws_s3_bucket.evidence.arn, "${aws_s3_bucket.evidence.arn}/*"]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid    = "DenyUnencryptedObjectUploads"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.evidence.arn}/*"]

    condition {
      test     = "StringNotEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["aws:kms"]
    }
  }

  statement {
    sid    = "DenyWrongEncryptionKey"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.evidence.arn}/*"]

    condition {
      test     = "StringNotEquals"
      variable = "s3:x-amz-server-side-encryption-aws-kms-key-id"
      values   = [aws_kms_key.evidence.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "secure_transport" {
  bucket = aws_s3_bucket.evidence.id
  policy = data.aws_iam_policy_document.evidence_bucket.json
}

data "aws_iam_policy_document" "runtime" {
  statement {
    sid = "InspectEvidenceBucket"
    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]
    resources = [aws_s3_bucket.evidence.arn]
  }

  statement {
    sid = "ReadAndAppendEvidence"
    actions = [
      "s3:GetObject",
      "s3:GetObjectRetention",
      "s3:GetObjectVersion",
      "s3:PutObject",
      "s3:PutObjectRetention",
    ]
    resources = ["${aws_s3_bucket.evidence.arn}/*"]
  }

  statement {
    sid = "UseEvidenceEncryptionKey"
    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:Encrypt",
      "kms:GenerateDataKey",
    ]
    resources = [aws_kms_key.evidence.arn]
  }

  statement {
    sid       = "DecryptOperationalSigningSeed"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.signing_envelope.arn]
  }
}
