# Copyright 2021 Agnostiq Inc.
#
# This file is part of Covalent.
#
# Licensed under the GNU Affero General Public License 3.0 (the "License").
# A copy of the License may be obtained with this software package or at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html
#
# Use of this file is prohibited except in compliance with the License. Any
# modifications or derivative works of this file must retain this copyright
# notice, and modified files must contain a notice indicating that they have
# been altered from the originals.
#
# Covalent is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the License for more details.
#
# Relief from the License may be granted by purchasing a commercial license.

data "aws_caller_identity" "current" {}

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "bucket" {
  bucket = "${var.name}-${var.aws_s3_bucket}"
  force_destroy = true
}

resource "aws_s3_bucket_acl" "bucket_acl" {
  bucket = aws_s3_bucket.bucket.id
  acl    = "private"
}

resource "aws_batch_compute_environment" "compute_environment" {
  compute_environment_name = "${var.name}-compute-environment"

  compute_resources {
    instance_role = aws_iam_instance_profile.ecs_instance_role.arn
    instance_type = var.instance_types
    max_vcpus = var.max_vcpus
    min_vcpus = var.min_vcpus

    security_group_ids = [ aws_security_group.sg.id ]

    subnets = [ var.vpc_id == "" ? "${element(module.vpc.public_subnets, 0)}" : var.subnet_id ]

    type = "EC2"
  }

  service_role = aws_iam_role.aws_batch_service_role.arn
  type         = "MANAGED"
  depends_on   = [aws_iam_role_policy_attachment.aws_batch_service_role_attachment]
}
resource "aws_batch_job_queue" "job_queue" {
  name     = "${var.name}-${var.aws_batch_queue}"
  state    = "ENABLED"
  priority = 1
  compute_environments = [
    aws_batch_compute_environment.compute_environment.arn
  ]
}

resource "aws_cloudwatch_log_group" "log_group" {
  name = "${var.name}-log-group"
}

resource "aws_cloudwatch_log_stream" "log_stream" {
  name           = "${var.name}-log-stream"
  log_group_name = aws_cloudwatch_log_group.log_group.name
}
