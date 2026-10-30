import unittest
from pathlib import Path

from state_key_policy import validate_state_keys


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")


class StateKeyPolicyTests(unittest.TestCase):
    def test_accepts_external_homolog_suffixes_without_fixing_them_in_code(self):
        validate_state_keys(
            "homolog",
            "homolog/custom-rds.tfstate",
            "homolog/custom-network.tfstate",
        )

    def test_accepts_production_rds_key_and_infrastructure_key_under_production(self):
        validate_state_keys(
            "production",
            "production/custom-rds.tfstate",
            "production/custom-network.tfstate",
        )

    def test_rejects_missing_or_unknown_environment_configuration(self):
        for environment, rds_key, infra_key in (
            (None, "homolog/rds.tfstate", "homolog/infra.tfstate"),
            ("homolog", None, "homolog/infra.tfstate"),
            ("homolog", "homolog/rds.tfstate", ""),
            ("staging", "staging/rds.tfstate", "staging/infra.tfstate"),
        ):
            with self.subTest(environment=environment, rds_key=rds_key, infra_key=infra_key):
                with self.assertRaises(ValueError):
                    validate_state_keys(environment, rds_key, infra_key)

    def test_rejects_keys_from_another_environment_or_wrong_root(self):
        invalid_pairs = (
            ("homolog", "homolog/rds.tfstate", "production/infra.tfstate"),
            ("homolog", "rds.tfstate", "homolog/infra.tfstate"),
            ("production", "production/rds.tfstate", "homolog/infra.tfstate"),
            ("production", "production/same.tfstate", "production/same.tfstate"),
        )
        for environment, rds_key, infra_key in invalid_pairs:
            with self.subTest(environment=environment, rds_key=rds_key, infra_key=infra_key):
                with self.assertRaises(ValueError):
                    validate_state_keys(environment, rds_key, infra_key)

    def test_rejects_traversal_and_empty_path_segments(self):
        for rds_key, infra_key in (
            ("homolog/rds/../state.bin", "homolog/eks.bin"),
            ("homolog//state.bin", "homolog/eks.bin"),
            ("homolog/rds.bin", "homolog/./eks.bin"),
        ):
            with self.subTest(rds_key=rds_key, infra_key=infra_key):
                with self.assertRaisesRegex(ValueError, "segmento de caminho inválido"):
                    validate_state_keys("homolog", rds_key, infra_key)

    def test_required_remote_state_has_no_legacy_default(self):
        variables = (ROOT / "infra/vars.tf").read_text(encoding="utf-8")
        infra_key = variables.split('variable "infra_state_key"', 1)[1].split("}", 1)[0]
        self.assertNotIn("default", infra_key)
        self.assertIn("TF_STATE_KEY: ${{ vars.AWS_TF_STATE_KEY }}", WORKFLOW)
        self.assertIn("TF_VAR_infra_state_key: ${{ vars.AWS_INFRA_STATE_KEY }}", WORKFLOW)

    def test_plan_artifact_contains_only_encrypted_plan_and_binds_run_commit(self):
        plan_artifact = WORKFLOW.split("- name: Armazenar plano criptografado desta execução", 1)[1].split("  apply:", 1)[0]
        self.assertIn("infra/rds.tfplan.gpg", plan_artifact)
        self.assertIn("infra/rds-plan-metadata.json", plan_artifact)
        self.assertNotIn("infra/rds.tfplan\n", plan_artifact)
        self.assertIn("run_attempt", WORKFLOW)
        self.assertIn("TF_PLAN_ENCRYPTION_KEY", WORKFLOW)
        self.assertIn("gpg --batch --yes --pinentry-mode loopback", WORKFLOW)
        self.assertIn("retention-days: 1", plan_artifact)


if __name__ == "__main__":
    unittest.main()
