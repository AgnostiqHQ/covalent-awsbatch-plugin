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

output "s3_bucket_name" {
  value       = aws_s3_bucket.bucket.id
  description = "S3 bucket to store job artifacts"
}

output "batch_queue" {
  value = aws_batch_job_queue.job_queue.name
  description = "AWS Batch job queue"
}

output "batch_job_role_name" {
  value = aws_iam_role.job_role.name
  description = "IAM role assigned to tasks"
}

output "batch_job_log_group_name" {
  value = aws_cloudwatch_log_group.log_group.name
  description = "Task Cloudwatch log group name"
}

output "batch_execution_role_name" {
  value = aws_iam_role.ecs_tasks_execution_role.name
  description = "ECS task execution role"
}
