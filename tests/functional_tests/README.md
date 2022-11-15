## Functional Test Instructions

### 1.Setup

In the project root run the following:

```sh
pip install -r ./tests/requirements.txt
pip install -r ./tests/functional_tests/requirements.txt
export PYTHONPATH=$(pwd)
```

Copy create `.env` file:

```sh
cp .env.example .env
```

Fill in the configuration values either manually or from terraform output.

### 2. Run Functional Tests

```sh
pytest -vvs -m functional_tests
```
