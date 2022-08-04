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

import os
from base64 import b64encode
from typing import Dict, List
from unittest.mock import MagicMock

import cloudpickle
import pytest

from covalent_awsbatch_plugin.awsbatch import AWSBatchExecutor
from covalent_awsbatch_plugin.scripts import DOCKER_SCRIPT, PYTHON_EXEC_SCRIPT


@pytest.fixture
def batch_executor(mocker):
    mocker.patch("covalent_awsbatch_plugin.awsbatch.get_config")
    return AWSBatchExecutor(
        credentials="mock_credentials",
        profile="mock_profile",
        s3_bucket_name="mock_s3_bucket_name",
        ecr_repo_name="mock_ecr_repo_name",
        batch_queue="mock_batch_queue",
        batch_job_definition_name="mock_batch_job_definition_name",
        batch_execution_role_name="mock_batch_execution_role_name",
        batch_job_role_name="mock_batch_job_role_name",
        batch_job_log_group_name="mock_batch_job_log_group_name",
        vcpu=0,
        memory=0.0,
        num_gpus=0,
        retry_attempts=0,
        time_limit=0,
        poll_freq=0.1,
        cache_dir="mock",
    )


def test_executor_init_default_values(mocker):
    """Test that the init values of the executor are set properly."""
    mocker.patch("covalent_awsbatch_plugin.awsbatch.get_config", return_value="mock")
    abe = AWSBatchExecutor()
    assert abe.credentials == "mock"
    assert abe.profile == "mock"
    assert abe.s3_bucket_name == "mock"
    assert abe.ecr_repo_name == "mock"
    assert abe.batch_queue == "mock"
    assert abe.batch_job_definition_name == "mock"
    assert abe.batch_execution_role_name == "mock"
    assert abe.batch_job_role_name == "mock"
    assert abe.batch_job_log_group_name == "mock"
    assert abe.vcpu == "mock"
    assert abe.memory == "mock"
    assert abe.num_gpus == "mock"
    assert abe.retry_attempts == "mock"
    assert abe.time_limit == "mock"
    assert abe.poll_freq == "mock"
    assert abe.cache_dir == "mock"


def test_get_aws_account(batch_executor, mocker):
    """Test the method to retrieve the aws account."""
    mm = MagicMock()
    mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3.Session", return_value=mm)
    batch_executor._get_aws_account()
    mm.client().get_caller_identity.called_once_with()
    mm.client().get_caller_identity.get.called_once_with("Account")


def test_execute(batch_executor, mocker):
    """Test the execute method."""

    def mock_func(x):
        return x

    mm = MagicMock()
    mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3.Session", return_value=mm)
    package_and_upload_mock = mocker.patch(
        "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._package_and_upload"
    )
    poll_batch_job_mock = mocker.patch(
        "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._poll_batch_job"
    )
    query_result_mock = mocker.patch(
        "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._query_result"
    )
    batch_executor.execute(
        function=mock_func,
        args=[],
        kwargs={"x": 1},
        dispatch_id="mock_dispatch_id",
        results_dir="/tmp",
        node_id=1,
    )
    package_and_upload_mock.assert_called_once_with(
        mock_func,
        "mock_dispatch_id-1",
        "/tmp/mock_dispatch_id",
        "result-mock_dispatch_id-1.pkl",
        [],
        {"x": 1},
    )
    poll_batch_job_mock.assert_called_once()
    query_result_mock.assert_called_once()
    mm.client().register_job_definition.assert_called_once()
    mm.client().submit_job.assert_called_once()


def test_format_exec_script(batch_executor):
    """Test method that constructs the executable tasks-execution Python script."""
    kwargs = {
        "func_filename": "mock_function_filename",
        "result_filename": "mock_result_filename",
        "docker_working_dir": "mock_docker_working_dir",
    }
    exec_script = batch_executor._format_exec_script(**kwargs)
    assert exec_script == PYTHON_EXEC_SCRIPT.format(
        s3_bucket_name=batch_executor.s3_bucket_name, **kwargs
    )


def test_format_dockerfile(batch_executor):
    """Test method that constructs the dockerfile."""
    docker_script = batch_executor._format_dockerfile(
        exec_script_filename="root/mock_exec_script_filename",
        docker_working_dir="mock_docker_working_dir",
    )
    assert docker_script == DOCKER_SCRIPT.format(
        func_basename="mock_exec_script_filename", docker_working_dir="mock_docker_working_dir"
    )


def test_upload_file_to_s3(batch_executor, mocker):
    """Test method to upload file to s3."""
    mm = MagicMock()
    mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3.Session", return_value=mm)
    batch_executor._upload_file_to_s3(
        "mock_s3_bucket_name", "mock_temp_function_filename", "mock_s3_function_filename"
    )
    mm.client().upload_file.assert_called_once_with(
        "mock_temp_function_filename", "mock_s3_bucket_name", "mock_s3_function_filename"
    )
    # print(mm.mock_calls)


