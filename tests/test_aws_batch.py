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

import pytest

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
        poll_freq=0,
    )


def test_run():
    pass


def test_execute():
    pass


def test_format_exec_script(batch_executor):
    """Test the function that constructs the executable tasks-execution Python script."""

    exec_script = batch_executor._format_exec_script(
        func_filename="mock_function_filename",
        result_filename="mock_result_filename",
        docker_working_dir="mock_docker_working_dir",
    )
    assert exec_script == PYTHON_EXEC_SCRIPT.format(
        func_filename="mock_function_filename",
        s3_bucket_name=batch_executor.s3_bucket_name,
        result_filename="mock_result_filename",
        docker_working_dir="mock_docker_working_dir",
    )


def test_format_dockerfile():
    pass


def test_package_and_upload():
    pass


def test_get_status():
    pass


def test_poll_batch_job_id():
    pass


def test_query_results():
    pass


def test_cancel():
    pass
