# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [UNRELEASED]

### Added

- Reading executor resource details from the config file by default.

[0.5.0] - 2022-08-02

### Added 

- Unit tests for awsbatch.py.

### Removed

- Test action for Python Version 3.10.

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
