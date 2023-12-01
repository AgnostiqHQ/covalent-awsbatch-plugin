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

variable "prefix" {
  default     = ""
  description = "prefix used for the AWS Resources created for the executor"
}
variable "region" {
  default     = ""
  description = "Region in which Covalent is deployed"
}

variable "aws_zone" {
  default     = "a"
  description = "Availability zone in which Covalent is deployed"
}

variable "vpc_id" {
  type        = string
  description = "Existing VPC ID"
  default     = ""
}

variable "subnet_id" {
  type        = string
  description = "Existing subnet ID"
  default     = ""
}

variable "instance_types" {
  type        = string
  description = "Instance type used for Covalent"
  default     = "optimal"
}

variable "min_vcpus" {
  type        = number
  description = "Minimum number of vCPUs to use for Covalent"
  default     = 0
}

variable "max_vcpus" {
  type        = number
  description = "Maximum number of vCPUs to use for Covalent"
  default     = 256
}

variable "aws_batch_job_definition" {
  default     = "job-definition"
  description = "Batch queue used for jobs"
}

variable "vpc_cidr" {
  default     = "10.0.0.0/24"
  description = "VPC CIDR range"
}


# Executor missing configuration
variable "credentials" {
  type        = string
  default     = ""
  description = "Path to the AWS shared configuration file"
}

variable "profile" {
  type        = string
  default     = ""
  description = "AWS profile used during execution"
}

variable "vcpus" {
  type        = number
  default     = 2
  description = "Number of vcpus a batch job will consume by default"
}

variable "memory" {
  type        = number
  default     = 3.25
  description = "Memory in GB for the batch job"
}

variable "num_gpus" {
  type        = number
  default     = 0
  description = "Number of GPUS required by the batch job"
}

variable "retry_attempts" {
  type        = number
  default     = 3
  description = "Number of retries to attempt before considering the batch job failed"
}

variable "time_limit" {
  type        = number
  default     = 300
  description = "Number of seconds before the batch job is considered to be timed out"
}

variable "cache_dir" {
  type        = string
  default     = "/tmp/covalent"
  description = "Path on local machine where temporary files are generated"
}

variable "poll_freq" {
  type        = number
  default     = 5
  description = "Frequency with which to poll AWS batch for the result object"
}
