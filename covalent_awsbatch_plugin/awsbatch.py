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

import os
import shutil
import tempfile
from typing import Any, Dict, List, Tuple

import cloudpickle as pickle
from covalent._shared_files.util_classes import DispatchInfo
from covalent._workflow.transport import TransportableObject
from covalent.executor import BaseExecutor

_EXECUTOR_PLUGIN_DEFAULTS = {
}

executor_plugin_name = "AWSBatchExecutor"


class AWSBatchExecutor(BaseExecutor):
    """AWS Batch executor plugin class."""

    def __init__():
        super().__init__()

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
        
        with self.get_dispatch_context(dispatch_info):
            print("Inside AWS Batch executor!")

            ### This section is re-used from the Docker/Fargate executors

            # Write execution script to file

            # Write Dockerfile

            # Build the Docker image

            # ECR config

            # Tag the image

            # Push to ECR

            ### BELOW is specific to AWS Batch

            # Create a Batch Job Queue (one time only / CDK)

            # Create a Batch Compute Environment (one time only / CDK)
            # Here you can set a list of EC2 instance types

            # Create an IAM role for the container (one time only / CDK)

            # Register a job definition
            batch = boto3.client("batch", profile_name=self.profile)

            response = batch.register_job_definition(
                jobDefinitionName=f"covalent-{dispatch_id}-{node_id}",
                type="container", # Assumes a single EC2 instance will be used
                containerProperties={
                    image=ecr_repo_uri,
                    jobRoleArn=self.batch_task_role_name, # Needs to be pre-configured
                    resourceRequirements=[
                        {
                            "type": "VCPU",
                            "value": str(self.vcpu*1024)
                        },
                        {
                            "type": "MEMORY",
                            "value": str(self.memory*1024)
                        },
                        {
                            "type": "GPU",
                            "value": self.num_gpus, # Optional in case GPUs are requested
                        },
                    ],
                    platformCapabilities=["EC2"],   # Default is EC2; Fargate is also supported
                },
            )
            # TODO: Check response

            # Submit the job
            response = batch.submit_job(
                jobName=f"covalent-{dispatch_id}-{node_id}",
                jobQueue=self.batch_queue,  # Configured via CDK
                jobDefinition=f"covalent-{dispatch_id}-{node_id}"
            )
            # TODO: Check response

            # TODO: Either poll and return result, or return the response status

            return 42
