"""Exécuter les contrôles Ansible Compose sans installer Docker ni démarrer de conteneur."""

import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ComposeCompatibilityTests(unittest.TestCase):
    def check_compose(self, version: str, options: str, compatible: bool):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            docker = root / "docker"
            docker.write_text(
                '#!/bin/sh\ncase "$*" in\n'
                f"'compose version --short') printf '%s\\n' {shlex.quote(version)} ;;\n"
                f"'compose up --help') printf '%s\\n' {shlex.quote(options)} ;;\n"
                "*) exit 1 ;;\nesac\n"
            )
            docker.chmod(0o700)
            playbook = root / "check.json"
            playbook.write_text(json.dumps([{
                "name": "Check Compose fixture", "hosts": "localhost", "connection": "local", "gather_facts": False,
                "environment": {"PATH": str(root) + os.pathsep + os.environ["PATH"]},
                "tasks": [{"ansible.builtin.import_tasks": str(ROOT / "ansible/tasks/check-docker.yml")}],
            }]))
            result = subprocess.run(
                [os.environ.get("ANSIBLE_PLAYBOOK", "ansible-playbook"), "-i", "localhost,", str(playbook)],
                cwd=ROOT, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode == 0, compatible, result.stdout + result.stderr)
            if compatible:
                self.assertIn("changed=0", result.stdout)
            else:
                self.assertIn("Docker Compose v2", result.stdout)

    def test_compose_v2_and_required_options_are_accepted(self):
        self.check_compose("2.26.1", "      --wait Wait for services\n      --wait-timeout int Timeout", True)

    def test_compose_version_prefix_is_accepted(self):
        self.check_compose("v2.26.1", "      --wait Wait\n      --wait-timeout int Timeout", True)

    def test_compose_v1_is_rejected(self):
        self.check_compose("1.29.2", "      --wait Wait\n      --wait-timeout int Timeout", False)

    def test_missing_wait_is_rejected(self):
        self.check_compose("2.26.1", "      --wait-timeout int Timeout", False)

    def test_missing_wait_timeout_is_rejected(self):
        self.check_compose("2.26.1", "      --wait Wait", False)


if __name__ == "__main__":
    unittest.main()
