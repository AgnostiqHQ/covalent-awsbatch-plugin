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


import json
import os
import subprocess
import sys

TERRAFORM_OUTPUTS = {}

try:
    terraform_dir = os.getenv("TF_DIR")
    proc = subprocess.run(
        [
            "terraform",
            f"-chdir={terraform_dir}",
            "output",
            "-json",
        ],
        check=True,
        capture_output=True,
    )
    TERRAFORM_OUTPUTS = json.loads(proc.stdout.decode())
except Exception as e:
    pass


def get(key: str, default):
    try:
        return TERRAFORM_OUTPUTS[key]["value"]
    except KeyError:
        return default
