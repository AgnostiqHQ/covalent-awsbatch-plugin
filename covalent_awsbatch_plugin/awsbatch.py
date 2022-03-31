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

# Infrastructure required for this executor:
#       1.-9. See Fargate executor
#       10. Batch Compute Environment
#           - Managed
#           - On-demand EC2 provisioning model
#           - c4, c5, p3, p4 instance types
#       11. Batch Job Queue
#           - Connect to the compute environment
#       12. CloudWatch Log Group
#       13. IAM Policy - CovalentBatchJobExecutionPolicy
#       14. IAM Role - CovalentBatchJobExecutionRole
#       15. IAM Policy - CovalentBatchJobPolicy
#       16. IAM Role - CovalentBatchJobRole
#       17. IAM Policy - CovalentBatchExecutorPolicy
#       18. IAM Policy - CovalentBatchExecutorInfraPolicy
#       19. Batch Job Definition - created at runtime
#       20. Batch Job - created at runtime

import base64
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import boto3
import cloudpickle as pickle
import docker
from covalent._shared_files.logger import app_log
from covalent._shared_files.util_classes import DispatchInfo
from covalent._workflow.transport import TransportableObject
from covalent.executor import BaseExecutor

_EXECUTOR_PLUGIN_DEFAULTS = {
    "credentials": os.environ.get("AWS_SHARED_CREDENTIALS_FILE")
    or os.path.join(os.environ["HOME"], ".aws/credentials"),
    "profile": os.environ.get("AWS_PROFILE") or "",
    "s3_bucket_name": "covalent-batch-job-resources",
    "ecr_repo_name": "covalent-batch-job-images",
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


class AWSBatchExecutor(BaseExecutor):
    """AWS Batch executor plugin class.

    Args:
        credentials: Full path to AWS credentials file.
        profile: Name of an AWS profile whose credentials are used.
        s3_bucket_name: Name of an S3 bucket where objects are stored.
        ecr_repo_name: Name of the ECR repository where job images are stored.
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
        credentials: str,
        profile: str,
        s3_bucket_name: str,
        ecr_repo_name: str,
        batch_queue: str,
        batch_job_definition_name: str,
        batch_execution_role_name: str,
        batch_job_role_name: str,
        batch_job_log_group_name: str,
        vcpu: int,
        memory: float,
        num_gpus: int,
        retry_attempts: int,
        time_limit: int,
        poll_freq: int,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.credentials = credentials
        self.profile = profile
        self.s3_bucket_name = s3_bucket_name
        self.ecr_repo_name = ecr_repo_name
        self.batch_queue = batch_queue
        self.batch_job_definition_name = batch_job_definition_name
        self.batch_execution_role_name = batch_execution_role_name
        self.batch_job_role_name = batch_job_role_name
        self.batch_job_log_group_name = batch_job_log_group_name
        self.vcpu = vcpu
        self.memory = memory
        self.num_gpus = num_gpus
        self.retry_attempts = retry_attempts
        self.time_limit = time_limit
        self.poll_freq = poll_freq

    def execute(
        self,
        function: TransportableObject,
        args: List,
        kwargs: Dict,
        dispatch_id: str,
        results_dir: str,
        node_id: int = -1,
    ) -> Tuple[Any, str, str]:

        dispatch_info = DispatchInfo(dispatch_id)
        result_filename = f"result-{dispatch_id}-{node_id}.pkl"
        task_results_dir = os.path.join(results_dir, dispatch_id)
        image_tag = f"{dispatch_id}-{node_id}"

        # AWS Credentials
        os.environ["AWS_SHARED_CREDENTIALS_FILE"] = self.credentials
        os.environ["AWS_PROFILE"] = self.profile

        # AWS Account Retrieval
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        account = identity.get("Account")

        if account is None:
            app_log.warning(identity)
            return None, "", identity

        # TODO: Move this to BaseExecutor
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

        with self.get_dispatch_context(dispatch_info):
            # This is re-used from the Docker/Fargate executors
            ecr_repo_uri = self._package_and_upload(
                function,
                image_tag,
                task_results_dir,
                result_filename,
                args,
                kwargs,
            )

            # BELOW is specific to AWS Batch

            # Create a Batch Job Queue (one time only / CDK)

            # Create a Batch Compute Environment (one time only / CDK)
            # Here you can set a list of EC2 instance types

            # Create an IAM role for the container (one time only / CDK)

            # Register a job definition
            batch = boto3.client("batch")

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

            batch.register_job_definition(
                jobDefinitionName=self.batch_job_definition_name,
                type="container",  # Assumes a single EC2 instance will be used
                containerProperties={
                    "image": ecr_repo_uri,
                    "jobRoleArn": f"arn:aws:iam::{account}:role/{self.batch_job_role_name}",
                    "executionRoleArn": f"arn:aws:iam::{account}:role/{self.batch_execution_role_name}",
                    "resourceRequirements": resources,
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-region": "us-east-1",
                            "awslogs-group": self.batch_job_log_group_name,
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
                jobName=f"covalent-batch-{dispatch_id}-{node_id}",
                jobQueue=self.batch_queue,
                jobDefinition=self.batch_job_definition_name,
            )

            job_id = response["jobId"]

            self._poll_batch_job(batch, job_id)

            return self._query_result(result_filename, task_results_dir, job_id, image_tag)

    def _format_exec_script(
        self,
        func_filename: str,
        result_filename: str,
        docker_working_dir: str,
        args: List,
        kwargs: Dict,
    ) -> str:
        """Create an executable Python script which executes the task.

        Args:
            func_filename: Name of the pickled function.
            result_filename: Name of the pickled result.
            docker_working_dir: Name of the working directory in the container.
            args: Positional arguments consumed by the task.
            kwargs: Keyword arguments consumed by the task.

        Returns:
            script: String object containing the executable Python script.
        """

        exec_script = """
import os
import boto3
import cloudpickle as pickle

local_func_filename = os.path.join("{docker_working_dir}", "{func_filename}")
local_result_filename = os.path.join("{docker_working_dir}", "{result_filename}")

s3 = boto3.client("s3")
s3.download_file("{s3_bucket_name}", "{func_filename}", local_func_filename)

with open(local_func_filename, "rb") as f:
    function = pickle.load(f)

result = function(*{args}, **{kwargs})

with open(local_result_filename, "wb") as f:
    pickle.dump(result, f)

s3.upload_file(local_result_filename, "{s3_bucket_name}", "{result_filename}")
""".format(
            func_filename=func_filename,
            args=args,
            kwargs=kwargs,
            s3_bucket_name=self.s3_bucket_name,
            result_filename=result_filename,
            docker_working_dir=docker_working_dir,
        )

        return exec_script

    def _format_dockerfile(self, exec_script_filename: str, docker_working_dir: str) -> str:
        """Create a Dockerfile which wraps an executable Python task.

        Args:
            exec_script_filename: Name of the executable Python script.
            docker_working_dir: Name of the working directory in the container.

        Returns:
            dockerfile: String object containing a Dockerfile.
        """

        dockerfile = """
FROM python:3.8-slim-buster

RUN apt-get update && apt-get install -y \\
  gcc \\
  && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --use-feature=in-tree-build boto3 cloudpickle

WORKDIR {docker_working_dir}

COPY {func_basename} {docker_working_dir}

ENTRYPOINT [ "python" ]
CMD ["{docker_working_dir}/{func_basename}"]
""".format(
            func_basename=os.path.basename(exec_script_filename),
            docker_working_dir=docker_working_dir,
        )

        return dockerfile

    def _package_and_upload(
        self,
        function: TransportableObject,
        image_tag: str,
        task_results_dir: str,
        result_filename: str,
        args: List,
        kwargs: Dict,
    ) -> str:
        """Package a task using Docker and upload it to AWS ECR.

        Args:
            function: A callable Python function.
            image_tag: Tag used to identify the Docker image.
            task_results_dir: Local directory where task results are stored.
            result_filename: Name of the pickled result.
            args: Positional arguments consumed by the task.
            kwargs: Keyword arguments consumed by the task.

        Returns:
            ecr_repo_uri: URI of the repository where the image was uploaded.
        """

        func_filename = f"func-{image_tag}.pkl"
        docker_working_dir = "/opt/covalent"

        with tempfile.NamedTemporaryFile(dir=self.cache_dir) as function_file:
            # Write serialized function to file
            pickle.dump(function.get_deserialized(), function_file)
            function_file.flush()

            # Upload pickled function to S3
            s3 = boto3.client("s3")
            s3.upload_file(function_file.name, self.s3_bucket_name, func_filename)

        with tempfile.NamedTemporaryFile(
            dir=self.cache_dir, mode="w"
        ) as exec_script_file, tempfile.NamedTemporaryFile(
            dir=self.cache_dir, mode="w"
        ) as dockerfile_file:
            # Write execution script to file
            exec_script = self._format_exec_script(
                func_filename,
                result_filename,
                docker_working_dir,
                args,
                kwargs,
            )
            exec_script_file.write(exec_script)
            exec_script_file.flush()

            # Write Dockerfile to file
            dockerfile = self._format_dockerfile(exec_script_file.name, docker_working_dir)
            dockerfile_file.write(dockerfile)
            dockerfile_file.flush()

            local_dockerfile = os.path.join(task_results_dir, f"Dockerfile_{image_tag}")
            shutil.copyfile(dockerfile_file.name, local_dockerfile)

            # Build the Docker image
            docker_client = docker.from_env()
            image, build_log = docker_client.images.build(
                path=self.cache_dir, dockerfile=dockerfile_file.name, tag=image_tag
            )

        # ECR config
        ecr = boto3.client("ecr")

        ecr_username = "AWS"
        ecr_credentials = ecr.get_authorization_token()["authorizationData"][0]
        ecr_password = (
            base64.b64decode(ecr_credentials["authorizationToken"])
            .replace(b"AWS:", b"")
            .decode("utf-8")
        )
        ecr_registry = ecr_credentials["proxyEndpoint"]
        ecr_repo_uri = f"{ecr_registry.replace('https://', '')}/{self.ecr_repo_name}:{image_tag}"

        docker_client.login(username=ecr_username, password=ecr_password, registry=ecr_registry)

        # Tag the image
        image.tag(ecr_repo_uri, tag=image_tag)

        # Push to ECR
        response = docker_client.images.push(ecr_repo_uri, tag=image_tag)

        return ecr_repo_uri

    def get_status(self, batch, job_id: str) -> Tuple[str, int]:
        """Query the status of a previously submitted Batch job.

        Args:
            batch: Batch client object.
            job_id: Identifier used to identify a Batch job.

        Returns:
            status: String describing the task status.
            exit_code: Exit code, if the task has completed, else -1.
        """

        job = batch.describe_jobs(jobs=[job_id])
        status = job["jobs"][0]["status"]
        try:
            exit_code = int(job["jobs"][0]["container"]["exitCode"])
        except KeyError:
            exit_code = -1

        return status, exit_code

    def _poll_batch_job(self, batch, job_id: str) -> None:
        """Poll a Batch job until completion.

        Args:
            batch: Batch client object.
            job_id: Identifier used to identify a Batch job.

        Returns:
            None
        """

        status, exit_code = self.get_status(batch, job_id)

        while status not in ["SUCCEEDED", "FAILED"]:
            time.sleep(self.poll_freq)
            status, exit_code = self.get_status(batch, job_id)

        if exit_code != 0:
            raise Exception(f"Job failed with exit code {exit_code}.")

    def _query_result(
        self,
        result_filename: str,
        task_results_dir: str,
        job_id: str,
        image_tag: str,
    ) -> Tuple[Any, str, str]:
        """Query and retrieve a completed job's result.

        Args:
            result_filename: Name of the pickled result file.
            task_results_dir: Local directory where task results are stored.
            job_id: Identifier used to identify a Batch job.
            image_tag: Tag used to identify the Docker image.

        Returns:
            result: The task's result, as a Python object.
            logs: The stdout and stderr streams corresponding to the task.
            empty_string: A placeholder empty string.
        """

        local_result_filename = os.path.join(task_results_dir, result_filename)

        s3 = boto3.client("s3")
        s3.download_file(self.s3_bucket_name, result_filename, local_result_filename)

        with open(local_result_filename, "rb") as f:
            result = pickle.load(f)
        os.remove(local_result_filename)

        batch = boto3.client("batch")
        log_stream_name = batch.describe_jobs(jobs=[job_id])["jobs"][0]["container"][
            "logStreamName"
        ]

        logs = boto3.client("logs")

        # TODO: This should be paginated, but the command doesn't support boto3 pagination
        # Up to 10000 log events can be returned from a single call to get_log_events()
        events = logs.get_log_events(
            logGroupName=self.batch_job_log_group_name,
            logStreamName=log_stream_name,
        )["events"]

        log_events = ""
        for event in events:
            log_events += event["message"] + "\n"

        return result, log_events, ""

    def cancel(self, job_id: str, reason: str = "None") -> None:
        """Cancel a Batch job.

        Args:
            job_id: Identifier used to specify a Batch job.
            reason: An optional string used to specify a cancellation reason.

        Returns:
            None
        """

        batch = boto3.client("batch")
        batch.terminate_job(jobId=job_id, reason=reason)
