&nbsp;

<div align="center">

<img src="https://raw.githubusercontent.com/AgnostiqHQ/covalent-awsbatch-plugin/main/assets/aws_batch_readme_banner.jpg" width=150%>

[![covalent](https://img.shields.io/badge/covalent-0.177.0-purple)](https://github.com/AgnostiqHQ/covalent)
[![python](https://img.shields.io/pypi/pyversions/covalent-awsbatch-plugin)](https://github.com/AgnostiqHQ/covalent-awsbatch-plugin)
[![tests](https://github.com/AgnostiqHQ/covalent-awsbatch-plugin/actions/workflows/tests.yml/badge.svg)](https://github.com/AgnostiqHQ/covalent-awsbatch-plugin/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/AgnostiqHQ/covalent-awsbatch-plugin/branch/main/graph/badge.svg?token=QNTR18SR5H)](https://codecov.io/gh/AgnostiqHQ/covalent-awsbatch-plugin)
[![agpl](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.en.html)

</div>

## Covalent AWS Batch Plugin

Covalent is a Pythonic workflow tool used to execute tasks on advanced computing hardware.

This executor plugin interfaces Covalent with [AWS Batch](https://docs.aws.amazon.com/batch/) which allows tasks in a covalent workflow to be executed as AWS batch jobs.

## 1. Installation

To use this plugin with Covalent, simply install it using `pip`:

```
pip install covalent-awsbatch-plugin
```

## 2. Usage Example

This is an example of how a workflow can be adapted to utilize the AWS Batch Executor. Here we train a simple Support Vector Machine (SVM) model and use an existing AWS Batch Compute environment to run the `train_svm` electron as a batch job. We also note we require [DepsPip](https://covalent.readthedocs.io/en/latest/concepts/concepts.html#depspip) to install the dependencies when creating the batch job.

```python
from numpy.random import permutation
from sklearn import svm, datasets
import covalent as ct

deps_pip = ct.DepsPip(
	packages=["numpy==1.23.2", "scikit-learn==1.1.2"]
)

executor = ct.executor.AWSBatchExecutor(
    s3_bucket_name = "covalent-batch-qa-job-resources",
    batch_queue = "covalent-batch-qa-queue",
    batch_execution_role_name = "ecsTaskExecutionRole",
    batch_job_role_name = "covalent-batch-qa-job-role",
    batch_job_log_group_name = "covalent-batch-qa-log-group",
    vcpu = 2, # Number of vCPUs to allocate
    memory = 3.75, # Memory in GB to allocate
    time_limit = 300, # Time limit of job in seconds
)

# Use executor plugin to train our SVM model.
@ct.electron(
    executor=executor,
    deps_pip=deps_pip
)
def train_svm(data, C, gamma):
    X, y = data
    clf = svm.SVC(C=C, gamma=gamma)
    clf.fit(X[90:], y[90:])
    return clf

@ct.electron
def load_data():
    iris = datasets.load_iris()
    perm = permutation(iris.target.size)
    iris.data = iris.data[perm]
    iris.target = iris.target[perm]
    return iris.data, iris.target

@ct.electron
def score_svm(data, clf):
    X_test, y_test = data
    return clf.score(
    	X_test[:90],
	 	y_test[:90]
    )

@ct.lattice
def run_experiment(C=1.0, gamma=0.7):
    data = load_data()
    clf = train_svm(
    	data=data,
    	C=C,
    	gamma=gamma
    )
    score = score_svm(
    	data=data,
	 	clf=clf
    )
    return score

# Dispatch the workflow
dispatch_id = ct.dispatch(run_experiment)(
	C=1.0,
	gamma=0.7
)

# Wait for our result and get result value
result = ct.get_result(dispatch_id=dispatch_id, wait=True).result

print(result)
```

During the execution of the workflow one can navigate to the UI to see the status of the workflow, once completed however the above script should also output a value with the score of our model.

```
0.9777777777777777
```


## 3. Configuration

There are many configuration options that can be passed in to the class `ct.executor.AWSBatchExecutor` or by modifying the [covalent config file](https://covalent.readthedocs.io/en/latest/how_to/config/customization.html) under the section `[executors.awsbatch]`

For more information about all of the possible configuration values visit our [read the docs (RTD) guide](https://covalent.readthedocs.io/en/latest/api/executors/awsbatch.html) for this plugin.

## 4. Required AWS Resources

In order to run your workflows with covalent there are a few notable AWS resources that need to be provisioned first.

For more information regarding which cloud resources need to be provisioned visit our [read the docs (RTD) guide](https://covalent.readthedocs.io/en/latest/api/executors/awsbatch.html) for this plugin.

The required AWS resources include a Batch Job Definition, Batch Job Role, Batch Queue, Batch Compute Environment, Log Group, Subnet, VPC, and an S3 Bucket.

## Getting Started with Covalent


For more information on how to get started with Covalent, check out the project [homepage](https://github.com/AgnostiqHQ/covalent) and the official [documentation](https://covalent.readthedocs.io/en/latest/).

## Release Notes

Release notes for this plugin are available in the [Changelog](https://github.com/AgnostiqHQ/covalent-awsbatch-plugin/blob/main/CHANGELOG.md).

## Citation

Please use the following citation in any publications:

> W. J. Cunningham, S. K. Radha, F. Hasan, J. Kanem, S. W. Neagle, and S. Sanand.
> *Covalent.* Zenodo, 2022. https://doi.org/10.5281/zenodo.5903364

## License

Covalent is licensed under the GNU Affero GPL 3.0 License. Covalent may be distributed under other licenses upon request. See the [LICENSE](https://github.com/AgnostiqHQ/covalent-executor-template/blob/main/LICENSE) file or contact the [support team](mailto:support@agnostiq.ai) for more details.
