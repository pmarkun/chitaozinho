variable "aws_region" {
  description = "AWS region that stores final evidence."
  type        = string
  default     = "sa-east-1"
}

variable "bucket_name" {
  description = "Globally unique name for the immutable evidence bucket."
  type        = string
}

variable "retention_days" {
  description = "Default COMPLIANCE retention. Use 1 only in the isolated synthetic test account."
  type        = number
  default     = 90

  validation {
    condition     = var.retention_days >= 1
    error_message = "Retention must be at least one day."
  }
}

variable "environment" {
  description = "Environment tag."
  type        = string
  default     = "staging"
}
