"""Valida keys de State compatíveis com os States autoritativos por ambiente."""

from __future__ import annotations

import os
import sys

ENVIRONMENTS = {"homolog", "production"}
HOMOLOG_STATE_KEYS = {
    "rds": "rds/terraform.tfstate",
    "infra": "eks/terraform.tfstate",
}
PRODUCTION_RDS_STATE_KEY = "production/rds/terraform.tfstate"


def validate_state_keys(
    deployment_environment: str | None,
    rds_state_key: str | None,
    infra_state_key: str | None,
) -> None:
    """Rejeita keys ausentes, cruzadas ou diferentes da convenção por root."""
    if deployment_environment not in ENVIRONMENTS:
        raise ValueError("Environment inválido para validar Terraform States.")

    keys = (rds_state_key, infra_state_key)
    if any(not isinstance(key, str) or not key or key != key.strip() for key in keys):
        raise ValueError("As keys Terraform RDS e infraestrutura são obrigatórias.")
    if rds_state_key == infra_state_key:
        raise ValueError("RDS e infraestrutura devem usar Terraform States distintos.")

    for key in keys:
        assert isinstance(key, str)
        if any(part in {"", ".", ".."} for part in key.split("/")):
            raise ValueError("Key Terraform contém segmento de caminho inválido.")

    if deployment_environment == "homolog":
        if rds_state_key != HOMOLOG_STATE_KEYS["rds"] or infra_state_key != HOMOLOG_STATE_KEYS["infra"]:
            raise ValueError(
                "Keys incompatíveis com os States RDS e VPC/EKS existentes de homologação."
            )
        return

    if rds_state_key != PRODUCTION_RDS_STATE_KEY:
        raise ValueError(
            "A key RDS de produção deve permanecer isolada no root production/rds."
        )
    # O sufixo VPC/EKS ainda requer alinhamento com o Environment do producer.
    if not infra_state_key.startswith("production/"):
        raise ValueError(
            "A key de infraestrutura de produção deve permanecer sob production/ "
            "e ser configurada para corresponder ao root produtor autoflow-infra."
        )


def main() -> int:
    try:
        validate_state_keys(
            os.environ.get("DEPLOYMENT_ENV"),
            os.environ.get("TF_STATE_KEY"),
            os.environ.get("TF_VAR_infra_state_key"),
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    print("Keys Terraform RDS e infraestrutura atendem à política do Environment selecionado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
