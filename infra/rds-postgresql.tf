resource "aws_db_subnet_group" "autoflow_rds_subnets" {
  name       = "autoflow-db-subnet-group"
  subnet_ids = data.terraform_remote_state.infra.outputs.private_subnet_ids
  tags = {
    Name = "autoflow-db-subnet-group"
  }
}

resource "aws_db_instance" "autoflow_rds" {
  identifier        = "autoflow-db"
  allocated_storage = 20
  engine            = "postgres"
  engine_version    = "17"
  instance_class    = "db.t3.micro"

  db_name  = "autoflow_db"
  username = var.database_username
  password = var.database_password

  db_subnet_group_name   = aws_db_subnet_group.autoflow_rds_subnets.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  publicly_accessible    = false

  storage_type              = "gp3"
  storage_encrypted         = true
  backup_retention_period   = 1
  skip_final_snapshot       = false
  final_snapshot_identifier = "autoflow-db-final"
  deletion_protection       = true
  monitoring_interval       = 0
  monitoring_role_arn       = null

  tags = {
    Name = "autoflow-db"
  }
}

data "aws_eks_cluster" "autoflow" {
  name = data.terraform_remote_state.infra.outputs.eks_cluster_name
}

data "terraform_remote_state" "infra" {
  backend = "s3"

  config = {
    bucket  = var.terraform_state_bucket
    key     = var.infra_state_key
    region  = var.region_default
    profile = var.aws_profile
  }
}
