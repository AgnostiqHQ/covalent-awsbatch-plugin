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

"""AWS Batch executor plugin for the Covalent dispatcher."""

import asyncio
from enum import Enum
import json
import os
import tempfile
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import boto3
import botocore
import cloudpickle as pickle
from covalent.executor.schemas import ResourceMap, TaskSpec, TaskUpdate
from covalent._shared_files import TaskCancelledError, TaskRuntimeError
from covalent._shared_files.config import get_config
from covalent._shared_files.logger import app_log
from covalent._shared_files.util_classes import RESULT_STATUS, Status
from covalent_aws_plugins import AWSExecutor
from pydantic import BaseModel

from .utils import _execute_partial_in_threadpool, _load_json_file, _load_pickle_file


class ExecutorPluginDefaults(BaseModel):
    """
    Default configuration values for the executor
    """

    credentials: str = ""
    profile: str = ""
    region: str = "us-east-1"
    s3_bucket_name: str = "covalent-batch-job-resources"
    batch_queue: str = "covalent-batch-queue"
    batch_execution_role_name: str = "ecsTaskExecutionRole"
    batch_job_role_name: str = "covalent-batch-job-role"
    batch_job_log_group_name: str = "covalent-batch-job-logs"
    cache_dir: str = "/tmp/covalent"
    vcpu: int = 2
    memory: float = 3.75
    num_gpus: int = 0
    retry_attempts: int = 3
    time_limit: int = 300
    poll_freq: int = 10
    container_image_uri: str = "public.ecr.aws/covalent/covalent-executor-base:stable"


class ExecutorInfraDefaults(BaseModel):
    """
    Configuration values for provisioning AWS Batch cloud infrastructure
    """

    prefix: Optional[str] = "covalent-batch"
    aws_region: str = "us-east-1"
    vpc_id: str = ""
    subnet_id: str = ""
    instance_types: str = "optimal"
    min_vcpus: int = 0
    max_vcpus: int = 256
    aws_s3_bucket: str = "job-resources"
    aws_batch_queue: str = "queue"
    aws_batch_job_definition: str = "job-definition"
    credentials: Optional[str] = ""
    profile: Optional[str] = ""
    vcpus: Optional[int] = 2
    memory: Optional[float] = 3.75
    num_gpus: Optional[int] = 0
    retry_attempts: Optional[int] = 3
    time_limit: Optional[int] = 300
    poll_freq: Optional[int] = 10
    container_image_uri: Optional[str] = "public.ecr.aws/covalent/covalent-executor-base:stable"


_EXECUTOR_PLUGIN_DEFAULTS = ExecutorPluginDefaults().dict()

EXECUTOR_PLUGIN_NAME = "AWSBatchExecutor"

FUNC_FILENAME = "func-{dispatch_id}-{node_id}.pkl"
RESULT_FILENAME = "{dispatch_id}/{node_id}/result.tobj"
STDOUT_FILENAME = "{dispatch_id}/{node_id}/stdout.txt"
STDERR_FILENAME = "{dispatch_id}/{node_id}/stderr.txt"
QELECTRON_DB_FILENAME = "{dispatch_id}/{node_id}/qelectron_db.mdb"
SUMMARY_FILENAME = "{dispatch_id}/{node_id}/summary.json"

JOB_NAME = "covalent-batch-{dispatch_id}-{task_group_id}"


# Valid Batch job terminal statuses
class StatusEnum(str, Enum):
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    SUCCEEDED = "SUCCEEDED"


class ReceiveModel(BaseModel):
    status: StatusEnum


