# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [UNRELEASED]

### Operations

- pre-commit autoupdate
- Added license workflow

## [0.20.1] - 2022-10-27

### Fixed

- Fixed parallel execution of electrons submitting jobs to batch

## [0.20.0] - 2022-10-27

### Changed 

- Updated tag of hardcoded ECR URI to `stable`

## [0.19.0] - 2022-10-25

### Changed 

- Updated covalent-aws-plugins version `>=0.7.0rc0`.
- Cleanup file based method

## [0.18.0] - 2022-10-25

### Changed

- Pinned version of covalent-aws-plugins to 0.5.0rc0 

## [0.17.0] - 2022-10-18

### Changed

- Updated `boto3` calls to make them compatible with the async library.

### Docs

- Updated docs to include more information about required/optional config values, and provide information about each cloud resource that needs to be provisioned 

## [0.16.1] - 2022-10-04

### Fixed

- Store `BASE_COVALENT_AWS_PLUGINS_ONLY` in a temporary file rather than storing it as an environment variable.

## [0.16.0] - 2022-10-04

### Changed

- Setting `BASE_COVALENT_AWS_PLUGINS_ONLY` environment system wide to circumvent `setup.py` subprocesses when installing.

## [0.15.0] - 2022-09-30

### Added

-  Logic to specify that only the base covalent-aws-plugins package is to be installed.

## [0.14.1] - 2022-09-20

### Fixed

- Using `get_config` to get default configuration when init parameters are not supplied

## [0.14.0] - 2022-09-15

### Changed

- Updated requirements.txt to pin aws executor plugins to pre-release version 0.1.0rc0

### Fixed

- Added missing await in asyncio.sleep during polling

## [0.13.0] - 2022-09-15

### Changed

- Inheriting from AWSExecutor, updated setup.py to properly treat github packages

## [0.12.0] - 2022-09-06

### Added

- Added live functional tests for CI pipeline

### Tests

- Enabled Codecov

## [0.11.0] - 2022-08-25

### Changed

- Changed covalent version in templated Dockerfile to correspond to 0.177.0

## [0.10.0] - 2022-08-17

### Changed

- Pinned `covalent` version to `stable`

## [0.9.0] - 2022-08-16

### Changed

- Updated required `covalent` version

## [0.8.1] - 2022-08-13

### Fixed

- Test trigger fixed

## [0.8.0] - 2022-08-13

### Added

- Workflow actions to support releases

## [0.7.1] - 2022-08-10

### Fixed

- The default AWS profile is set to `default`.

## [0.7.0] - 2022-08-03

### Added

- Reading executor resource details from the config file by default.

[0.6.0] - 2022-08-03

### Added 

- Unit tests for awsbatch.py.

### Removed

- Test action for Python Version 3.10.

## [0.5.0] - 2022-08-03

### Changed

- Updated the README.

## [0.4.0] - 2022-07-28

### Added

- Basic CICD pipeline to run the tests.

## [0.3.0] - 2022-07-27

### Added

- Empty `run` abstract method.

### Changed

- README to ensure that the provisioning instructions are up-to-date.
- Implementation of execute method so that the batch executor works.

## [0.2.0] - 2022-07-27

### Added

- AWS Batch Executor plugin banner to README.

## [0.1.0] - 2022-03-31

### Changed

- Changed global variable executor_plugin_name -> EXECUTOR_PLUGIN_NAME in executors to conform with PEP8.
