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


import os

import covalent as ct
import terraform_output

BATCH_EXECUTOR_S3_BUCKET = terraform_output.get("s3_bucket_name", "covalent-batch-job-resources")
BATCH_EXECUTOR_ECR_REPO = terraform_output.get("ecr_repo_name", "covalent-batch-job-images")
BATCH_EXECUTOR_JOB_DEFINITION_NAME = terraform_output.get(
    "batch_job_definition_name", "covalent-batch-jobs"
)
BATCH_EXECUTOR_QUEUE = terraform_output.get("batch_queue", "covalent-batch-queue")
BATCH_EXECUTOR_EXECUTION_ROLE_NAME = terraform_output.get(
    "batch_execution_role_name", "ecsTaskExecutionRole"
)
BATCH_EXECUTOR_JOB_ROLE = terraform_output.get("batch_job_role_name", "CovalentBatchJobRole")
BATCH_EXECUTOR_LOG_GROUP = terraform_output.get(
    "batch_job_log_group_name", "covalent-batch-job-logs"
)


executor_config = {
    "s3_bucket_name": os.getenv("BATCH_EXECUTOR_S3_BUCKET", BATCH_EXECUTOR_S3_BUCKET),
    "ecr_repo_name": os.getenv("BATCH_EXECUTOR_ECR_REPO", BATCH_EXECUTOR_ECR_REPO),
    "batch_job_definition_name": os.getenv(
        "BATCH_EXECUTOR_JOB_DEFINITION_NAME", BATCH_EXECUTOR_JOB_DEFINITION_NAME
    ),
    "batch_queue": os.getenv("BATCH_EXECUTOR_BATCH_QUEUE", BATCH_EXECUTOR_QUEUE),
    "batch_execution_role_name": os.getenv(
        "BATCH_EXECUTOR_EXECUTION_ROLE_NAME", BATCH_EXECUTOR_EXECUTION_ROLE_NAME
    ),
    "batch_job_role_name": os.getenv("BATCH_EXECUTOR_JOB_ROLE", BATCH_EXECUTOR_JOB_ROLE),
    "batch_job_log_group_name": os.getenv("BATCH_EXECUTOR_LOG_GROUP", BATCH_EXECUTOR_LOG_GROUP),
    "vcpu": os.getenv("BATCH_EXECUTOR_VCPU", 2),
    "memory": os.getenv("BATCH_EXECUTOR_MEMORY", 3.75),
}

print("Using Executor Config:")
print(executor_config)

executor = ct.executor.AWSBatchExecutor(**executor_config)