class AWSBatchExecutor(AWSExecutor):
    # Opt into the new API
    SUPPORTS_MANAGED_EXECUTION = True

    """AWS Batch executor plugin class.

    Args:
        credentials: Full path to AWS credentials file.
        profile: Name of an AWS profile whose credentials are used.
        s3_bucket_name: Name of an S3 bucket where objects are stored.
        batch_queue: Name of the Batch queue used for job management.
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
        container_image_uri: URI of the docker container image used by the executor.
    """

    def __init__(
        self,
        credentials: str = None,
        profile: str = None,
        region: str = None,
        s3_bucket_name: str = None,
        batch_queue: str = None,
        batch_execution_role_name: str = None,
        batch_job_role_name: str = None,
        batch_job_log_group_name: str = None,
        vcpu: int = None,
        memory: float = None,
        num_gpus: int = None,
        retry_attempts: int = None,
        time_limit: int = None,
        poll_freq: int = None,
        cache_dir: str = None,
        container_image_uri: str = None,
    ):
        super().__init__(
            region=region or get_config("executors.awsbatch.region"),
            credentials_file=credentials or get_config("executors.awsbatch.credentials"),
            profile=profile or get_config("executors.awsbatch.profile"),
            s3_bucket_name=s3_bucket_name or get_config("executors.awsbatch.s3_bucket_name"),
            execution_role=batch_execution_role_name
            or get_config("executors.awsbatch.batch_execution_role_name"),
            poll_freq=poll_freq or get_config("executors.awsbatch.poll_freq"),
            log_group_name=batch_job_log_group_name
            or get_config("executors.awsbatch.batch_job_log_group_name"),
        )

        self.batch_queue = batch_queue or get_config("executors.awsbatch.batch_queue")
        self.batch_job_role_name = batch_job_role_name or get_config(
            "executors.awsbatch.batch_job_role_name"
        )
        self.vcpu = vcpu or get_config("executors.awsbatch.vcpu")
        self.memory = memory or get_config("executors.awsbatch.memory")
        self.num_gpus = num_gpus or get_config("executors.awsbatch.num_gpus")
        self.retry_attempts = retry_attempts or get_config("executors.awsbatch.retry_attempts")
        self.time_limit = time_limit or get_config("executors.awsbatch.time_limit")
        self.container_image_uri = container_image_uri or get_config(
            "executors.awsbatch.container_image_uri"
        )

        self.cache_dir = cache_dir or get_config("executors.awsbatch.cache_dir")

        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

        config = {
            "profile": self.profile,
            "region": self.region,
            "credentials": self.credentials_file,
            "s3_bucket_name": self.s3_bucket_name,
            "batch_queue": self.batch_queue,
            "batch_job_role_name": self.batch_job_role_name,
            "batch_job_log_group_name": self.log_group_name,
            "batch_execution_role_name": self.execution_role,
            "vcpu": self.vcpu,
            "memory": self.memory,
            "num_gpus": self.num_gpus,
            "retry_attempts": self.retry_attempts,
            "time_limit": self.time_limit,
            "cache_dir": self.cache_dir,
            "poll_freq": self.poll_freq,
            "container_image_uri": self.container_image_uri,
        }

        self._debug_log("Starting AWS Batch Executor with config:")
        self._debug_log(config)

    def _debug_log(self, message):
        app_log.debug(f"AWS Batch Executor: {message}")

    async def run(self, function: Callable, args: List, kwargs: Dict, task_metadata: Dict):
        raise NotImplementedError

    async def submit_task(self):
        raise NotImplementedError

    async def _poll_task(self):
        raise NotImplementedError

    async def _upload_task(self):
        raise NotImplementedError

    async def query_result(self):
        raise NotImplementedError

    async def submit_task_group(
        self,
        task_specs: List[TaskSpec],
        resource_map: ResourceMap,
        task_group_metadata: Dict,
        identity: Dict
    ) -> Any:
        """
        Invokes the task on the remote backend.

        Args:
            task_metadata: Dictionary of metadata for the task. Current keys are `dispatch_id` and `node_id`.
            identity: Dictionary from _validate_credentials call { "Account": "AWS Account ID", ...}
        Return:
            task_uuid: Task UUID defined on the remote backend.
        """
        dispatch_id = task_group_metadata["dispatch_id"]
        task_group_id = task_group_metadata["task_group_id"]
        account = identity["Account"]

        self._debug_log("Submitting task...")
        boto_session = boto3.Session(**self.boto_session_options())
        batch = boto_session.client("batch")

        region = boto_session.region_name

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

        COVALENT_TASK_SPECS = json.dumps([t.model_dump() for t in task_specs])
        COVALENT_RESOURCE_MAP = resource_map.model_dump_json()
        COVALENT_TASK_GROUP_METADATA = json.dumps(task_group_metadata)

        output_upload_uris = [
            (
                f"s3://{self.s3_bucket_name}/{RESULT_FILENAME.format(dispatch_id=dispatch_id, node_id=t.function_id)}",
                f"s3://{self.s3_bucket_name}/{STDOUT_FILENAME.format(dispatch_id=dispatch_id, node_id=t.function_id)}",
                f"s3://{self.s3_bucket_name}/{STDERR_FILENAME.format(dispatch_id=dispatch_id, node_id=t.function_id)}",
                f"s3://{self.s3_bucket_name}/{QELECTRON_DB_FILENAME.format(dispatch_id=dispatch_id, node_id=t.function_id)}",
            )
            for t in task_specs
        ]
        COVALENT_OUTPUT_UPLOAD_URIS = json.dumps(output_upload_uris)
        summary_upload_uris = [
            f"s3://{self.s3_bucket_name}/{SUMMARY_FILENAME.format(dispatch_id=dispatch_id, node_id=t.function_id)}"
            for t in task_specs
        ]
        COVALENT_SUMMARY_UPLOAD_URIS = json.dumps(summary_upload_uris)

        S3_STAGING_PREFIX = f"s3://{self.s3_bucket_name}/{dispatch_id}/sublattice_staging"

        # Register the job definition
        jobDefinitionName = f"{dispatch_id}-{task_group_id}"
        self._debug_log(f"Registering job definition {jobDefinitionName}...")
        env = [
            {
                "name": "COVALENT_TASK_SPECS",
                "value": COVALENT_TASK_SPECS,
            },
            {
                "name": "COVALENT_RESOURCE_MAP",
                "value": COVALENT_RESOURCE_MAP,
            },
            {
                "name": "COVALENT_TASK_GROUP_METADATA",
                "value": COVALENT_TASK_GROUP_METADATA,
            },
            {
                "name": "COVALENT_OUTPUT_UPLOAD_URIS",
                "value": COVALENT_OUTPUT_UPLOAD_URIS,
            },
            {
                "name": "COVALENT_SUMMARY_UPLOAD_URIS",
                "value": COVALENT_SUMMARY_UPLOAD_URIS,
            },
            {
                "name": "COVALENT_STAGING_URI_PREFIX",
                "value": S3_STAGING_PREFIX,
            },
        ]
        app_log.debug("Job Environment:")
        app_log.debug(env)
        partial_func = partial(
            batch.register_job_definition,
            jobDefinitionName=jobDefinitionName,
            type="container",  # Assumes a single EC2 instance will be used
            containerProperties={
                "environment": env,
                "image": self.container_image_uri,
                "jobRoleArn": f"arn:aws:iam::{account}:role/{self.batch_job_role_name}",
                "executionRoleArn": f"arn:aws:iam::{account}:role/{self.execution_role}",
                "resourceRequirements": resources,
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-region": region,
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
        registered_job_definition = await _execute_partial_in_threadpool(partial_func)
        app_log.debug("Registered Job Definition:")
        app_log.debug(registered_job_definition)

        # Submit the job
        partial_func = partial(
            batch.submit_job,
            jobName=JOB_NAME.format(dispatch_id=dispatch_id, task_group_id=task_group_id),
            jobQueue=self.batch_queue,
            jobDefinition=jobDefinitionName,
        )
        response = await _execute_partial_in_threadpool(partial_func)
        return response["jobId"]

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
        partial_func = partial(batch.describe_jobs, jobs=[job_id])
        job = await _execute_partial_in_threadpool(partial_func)
        status = job["jobs"][0]["status"]

        self._debug_log(f"Got job status {status}")
        try:
            exit_code = int(job["jobs"][0]["container"]["exitCode"])
        except Exception as e:
            exit_code = -1
        return status, exit_code

    async def _poll_job(self, job_id: str) -> StatusEnum:
        """Poll a Batch job until completion."""
        self._debug_log(f"Polling Batch job with id {job_id}...")

        status, exit_code = await self.get_status(job_id)

        if status == "CANCELLED":
            return status

        while status not in ["SUCCEEDED", "FAILED"]:
            await asyncio.sleep(self.poll_freq)
            status, exit_code = await self.get_status(job_id)

        return status

    async def cancel(self, task_metadata: Dict, job_handle: str) -> bool:
        """
        Cancel the batch job.

        Args:
            task_metadata: Dictionary with the task's dispatch_id and node id.
            job_handle: Unique job handle assigned to the task by AWS Batch.

        Returns:
            If the job was cancelled or not
        """
        self._debug_log("Cancelling job ID {job_handle}...")
        try:
            batch = boto3.Session(**self.boto_session_options()).client("batch")
            partial_func = partial(
                batch.terminate_job,
                jobId=job_handle,
                reason=f"Triggered cancellation with {task_metadata}",
            )
            await _execute_partial_in_threadpool(partial_func)
            return True
        except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as error:
            app_log.debug(
                f"Failed to cancel AWS Batch job: {job_handle} with \
                          task_metadata: {task_metadata} with error:{error}"
            )
            return False

    async def send(
        self,
        task_specs: List[TaskSpec],
        resources: ResourceMap,
        task_group_metadata: Dict,
    ):

        dispatch_id = task_group_metadata["dispatch_id"]
        task_group_id = task_group_metadata["task_group_id"]

        batch_job_name = JOB_NAME.format(dispatch_id=dispatch_id, task_group_id=task_group_id)

        self._debug_log(f"Executing Dispatch ID {dispatch_id} Task Group {task_group_id}")

        self._debug_log("Validating Credentials...")
        partial_func = partial(self._validate_credentials, raise_exception=True)
        identity = await _execute_partial_in_threadpool(partial_func)

        if await self.get_cancel_requested():
            raise TaskCancelledError(f"AWS Batch job {batch_job_name} requested to be cancelled")

        job_id = await self.submit_task_group(task_specs, resources, task_group_metadata, identity)
        self._debug_log(f"Successfully submitted job with ID: {job_id}")
        await self.set_job_handle(handle=job_id)

        return job_id

    async def poll(self, task_group_metadata: Dict, job_id: str) -> Dict:
        return {"status": await self._poll_job(job_id)}

    async def receive(self, task_group_metadata: Dict, data: Any) -> List[TaskUpdate]:
        # Job should have reached a terminal state by the time this is invoked.
        dispatch_id = task_group_metadata["dispatch_id"]
        task_group_id = task_group_metadata["task_group_id"]

        received = ReceiveModel.model_validate(data)
        s3 = boto3.Session(**self.boto_session_options()).client("s3")
        task_updates = []

        # Try to retrieve whatever task artifacts have been uploaded
        # Electrons with a complete execution summary are either COMPLETED or FAILED.
        # Electrons with no execution summary are either FAILED or CANCELLED depending on the overall Batch job status

        for i, node_id in enumerate(task_group_metadata["node_ids"]):
            summary_filename = SUMMARY_FILENAME.format(dispatch_id=dispatch_id, node_id=node_id)

            try:
                resp = s3.get_object(Bucket=self.s3_bucket_name, Key=summary_filename)
                result_summary = json.loads(resp["Body"].read())
                status = RESULT_STATUS.FAILED if result_summary["exception_occurred"] else RESULT_STATUS.COMPLETED
                assets = {
                    "output": {
                        "remote_uri": result_summary["output_uri"],
                    },
                    "stdout": {
                        "remote_uri": result_summary["stdout_uri"],
                    },
                    "stderr": {
                        "remote_uri": result_summary["stderr_uri"],
                    },
                    "qelectron_db": {
                        "remote_uri": result_summary["qelectron_db_uri"],
                    },
                }
                update = {
                    "dispatch_id": dispatch_id,
                    "node_id": node_id,
                    "status": status,
                    "assets": assets,
                }
                task_updates.append(TaskUpdate(**update))

            except s3.exceptions.NoSuchKey:
                for j in range(i, len(task_group_metadata["node_ids"])):
                    status = RESULT_STATUS.CANCELLED if received.status == StatusEnum.CANCELLED else RESULT_STATUS.FAILED
                    update = {
                        "dispatch_id": dispatch_id,
                        "node_id": task_group_metadata["node_ids"][j],
                        "status": status,
                        "assets": {}
                    }
                    task_updates.append(TaskUpdate(**update))
                    break

        return task_updates

    def get_upload_uri(self, task_group_metadata: Dict, object_key: str) -> str:
        dispatch_id = task_group_metadata["dispatch_id"]
        gid = task_group_metadata["task_group_id"]
        s3_object_key = f"{dispatch_id}/uploads/{gid}/{object_key}"
        s3_bucket_name = self.s3_bucket_name
        return f"s3://{s3_bucket_name}/{s3_object_key}"
