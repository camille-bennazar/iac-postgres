"""Tester l'archivage exclusivement dans des projets temporaires."""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("maintenance", ROOT / "scripts/maintenance.py")
maintenance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maintenance)


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(temporary)
        self.enterContext(patch.object(maintenance, "PROJECT_ROOT", self.root))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def create(self, relative, content="fixture"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_round_trip_preserves_configs_lock_and_file_contents(self):
        """Nettoyage puis restauration : données conservées, fichiers privés protégés."""
        generated = ["terraform/terraform.tfstate", "terraform/terraform.tfstate.backup",
                     "terraform/.terraform/provider", "inventory.json", ".ansible/tmp/module",
                     "scripts/__pycache__/local.pyc", "terraform/test.tfplan", "crash.log"]
        protected = ["databases.yml", "terraform/terraform.tfvars", "terraform/.terraform.lock.hcl"]
        for name in generated + protected:
            self.create(name, name)
        maintenance.clear()
        available = maintenance.archives()
        self.assertEqual(len(available), 1)
        archive, _ = available[0]
        self.assertEqual(archive.stat().st_mode & 0o777, 0o700)
        self.assertEqual((archive / "files/terraform/terraform.tfstate").stat().st_mode & 0o777, 0o600)
        for name in generated:
            self.assertFalse((self.root / name).exists())
        for name in protected:
            self.assertEqual((self.root / name).read_text(), name)
        for command in maintenance.STATE_COMMANDS:
            with self.assertRaises(maintenance.MaintenanceError):
                maintenance.guard(command)
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.clear_tmp()
        maintenance.restore(archive.name)
        for name in generated:
            self.assertEqual((self.root / name).read_text(), name)
        maintenance.guard("apply")
        maintenance.clear_tmp()
        self.assertFalse((self.root / "tmp").exists())

    def test_repeated_clean_and_forced_purge(self):
        """Nettoyage répétable ; purge du state uniquement avec option explicite."""
        maintenance.clear()
        self.create("terraform/terraform.tfstate")
        maintenance.clear()
        maintenance.clear()
        self.assertEqual(len(maintenance.archives()), 1)
        maintenance.clear_tmp(force=True)
        self.assertFalse((self.root / "tmp").exists())

    def test_restore_conflict_does_not_move_any_file(self):
        """Un conflit bloque toute la restauration et conserve l'archive."""
        self.create("inventory.json")
        self.create("terraform/terraform.tfstate", "original")
        maintenance.clear()
        archive, _ = maintenance.archives()[0]
        self.create("terraform/terraform.tfstate", "new")
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.restore(archive.name)
        self.assertFalse((self.root / "inventory.json").exists())
        self.assertEqual((self.root / "terraform/terraform.tfstate").read_text(), "new")
        self.assertEqual((archive / "files/terraform/terraform.tfstate").read_text(), "original")

    def test_interrupted_clear_is_restorable(self):
        """Une interruption entre deux déplacements ne perd aucun fichier."""
        self.create("inventory.json", "inventory")
        self.create("terraform/terraform.tfstate", "state")
        replace = maintenance.os.replace
        calls = 0

        def interrupt(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated interruption")
            return replace(source, destination)

        with patch.object(maintenance.os, "replace", side_effect=interrupt):
            with self.assertRaises(OSError):
                maintenance.clear()
        archive, _ = maintenance.archives()[0]
        maintenance.restore(archive.name)
        self.assertEqual((self.root / "inventory.json").read_text(), "inventory")
        self.assertEqual((self.root / "terraform/terraform.tfstate").read_text(), "state")

    def test_rejects_symlinks_without_touching_external_file(self):
        """Les liens symboliques et les chemins externes sont refusés."""
        external = self.create("private", "keep")
        (self.root / "inventory.json").symlink_to(external)
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.clear()
        self.assertEqual(external.read_text(), "keep")
        for relative in ("../private", "/tmp/private", "."):
            with self.assertRaises(maintenance.MaintenanceError):
                maintenance.safe_path(self.root, relative)

    def test_rejects_symlink_inside_cache(self):
        self.create("terraform/.terraform/provider")
        (self.root / "terraform/.terraform/link").symlink_to(self.root / "private")
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.clear()

    def test_rejects_unsafe_manifest_and_unknown_archive(self):
        for path in ("../__pycache__", ".git/__pycache__", "databases.yml"):
            manifest = self.create("tmp/archive-bad/manifest.json", json.dumps({"version": 1, "paths": [path]}))
            with self.assertRaises(maintenance.MaintenanceError):
                maintenance.clear_tmp(force=True)
            manifest.unlink()
            manifest.parent.rmdir()
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.restore("../escape")

    def test_lock_blocks_concurrent_operations(self):
        """Deux opérations ne peuvent pas utiliser les fichiers locaux simultanément."""
        with maintenance.project_lock():
            with self.assertRaises(maintenance.MaintenanceError):
                with maintenance.project_lock():
                    self.fail("second lock acquired")

    def test_tofu_lock_blocks_clear(self):
        self.create("terraform/.terraform.tfstate.lock.info")
        self.create("terraform/terraform.tfstate")
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.clear()
        self.assertTrue((self.root / "terraform/terraform.tfstate").exists())

    def test_make_commands_archive_guard_restore_and_purge(self):
        """Les vraies commandes Make transmettent les options et protègent le state."""
        shutil.copyfile(ROOT / "Makefile", self.root / "Makefile")
        (self.root / "scripts").mkdir()
        shutil.copyfile(ROOT / "scripts/maintenance.py", self.root / "scripts/maintenance.py")
        self.create("terraform/terraform.tfstate", "state")
        environment = dict(os.environ)
        environment.pop("IAC_LOCKED", None)

        def make(*arguments):
            return subprocess.run(
                [shutil.which("make"), f"PYTHON={sys.executable}", "TOFU=/bin/false", *arguments],
                cwd=self.root, env=environment, capture_output=True, text=True, timeout=10,
            )

        result = make("clear")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        archive = next((self.root / "tmp").iterdir()).name
        for command in ("check", "security", "init", "plan", "apply", "configure", "status"):
            result = make(command)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("State archivé", result.stderr)
        self.assertFalse((self.root / "terraform/.terraform").exists())
        result = make("clear-tmp")
        self.assertNotEqual(result.returncode, 0)
        result = make("restore", f"ARCHIVE={archive}")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / "terraform/terraform.tfstate").read_text(), "state")
        self.assertEqual(make("clear").returncode, 0)
        self.assertEqual(make("clear-tmp", "PURGE_STATE=1").returncode, 0)
        self.assertFalse((self.root / "tmp").exists())


if __name__ == "__main__":
    unittest.main()
