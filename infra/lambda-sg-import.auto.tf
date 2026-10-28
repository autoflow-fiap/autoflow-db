data "aws_security_groups" "existing_lambda_sg" {
  filter {
    name   = "group-name"
    values = ["autoflow-lambda-sg"]
  }

  filter {
    name   = "vpc-id"
    values = [data.terraform_remote_state.infra.outputs.vpc_id]
  }
}

import {
  for_each = toset(data.aws_security_groups.existing_lambda_sg.ids)
  to       = aws_security_group.lambda_sg
  id       = each.value
}
