terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # State is local on purpose (aws/terraform/terraform.tfstate, gitignored).
  # It holds generated secrets in plain text, so it must never be committed; for
  # a one-person proof of concept a local file is the simplest thing that is
  # safe. See README "State" for moving it to an S3 backend.
}

provider "aws" {
  region = var.region

  # Every resource is tagged, which is what teardown.sh uses to prove nothing
  # was left behind, and what Cost Explorer can group the bill by.
  default_tags {
    tags = local.tags
  }
}
