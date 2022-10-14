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

"""Unit tests for AWS Batch executor utils file."""

from functools import partial

import pytest

from covalent_awsbatch_plugin.utils import _execute_partial_in_threadpool


@pytest.mark.asyncio
async def test_execute_partial_in_threadpool():
    """Test method to execute partial function in asyncio threadpool."""

    def test_func(x):
        return x

    partial_func = partial(test_func, x=1)
    future = await _execute_partial_in_threadpool(partial_func)
    assert future == 1
