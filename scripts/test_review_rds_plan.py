import unittest
from pathlib import Path
from unittest.mock import patch

from review_rds_plan import review_plan_file, validate_plan


class ReviewRdsPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).parents[1]
        cls.root = root
        cls.workflow = (root / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        cls.plan_job = cls.workflow.split("\n  plan:\n", 1)[1].split("\n  apply:\n", 1)[0]
        cls.apply_job = cls.workflow.split("\n  apply:\n", 1)[1]

    def test_rds_discovers_cluster_name_from_infrastructure_state_output(self):
        rds = (self.root / "infra/rds-postgresql.tf").read_text(encoding="utf-8")
        variables = (self.root / "infra/vars.tf").read_text(encoding="utf-8")
        self.assertIn("data.terraform_remote_state.infra.outputs.eks_cluster_name", rds)
        self.assertRegex(rds, r"bucket\s*=\s*var\.terraform_state_bucket")
        self.assertNotIn("expected_bucket_owner", rds)
        self.assertRegex(rds, r"key\s*=\s*var\.infra_state_key")
        self.assertIn('aws s3api head-object --bucket "$TF_STATE_BUCKET" --key "$TF_VAR_infra_state_key" --expected-bucket-owner "$AWS_EXPECTED_ACCOUNT_ID"', self.plan_job)
        self.assertNotIn('variable "eks_cluster_name"', variables)
        self.assertNotIn('variable "lambda_security_group_id"', variables)
        self.assertNotIn('variable "role_arn"', variables)

    def test_homolog_and_production_select_their_environment_and_project(self):
        environment = "${{ github.ref == 'refs/heads/main' && 'production' || 'homolog' }}"
        project = "${{ github.ref == 'refs/heads/main' && 'autoflow-production' || 'autoflow' }}"
        for job in (self.plan_job, self.apply_job):
            with self.subTest(job="plan" if job is self.plan_job else "apply"):
                self.assertIn(f"environment: {environment}", job)
                self.assertIn(f"DEPLOYMENT_ENV: {environment}", job)
                self.assertIn(f"TF_VAR_project_name: {project}", job)
        self.assertIn('default = "autoflow"', (self.root / "infra/vars.tf").read_text(encoding="utf-8"))

    def test_resource_names_are_isolated_by_project_name(self):
        rds = (self.root / "infra/rds-postgresql.tf").read_text(encoding="utf-8")
        security_groups = (self.root / "infra/sg.tf").read_text(encoding="utf-8")
        lambda_import = (self.root / "infra/lambda-sg-import.auto.tf").read_text(encoding="utf-8")
        suffixes = {
            "rds_identifier": "-db",
            "db_subnet_group_name": "-db-subnet-group",
            "final_snapshot_identifier": "-db-final",
            "rds_security_group_name": "-rds-sg",
            "lambda_security_group_name": "-lambda-sg",
        }
        combined = rds + security_groups
        for local_name, suffix in suffixes.items():
            with self.subTest(resource=local_name):
                self.assertRegex(
                    combined,
                    rf'\b{local_name}\s*=\s*"\$\{{var\.project_name\}}{suffix}"',
                )
        self.assertIn("values = [local.lambda_security_group_name]", lambda_import)

        names = {
            project: {name: f"{project}{suffix}" for name, suffix in suffixes.items()}
            for project in ("autoflow", "autoflow-production")
        }
        self.assertEqual(names["autoflow"]["rds_identifier"], "autoflow-db")
        self.assertEqual(names["autoflow-production"]["rds_identifier"], "autoflow-production-db")
        self.assertTrue(set(names["autoflow"].values()).isdisjoint(names["autoflow-production"].values()))

    def test_plan_and_apply_use_environment_scoped_aws_credentials_and_states(self):
        conditions = {
            "plan": "(github.ref == 'refs/heads/develop' || github.ref == 'refs/heads/main') && github.event_name == 'workflow_dispatch' && (github.ref != 'refs/heads/main' || github.ref_protected)",
            "apply": "(github.ref == 'refs/heads/develop' || github.ref == 'refs/heads/main') && github.event_name == 'workflow_dispatch' && inputs.apply == true && (github.ref != 'refs/heads/main' || github.ref_protected)",
        }
        for name, job in (("plan", self.plan_job), ("apply", self.apply_job)):
            with self.subTest(job=name):
                self.assertIn(conditions[name], job)
                self.assertIn("AWS_EXPECTED_ACCOUNT_ID: ${{ vars.AWS_EXPECTED_ACCOUNT_ID }}", job)
                self.assertIn("AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}", job)
                self.assertIn("AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}", job)
                self.assertIn("AWS_SESSION_TOKEN: ${{ secrets.AWS_SESSION_TOKEN }}", job)
                self.assertIn("AWS_TF_STATE_KEY: ${{ vars.AWS_TF_STATE_KEY }}", job)
                self.assertIn("TF_VAR_infra_state_key: ${{ vars.AWS_INFRA_STATE_KEY }}", job)
                self.assertIn("python scripts/state_key_policy.py", job)
                self.assertLess(
                    job.index("python scripts/state_key_policy.py"),
                    job.index("aws-actions/configure-aws-credentials@v4"),
                )
                self.assertIn("/environments/$DEPLOYMENT_ENV/variables", job)
                self.assertIn("/environments/$DEPLOYMENT_ENV/secrets", job)
                self.assertIn("for name in AWS_REGION AWS_EXPECTED_ACCOUNT_ID", job)
                self.assertIn("for name in AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN DATABASE_USERNAME DATABASE_PASSWORD", job)
                self.assertIn('[[ "$AWS_EXPECTED_ACCOUNT_ID" =~ ^[0-9]{12}$ ]]', job)
                self.assertIn("python scripts/verify_aws_account.py", job)
                self.assertIn('--expected-bucket-owner "$AWS_EXPECTED_ACCOUNT_ID"', job)
                self.assertIn('backend-config="allowed_account_ids=$TF_VAR_aws_allowed_account_ids"', job)
        self.assertIn("rds-deployment-config.sha256", self.plan_job)
        self.assertIn("rds-deployment-config.sha256", self.apply_job)

    def test_feature_pushes_and_pull_requests_run_ci_without_aws_apply(self):
        ci = (self.root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [develop, main, 'feature/**']", ci)
        self.assertIn("pull_request:", ci)
        self.assertNotIn("  push:", self.workflow.split("permissions:", 1)[0])
        self.assertNotIn("  pull_request:", self.workflow.split("permissions:", 1)[0])
        validate_job = self.workflow.split("\n  plan:\n", 1)[0]
        self.assertNotIn("configure-aws-credentials", validate_job)
        self.assertNotIn("AWS_ACCESS_KEY_ID", validate_job)
        self.assertIn("github.event_name == 'workflow_dispatch'", self.plan_job)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.apply == true", self.apply_job)
        self.assertNotIn("ALLOW_DESTRUCTIVE", self.workflow)
        self.assertIn("python ../scripts/review_rds_plan.py rds.tfplan", self.plan_job)
        self.assertIn("python ../scripts/review_rds_plan.py rds.tfplan", self.apply_job)

    def test_manual_apply_requires_explicit_input_after_plan_and_environment_gate(self):
        self.assertIn("github.event_name == 'workflow_dispatch'", self.plan_job)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.apply == true", self.apply_job)
        self.assertNotIn("github.event_name == 'push'", self.plan_job + self.apply_job)
        self.assertIn("needs: plan", self.apply_job)
        self.assertIn("environment: ${{ github.ref == 'refs/heads/main' && 'production' || 'homolog' }}", self.apply_job)
        self.assertLess(
            self.apply_job.index("Exigir approvals efetivos no Environment selecionado"),
            self.apply_job.index("aws-actions/configure-aws-credentials@v4"),
        )

    def test_apply_requires_effective_approvals_before_aws_credentials(self):
        approval_gate = self.apply_job.index("Exigir approvals efetivos no Environment selecionado")
        environment_configuration = self.apply_job.index("Exigir configurações no GitHub Environment selecionado")
        configuration_gate = self.apply_job.index("Validar configuração do Environment e integridade do plano")
        aws_credentials = self.apply_job.index("aws-actions/configure-aws-credentials@v4")
        self.assertLess(environment_configuration, aws_credentials)
        self.assertLess(approval_gate, aws_credentials)
        self.assertLess(configuration_gate, aws_credentials)
        self.assertIn("TERRAFORM_APPLY_APPROVAL_CONFIGURED", self.apply_job)
        self.assertIn("required_reviewers", self.apply_job)
        self.assertIn("deployment-branch-policies", self.apply_job)
        self.assertIn("EXPECTED_BRANCH=develop", self.apply_job)
        self.assertIn("EXPECTED_BRANCH=main", self.apply_job)
        self.assertIn("github.ref_protected", self.plan_job)
        self.assertIn("github.ref_protected", self.apply_job)

    def test_rds_is_private_encrypted_and_protected_with_final_snapshot(self):
        rds = (self.root / "infra/rds-postgresql.tf").read_text(encoding="utf-8")
        self.assertIn("publicly_accessible    = false", rds)
        self.assertIn("storage_encrypted         = true", rds)
        self.assertIn("skip_final_snapshot       = false", rds)
        self.assertIn("deletion_protection       = true", rds)

    def test_plan_and_apply_do_not_share_a_hardcoded_account_id(self):
        self.assertNotRegex(self.workflow, r"\b[0-9]{12}\b")
        self.assertIn("TF_VAR_aws_allowed_account_ids: '[\"${{ vars.AWS_EXPECTED_ACCOUNT_ID }}\"]'", self.workflow)
        self.assertIn("aws-actions/configure-aws-credentials@v4", self.workflow)

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
