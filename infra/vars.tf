variable "project_name" {
  default = "autoflow"
}

variable "region_default" {
  default = "us-east-1"
}

variable "aws_profile" {
  description = "Perfil AWS opcional fornecido pela configuração local do processo."
  type        = string
  default     = null
}

variable "aws_allowed_account_ids" {
  description = "Contas AWS permitidas para este provider; fornecidas externamente por ambiente."
  type        = list(string)

  validation {
    condition     = length(var.aws_allowed_account_ids) > 0 && alltrue([for id in var.aws_allowed_account_ids : can(regex("^[0-9]{12}$", id))])
    error_message = "aws_allowed_account_ids deve conter pelo menos um ID de conta AWS válido, fornecido externamente."
  }
}

variable "cidr_vpc" {
  default = "10.0.0.0/16"
}

variable "instance_type" {
  default = "t3.medium"
}

variable "database_password" {
  description = "Senha do banco de dados RDS"
  type        = string
  sensitive   = true
}

variable "database_username" {
  description = "Usuário do banco de dados"
  type        = string
}

variable "terraform_state_bucket" {
  description = "Bucket externo que contém os states Terraform consumidos por este ambiente."
  type        = string
}

variable "infra_state_key" {
  description = "Key do state de VPC/EKS consumido pelo root RDS."
  type        = string
}
