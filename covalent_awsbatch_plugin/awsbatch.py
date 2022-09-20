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

"""AWS Batch executor plugin for the Covalent dispatcher."""

import asyncio
import base64
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import boto3
import cloudpickle as pickle
import docker
from covalent._shared_files.config import get_config
from covalent._shared_files.logger import app_log
from covalent._shared_files.util_classes import DispatchInfo
from covalent.executor import BaseExecutor
from covalent_aws_plugins import AWSExecutor

_EXECUTOR_PLUGIN_DEFAULTS = {
    "credentials": os.environ.get("AWS_SHARED_CREDENTIALS_FILE")
    or os.path.join(os.environ["HOME"], ".aws/credentials"),
    "profile": os.environ.get("AWS_PROFILE") or "default",
    "s3_bucket_name": "covalent-batch-job-resources",
    "batch_queue": "covalent-batch-queue",
    "batch_job_definition_name": "covalent-batch-jobs",
    "batch_execution_role_name": "ecsTaskExecutionRole",
    "batch_job_role_name": "CovalentBatchJobRole",
    "batch_job_log_group_name": "covalent-batch-job-logs",
    "vcpu": 2,
    "memory": 3.75,
    "num_gpus": 0,
    "retry_attempts": 3,
    "time_limit": 300,
    "cache_dir": "/tmp/covalent",
    "poll_freq": 10,
}

EXECUTOR_PLUGIN_NAME = "AWSBatchExecutor"

FUNC_FILENAME = "func-{dispatch_id}-{node_id}.pkl"
RESULT_FILENAME = "result-{dispatch_id}-{node_id}.pkl"
JOB_NAME = "covalent-batch-{dispatch_id}-{node_id}"
COVALENT_EXEC_BASE_URI = "public.ecr.aws/covalent/covalent-executor-base:latest"


