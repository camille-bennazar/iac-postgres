"""Vérifier les fichiers locaux dans des répertoires temporaires."""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("local", PROJECT_ROOT / "scripts/local.py")
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


class LocalFilesTests(unittest.TestCase):
    def test_malformed_inventory_never_overwrites_previous_inventory(self):
        """Une sortie absente, mal typée ou sans IPv4 conserve l'inventaire précédent."""
        def payload(hosts):
            return {"all": {"children": {"postgres": {"hosts": hosts}}}}

        cases = [None, [], {}, payload([]), payload({}), payload({"vm": None}),
                 payload({"vm": {"ansible_host": 123}}),
                 payload({"vm": {"ansible_host": "not-an-ip"}}),
                 payload({"vm": {"ansible_host": "2001:db8::1"}})]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "inventory.json").write_text("previous")
            with patch.object(local, "PROJECT_ROOT", root):
                for value in cases:
                    with self.subTest(value=value), patch("sys.stdin", io.StringIO(json.dumps(value))):
                        with self.assertRaises((TypeError, KeyError, ValueError)):
                            local.inventory()
                        self.assertEqual((root / "inventory.json").read_text(), "previous")

    def test_setup_refuses_symlink_to_private_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "terraform").mkdir()
            target = root / "private"
            target.write_text("keep")
            (root / "terraform/terraform.tfvars").symlink_to(target)
            with patch.object(local, "PROJECT_ROOT", root), self.assertRaises(ValueError):
                local.setup()
            self.assertEqual(target.read_text(), "keep")

    def test_setup_preserves_existing_files_and_protects_secrets(self):
        with tempfile.TemporaryDirectory() as temporary:
            project_root = Path(temporary)
            (project_root / "terraform").mkdir()
            for name in ("terraform/terraform.tfvars", "databases.yml"):
                (project_root / f"{name}.example").write_text("example")

            with (
                patch.object(local, "PROJECT_ROOT", project_root),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                local.setup()
                (project_root / "databases.yml").write_text("existing secret")
                local.setup()

            configuration = project_root / "databases.yml"
            self.assertEqual(configuration.read_text(), "existing secret")
            self.assertEqual(configuration.stat().st_mode & 0o777, 0o600)

    def test_inventory_uses_output_and_keeps_old_file_on_invalid_input(self):
        inventory = {
            "all": {
                "children": {
                    "postgres": {
                        "hosts": {
                            "database_vm": {
                                "ansible_host": "10.20.30.40",
                                "ansible_user": "debian",
                            }
                        }
                    }
                }
            }
        }

        with tempfile.TemporaryDirectory() as temporary:
            project_root = Path(temporary)
            with (
                patch.object(local, "PROJECT_ROOT", project_root),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                with patch("sys.stdin", io.StringIO(json.dumps(inventory))):
                    local.inventory()
                with (
                    patch("sys.stdin", io.StringIO("{}")),
                    self.assertRaises(KeyError),
                ):
                    local.inventory()

            generated_inventory = project_root / "inventory.json"
            self.assertEqual(json.loads(generated_inventory.read_text()), inventory)
            self.assertEqual(generated_inventory.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
