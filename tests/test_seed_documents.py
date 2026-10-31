"""Valida documentos de demonstração e, opcionalmente, a migração em PostgreSQL."""

import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "V49__corrigir_documentos_seeds_demo.sql"
DOCUMENTS = {
    "ana@exemplo.com": "80657439193",
    "pedro@exemplo.com": "74185296355",
    "contato@xyz.com.br": "80657439120452",
    "fernanda@exemplo.com": "63920481704",
}


def _digit(base, weights):
    remainder = sum(int(digit) * weight for digit, weight in zip(base, weights)) % 11
    return "0" if remainder < 2 else str(11 - remainder)


def valid_document(document):
    if not document.isdigit() or len(set(document)) == 1:
        return False
    if len(document) == 11:
        first = _digit(document[:9], range(10, 1, -1))
        second = _digit(document[:10], range(11, 1, -1))
    elif len(document) == 14:
        first = _digit(document[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        second = _digit(document[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    else:
        return False
    return document[-2:] == first + second


class SeedDocumentTests(unittest.TestCase):
    def test_audit_of_original_v40_and_v48_seed_documents(self):
        self.assertFalse(valid_document("22255588814"))
        self.assertFalse(valid_document("33366699926"))
        self.assertTrue(valid_document("12345678000195"))
        self.assertFalse(valid_document("44477700815"))
        self.assertTrue(valid_document("11144477735"))

    def test_documents_have_valid_check_digits_and_are_unique(self):
        self.assertTrue(all(valid_document(value) for value in DOCUMENTS.values()))
        self.assertEqual(len(DOCUMENTS.values()), len(set(DOCUMENTS.values())))

    def test_migration_updates_both_identity_tables_and_os_snapshot(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("UPDATE usuarios", sql)
        self.assertIn("UPDATE clientes", sql)
        self.assertIn("UPDATE ordem_servico", sql)
        for email, document in DOCUMENTS.items():
            self.assertIn(email, sql)
            self.assertIn(document, sql)
        self.assertIn("c.usuario_id IS DISTINCT FROM u.id", sql)
        self.assertIn("RAISE EXCEPTION", sql)

    @unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "defina TEST_DATABASE_URL para PostgreSQL descartável")
    def test_migration_constraints_and_referential_integrity(self):
        import psycopg2

        connection = psycopg2.connect(os.environ["TEST_DATABASE_URL"])
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        CREATE TEMP TABLE usuarios (
                            id BIGINT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                            cpf_cnpj VARCHAR(18) UNIQUE
                        );
                        CREATE TEMP TABLE clientes (
                            id BIGINT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                            cpf_cnpj VARCHAR(14) UNIQUE NOT NULL,
                            usuario_id BIGINT UNIQUE REFERENCES usuarios(id)
                        );
                        CREATE TEMP TABLE ordem_servico (
                            id BIGINT PRIMARY KEY, cliente_id BIGINT REFERENCES clientes(id),
                            cliente_cpf_cnpj VARCHAR(50)
                        );
                        INSERT INTO usuarios VALUES
                        (1, 'ana@exemplo.com', NULL), (2, 'pedro@exemplo.com', NULL),
                        (3, 'contato@xyz.com.br', NULL), (4, 'fernanda@exemplo.com', NULL);
                        INSERT INTO clientes VALUES
                        (11, 'ana@exemplo.com', '22255588814', 1),
                        (12, 'pedro@exemplo.com', '33366699926', 2),
                        (13, 'contato@xyz.com.br', '12345678000195', 3),
                        (14, 'fernanda@exemplo.com', '44477700815', 4);
                        INSERT INTO ordem_servico VALUES
                        (101, 11, '22255588814'), (102, 12, '33366699926'),
                        (103, 13, '12345678000195'), (104, 14, '44477700815');
                    """)
                    sql = MIGRATION.read_text(encoding="utf-8")
                    cursor.execute(sql)
                    cursor.execute("""
                        SELECT count(*) FROM usuarios u
                        JOIN clientes c ON c.usuario_id = u.id AND c.cpf_cnpj = u.cpf_cnpj
                        JOIN ordem_servico os ON os.cliente_id = c.id AND os.cliente_cpf_cnpj = c.cpf_cnpj
                    """)
                    self.assertEqual(cursor.fetchone()[0], 4)
                    cursor.execute("SELECT count(*) FROM ordem_servico")
                    self.assertEqual(cursor.fetchone()[0], 4)
                    with self.assertRaises(psycopg2.errors.UniqueViolation):
                        cursor.execute("UPDATE usuarios SET cpf_cnpj = '74185296355' WHERE id = 1")
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
