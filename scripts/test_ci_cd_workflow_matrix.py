from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def section(content: str, job: str, next_job: str | None = None) -> str:
    start = content.index(f"\n  {job}:\n") + 1
    end = content.index(f"\n  {next_job}:\n", start) if next_job else len(content)
    return content[start:end]


class CiCdWorkflowMatrixTests(unittest.TestCase):
    def test_ci_triggers_are_automatic_and_offline(self):
        ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        triggers = ci.split("permissions:", 1)[0]
        self.assertIn("branches: [develop, main, 'feature/**']", triggers)
        self.assertIn("branches: [develop, main]", triggers)
        self.assertNotIn("workflow_dispatch:", triggers)
        self.assertNotRegex(ci, r"(?im)^\s*run:.*\bterraform\s+(?:plan|apply|destroy)\b")
        self.assertNotIn("aws-actions/configure-aws-credentials", ci)

    def test_opt_in_push_plan_and_explicit_manual_apply_are_environment_scoped(self):
        content = (WORKFLOWS / "pipeline.yml").read_text(encoding="utf-8")
        triggers = content.split("permissions:", 1)[0]
        gate = section(content, "gate", "validate")
        plan = section(content, "plan", "apply")
        apply = section(content, "apply")
        self.assertIn("on:\n  workflow_dispatch:", triggers)
        self.assertIn("  push:\n    branches: [develop, main]", triggers)
        self.assertNotIn("  pull_request:", triggers)
        self.assertIn("python scripts/validate_cd_trigger.py", gate)
        self.assertNotIn("configure-aws-credentials", gate)
        self.assertNotIn("terraform plan", gate)
        for job in (plan, apply):
            self.assertIn("github.ref == 'refs/heads/develop'", job)
            self.assertIn("github.ref == 'refs/heads/main'", job)
            self.assertIn("github.ref_protected", job)
            self.assertIn("environment: ${{ github.ref == 'refs/heads/main' && 'production' || 'homolog' }}", job)
            self.assertIn("AWS_TF_STATE_KEY: ${{ vars.AWS_TF_STATE_KEY }}", job)
            self.assertIn("TF_VAR_infra_state_key: ${{ vars.AWS_INFRA_STATE_KEY }}", job)
        self.assertIn("github.event_name == 'workflow_dispatch'", plan)
        self.assertIn("needs.gate.outputs.auto_cd_enabled == 'true'", plan)
        self.assertIn("needs: [gate, validate]", plan)
        self.assertNotIn("--approval-gate", plan)
        self.assertIn("github.event_name == 'workflow_dispatch'", apply)
        self.assertIn("inputs.apply == true", apply)
        self.assertIn("needs: [gate, plan]", apply)
        self.assertIn("TERRAFORM_APPLY_APPROVAL_CONFIGURED", apply)
        self.assertIn("required_reviewers", apply)
        self.assertIn("deployment-branch-policies", apply)
        self.assertIn("EXPECTED_BRANCH=develop", apply)
        self.assertIn("EXPECTED_BRANCH=main", apply)
        self.assertIn('test "$APPROVAL_CONFIGURED" = "true"', apply)
        self.assertNotIn("github.event_name == 'push'", apply)

    def test_environment_values_are_validated_without_variable_or_secret_api_queries(self):
        content = (WORKFLOWS / "pipeline.yml").read_text(encoding="utf-8")
        plan = section(content, "plan", "apply")
        apply = section(content, "apply")
        config_step_name = "      - name: Exigir configurações no GitHub Environment selecionado\n"
        required_variables = (
            "AWS_REGION",
            "AWS_EXPECTED_ACCOUNT_ID",
            "AWS_TERRAFORM_STATE_BUCKET",
            "AWS_TF_STATE_KEY",
            "AWS_INFRA_STATE_KEY",
            "TERRAFORM_APPLY_APPROVAL_CONFIGURED",
        )
        required_secrets = (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "DATABASE_USERNAME",
            "DATABASE_PASSWORD",
            "TF_PLAN_ENCRYPTION_KEY",
        )

        for job in (plan, apply):
            with self.subTest(job="plan" if job == plan else "apply"):
                start = job.index(config_step_name)
                end = job.find("\n      - ", start + len(config_step_name))
                config_step = job[start:] if end == -1 else job[start:end]
                self.assertNotIn("gh api", config_step)
                self.assertNotIn("/variables?", config_step)
                self.assertNotIn("/secrets?", config_step)
                self.assertIn(f"for name in {' '.join(required_variables)}; do", config_step)
                self.assertIn(f"for name in {' '.join(required_secrets)}; do", config_step)
                self.assertIn('if [[ -z "${!name}" ]]; then', config_step)
                run_script = config_step.split("run: |", 1)[1]
                for name in required_variables:
                    self.assertIn(f"{name}: ${{{{ vars.{name} }}}}", config_step)
                for name in required_secrets:
                    self.assertIn(f"{name}: ${{{{ secrets.{name} }}}}", config_step)
                    self.assertNotRegex(
                        run_script,
                        rf"(?m)^\s*(?:echo|printf)\b[^\n]*\${name}\b",
                    )
                self.assertIn('[[ "$AWS_EXPECTED_ACCOUNT_ID" =~ ^[0-9]{12}$ ]]', job)
                self.assertIn('test "$AWS_REGION" = "us-east-1"', job)
                self.assertIn('test -n "$TF_STATE_BUCKET"', job)
                self.assertIn('test -n "$TF_STATE_KEY"', job)
                self.assertIn('test -n "$TF_VAR_infra_state_key"', job)
                self.assertIn('test -n "$TF_VAR_database_username"', job)
                self.assertIn('test -n "$TF_VAR_database_password"', job)
                self.assertIn('len(os.environ["TF_PLAN_ENCRYPTION_KEY"]) >= 32', job)
                self.assertIn("python scripts/state_key_policy.py", job)

    def test_encrypted_plan_integrity_and_state_isolation_are_preserved(self):
        content = (WORKFLOWS / "pipeline.yml").read_text(encoding="utf-8")
        plan = section(content, "plan", "apply")
        apply = section(content, "apply")
        self.assertIn("rds.tfplan.gpg", plan)
        self.assertIn("rds.tfplan.gpg", apply)
        self.assertIn("rds.tfplan.sha256", apply)
        self.assertIn("rds-plan-metadata.json", apply)
        self.assertIn('backend-config="encrypt=true"', plan)
        self.assertIn('backend-config="use_lockfile=true"', plan)
        self.assertIn("--expected-bucket-owner", plan)
        self.assertIn("python scripts/state_key_policy.py", plan)
        self.assertIn("python scripts/state_key_policy.py", apply)
        self.assertNotRegex(content, r"(?<!\d)\d{12}(?!\d)")


if __name__ == "__main__":
    unittest.main()
