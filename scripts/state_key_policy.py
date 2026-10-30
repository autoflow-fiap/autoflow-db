"""Valida keys de State por ambiente sem fixar os sufixos externos."""

from __future__ import annotations

import os
import sys

ENVIRONMENTS = {"homolog", "production"}


def validate_state_keys(
    deployment_environment: str | None,
    rds_state_key: str | None,
    infra_state_key: str | None,
) -> None:
    """Rejeita keys ausentes, cruzadas ou iguais entre os roots consumidos."""
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

    prefix = f"{deployment_environment}/"
    for key in keys:
        assert isinstance(key, str)
        if not key.startswith(prefix) or len(key) == len(prefix):
            raise ValueError(
                f"Cada key Terraform deve iniciar com o prefixo obrigatório {prefix}."
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

    print("Keys Terraform RDS e infraestrutura atendem ao Environment e são distintas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
