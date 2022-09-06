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
