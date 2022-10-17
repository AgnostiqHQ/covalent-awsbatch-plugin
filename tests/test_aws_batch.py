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

"""Unit tests for AWS batch executor."""

from pathlib import Path
from typing import Dict, List
from unittest.mock import AsyncMock

import cloudpickle
import pytest

from covalent_awsbatch_plugin.awsbatch import FUNC_FILENAME, RESULT_FILENAME, AWSBatchExecutor


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
    MOCK_DISPATCH_ID = 112233
    MOCK_NODE_ID = 1

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
            "batch_job_definition_name": self.MOCK_JOB_DEF_NAME,
            "batch_execution_role_name": self.MOCK_EXECUTION_ROLE,
            "batch_job_role_name": self.MOCK_JOB_ROLE,
            "batch_job_log_group_name": self.MOCK_LOG_GROUP_NAME,
            "vcpu": self.MOCK_VCPU,
            "memory": self.MOCK_MEMORY,
            "num_gpus": self.MOCK_GPUS,
            "retry_attempts": self.MOCK_RETRY_ATTEMPTS,
            "time_limit": self.MOCK_TIME_LIMIT,
            "poll_freq": self.MOCK_POLL_FREQ,
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
        assert executor.batch_job_definition_name == self.MOCK_JOB_DEF_NAME
        assert executor.execution_role == self.MOCK_EXECUTION_ROLE
        assert executor.batch_job_role_name == self.MOCK_JOB_ROLE
        assert executor.log_group_name == self.MOCK_LOG_GROUP_NAME
        assert executor.vcpu == self.MOCK_VCPU
        assert executor.memory == self.MOCK_MEMORY
        assert executor.num_gpus == self.MOCK_GPUS
        assert executor.retry_attempts == self.MOCK_RETRY_ATTEMPTS
        assert executor.time_limit == self.MOCK_TIME_LIMIT
        assert executor.poll_freq == self.MOCK_POLL_FREQ

    @pytest.mark.asyncio
    async def test_upload_file_to_s3(self, mock_executor, mocker):
        """Test method to upload file to s3."""
        boto3_mock = mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3")

        def some_function():
            pass

        await mock_executor._upload_task_to_s3(
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

        await mock_executor._poll_task(job_id="1")
        with pytest.raises(Exception):
            await mock_executor._poll_task(job_id="1")
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
    async def test_get_batch_logstream(self, mock_executor, mocker):
        """Test the method to get the batch logstream."""
        RETURN_VALUE = {"jobs": [{"container": {"logStreamName": "mockLogStream"}}]}

        boto3_mock = mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3")
        client_mock = boto3_mock.Session().client()

        threadpool_mock = mocker.patch(
            "covalent_awsbatch_plugin.awsbatch._execute_partial_in_threadpool",
            return_value=RETURN_VALUE,
        )

        future = await mock_executor._get_batch_logstream("1")
        assert future == "mockLogStream"
        threadpool_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_log_events(self, mock_executor, mocker):
        """Test the method to get log events."""

        MOCK_STREAM = "mock-stream-name"

        boto3_mock = mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3")
        client_mock = boto3_mock.Session().client()

        client_mock.get_log_events.return_value = {
            "events": [{"message": "hello"}, {"message": "world"}]
        }
        assert await mock_executor._get_log_events(MOCK_STREAM) == "hello\nworld\n"
        client_mock.get_log_events.assert_called_once_with(
            logGroupName=self.MOCK_LOG_GROUP_NAME, logStreamName=MOCK_STREAM
        )

    @pytest.mark.asyncio
    async def test_cancel(self, mock_executor, mocker):
        """Test job cancellation method."""

        MOCK_JOB_ID = 1
        MOCK_CANCELLATION_REASON = "unknown"
        boto3_mock = mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3")
        client_mock = boto3_mock.Session().client()

        await mock_executor.cancel(job_id=MOCK_JOB_ID, reason=MOCK_CANCELLATION_REASON)
        client_mock.terminate_job.assert_called_once_with(
            jobId=MOCK_JOB_ID, reason=MOCK_CANCELLATION_REASON
        )

    @pytest.mark.asyncio
    async def test_query_results(self, mock_executor, mocker, tmp_path: Path):
        """Test the method to query the result object."""

        mock_cwd = tmp_path
        mock_executor._cwd = mock_cwd.resolve()
        mock_local_result_path = mock_cwd / self.MOCK_RESULT_FILENAME
        mock_local_result_path.touch()

        mocker.patch("covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._download_file_from_s3")
        mocker.patch("covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._get_batch_logstream")
        mocker.patch("covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._get_log_events")

        MOCK_RESULT_CONTENTS = "mock_result"

        with open(mock_local_result_path, "wb") as f:
            cloudpickle.dump(MOCK_RESULT_CONTENTS, f)

        assert await mock_executor.query_result(self.MOCK_TASK_METADATA) == MOCK_RESULT_CONTENTS

    @pytest.mark.asyncio
    async def test_run(self, mocker, mock_executor):
        """Test the run method."""

        MOCK_IDENTITY = {"Account": 1234}

        def mock_func(x):
            return x

        boto3_mock = mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3")

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
            "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor.query_result"
        )

        validate_credentials_mock.return_value = MOCK_IDENTITY

        await mock_executor.run(
            function=mock_func, args=[], kwargs={"x": 1}, task_metadata=self.MOCK_TASK_METADATA
        )

        upload_task_mock.assert_called_once_with(mock_func, [], {"x": 1}, self.MOCK_TASK_METADATA)
        validate_credentials_mock.assert_called_once()
        submit_task_mock.assert_called_once_with(self.MOCK_TASK_METADATA, MOCK_IDENTITY)

        returned_job_id = await submit_task_mock()

        _poll_task_mock.assert_called_once_with(returned_job_id)
        query_result_mock.assert_called_once_with(self.MOCK_TASK_METADATA)
