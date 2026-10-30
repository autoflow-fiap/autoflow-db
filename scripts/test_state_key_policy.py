import unittest

from state_key_policy import HOMOLOG_STATE_KEYS, PRODUCTION_RDS_STATE_KEY, validate_state_keys


class StateKeyPolicyTests(unittest.TestCase):
    def test_accepts_existing_homolog_keys_without_migrating_state(self):
        validate_state_keys(
            "homolog",
            "rds/terraform.tfstate",
            "eks/terraform.tfstate",
        )

    def test_accepts_production_rds_key_and_infrastructure_key_under_production(self):
        validate_state_keys(
            "production",
            "production/rds/terraform.tfstate",
            "production/infra/terraform.tfstate",
        )

    def test_homolog_and_production_never_share_a_root_key(self):
        homolog_keys = set(HOMOLOG_STATE_KEYS.values())
        production_keys = {PRODUCTION_RDS_STATE_KEY, "production/infra/terraform.tfstate"}
        self.assertTrue(homolog_keys.isdisjoint(production_keys))

    def test_rejects_missing_or_unknown_environment_configuration(self):
        for environment, rds_key, infra_key in (
            (None, "rds/terraform.tfstate", "eks/terraform.tfstate"),
            ("homolog", None, "eks/terraform.tfstate"),
            ("homolog", "rds/terraform.tfstate", ""),
            ("staging", "rds/terraform.tfstate", "eks/terraform.tfstate"),
        ):
            with self.subTest(environment=environment, rds_key=rds_key, infra_key=infra_key):
                with self.assertRaises(ValueError):
                    validate_state_keys(environment, rds_key, infra_key)

    def test_rejects_keys_from_another_environment_or_wrong_root(self):
        invalid_pairs = (
            ("homolog", "homolog/rds/terraform.tfstate", "homolog/infra/terraform.tfstate"),
            ("homolog", "rds/terraform.tfstate", "production/infra/terraform.tfstate"),
            ("production", "rds/terraform.tfstate", "eks/terraform.tfstate"),
            ("production", "production/infra/terraform.tfstate", "production/infra/terraform.tfstate"),
            ("production", "production/rds/terraform.tfstate", "production/rds/terraform.tfstate"),
        )
        for environment, rds_key, infra_key in invalid_pairs:
            with self.subTest(environment=environment, rds_key=rds_key, infra_key=infra_key):
                with self.assertRaises(ValueError):
                    validate_state_keys(environment, rds_key, infra_key)

    def test_rejects_traversal_and_empty_path_segments(self):
        for rds_key, infra_key in (
            ("rds/../terraform.tfstate", "eks/terraform.tfstate"),
            ("rds//terraform.tfstate", "eks/terraform.tfstate"),
            ("rds/terraform.tfstate", "eks/./terraform.tfstate"),
        ):
            with self.subTest(rds_key=rds_key, infra_key=infra_key):
                with self.assertRaisesRegex(ValueError, "segmento de caminho inválido"):
                    validate_state_keys("homolog", rds_key, infra_key)


if __name__ == "__main__":
    unittest.main()
