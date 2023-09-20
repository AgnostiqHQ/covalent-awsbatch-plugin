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

"""Unit tests for AWS Batch executor utils file."""

import tempfile
from functools import partial
from pathlib import Path

import cloudpickle as pickle
import pytest

from covalent_awsbatch_plugin.utils import _execute_partial_in_threadpool, _load_pickle_file


@pytest.mark.asyncio
async def test_execute_partial_in_threadpool():
    """Test method to execute partial function in asyncio threadpool."""

    def test_func(x):
        return x

    partial_func = partial(test_func, x=1)
    future = await _execute_partial_in_threadpool(partial_func)
    assert future == 1


def test_load_pickle_file(mocker):
    """Test the method used to load the pickled file and delete the file afterwards."""
    temp_fp = "/tmp/test.pkl"
    with open(temp_fp, "wb") as f:
        pickle.dump("test success", f)

    assert Path(temp_fp).exists()
    res = _load_pickle_file(temp_fp)
    assert res == "test success"
    assert not Path(temp_fp).exists()
