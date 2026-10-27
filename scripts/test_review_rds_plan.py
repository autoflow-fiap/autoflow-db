import unittest
from pathlib import Path
from unittest.mock import patch

from review_rds_plan import review_plan_file, validate_plan


class ReviewRdsPlanTests(unittest.TestCase):
    def test_rds_discovers_cluster_name_from_infrastructure_state_output(self):
        root = Path(__file__).parents[1]
        rds = (root / "infra/rds-postgresql.tf").read_text(encoding="utf-8")
        variables = (root / "infra/vars.tf").read_text(encoding="utf-8")
        self.assertIn("data.terraform_remote_state.infra.outputs.eks_cluster_name", rds)
        self.assertNotIn('variable "eks_cluster_name"', variables)
        self.assertNotIn('variable "lambda_security_group_id"', variables)
        self.assertNotIn('variable "role_arn"', variables)

    def test_workflow_dispatch_runs_plan_and_approved_apply_on_develop(self):
        workflow = (Path(__file__).parents[1] / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        condition = "github.ref == 'refs/heads/develop' && (github.event_name == 'push' || github.event_name == 'workflow_dispatch')"
        plan, apply = workflow.split("  plan:", 1)[1].split("  apply:", 1)[0], workflow.split("  apply:", 1)[1]
        self.assertIn(condition, plan)
        self.assertIn(condition, apply)
        self.assertIn("environment: homolog", apply)

    def test_accepts_no_changes(self):
        self.assertEqual(validate_plan({"resource_changes": []}), 0)

    def test_noop_and_data_source_reads_are_no_changes(self):
        plan = {
            "resource_changes": [
                {
                    "address": "aws_db_instance.autoflow_rds",
                    "type": "aws_db_instance",
                    "change": {
                        "actions": ["no-op"],
                        "before": {"identifier": "rds-name", "deletion_protection": True},
                        "after": {"identifier": "rds-name", "deletion_protection": True},
                    },
                },
                {"address": "data.aws_eks_cluster.autoflow", "change": {"actions": ["read"]}},
            ],
            "planned_values": {"root_module": {"resources": []}},
            "prior_state": {"values": {"root_module": {"resources": []}}},
        }
        self.assertEqual(validate_plan(plan), 0)

    def test_accepts_non_destructive_changes(self):
        plan = {
            "resource_changes": [
                {"address": "aws_db_instance.autoflow_rds", "change": {"actions": ["update"]}},
                {"address": "aws_security_group.rds_sg", "change": {"actions": ["create"]}},
            ]
        }
        self.assertEqual(validate_plan(plan), 2)

    def test_accepts_initial_rds_creation_with_protected_attributes(self):
        plan = {
            "resource_changes": [
                {
                    "address": "aws_db_instance.autoflow_rds",
                    "type": "aws_db_instance",
                    "change": {
                        "actions": ["create"],
                        "before": None,
                        "after": {
                            "identifier": "autoflow-db",
                            "backup_retention_period": 1,
                            "skip_final_snapshot": False,
                            "final_snapshot_identifier": "autoflow-db-final",
                            "deletion_protection": True,
                        },
                    },
                }
            ]
        }
        self.assertEqual(validate_plan(plan), 1)

    def test_rejects_destroy_of_any_resource(self):
        plan = {
            "resource_changes": [
                {"address": "aws_db_instance.autoflow_rds", "change": {"actions": ["delete"]}}
            ]
        }
        with self.assertRaisesRegex(
            ValueError, r"aws_db_instance\.autoflow_rds \[delete\] regra=block_delete_or_replace"
        ):
            validate_plan(plan)

    def test_rejects_replace_even_for_network_resources(self):
        plan = {
            "resource_changes": [
                {"address": "aws_subnet.private", "change": {"actions": ["delete", "create"]}}
            ]
        }
        with self.assertRaisesRegex(
            ValueError, r"aws_subnet\.private \[delete,create\] regra=block_delete_or_replace"
        ):
            validate_plan(plan)

    def test_replace_diagnostic_reports_attribute_names_without_values(self):
        sensitive_value = "dont-print-this-password"
        plan = {
            "resource_changes": [
                {
                    "address": "aws_db_instance.autoflow_rds",
                    "type": "aws_db_instance",
                    "change": {
                        "actions": ["delete", "create"],
                        "replace_paths": [["allocated_storage"], ["instance_class"]],
                        "before": {
                            "identifier": "autoflow-db",
                            "deletion_protection": True,
                            "password": sensitive_value,
                        },
                        "after": {
                            "identifier": "autoflow-db",
                            "deletion_protection": True,
                            "password": sensitive_value,
                        },
                    },
                }
            ]
        }

        with self.assertRaises(ValueError) as error:
            validate_plan(plan)

        diagnostic = str(error.exception)
        self.assertIn("aws_db_instance.autoflow_rds", diagnostic)
        self.assertIn("[delete,create]", diagnostic)
        self.assertIn("allocated_storage", diagnostic)
        self.assertIn("instance_class", diagnostic)
        self.assertNotIn(sensitive_value, diagnostic)

    def test_rejects_change_to_rds_identifier_or_backup_configuration(self):
        for attribute, rule in (
            ("identifier", "protect_rds_identifier"),
            ("backup_retention_period", "protect_rds_backup_retention"),
            ("skip_final_snapshot", "protect_rds_skip_final_snapshot"),
            ("final_snapshot_identifier", "protect_rds_final_snapshot_identifier"),
            ("deletion_protection", "protect_rds_deletion_protection"),
        ):
            with self.subTest(attribute=attribute):
                plan = {
                    "resource_changes": [
                        {
                            "address": "aws_db_instance.autoflow_rds",
                            "type": "aws_db_instance",
                            "change": {
                                "actions": ["update"],
                                "before": {attribute: "old"},
                                "after": {attribute: "new"},
                            },
                        }
                    ]
                }
                with self.assertRaisesRegex(
                    ValueError,
                    rf"aws_db_instance\.autoflow_rds \[update\] regra={rule}",
                ):
                    validate_plan(plan)

    def test_json_diagnostics_do_not_expose_terraform_stderr(self):
        secret = "sensitive-plan-content"
        with patch("review_rds_plan.read_plan", side_effect=__import__("json").JSONDecodeError(secret, "", 0)):
            with self.assertRaisesRegex(RuntimeError, r"terraform_show_invalid_json line=1 column=1") as error:
                review_plan_file("rds.tfplan")
        self.assertNotIn(secret, str(error.exception))

    def test_terraform_show_failure_does_not_expose_stderr(self):
        import subprocess

        secret = "sensitive-plan-content"
        failure = subprocess.CalledProcessError(1, "terraform", stderr=secret)
        with patch("review_rds_plan.read_plan", side_effect=failure):
            with self.assertRaisesRegex(RuntimeError, "terraform_show_failed exit_code=1") as error:
                review_plan_file("rds.tfplan")
        self.assertNotIn(secret, str(error.exception))

    def test_rejects_plan_without_resource_changes(self):
        with self.assertRaisesRegex(ValueError, "resource_changes ausente"):
            validate_plan({"planned_values": {}, "prior_state": {}})

    def test_rejects_resource_change_without_actions(self):
        plan = {"resource_changes": [{"address": "aws_db_instance.autoflow_rds", "change": {}}]}
        with self.assertRaisesRegex(ValueError, "ações de recurso inválidas"):
            validate_plan(plan)


if __name__ == "__main__":
    unittest.main()
