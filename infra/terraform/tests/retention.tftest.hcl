mock_provider "aws" {}

variables {
  bucket_name = "chitaozinho-acceptance-test"
}

run "isolated_test_uses_minimum_retention" {
  command = plan

  variables {
    environment    = "test"
    retention_days = 1
  }

  assert {
    condition     = aws_s3_bucket.evidence.object_lock_enabled
    error_message = "The test bucket must enable Object Lock at creation."
  }

  assert {
    condition     = aws_s3_bucket_object_lock_configuration.evidence.rule[0].default_retention[0].mode == "COMPLIANCE"
    error_message = "The test bucket must use COMPLIANCE retention."
  }
}

run "reject_test_retention_above_minimum" {
  command = plan

  variables {
    environment    = "test"
    retention_days = 2
  }

  expect_failures = [
    aws_s3_bucket.evidence,
  ]
}

run "reject_short_staging_retention" {
  command = plan

  variables {
    environment    = "staging"
    retention_days = 1
  }

  expect_failures = [
    aws_s3_bucket.evidence,
  ]
}

run "production_uses_approved_minimum" {
  command = plan

  variables {
    environment    = "production"
    retention_days = 90
  }
}

run "reject_region_outside_brazil" {
  command = plan

  variables {
    aws_region = "us-east-1"
  }

  expect_failures = [
    var.aws_region,
  ]
}

run "reject_unknown_environment" {
  command = plan

  variables {
    environment = "preview"
  }

  expect_failures = [
    var.environment,
  ]
}
