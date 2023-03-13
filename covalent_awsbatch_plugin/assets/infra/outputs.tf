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
