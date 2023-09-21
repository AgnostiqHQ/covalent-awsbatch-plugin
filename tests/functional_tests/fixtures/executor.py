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

from dotenv import load_dotenv

load_dotenv()

import os

from covalent_awsbatch_plugin.awsbatch import AWSBatchExecutor

executor_config = {
    "region": os.getenv("executor_region"),
    "s3_bucket_name": os.getenv("executor_s3_bucket_name"),
    "ecr_repo_name": os.getenv("executor_ecr_repo_name"),
    "batch_job_definition_name": os.getenv("executor_batch_job_definition_name"),
    "batch_queue": os.getenv("executor_batch_queue"),
    "batch_execution_role_name": os.getenv("executor_batch_execution_role_name"),
    "batch_job_role_name": os.getenv("executor_batch_job_role_name"),
    "batch_job_log_group_name": os.getenv("executor_batch_job_log_group_name"),
    "vcpu": os.getenv("executor_vcpu", 2),
    "memory": os.getenv("executor_memory", 3.75),
}

print("Using Executor Configuration:")
print(executor_config)

executor = AWSBatchExecutor(**executor_config)
