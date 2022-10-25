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


import sys

import covalent as ct

# Extract terraform outputs & instantiate executor
import executor_instance

# Basic Workflow


@ct.electron(executor=executor_instance.executor)
def join_words(a, b):
    return ", ".join([a, b])


@ct.electron
def excitement(a):
    return f"{a}!"


@ct.lattice
def basic_workflow(a, b):
    phrase = join_words(a, b)
    return excitement(phrase)


# Dispatch the workflow
dispatch_id = ct.dispatch(basic_workflow)("Hello", "World")
result = ct.get_result(dispatch_id=dispatch_id, wait=True)
status = str(result.status)

print(result)

if status == str(ct.status.FAILED):
    print("Basic Workflow failed to run.")
    sys.exit(1)