class AWSBatchExecutor(AWSExecutor):
    """AWS Batch executor plugin class.

    Args:
        credentials: Full path to AWS credentials file.
        profile: Name of an AWS profile whose credentials are used.
        s3_bucket_name: Name of an S3 bucket where objects are stored.
        batch_queue: Name of the Batch queue used for job management.
        batch_job_definition_name: Name of the Batch job definition for a user, project, or experiment.
        batch_execution_role_name: Name of the IAM role used by the Batch ECS agent.
        batch_job_role_name: Name of the IAM role used within the container.
        batch_job_log_group_name: Name of the CloudWatch log group where container logs are stored.
        vcpu: Number of vCPUs available to a task.
        memory: Memory (in GB) available to a task.
        num_gpus: Number of GPUs available to a task.
        retry_attempts: Number of times a job is retried if it fails.
        time_limit: Time limit (in seconds) after which jobs are killed.
        poll_freq: Frequency with which to poll a submitted task.
        cache_dir: Cache directory used by this executor for temporary files.
    """

    def __init__(
        self,
        credentials: str = None,
        profile: str = None,
        s3_bucket_name: str = None,
        batch_queue: str = None,
        batch_job_definition_name: str = None,
        batch_execution_role_name: str = None,
        batch_job_role_name: str = None,
        batch_job_log_group_name: str = None,
        vcpu: int = None,
        memory: float = None,
        num_gpus: int = None,
        retry_attempts: int = None,
        time_limit: int = None,
        poll_freq: int = None,
        **kwargs,
    ):
        super().__init__(
            credentials_file=credentials or get_config("executors.awsbatch.credentials"),
            profile=profile or get_config("executors.awsbatch.profile"),
            s3_bucket_name=s3_bucket_name or get_config("executors.awsbatch.s3_bucket_name"),
            execution_role=batch_execution_role_name
            or get_config("executors.awsbatch.batch_execution_role_name"),
            poll_freq=poll_freq or get_config("executors.awsbatch.poll_freq"),
            log_group_name=batch_job_log_group_name
            or get_config("executors.awsbatch.batch_job_log_group_name"),
            **kwargs,
        )

        self.batch_queue = batch_queue or get_config("executors.awsbatch.batch_queue")
        self.batch_job_definition_name = batch_job_definition_name or get_config(
            "executors.awsbatch.batch_job_definition_name"
        )
        self.batch_job_role_name = batch_job_role_name or get_config(
            "executors.awsbatch.batch_job_role_name"
        )
        self.vcpu = vcpu or get_config("executors.awsbatch.vcpu")
        self.memory = memory or get_config("executors.awsbatch.memory")
        self.num_gpus = num_gpus or get_config("executors.awsbatch.num_gpus")
        self.retry_attempts = retry_attempts or get_config("executors.awsbatch.retry_attempts")
        self.time_limit = time_limit or get_config("executors.awsbatch.time_limit")
        self._cwd = tempfile.mkdtemp()

        self.cache_dir = self.cache_dir or get_config("executors.awsbatch.cache_dir")

        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

        config = {
            "profile": self.profile,
            "region": self.region,
            "credentials": self.credentials_file,
            "batch_queue": self.batch_queue,
            "batch_job_definition_name": self.batch_job_definition_name,
            "batch_job_role_name": self.batch_job_role_name,
            "vcpu": self.vcpu,
            "memory": self.memory,
            "num_gpus": self.num_gpus,
            "retry_attempts": self.retry_attempts,
            "time_limit": self.time_limit,
            "cache_dir": self.cache_dir,
            "_cwd": self._cwd,
        }

        self._debug_log("Starting AWS Batch Executor with config:")
        self._debug_log(config)

    def _debug_log(self, message):
        app_log.debug(f"AWS Batch Executor: {message}")

    async def run(self, function: Callable, args: List, kwargs: Dict, task_metadata: Dict):

        dispatch_id = task_metadata["dispatch_id"]
        node_id = task_metadata["node_id"]

        self._debug_log(f"Executing Dispatch ID {dispatch_id} Node {node_id}")

        self._debug_log("Validating Credentials...")
        identity = self._validate_credentials(raise_exception=True)

        await self._upload_task(function, args, kwargs, task_metadata)
        job_id = await self.submit_task(task_metadata, identity)
        self._debug_log(f"Successfully submitted job with ID: {job_id}")

        await self._poll_task(job_id)

        return await self.query_result(task_metadata)

    async def _upload_task(self, function, args, kwargs, task_metadata) -> None:
        """
        Uploads the pickled function to the remote cache.
        """

        dispatch_id = task_metadata["dispatch_id"]
        node_id = task_metadata["node_id"]

        s3 = boto3.Session(**self.boto_session_options()).client("s3")
        s3_object_filename = FUNC_FILENAME.format(dispatch_id=dispatch_id, node_id=node_id)

        self._debug_log(
            f"Uploading task to S3 bucket {self.s3_bucket_name} as object {s3_object_filename}..."
        )

        with tempfile.NamedTemporaryFile(dir=self.cache_dir) as function_file:
            # Write serialized function to file
            pickle.dump((function, args, kwargs), function_file)
            function_file.flush()
            s3.upload_file(function_file.name, self.s3_bucket_name, s3_object_filename)

    async def submit_task(self, task_metadata: Dict, identity: Dict) -> Any:
        """
        Invokes the task on the remote backend.

        Args:
            task_metadata: Dictionary of metadata for the task. Current keys are `dispatch_id` and `node_id`.
            identity: Dictionary from _validate_credentials call { "Account": "AWS Account ID", ...}
        Return:
            task_uuid: Task UUID defined on the remote backend.
        """

        dispatch_id = task_metadata["dispatch_id"]
        node_id = task_metadata["node_id"]
        account = identity["Account"]

        self._debug_log("Submitting task...")

        dispatch_info = DispatchInfo(dispatch_id)

        with self.get_dispatch_context(dispatch_info):

            batch = boto3.Session(**self.boto_session_options()).client("batch")

            resources = [
                {"type": "VCPU", "value": str(int(self.vcpu))},
                {"type": "MEMORY", "value": str(int(self.memory * 1024))},
            ]
            if self.num_gpus:
                resources += [
                    {
                        "type": "GPU",
                        "value": str(self.num_gpus),
                    },
                ]

            # Register the job definition
            self._debug_log(f"Registering job definition {self.batch_job_definition_name}...")
            batch.register_job_definition(
                jobDefinitionName=self.batch_job_definition_name,
                type="container",  # Assumes a single EC2 instance will be used
                containerProperties={
                    "environment": [
                        {"name": "S3_BUCKET_NAME", "value": self.s3_bucket_name},
                        {
                            "name": "COVALENT_TASK_FUNC_FILENAME",
                            "value": FUNC_FILENAME.format(
                                dispatch_id=dispatch_id, node_id=node_id
                            ),
                        },
                        {
                            "name": "RESULT_FILENAME",
                            "value": RESULT_FILENAME.format(
                                dispatch_id=dispatch_id, node_id=node_id
                            ),
                        },
                    ],
                    "image": COVALENT_EXEC_BASE_URI,
                    "jobRoleArn": f"arn:aws:iam::{account}:role/{self.batch_job_role_name}",
                    "executionRoleArn": f"arn:aws:iam::{account}:role/{self.execution_role}",
                    "resourceRequirements": resources,
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-region": "us-east-1",
                            "awslogs-group": self.log_group_name,
                            "awslogs-create-group": "true",
                            "awslogs-stream-prefix": "covalent-batch",
                        },
                    },
                },
                retryStrategy={
                    "attempts": self.retry_attempts,
                },
                timeout={
                    "attemptDurationSeconds": self.time_limit,
                },
                platformCapabilities=["EC2"],
            )

            # Submit the job
            response = batch.submit_job(
                jobName=JOB_NAME.format(dispatch_id=dispatch_id, node_id=node_id),
                jobQueue=self.batch_queue,
                jobDefinition=self.batch_job_definition_name,
            )
            job_id = response["jobId"]

            return job_id

    async def get_status(self, job_id: str) -> Tuple[str, int]:
        """Query the status of a previously submitted Batch job.

        Args:
            batch: Batch client object.
            job_id: Identifier used to identify a Batch job.

        Returns:
            status: String describing the task status.
            exit_code: Exit code, if the task has completed, else -1.
        """
        self._debug_log("Checking job status...")
        batch = boto3.Session(**self.boto_session_options()).client("batch")

        job = batch.describe_jobs(jobs=[job_id])
        status = job["jobs"][0]["status"]

        self._debug_log(f"Got job status {status}")
        try:
            exit_code = int(job["jobs"][0]["container"]["exitCode"])
        except Exception as e:
            exit_code = -1

        return status, exit_code

    async def _poll_task(self, job_id: str) -> Any:
        """Poll a Batch job until completion.

        Args:
            batch: Batch client object.
            job_id: Identifier used to identify a Batch job.

        Returns:
            None
        """

        self._debug_log(f"Polling task with job id {job_id}...")

        status, exit_code = await self.get_status(job_id)

        while status not in ["SUCCEEDED", "FAILED"]:
            await asyncio.sleep(self.poll_freq)
            status, exit_code = await self.get_status(job_id)

        if exit_code != 0:
            raise Exception(f"Job failed with exit code {exit_code}.")

    async def cancel(self, job_id: str, reason: str = "None") -> None:
        """Cancel a Batch job.

        Args:
            job_id: Identifier used to specify a Batch job.
            reason: An optional string used to specify a cancellation reason.

        Returns:
            None
        """

        self._debug_log("Cancelling job ID {job_id}...")
        batch = boto3.Session(**self.boto_session_options()).client("batch")
        batch.terminate_job(jobId=job_id, reason=reason)

    async def _get_log_events(self, log_stream_name: str) -> str:
        """Get log events corresponding to the log group and stream names."""
        logs = boto3.Session(**self.boto_session_options()).client("logs")

        # TODO: This should be paginated, but the command doesn't support boto3 pagination
        # Up to 10000 log events can be returned from a single call to get_log_events()
        events = logs.get_log_events(
            logGroupName=self.log_group_name,
            logStreamName=log_stream_name,
        )["events"]

        return "".join(event["message"] + "\n" for event in events)

    async def _download_file_from_s3(
        self, s3_bucket_name: str, result_filename: str, local_result_filename: str
    ) -> None:
        """Download file from s3 into local file."""
        s3 = boto3.Session(**self.boto_session_options()).client("s3")
        s3.download_file(s3_bucket_name, result_filename, local_result_filename)

    async def query_result(self, task_metadata: Dict) -> Tuple[Any, str, str]:
        """Query and retrieve a completed job's result.

        Args:
            task_metadata: Dictionary containing the task dispatch_id and node_id

        Returns:
            result: The task's result, as a Python object.
        """

        dispatch_id = task_metadata["dispatch_id"]
        node_id = task_metadata["node_id"]

        result_filename = RESULT_FILENAME.format(dispatch_id=dispatch_id, node_id=node_id)
        local_result_filename = os.path.join(self._cwd, result_filename)

        app_log.debug(
            "Downloading result file {result_filename} from S3 bucket {self.s3_bucket_name} to local path {local_result_filename}..."
        )
        await self._download_file_from_s3(
            self.s3_bucket_name, result_filename, local_result_filename
        )

        with open(local_result_filename, "rb") as f:
            result = pickle.load(f)
        os.remove(local_result_filename)

        return result

    async def _get_batch_logstream(self, job_id: str) -> str:
        """Get the log stream name corresponding to the batch."""
        batch = boto3.Session(profile_name=self.profile).client("batch")
        return batch.describe_jobs(jobs=[job_id])["jobs"][0]["container"]["logStreamName"]
