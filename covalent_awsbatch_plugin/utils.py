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

"""Helper methods for AWS Batch executor plugin."""

import asyncio
import json
import os

import cloudpickle as pickle


async def _execute_partial_in_threadpool(partial_func):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial_func)


def _load_pickle_file(filename):
    """Method to load the pickle file."""
    with open(filename, "rb") as f:
        result = pickle.load(f)
    os.remove(filename)
    return result


def _load_json_file(filename):
    """Method to load the json file."""
    with open(filename, "r", encoding="utf-8") as f:
        result = json.load(f)
    os.remove(filename)
    return result
