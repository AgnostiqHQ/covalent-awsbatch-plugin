&nbsp;

<div align="center">

<img src="https://raw.githubusercontent.com/AgnostiqHQ/covalent-awsbatch-plugin/main/assets/aws_batch_readme_banner.jpg" width=150%>

</div>

## Covalent AWS Batch Plugin

Covalent is a Pythonic workflow tool used to execute tasks on advanced computing hardware. This executor plugin interfaces Covalent with [AWS Batch](https://docs.aws.amazon.com/batch/). In order for workflows to be deployable, users must have AWS credentials attached to the [CovalentBatchExecutorPolicy](https://github.com/AgnostiqHQ/covalent-awsbatch-plugin/blob/main/infra/iam/CovalentBatchExecutorPolicy.json). Users will need additional permissions to provision or manage cloud infrastructure used by this plugin.

To use this plugin with Covalent, clone this repository and install it using `pip`:

```
git clone git@github.com:AgnostiqHQ/covalent-awsbatch-plugin.git
cd covalent-awsbatch-plugin
pip install .
```

Users must add the correct entries to their Covalent [configuration](https://covalent.readthedocs.io/en/latest/how_to/config/customization.html) to support the AWS Batch plugin. Below is an example which works using some basic infrastructure created for testing purposes:

```console
[executors.awsbatch]
credentials = "/home/user/.aws/credentials"
profile = ""
s3_bucket_name = "covalent-batch-job-resources"
ecr_repo_name = "covalent-batch-job-images"
batch_job_definition_name = "covalent-batch-jobs"
batch_queue = "covalent-batch-queue"
batch_execution_role_name = "ecsTaskExecutionRole"
batch_job_role_name = "CovalentBatchJobRole"
batch_job_log_group_name = "covalent-batch-job-logs"
vcpu = 2
memory = 3.75
num_gpus = 0
retry_attempts = 3
time_limit = 300
cache_dir = "/tmp/covalent"
poll_freq = 10
```

In the test infrastructure, jobs can run on any instance in the c4 family. If GPUs are required, other instance families should be configured in the compute environment used by the batch queue.

The user can set the executor using the parameters set in the config file with the string name `awsbatch`:

```python
@ct.electron(executor="awsbatch")
def my_custom_task(x, y):
    return x + y
```

In addition, users can instantiate an `AWSBatchExecutor` object to customize the resources and other behavior:

```python
# Request 16 vCPUs and 1GB memory per thread, with a 10-minute time limit.
executor = ct.executor.AWSBatchExecutor(
    vcpu=16,
    memory=16,
    time_limit=600
)

@ct.electron(executor=executor)
def my_custom_task(x, y):
    return x + y
```

In the latter scenario, the parameters that are not set explicitly are read from the config file.

For more information about how to get started with Covalent, check out the project [homepage](https://github.com/AgnostiqHQ/covalent) and the official [documentation](https://covalent.readthedocs.io/en/latest/).

## Release Notes

Release notes are available in the [Changelog](https://github.com/AgnostiqHQ/covalent-awsbatch-plugin/blob/main/CHANGELOG.md).

## Citation

Please use the following citation in any publications:

> W. J. Cunningham, S. K. Radha, F. Hasan, J. Kanem, S. W. Neagle, and S. Sanand.
> *Covalent.* Zenodo, 2022. https://doi.org/10.5281/zenodo.5903364

## License

Covalent is licensed under the GNU Affero GPL 3.0 License. Covalent may be distributed under other licenses upon request. See the [LICENSE](https://github.com/AgnostiqHQ/covalent-awsbatch-plugin/blob/main/LICENSE) file or contact the [support team](mailto:support@agnostiq.ai) for more details.
