data "aws_iam_policy_document" "assume_role_policy" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_tasks_execution_role" {
  name               = "${var.prefix}-task-execution-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role_policy.json
}

resource "aws_iam_role_policy_attachment" "ecs_tasks_execution_role" {
  role       = aws_iam_role.ecs_tasks_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy_attachment" "ecs_instance_role" {
  role       = aws_iam_role.ecs_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_instance_profile" "ecs_instance_role" {
  name = "${var.prefix}-instance-profile"
  role = aws_iam_role.ecs_instance_role.name
}


resource "aws_iam_role" "ecs_instance_role" {
  name = "${var.prefix}-instance-role"

  assume_role_policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Action" : "sts:AssumeRole",
        "Effect" : "Allow",
        "Principal" : {
          "Service" : "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role" "aws_batch_service_role" {
  name = "${var.prefix}-service-role"

  assume_role_policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Action" : "sts:AssumeRole",
        "Effect" : "Allow",
        "Principal" : {
          "Service" : "batch.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "aws_batch_service_role_attachment" {
  role       = aws_iam_role.aws_batch_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

resource "aws_iam_role_policy" "job_policy" {
  name = "${var.prefix}-job-policy"
  role = aws_iam_role.job_role.id

  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Sid" : "BatchJobMgmt",
        "Effect" : "Allow",
        "Action" : [
          "batch:TerminateJob",
          "batch:DescribeJobs",
          "batch:SubmitJob",
          "batch:RegisterJobDefinition"
        ],
        "Resource" : "*"
      },
      {
        "Sid" : "ECRAuth",
        "Effect" : "Allow",
        "Action" : [
          "ecr:GetAuthorizationToken"
        ],
        "Resource" : "*"
      },
      {
        "Sid" : "IAMRoles",
        "Effect" : "Allow",
        "Action" : [
          "iam:GetRole",
          "iam:PassRole"
        ],
        "Resource" : [
          "${aws_iam_role.job_role.arn}",
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/ecsTaskExecutionRole"
        ]
      },
      {
        "Sid" : "ObjectStore",
        "Effect" : "Allow",
        "Action" : [
          "s3:ListBucket",
          "s3:PutObject",
          "s3:GetObject"
        ],
        "Resource" : [
          "arn:aws:s3:::${aws_s3_bucket.bucket.id}/*",
          "arn:aws:s3:::${aws_s3_bucket.bucket.id}"
        ]
      },
      {
        "Sid" : "LogRead",
        "Effect" : "Allow",
        "Action" : [
          "logs:GetLogEvents"
        ],
        "Resource" : [
          "arn:aws:logs:us-east-1:${data.aws_caller_identity.current.account_id}:log-group:${aws_cloudwatch_log_group.log_group.name}:log-stream:*"
        ]
      }
    ]
  })
}

resource "aws_iam_role" "job_role" {
  name = "${var.prefix}-job-role"

  assume_role_policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Sid" : "",
        "Effect" : "Allow",
        "Principal" : {
          "Service" : "ecs-tasks.amazonaws.com"
        },
        "Action" : "sts:AssumeRole"
      }
    ]
  })
}
