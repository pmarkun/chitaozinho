variable "aws_region" {
  description = "AWS region that stores final evidence."
  type        = string
  default     = "sa-east-1"

  validation {
    condition     = var.aws_region == "sa-east-1"
    error_message = "Evidence storage must remain in sa-east-1."
  }
}

variable "bucket_name" {
  description = "Globally unique name for the immutable evidence bucket."
  type        = string

  validation {
    condition = (
      length(var.bucket_name) >= 3 &&
      length(var.bucket_name) <= 63 &&
      can(regex("^[a-z0-9][a-z0-9.-]*[a-z0-9]$", var.bucket_name))
    )
    error_message = "Bucket name must be a valid 3-63 character S3 name."
  }
}

variable "retention_days" {
  description = "Default COMPLIANCE retention: exactly 1 in test and at least 90 elsewhere."
  type        = number
  default     = 90

  validation {
    condition = (
      var.retention_days >= 1 &&
      var.retention_days <= 36500 &&
      floor(var.retention_days) == var.retention_days
    )
    error_message = "Retention must be a whole number from 1 to 36500 days."
  }
}

variable "environment" {
  description = "Environment tag."
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["test", "staging", "production"], var.environment)
    error_message = "Environment must be test, staging or production."
  }
}
