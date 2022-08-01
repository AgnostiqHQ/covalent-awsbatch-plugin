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

from typing import Dict, List
from unittest.mock import MagicMock

import pytest
from moto import mock_batch

from covalent_awsbatch_plugin.awsbatch import AWSBatchExecutor
from covalent_awsbatch_plugin.scripts import DOCKER_SCRIPT, PYTHON_EXEC_SCRIPT


@pytest.fixture
def batch_executor():
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
    )


def test_execute():
    pass


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


def test_package_and_upload():
    pass


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


def test_query_results():
    pass


def test_cancel(batch_executor, mocker):
    """Test job cancellation method."""

    mm = MagicMock()

    mocker.patch("covalent_awsbatch_plugin.awsbatch.boto3.client", return_value=mm.terminate_job())
    batch_executor.cancel(job_id="1", reason="unknown")
    mm.terminate_job.assert_called_once_with()
