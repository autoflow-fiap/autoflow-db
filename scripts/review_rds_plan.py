"""Aplica uma política fail-closed ao plano binário de Terraform do RDS."""

import json
import re
import subprocess
import sys
from pathlib import Path

PROTECTED_RDS_ATTRIBUTES = {
    "identifier": "protect_rds_identifier",
    "backup_retention_period": "protect_rds_backup_retention",
    "skip_final_snapshot": "protect_rds_skip_final_snapshot",
    "final_snapshot_identifier": "protect_rds_final_snapshot_identifier",
    "deletion_protection": "protect_rds_deletion_protection",
}


def replace_attribute_names(replace_paths):
    """Extrai somente nomes de atributos dos caminhos de substituição."""
    if not isinstance(replace_paths, list):
        return []

    names = set()
    for path in replace_paths:
        if not isinstance(path, list):
            continue
        for step in path:
            if isinstance(step, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", step):
                names.add(step)
    return sorted(names)


def validate_plan(plan):
    """Rejeita exclusões/replace e alterações em identidade/backup do RDS."""
    if not isinstance(plan, dict) or "resource_changes" not in plan:
        raise ValueError("Plano inválido: resource_changes ausente.")
    resource_changes = plan["resource_changes"]
    if not isinstance(resource_changes, list):
        raise ValueError("Plano inválido: resource_changes não é uma lista.")

    violations = []
    actionable_changes = 0
    for resource in resource_changes:
        if not isinstance(resource, dict):
            raise ValueError("Plano inválido: entrada de resource_changes inválida.")
        address = resource.get("address", "<endereço ausente>")
        change = resource.get("change", {})
        if not isinstance(change, dict):
            raise ValueError("Plano inválido: change de recurso inválido.")
        actions = change.get("actions", [])
        if (
            not isinstance(actions, list)
            or not actions
            or not all(isinstance(action, str) for action in actions)
        ):
            raise ValueError("Plano inválido: ações de recurso inválidas.")
        action_label = ",".join(actions)
        if actions not in (["no-op"], ["read"]):
            actionable_changes += 1
        if "delete" in actions:
            attributes = replace_attribute_names(change.get("replace_paths", []))
            detail = f" atributos_replace={','.join(attributes)}" if attributes else ""
            violations.append((address, action_label, f"block_delete_or_replace{detail}"))
        if resource.get("type") != "aws_db_instance":
            continue
        before = change.get("before") or {}
        after = change.get("after") or {}
        if not isinstance(before, dict) or not isinstance(after, dict):
            raise ValueError("Plano inválido: atributos do RDS inválidos.")
        # Valores definidos em uma criação inicial não são alterações de
        # identidade/backup em um recurso já existente.
        if actions == ["create"] and not before:
            continue
        for attribute, rule in PROTECTED_RDS_ATTRIBUTES.items():
            if before.get(attribute) != after.get(attribute):
                violations.append((address, action_label, rule))
    if violations:
        details = "; ".join(
            f"{address} [{actions}] regra={rule}"
            for address, actions, rule in violations
        )
        raise ValueError(f"Plano bloqueado: {details}")
    return actionable_changes


def read_plan(path):
    if not Path(path).is_file():
        raise FileNotFoundError("Arquivo de plano Terraform não encontrado.")
    result = subprocess.run(
        ["terraform", "show", "-json", path],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def review_plan_file(path):
    """Executa Terraform show sem propagar stdout/stderr potencialmente sensíveis."""
    try:
        return validate_plan(read_plan(path))
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"terraform_show_failed exit_code={error.returncode}") from None
    except json.JSONDecodeError as error:
        raise RuntimeError(f"terraform_show_invalid_json line={error.lineno} column={error.colno}") from None


def main():
    if len(sys.argv) != 2:
        print("Uso: python review_rds_plan.py <arquivo.tfplan>", file=sys.stderr)
        return 2
    try:
        count = review_plan_file(sys.argv[1])
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    if count == 0:
        print("Plano aprovado: No changes.")
    else:
        print("Plano aprovado: nenhuma exclusão ou substituição detectada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
