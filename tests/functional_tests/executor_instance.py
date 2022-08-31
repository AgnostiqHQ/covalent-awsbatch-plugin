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
