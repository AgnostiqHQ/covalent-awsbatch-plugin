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
from covalent._workflow.transport import TransportableObject
from covalent.executor import BaseExecutor

from .scripts import DOCKER_SCRIPT, PYTHON_EXEC_SCRIPT

_EXECUTOR_PLUGIN_DEFAULTS = {
    "credentials": os.environ.get("AWS_SHARED_CREDENTIALS_FILE")
    or os.path.join(os.environ["HOME"], ".aws/credentials"),
    "profile": os.environ.get("AWS_PROFILE") or "default",
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
        credentials: str = None,
        profile: str = None,
        s3_bucket_name: str = None,
        ecr_repo_name: str = None,
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
        super().__init__(**kwargs)

        self.credentials = credentials or get_config("executors.awsbatch.credentials")
        self.profile = profile or get_config("executors.awsbatch.profile")
        self.s3_bucket_name = s3_bucket_name or get_config("executors.awsbatch.s3_bucket_name")
        self.ecr_repo_name = ecr_repo_name or get_config("executors.awsbatch.ecr_repo_name")
        self.batch_queue = batch_queue or get_config("executors.awsbatch.batch_queue")
        self.batch_job_definition_name = batch_job_definition_name or get_config(
            "executors.awsbatch.batch_job_definition_name"
        )
        self.batch_execution_role_name = batch_execution_role_name or get_config(
            "executors.awsbatch.batch_execution_role_name"
        )
        self.batch_job_role_name = batch_job_role_name or get_config(
            "executors.awsbatch.batch_job_role_name"
        )
        self.batch_job_log_group_name = batch_job_log_group_name or get_config(
            "executors.awsbatch.batch_job_log_group_name"
        )
        self.vcpu = vcpu or get_config("executors.awsbatch.vcpu")
        self.memory = memory or get_config("executors.awsbatch.memory")
        self.num_gpus = num_gpus or get_config("executors.awsbatch.num_gpus")
        self.retry_attempts = retry_attempts or get_config("executors.awsbatch.retry_attempts")
        self.time_limit = time_limit or get_config("executors.awsbatch.time_limit")
        self.poll_freq = poll_freq or get_config("executors.awsbatch.poll_freq")

        if self.cache_dir == "":
            self.cache_dir = get_config("executors.awsbatch.cache_dir")

        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

    def run(self, function: Callable, args: List, kwargs: Dict):
        pass

    def _get_aws_account(self) -> Tuple[Dict, str]:
        """Get AWS account."""
        sts = boto3.Session(profile_name=self.profile).client("sts")
        identity = sts.get_caller_identity()
        return identity, identity.get("Account")

    def execute(
        self,
        function: Callable,
        args: List,
        kwargs: Dict,
        dispatch_id: str,
        results_dir: str,
        node_id: int = -1,
    ) -> Tuple[Any, str, str]:

        app_log.debug("AWS BATCH EXECUTOR: INSIDE EXECUTE METHOD")
        dispatch_info = DispatchInfo(dispatch_id)
        result_filename = f"result-{dispatch_id}-{node_id}.pkl"
        task_results_dir = os.path.join(results_dir, dispatch_id)
        image_tag = f"{dispatch_id}-{node_id}"
        app_log.debug("AWS BATCH EXECUTOR: IMAGE TAG CONSTRUCTED")

        # AWS Credentials
        os.environ["AWS_SHARED_CREDENTIALS_FILE"] = self.credentials
        os.environ["AWS_PROFILE"] = self.profile
        app_log.debug("AWS BATCH EXECUTOR: GET CREDENTIALS AND PROFILE SUCCESS")

        identity, account = self._get_aws_account()
        app_log.debug("AWS BATCH EXECUTOR: GET ACCOUNT SUCCESS")

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
            app_log.debug("AWS BATCH EXECUTOR: PACKAGE AND UPLOAD SUCCESS")
            app_log.debug(f"AWS BATCH EXECUTOR: ECR REPO URI SUCCESS ({ecr_repo_uri})")

            # Register a job definition
            batch = boto3.Session(profile_name=self.profile).client("batch")

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

            app_log.debug("AWS BATCH EXECUTOR: BOTO CLIENT INIT SUCCESS")

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

            app_log.debug("AWS BATCH EXECUTOR: BATCH JOB DEFINITION REGISTER SUCCESS")

            # Submit the job
            response = batch.submit_job(
                jobName=f"covalent-batch-{dispatch_id}-{node_id}",
                jobQueue=self.batch_queue,
                jobDefinition=self.batch_job_definition_name,
            )

            app_log.debug("AWS BATCH EXECUTOR: JOB SUBMISSION SUCCESS")

            job_id = response["jobId"]
            app_log.debug(f"AWS BATCH EXECUTOR: JOB ID {job_id}")

            self._poll_batch_job(batch, job_id)
            app_log.debug("AWS BATCH EXECUTOR: BATCH JOB POLL SUCCESS")

            return self._query_result(result_filename, task_results_dir, job_id)

    def _format_exec_script(
        self,
        func_filename: str,
        result_filename: str,
        docker_working_dir: str,
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

        app_log.debug("AWS BATCH EXECUTOR: INSIDE FORMAT EXECSCRIPT METHOD")
        return PYTHON_EXEC_SCRIPT.format(
            func_filename=func_filename,
            s3_bucket_name=self.s3_bucket_name,
            result_filename=result_filename,
            docker_working_dir=docker_working_dir,
        )

    def _format_dockerfile(self, exec_script_filename: str, docker_working_dir: str) -> str:
        """Create a Dockerfile which wraps an executable Python task.

        Args:
            exec_script_filename: Name of the executable Python script.
            docker_working_dir: Name of the working directory in the container.

        Returns:
            dockerfile: String object containing a Dockerfile.
        """

        app_log.debug("AWS BATCH EXECUTOR: INSIDE FORMAT DOCKERFILE METHOD")
        return DOCKER_SCRIPT.format(
            func_basename=os.path.basename(exec_script_filename),
            docker_working_dir=docker_working_dir,
        )

    def _upload_file_to_s3(
        self, s3_bucket_name: str, temp_function_filename: str, s3_function_filename: str
    ) -> None:
        """Upload file to s3."""
        s3 = boto3.Session(profile_name=self.profile).client("s3")
        s3.upload_file(temp_function_filename, s3_bucket_name, s3_function_filename)

    def _get_ecr_info(self, image_tag: str) -> tuple:
        """Retrieve ecr details."""
        ecr = boto3.Session(profile_name=self.profile).client("ecr")
        ecr_credentials = ecr.get_authorization_token()["authorizationData"][0]
        ecr_password = (
            base64.b64decode(ecr_credentials["authorizationToken"])
            .replace(b"AWS:", b"")
            .decode("utf-8")
        )
        ecr_registry = ecr_credentials["proxyEndpoint"]
        ecr_repo_uri = f"{ecr_registry.replace('https://', '')}/{self.ecr_repo_name}:{image_tag}"
        return ecr_password, ecr_registry, ecr_repo_uri

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

        app_log.debug("AWS BATCH EXECUTOR: INSIDE PACKAGE AND UPLOAD METHOD")
        func_filename = f"func-{image_tag}.pkl"
        docker_working_dir = "/opt/covalent"

        with tempfile.NamedTemporaryFile(dir=self.cache_dir) as function_file:
            # Write serialized function to file
            pickle.dump((function, args, kwargs), function_file)
            function_file.flush()
            self._upload_file_to_s3(
                temp_function_filename=function_file.name,
                s3_bucket_name=self.s3_bucket_name,
                s3_function_filename=func_filename,
            )

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
            )
            exec_script_file.write(exec_script)
            exec_script_file.flush()

            # Write Dockerfile to file
            dockerfile = self._format_dockerfile(exec_script_file.name, docker_working_dir)
            dockerfile_file.write(dockerfile)
            dockerfile_file.flush()
            app_log.debug("AWS BATCH EXECUTOR: WRITE DOCKERFILE SUCCESS")

            local_dockerfile = os.path.join(task_results_dir, f"Dockerfile_{image_tag}")
            shutil.copyfile(dockerfile_file.name, local_dockerfile)

            # Build the Docker image
            docker_client = docker.from_env()
            image, build_log = docker_client.images.build(
                path=self.cache_dir,
                dockerfile=dockerfile_file.name,
                tag=image_tag,
                platform="linux/amd64",
            )
            app_log.debug("AWS BATCH EXECUTOR: DOCKER BUILD SUCCESS")

        ecr_username = "AWS"
        ecr_password, ecr_registry, ecr_repo_uri = self._get_ecr_info(image_tag)
        app_log.debug("AWS BATCH EXECUTOR: ECR INFO RETRIEVAL SUCCESS")

        docker_client.login(username=ecr_username, password=ecr_password, registry=ecr_registry)
        app_log.debug("AWS BATCH EXECUTOR: DOCKER CLIENT LOGIN SUCCESS")

        # Tag the image
        image.tag(ecr_repo_uri, tag=image_tag)
        app_log.debug("AWS BATCH EXECUTOR: IMAGE TAG SUCCESS")

        try:
            response = docker_client.images.push(ecr_repo_uri, tag=image_tag)
            app_log.debug(f"AWS BATCH EXECUTOR: DOCKER IMAGE PUSH SUCCESS {response}")
        except Exception as e:
            app_log.debug(f"{e}")

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

        app_log.debug("AWS BATCH EXECUTOR: INSIDE GET STATUS METHOD")
        job = batch.describe_jobs(jobs=[job_id])
        app_log.debug(f"AWS BATCH EXECUTOR: DESCRIBE BATCH JOBS SUCCESS {job}.")
        status = job["jobs"][0]["status"]
        app_log.debug(f"AWS BATCH EXECUTOR: JOB STATUS SUCCESS {status}.")
        try:
            exit_code = int(job["jobs"][0]["container"]["exitCode"])
        except Exception as e:
            exit_code = -1
        app_log.debug(f"AWS BATCH EXECUTOR: STATUS AND EXIT CODE SUCCESS {status, exit_code}.")

        return status, exit_code

    def _poll_batch_job(self, batch, job_id: str) -> None:
        # sourcery skip: raise-specific-error
        """Poll a Batch job until completion.

        Args:
            batch: Batch client object.
            job_id: Identifier used to identify a Batch job.

        Returns:
            None
        """

        app_log.debug("AWS BATCH EXECUTOR: INSIDE POLL BATCH JOB METHOD")
        status, exit_code = self.get_status(batch, job_id)

        while status not in ["SUCCEEDED", "FAILED"]:
            time.sleep(self.poll_freq)
            status, exit_code = self.get_status(batch, job_id)

        if exit_code != 0:
            app_log.debug(f"Job failed with exit code {exit_code}.")
            raise Exception(f"Job failed with exit code {exit_code}.")

    def _download_file_from_s3(
        self, s3_bucket_name: str, result_filename: str, local_result_filename: str
    ) -> None:
        """Download file from s3 into local file."""
        s3 = boto3.Session(profile_name=self.profile).client("s3")
        s3.download_file(s3_bucket_name, result_filename, local_result_filename)

    def _get_batch_logstream(self, job_id: str) -> str:
        """Get the log stream name corresponding to the batch."""
        batch = boto3.Session(profile_name=self.profile).client("batch")
        return batch.describe_jobs(jobs=[job_id])["jobs"][0]["container"]["logStreamName"]

    def _get_log_events(self, log_group_name: str, log_stream_name: str) -> str:
        """Get log events corresponding to the log group and stream names."""
        logs = boto3.Session(profile_name=self.profile).client("logs")

        # TODO: This should be paginated, but the command doesn't support boto3 pagination
        # Up to 10000 log events can be returned from a single call to get_log_events()
        events = logs.get_log_events(
            logGroupName=log_group_name,
            logStreamName=log_stream_name,
        )["events"]
        return "".join(event["message"] + "\n" for event in events)

    def _query_result(
        self,
        result_filename: str,
        task_results_dir: str,
        job_id: str,
    ) -> Tuple[Any, str, str]:
        """Query and retrieve a completed job's result.

        Args:
            result_filename: Name of the pickled result file.
            task_results_dir: Local directory where task results are stored.
            job_id: Identifier used to identify a Batch job.

        Returns:
            result: The task's result, as a Python object.
            logs: The stdout and stderr streams corresponding to the task.
            empty_string: A placeholder empty string.
        """

        app_log.debug("AWS BATCH EXECUTOR: INSIDE QUERY RESULT METHOD")
        local_result_filename = os.path.join(task_results_dir, result_filename)

        self._download_file_from_s3(self.s3_bucket_name, result_filename, local_result_filename)

        with open(local_result_filename, "rb") as f:
            result = pickle.load(f)
        os.remove(local_result_filename)

        log_stream_name = self._get_batch_logstream(job_id)
        log_events = self._get_log_events(self.batch_job_log_group_name, log_stream_name)
        return result, log_events, ""

    def cancel(self, job_id: str, reason: str = "None") -> None:
        """Cancel a Batch job.

        Args:
            job_id: Identifier used to specify a Batch job.
            reason: An optional string used to specify a cancellation reason.

        Returns:
            None
        """

        app_log.debug("AWS BATCH EXECUTOR: INSIDE CANCEL METHOD")
        batch = boto3.Session(profile_name=self.profile).client("batch")
        batch.terminate_job(jobId=job_id, reason=reason)
