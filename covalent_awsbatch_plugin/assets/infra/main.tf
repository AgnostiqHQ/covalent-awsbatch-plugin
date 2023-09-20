# Copyright 2021 Agnostiq Inc.
#
# This file is part of Covalent.
#
# Licensed under the Apache License 2.0 (the "License"). A copy of the
# License may be obtained with this software package or at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Use of this file is prohibited except in compliance with the License.
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

data "aws_caller_identity" "current" {}

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "bucket" {
  bucket = "${var.prefix}-${var.aws_s3_bucket}"
  force_destroy = true
}

resource "aws_batch_compute_environment" "compute_environment" {
  compute_environment_name = "${var.prefix}-compute-environment"

  compute_resources {
    instance_role = aws_iam_instance_profile.ecs_instance_role.arn
    instance_type = [var.instance_types]
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
  name     = "${var.prefix}-${var.aws_batch_queue}"
  state    = "ENABLED"
  priority = 1
  compute_environments = [
    aws_batch_compute_environment.compute_environment.arn
  ]
}

resource "aws_cloudwatch_log_group" "log_group" {
  name = "${var.prefix}-log-group"
}

resource "aws_cloudwatch_log_stream" "log_stream" {
  name           = "${var.prefix}-log-stream"
  log_group_name = aws_cloudwatch_log_group.log_group.name
}


# Executor Covalent config section
data template_file executor_config {
  template = "${file("${path.module}/awsbatch.conf.tftpl")}"

  vars = {
    credentials=var.credentials
    profile=var.profile
    region=var.aws_region
    s3_bucket_name=aws_s3_bucket.bucket.id
    batch_queue=aws_batch_job_queue.job_queue.name
    batch_execution_role_name=aws_iam_role.ecs_tasks_execution_role.name
    batch_job_role_name=aws_iam_role.job_role.name
    batch_job_log_group_name=aws_cloudwatch_log_group.log_group.name
    vcpu=tonumber(var.vcpus)
    memory=tonumber(var.memory)
    num_gpus=tonumber(var.num_gpus)
    retry_attempts=tonumber(var.retry_attempts)
    time_limit=tonumber(var.time_limit)
    cache_dir=var.cache_dir
    poll_freq=tonumber(var.poll_freq)
  }
}

resource local_file executor_config {
  content = data.template_file.executor_config.rendered
  filename = "${path.module}/awsbatch.conf"
}
