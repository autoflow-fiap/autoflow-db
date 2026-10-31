output "postgres_endpoint" {
  value = aws_db_instance.autoflow_rds.address
}

output "postgres_port" {
  value = aws_db_instance.autoflow_rds.port
}

output "lambda_security_group_id" {
  value = aws_security_group.lambda_sg.id
}

