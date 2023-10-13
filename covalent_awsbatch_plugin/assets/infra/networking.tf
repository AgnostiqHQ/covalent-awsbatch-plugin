module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  create_vpc = (var.vpc_id == "")

  name = "${var.prefix}-vpc"
  cidr = var.vpc_cidr

  azs = ["${var.aws_region}a"]

  public_subnets = [
    cidrsubnet(var.vpc_cidr, 0, 0)
  ]
  private_subnets = []

  enable_nat_gateway   = false
  single_nat_gateway   = false
  enable_dns_hostnames = true
  map_public_ip_on_launch = true
}

resource "aws_security_group" "sg" {
  name = "${var.prefix}-sg"
  description = "Allow traffic to Covalent server"
  vpc_id = "${var.vpc_id == "" ? module.vpc.vpc_id : var.vpc_id}"

  egress {
    description = "Allow all outbound traffic"
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