def test_ecr_info(batch_executor, mocker):
    """Test method to retrieve ecr related info."""
    mm = MagicMock()
    mm.client().get_authorization_token.return_value = {
        "authorizationData": [
            {
                "authorizationToken": b64encode(b"fake_token"),
                "proxyEndpoint": "proxy_endpoint",
            }
        ]
    }
    mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3.Session", return_value=mm)
    assert batch_executor._get_ecr_info("mock_image_tag") == (
        "fake_token",
        "proxy_endpoint",
        "proxy_endpoint/mock_ecr_repo_name:mock_image_tag",
    )
    mm.client().get_authorization_token.assert_called_once_with()


def test_package_and_upload(batch_executor, mocker):
    """Test the package and upload method."""
    upload_file_to_s3_mock = mocker.patch(
        "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._upload_file_to_s3"
    )
    format_exec_script_mock = mocker.patch(
        "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._format_exec_script", return_value=""
    )
    format_dockerfile_mock = mocker.patch(
        "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._format_dockerfile", return_value=""
    )
    get_ecr_info_mock = mocker.patch(
        "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._get_ecr_info",
        return_value=("", "", ""),
    )
    mocker.patch("covalent_awsbatch_plugin.awsbatch.shutil.copyfile")
    mm = MagicMock()
    tag_mock = MagicMock()
    mm.images.build.return_value = tag_mock, "logs"
    mocker.patch("covalent_awsbatch_plugin.awsbatch.docker.from_env", return_value=mm)

    batch_executor._package_and_upload(
        "mock_transportable_object",
        "mock_image_tag",
        "mock_task_results_dir",
        "mock_result_filename",
        [],
        {},
    )
    upload_file_to_s3_mock.assert_called_once()
    format_exec_script_mock.assert_called_once()
    format_dockerfile_mock.assert_called_once()
    get_ecr_info_mock.assert_called_once()


def test_get_status(batch_executor):
    """Test the get status method."""

    class MockBatch:
        def describe_jobs(self, jobs: List) -> Dict:
            if jobs[0] == "1":
                return {"jobs": [{"status": "SUCCESS", "container": {"exitCode": 1}}]}
            elif jobs[0] == "2":
                return {"jobs": [{"status": "RUNNING"}]}

    status, exit_code = batch_executor.get_status(batch=MockBatch(), job_id="1")
    assert status == "SUCCESS"
    assert exit_code == 1

    status, exit_code = batch_executor.get_status(batch=MockBatch(), job_id="2")
    assert status == "RUNNING"
    assert exit_code == -1


def test_poll_batch_job(batch_executor, mocker):
    """Test the method to poll the batch job."""
    get_status_mock = mocker.patch(
        "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor.get_status",
        side_effect=[("RUNNING", 1), ("SUCCEEDED", 0), ("RUNNING", 1), ("FAILED", 2)],
    )

    batch_executor._poll_batch_job(batch=MagicMock(), job_id="1")
    with pytest.raises(Exception):
        batch_executor._poll_batch_job(batch=MagicMock(), job_id="1")
    get_status_mock.assert_called()


def test_download_file_from_s3(batch_executor, mocker):
    """Test method to download file from s3 into local file."""
    mm = MagicMock()
    mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3.Session", return_value=mm)
    batch_executor._download_file_from_s3(
        "mock_s3_bucket_name", "mock_result_filename", "mock_local_result_filename"
    )
    mm.client().download_file.assert_called_once_with(
        "mock_s3_bucket_name", "mock_result_filename", "mock_local_result_filename"
    )


def test_get_batch_logstream(batch_executor, mocker):
    """Test the method to get the batch logstream."""
    mm = MagicMock()
    mm.client().describe_jobs.return_value = {
        "jobs": [{"container": {"logStreamName": "mockLogStream"}}]
    }
    mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3.Session", return_value=mm)
    assert batch_executor._get_batch_logstream("1") == "mockLogStream"
    mm.client().describe_jobs.assert_called_once_with(jobs=["1"])


def test_get_log_events(batch_executor, mocker):
    """Test the method to get log events."""
    mm = MagicMock()
    mm.client().get_log_events.return_value = {
        "events": [{"message": "hello"}, {"message": "world"}]
    }
    mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3.Session", return_value=mm)
    assert batch_executor._get_log_events("mock_group", "mock_stream") == "hello\nworld\n"
    mm.client().get_log_events.assert_called_once_with(
        logGroupName="mock_group", logStreamName="mock_stream"
    )


def test_query_results(batch_executor, mocker):
    """Test the method to query the results."""
    mocker.patch("covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._download_file_from_s3")
    mocker.patch("covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._get_batch_logstream")
    mocker.patch(
        "covalent_awsbatch_plugin.awsbatch.AWSBatchExecutor._get_log_events",
        return_value="mock_logs",
    )
    task_results_dir, result_filename = "/tmp", "mock_result_filename.pkl"
    local_result_filename = os.path.join(task_results_dir, result_filename)
    with open(local_result_filename, "wb") as f:
        cloudpickle.dump("hello world", f)
    assert batch_executor._query_result(result_filename, task_results_dir, "1") == (
        "hello world",
        "mock_logs",
        "",
    )


def test_cancel(batch_executor, mocker):
    """Test job cancellation method."""
    mm = MagicMock()
    mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3.Session", return_value=mm)
    batch_executor.cancel(job_id="1", reason="unknown")
    mm.client().terminate_job.assert_called_once_with(jobId="1", reason="unknown")
