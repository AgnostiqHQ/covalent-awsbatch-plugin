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
import executor_instance
from numpy.random import permutation
from sklearn import datasets, svm

deps_pip = ct.DepsPip(packages=["numpy==1.22.4", "scikit-learn==1.1.2"])


@ct.electron
def load_data():
    iris = datasets.load_iris()
    perm = permutation(iris.target.size)
    iris.data = iris.data[perm]
    iris.target = iris.target[perm]
    return iris.data, iris.target


@ct.electron(executor=executor_instance.executor, deps_pip=deps_pip)
def train_svm(data, C, gamma):
    X, y = data
    clf = svm.SVC(C=C, gamma=gamma)
    clf.fit(X[90:], y[90:])
    return clf


@ct.electron
def score_svm(data, clf):
    X_test, y_test = data
    return clf.score(X_test[:90], y_test[:90])


@ct.lattice
def run_experiment(C=1.0, gamma=0.7):
    data = load_data()
    clf = train_svm(data=data, C=C, gamma=gamma)
    score = score_svm(data=data, clf=clf)
    return score


dispatchable_func = ct.dispatch(run_experiment)

dispatch_id = dispatchable_func(C=1.0, gamma=0.7)
result = ct.get_result(dispatch_id=dispatch_id, wait=True)
status = str(result.status)

print(result)

if status == str(ct.status.FAILED):
    print("Basic Workflow failed to run.")
    sys.exit(1)
