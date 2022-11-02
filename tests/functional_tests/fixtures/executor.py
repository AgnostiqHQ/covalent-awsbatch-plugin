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

from dotenv import load_dotenv

load_dotenv()

import os

from covalent_awsbatch_plugin.awsbatch import AWSBatchExecutor

executor_config = {
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
