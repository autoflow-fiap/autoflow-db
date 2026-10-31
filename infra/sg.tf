locals {
  rds_security_group_name    = "${var.project_name}-rds-sg"
  lambda_security_group_name = "${var.project_name}-lambda-sg"
}

resource "aws_security_group" "rds_sg" {
  name        = local.rds_security_group_name
  description = "Permite trafego do cluster EKS para o RDS"
  vpc_id      = data.terraform_remote_state.infra.outputs.vpc_id

  ingress {
    description     = "Acesso a partir do cluster security group do EKS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [data.aws_eks_cluster.autoflow.vpc_config[0].cluster_security_group_id]
  }

  ingress {
    description     = "Lambda para RDS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}


resource "aws_security_group" "lambda_sg" {
  name        = local.lambda_security_group_name
  description = "Security Group da Lambda de validacao de CPF"
  vpc_id      = data.terraform_remote_state.infra.outputs.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
