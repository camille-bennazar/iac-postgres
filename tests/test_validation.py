"""Vérifier les règles Ansible et leurs diagnostics, sans connexion distante."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VALIDATION_TASKS = PROJECT_ROOT / "ansible/tasks/validate.yml"
FAKE_PASSWORD = 'S3cr3t$with"quotes:and\\slashes!'


def validation_cases():
    """Décrire les configurations et le diagnostic attendu ; None signifie succès."""
    valid = {
        "id": "app",
        "name": "app",
        "user": "app",
        "port": 5432,
        "password": FAKE_PASSWORD,
    }
    cases = [
        ("valid configuration", [valid], None),
        ("empty list", [], None),
    ]

    invalid_fields = [
        ("id with path traversal", "id", "../escape"),
        ("id with newline", "id", "app\n"),
        ("invalid SQL name", "name", "bad;sql"),
        ("reserved user prefix", "user", "pg_app"),
        ("example password", "password", "CHANGE_ME_USE_A_RANDOM_PASSWORD"),
        ("short password", "password", "short"),
        ("password with newline", "password", "x" * 20 + "\n"),
        ("quoted port", "port", "5432"),
        ("port out of range", "port", 65536),
    ]
    for name, field, value in invalid_fields:
        cases.append((name, [dict(valid, **{field: value})], field))

    missing_password = {key: value for key, value in valid.items() if key != "password"}
    cases.extend([
        (
            "duplicate ports",
            [valid, dict(valid, id="other")],
            "databases[1] : port dupliqué",
        ),
        (
            "duplicate ids",
            [valid, dict(valid, port=5433)],
            "databases[1] : id dupliqué",
        ),
        ("missing password", [missing_password], "password"),
        ("mapping instead of list", {"secret": FAKE_PASSWORD}, "databases"),
        ("string instead of entry", [FAKE_PASSWORD], "databases"),
        ("id containing a secret", [dict(valid, id=FAKE_PASSWORD)], "databases"),
    ])
    return cases


class DatabaseValidationTests(unittest.TestCase):
    def run_validation(self, databases):
        """Exécuter uniquement les tâches de validation dans un playbook local."""
        playbook = [{
            "name": "Validate fixture",
            "hosts": "localhost",
            "gather_facts": False,
            "vars": {"databases": databases},
            "tasks": [{"ansible.builtin.import_tasks": str(VALIDATION_TASKS)}],
        }]

        with tempfile.TemporaryDirectory() as temporary:
            playbook_path = Path(temporary) / "check.json"
            playbook_path.write_text(json.dumps(playbook))
            return subprocess.run(
                [
                    os.environ.get("ANSIBLE_PLAYBOOK", "ansible-playbook"),
                    "-i",
                    "localhost,",
                    str(playbook_path),
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

    def check_case(self, databases, expected_error):
        result = self.run_validation(databases)
        self.assertEqual(result.returncode == 0, expected_error is None,
                         "Code de retour inattendu (sortie masquée pour protéger les secrets).")
        if expected_error is not None:
            self.assertIn("databases", result.stdout)
            self.assertIn(expected_error, result.stdout)
            self.assertNotIn('"censored"', result.stdout)
        output = result.stdout + result.stderr
        self.assertNotIn(FAKE_PASSWORD, output)
        if isinstance(databases, list):
            for entry in databases:
                if isinstance(entry, dict) and isinstance(entry.get("password"), str):
                    self.assertNotIn(entry["password"], output)


def add_case(name, databases, expected_error):
    def test(self):
        self.check_case(databases, expected_error)
    test.__doc__ = "Validation PostgreSQL : " + name
    setattr(DatabaseValidationTests, "test_" + name.replace(" ", "_"), test)


for case in validation_cases():
    add_case(*case)


if __name__ == "__main__":
    unittest.main()
