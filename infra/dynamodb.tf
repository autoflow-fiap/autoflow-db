resource "aws_dynamodb_table" "autoflow_users" {
  name                        = "autoflow-users"
  billing_mode                = "PROVISIONED"
  read_capacity               = 5
  write_capacity              = 5
  hash_key                    = "cpf_cnpj"
  deletion_protection_enabled = false

  attribute {
    name = "cpf_cnpj"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled = false
  }

  tags = {
    Name = "autoflow-users"
  }
}
