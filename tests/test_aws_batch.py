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

"""Unit tests for AWS batch executor."""

import json
import tempfile
from pathlib import Path
from typing import Dict, List
from unittest.mock import AsyncMock

import cloudpickle
import pytest
from botocore.exceptions import ClientError
from covalent._shared_files.exceptions import TaskCancelledError, TaskRuntimeError

from covalent_awsbatch_plugin.awsbatch import (
    FUNC_FILENAME,
    JOB_NAME,
    RESULT_FILENAME,
    AWSBatchExecutor,
)


class TestAWSBatchExecutor:

    MOCK_PROFILE = "my_profile"
    MOCK_S3_BUCKET_NAME = "s3-bucket"
    MOCK_BATCH_QUEUE = "batch-queue"
    MOCK_JOB_DEF_NAME = "job-definition"
    MOCK_EXECUTION_ROLE = "batch-execution-role"
    MOCK_JOB_ROLE = "batch-job-role"
    MOCK_LOG_GROUP_NAME = "batch-log-group"
    MOCK_VCPU = 0.1234
    MOCK_MEMORY = "123"
    MOCK_GPUS = 1
    MOCK_RETRY_ATTEMPTS = 1
    MOCK_TIME_LIMIT = 1
    MOCK_POLL_FREQ = 1
    MOCK_CONTAINER_IMAGE_URI = "container-image-uri"
    MOCK_DISPATCH_ID = 112233
    MOCK_NODE_ID = 1
    MOCK_BATCH_JOB_NAME = JOB_NAME.format(dispatch_id=MOCK_DISPATCH_ID, node_id=MOCK_NODE_ID)

    @property
    def MOCK_FUNC_FILENAME(self):
        return FUNC_FILENAME.format(dispatch_id=self.MOCK_DISPATCH_ID, node_id=self.MOCK_NODE_ID)

    @property
    def MOCK_RESULT_FILENAME(self):
        return RESULT_FILENAME.format(dispatch_id=self.MOCK_DISPATCH_ID, node_id=self.MOCK_NODE_ID)

    @property
    def MOCK_TASK_METADATA(self):
        return {"dispatch_id": self.MOCK_DISPATCH_ID, "node_id": self.MOCK_NODE_ID}

    @pytest.fixture
    def mock_executor_config(self, tmp_path: Path):
        MOCK_CREDENTIALS_FILE = tmp_path / "credentials"
        MOCK_CREDENTIALS_FILE.touch()
        return {
            "credentials": str(MOCK_CREDENTIALS_FILE),
            "profile": self.MOCK_PROFILE,
            "s3_bucket_name": self.MOCK_S3_BUCKET_NAME,
            "batch_queue": self.MOCK_BATCH_QUEUE,
            "batch_execution_role_name": self.MOCK_EXECUTION_ROLE,
            "batch_job_role_name": self.MOCK_JOB_ROLE,
            "batch_job_log_group_name": self.MOCK_LOG_GROUP_NAME,
            "vcpu": self.MOCK_VCPU,
            "memory": self.MOCK_MEMORY,
            "num_gpus": self.MOCK_GPUS,
            "retry_attempts": self.MOCK_RETRY_ATTEMPTS,
            "time_limit": self.MOCK_TIME_LIMIT,
            "poll_freq": self.MOCK_POLL_FREQ,
            "container_image_uri": self.MOCK_CONTAINER_IMAGE_URI,
        }

    @pytest.fixture
    def mock_executor(self, mock_executor_config):
        return AWSBatchExecutor(**mock_executor_config)

    def test_executor_init_default_values(self, mocker, mock_executor_config):
        """Test that the init values of the executor are set properly."""

        # only call to get_config is get_config("executors.ecs.cache_dir")
        mocker.patch("covalent_awsbatch_plugin.awsbatch.get_config", return_value="mock")
        # print(mock_executor_config)
        executor = AWSBatchExecutor(**mock_executor_config)

        assert executor.profile == self.MOCK_PROFILE
        assert executor.s3_bucket_name == self.MOCK_S3_BUCKET_NAME
        assert executor.batch_queue == self.MOCK_BATCH_QUEUE
        assert executor.execution_role == self.MOCK_EXECUTION_ROLE
        assert executor.batch_job_role_name == self.MOCK_JOB_ROLE
        assert executor.log_group_name == self.MOCK_LOG_GROUP_NAME
        assert executor.vcpu == self.MOCK_VCPU
        assert executor.memory == self.MOCK_MEMORY
        assert executor.num_gpus == self.MOCK_GPUS
        assert executor.retry_attempts == self.MOCK_RETRY_ATTEMPTS
        assert executor.time_limit == self.MOCK_TIME_LIMIT
        assert executor.poll_freq == self.MOCK_POLL_FREQ
        assert executor.container_image_uri == self.MOCK_CONTAINER_IMAGE_URI

    @pytest.mark.asyncio
    async def test_upload_file_to_s3(self, mock_executor, mocker):
        """Test method to upload file to s3."""
        boto3_mock = mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3")

        def some_function():
            pass

        mock_executor._upload_task_to_s3(
            some_function,
            self.MOCK_DISPATCH_ID,
            self.MOCK_NODE_ID,
            ("some_arg"),
            {"some": "kwarg"},
        )
        boto3_mock.Session().client().upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_task(self, mock_executor, mocker):
        """Test for method to call the upload task method."""

        def some_function(x):
            return x

        upload_to_s3_mock = mocker.patch(
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._upload_task_to_s3",
            return_value=AsyncMock(),
        )

        await mock_executor._upload_task(some_function, (1), {}, self.MOCK_TASK_METADATA)
        upload_to_s3_mock.assert_called_once_with(
            self.MOCK_DISPATCH_ID, self.MOCK_NODE_ID, some_function, (1), {}
        )

    @pytest.mark.asyncio
    async def test_get_status(self, mocker, mock_executor):
        """Test the get status method."""

        boto3_mock = mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3")

        def describe_jobs(jobs: List) -> Dict:
            if jobs[0] == "1":
                return {"jobs": [{"status": "SUCCESS", "container": {"exitCode": 1}}]}
            elif jobs[0] == "2":
                return {"jobs": [{"status": "RUNNING"}]}

        boto3_mock.Session().client().describe_jobs.side_effect = describe_jobs
        status, exit_code = await mock_executor.get_status(job_id="1")
        assert status == "SUCCESS"
        assert exit_code == 1

        status, exit_code = await mock_executor.get_status(job_id="2")
        assert status == "RUNNING"
        assert exit_code == -1

    @pytest.mark.asyncio
    async def test_poll_task(self, mock_executor, mocker):
        """Test the method to poll the batch job."""

        get_status_mock = mocker.patch(
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor.get_status",
            side_effect=[("RUNNING", 1), ("SUCCEEDED", 0), ("RUNNING", 1), ("FAILED", 2)],
        )

        kwargs = {
            "dispatch_id": self.MOCK_DISPATCH_ID,
            "node_id": self.MOCK_NODE_ID,
        }

        await mock_executor._poll_task(job_id="1", **kwargs)
        with pytest.raises(Exception):
            await mock_executor._poll_task(job_id="1", **kwargs)
        get_status_mock.assert_called()

    @pytest.mark.asyncio
    async def test_poll_task_cancelled(self, mock_executor, mocker):
        """Test for exception when to poll the batch job."""

        get_status_mock = mocker.patch(
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor.get_status",
            side_effect=[("CANCELLED", 1)],
        )

        kwargs = {
            "dispatch_id": self.MOCK_DISPATCH_ID,
            "node_id": self.MOCK_NODE_ID,
        }

        with pytest.raises(TaskCancelledError) as error:
            await mock_executor._poll_task(job_id="1", **kwargs)

        assert str(error.value) == "Job id 1 is cancelled."
        get_status_mock.assert_called()

    @pytest.mark.asyncio
    async def test_poll_task_failed(self, mock_executor, mocker):
        """Test for exception when to poll the batch job."""

        get_status_mock = mocker.patch(
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor.get_status",
            side_effect=[("FAILED", 1)],
        )

        stdout = ""
        stderr = "Exception: some error happened."
        traceback = f'Traceback (most recent call last):\n  File "/path/to/file", line 1, in module.py\n{stderr}'
        exception_class_name = "Exception"

        mocker.patch(
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._download_io_output",
            return_value=(stdout, stderr, traceback, exception_class_name),
        )

        kwargs = {
            "dispatch_id": self.MOCK_DISPATCH_ID,
            "node_id": self.MOCK_NODE_ID,
        }

        with pytest.raises(TaskRuntimeError) as error:
            await mock_executor._poll_task(job_id="1", **kwargs)

        assert str(error.value) == traceback
        get_status_mock.assert_called()

    @pytest.mark.asyncio
    async def test_download_file_from_s3(self, mock_executor, mocker):
        """Test method to download file from s3 into local file."""

        boto3_mock = mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3")

        await mock_executor._download_file_from_s3(
            "mock_s3_bucket_name", "mock_result_filename", "mock_local_result_filename"
        )
        boto3_mock.Session().client().download_file.assert_called_once_with(
            "mock_s3_bucket_name", "mock_result_filename", "mock_local_result_filename"
        )

    @pytest.mark.asyncio
    async def test_download_io_output(self, mock_executor, mocker):
        """Test method to download IO output from S3."""

        io_filename = f"io_output-{self.MOCK_DISPATCH_ID}-{self.MOCK_NODE_ID}.json"
        tmp_dir = Path(tempfile.gettempdir())
        boto3_mock = mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3")

        local_io_output_file = tmp_dir / io_filename

        with open(local_io_output_file, "w", encoding="utf-8") as f:
            json.dump(("mock_stdout", "mock_stderr", None, None), f)

        mock_executor.cache_dir = tmp_dir
        await mock_executor._download_io_output(self.MOCK_DISPATCH_ID, self.MOCK_NODE_ID)

        boto3_mock.Session().client().download_file.assert_called_once_with(
            self.MOCK_S3_BUCKET_NAME, io_filename, str(local_io_output_file)
        )

        # `_load_json_file` inside `_download_io_output` should delete the temp file.
        assert not local_io_output_file.exists()

    @pytest.mark.asyncio
    async def test_cancel(self, mock_executor, mocker):
        """Test job cancellation method."""

        MOCK_JOB_ID = 1
        mock_dispatch_id = "abcdef"
        mock_node_id = 0
        mock_task_metadata = {"dispatch_id": mock_dispatch_id, "node_id": mock_node_id}
        boto3_mock = mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3")
        client_mock = boto3_mock.Session().client()

        is_cancelled = await mock_executor.cancel(
            task_metadata=mock_task_metadata, job_handle=MOCK_JOB_ID
        )

        client_mock.terminate_job.assert_called_once_with(
            jobId=MOCK_JOB_ID, reason=f"Triggered cancellation with {mock_task_metadata}"
        )
        assert is_cancelled is True

    @pytest.mark.asyncio
    async def test_cancel_failed(self, mock_executor, mocker):
        """Test job cancellation method."""

        MOCK_JOB_ID = 1
        mock_dispatch_id = "abcdef"
        mock_node_id = 0
        mock_task_metadata = {"dispatch_id": mock_dispatch_id, "node_id": mock_node_id}
        boto3_mock = mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3")
        client_mock = boto3_mock.Session().client()
        error = ClientError(
            operation_name="TerminateJob",
            error_response={
                "Error": {
                    "Code": "UnreachableHostException",
                    "Message": 'Could not connect to the endpoint URL: "https://batch.us-east-1.amazonaws.com/v1/canceljob"',
                }
            },
        )
        client_mock.terminate_job.side_effect = error

        is_cancelled = await mock_executor.cancel(
            task_metadata=mock_task_metadata, job_handle=MOCK_JOB_ID
        )

        assert is_cancelled is False
        client_mock.terminate_job.assert_called_once_with(
            jobId=MOCK_JOB_ID, reason=f"Triggered cancellation with {mock_task_metadata}"
        )

    @pytest.mark.asyncio
    async def test_query_results(self, mock_executor, mocker, tmp_path: Path):
        """Test the method to query the result object."""

        mock_cwd = tmp_path
        mock_executor.cache_dir = mock_cwd.resolve()
        mock_local_result_path = mock_cwd / self.MOCK_RESULT_FILENAME
        mock_local_result_path.touch()

        MOCK_IO_OUTPUT = tuple([""] * 4)

        mocker.patch("covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._download_file_from_s3")
        mocker.patch(
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._download_io_output",
            return_value=MOCK_IO_OUTPUT,
        )

        # result, stdout, stderr
        MOCK_RESULT_CONTENTS = "mock_result", MOCK_IO_OUTPUT[0], MOCK_IO_OUTPUT[1]

        with open(mock_local_result_path, "wb") as f:
            cloudpickle.dump(MOCK_RESULT_CONTENTS[0], f)

        assert await mock_executor.query_result(self.MOCK_TASK_METADATA) == MOCK_RESULT_CONTENTS

    @pytest.mark.asyncio
    async def test_run(self, mocker, mock_executor):
        """Test the run method."""

        MOCK_IDENTITY = {"Account": 1234}

        def mock_func(x):
            return x

        # result, stdout, stderr
        MOCK_RESULT_CONTENTS = "mock_result", "", ""

        upload_task_mock = mocker.patch(
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._upload_task"
        )
        validate_credentials_mock = mocker.patch(
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._validate_credentials"
        )
        submit_task_mock = mocker.patch(
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor.submit_task"
        )
        _poll_task_mock = mocker.patch(
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._poll_task"
        )
        query_result_mock = mocker.patch(
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor.query_result",
            return_value=MOCK_RESULT_CONTENTS,
        )
        mock_executor.get_cancel_requested = AsyncMock(return_value=False)
        mock_executor.set_job_handle = AsyncMock()

        validate_credentials_mock.return_value = MOCK_IDENTITY

        await mock_executor.run(
            function=mock_func, args=[], kwargs={"x": 1}, task_metadata=self.MOCK_TASK_METADATA
        )

        upload_task_mock.assert_called_once_with(mock_func, [], {"x": 1}, self.MOCK_TASK_METADATA)
        validate_credentials_mock.assert_called_once()
        submit_task_mock.assert_called_once_with(self.MOCK_TASK_METADATA, MOCK_IDENTITY)

        returned_job_id = await submit_task_mock()

        _poll_task_mock.assert_called_once_with(
            returned_job_id, self.MOCK_DISPATCH_ID, self.MOCK_NODE_ID
        )
        query_result_mock.assert_called_once_with(self.MOCK_TASK_METADATA)

    @pytest.mark.asyncio
    async def test_run_cancel_before_upload(self, mocker, mock_executor):
        """Test the run method when cancel is requested before uploading to S3"""

        MOCK_IDENTITY = {"Account": 1234}

        def mock_func(x):
            return x

        validate_credentials_mock = mocker.patch(
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._validate_credentials"
        )
        validate_credentials_mock.return_value = MOCK_IDENTITY
        mock_executor.get_cancel_requested = AsyncMock(return_value=True)

        with pytest.raises(TaskCancelledError) as exception:
            await mock_executor.run(
                function=mock_func, args=[], kwargs={"x": 1}, task_metadata=self.MOCK_TASK_METADATA
            )
            assert (
                exception == f"AWS Batch job {self.MOCK_BATCH_JOB_NAME} requested to be cancelled"
            )

        validate_credentials_mock.assert_called_once()
        mock_executor.get_cancel_requested.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_cancel_before_submit_task(self, mocker, mock_executor):
        """Test the run method when cancel is requested before submitting task to AWS Batch."""

        MOCK_IDENTITY = {"Account": 1234}

        def mock_func(x):
            return x

        validate_credentials_mock = mocker.patch(
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._validate_credentials"
        )
        validate_credentials_mock.return_value = MOCK_IDENTITY
        mock_executor.get_cancel_requested = AsyncMock(side_effect=[False, True])
        upload_task_mock = mocker.patch(
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._upload_task"
        )

        with pytest.raises(TaskCancelledError) as exception:
            await mock_executor.run(
                function=mock_func, args=[], kwargs={"x": 1}, task_metadata=self.MOCK_TASK_METADATA
            )
            assert (
                exception == f"AWS Batch job {self.MOCK_BATCH_JOB_NAME} requested to be cancelled"
            )

        validate_credentials_mock.assert_called_once()
        upload_task_mock.assert_called_once_with(mock_func, [], {"x": 1}, self.MOCK_TASK_METADATA)
        assert mock_executor.get_cancel_requested.call_count == 2

    @pytest.mark.asyncio
    async def test_submit_task(self, mocker, mock_executor):
        MOCK_IDENTITY = {"Account": 1234}
        boto3_mock = mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3")
        await mock_executor.submit_task(self.MOCK_TASK_METADATA, MOCK_IDENTITY)
        boto3_mock.Session().client().submit_job.assert_called_once()
        boto3_mock.Session().client().register_job_definition.assert_called_once()
