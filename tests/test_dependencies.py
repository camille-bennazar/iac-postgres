"""Refuser les régressions d'épinglage avant l'installation en CI."""

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("dependencies", ROOT / "scripts/dependencies.py")
dependencies = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dependencies)


class DependencyPolicyTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for name in ("mise.toml", "mise.lock", "dependencies.json", "ruff.toml"):
            shutil.copyfile(ROOT / name, self.root / name)
        for name in (".mise", ".github"):
            shutil.copytree(ROOT / name, self.root / name, ignore=shutil.ignore_patterns(".venv", "__pycache__"))
        (self.root / "terraform").mkdir()
        for name in ("versions.tf", ".terraform.lock.hcl"):
            shutil.copyfile(ROOT / "terraform" / name, self.root / "terraform" / name)
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def test_repository_dependencies_satisfy_policy(self):
        dependencies.check(self.root)

    def test_mutable_image_is_rejected(self):
        path = self.root / "dependencies.json"
        pins = json.loads(path.read_text())
        pins["postgres"]["image"] = "postgres:17"
        path.write_text(json.dumps(pins))
        with self.assertRaisesRegex(ValueError, "PostgreSQL non épinglée"):
            dependencies.check(self.root)

    def test_inconsistent_ruff_python_target_is_rejected(self):
        path = self.root / "ruff.toml"
        path.write_text(path.read_text().replace('target-version = "py314"', 'target-version = "py313"'))
        with self.assertRaisesRegex(ValueError, "cible Python de Ruff"):
            dependencies.check(self.root)

    def test_stale_tool_lock_is_rejected(self):
        path = self.root / "mise.lock"
        version = dependencies.read_toml(self.root / "mise.toml")["tools"]["trivy"]
        path.write_text(path.read_text().replace(f'version = "{version}"', 'version = "0.0.0"'))
        with self.assertRaisesRegex(ValueError, "Verrou périmé"):
            dependencies.check(self.root)

    def test_missing_python_graph_is_rejected(self):
        for path in (self.root / ".mise").rglob("uv.lock"):
            path.unlink()
        with self.assertRaises(FileNotFoundError):
            dependencies.check(self.root)

    def test_python_graph_for_other_interpreters_is_rejected(self):
        for path in (self.root / ".mise/locks").rglob("pyproject.toml"):
            with self.subTest(project=path.parent.name):
                original = path.read_text()
                path.write_text(original.replace('==3.14.*', '>=3.10'))
                with self.assertRaisesRegex(ValueError, "graphe Python doit cibler"):
                    dependencies.check(self.root)
                path.write_text(original)

    def test_python_lock_with_wider_range_is_rejected(self):
        path = next((self.root / ".mise/locks").rglob("uv.lock"))
        path.write_text(path.read_text().replace('==3.14.*', '>=3.10', 1))
        with self.assertRaisesRegex(ValueError, "graphe Python doit cibler"):
            dependencies.check(self.root)

    def test_python_dependency_without_wheel_is_rejected(self):
        path = next((self.root / ".mise/locks/ansible").rglob("uv.lock"))
        path.write_text(path.read_text().replace("wheels = [", "wheels = []\nunused_wheels = [", 1))
        with self.assertRaisesRegex(ValueError, "sans wheel"):
            dependencies.check(self.root)

    def test_action_tag_is_rejected(self):
        path = self.root / ".github/workflows/ci.yml"
        content = path.read_text()
        reference = next(line.split("uses: ", 1)[1].split()[0] for line in content.splitlines() if "uses: actions/checkout@" in line)
        path.write_text(content.replace(reference, "actions/checkout@v7"))
        with self.assertRaisesRegex(ValueError, "Action GitHub non épinglée"):
            dependencies.check(self.root)


if __name__ == "__main__":
    unittest.main()
