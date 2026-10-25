"""Vérifier l'orchestration des scanners et la couverture de l'historique."""

import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("security", ROOT / "scripts/security.py")
security = importlib.util.module_from_spec(spec)
spec.loader.exec_module(security)


class SecurityTests(unittest.TestCase):
    def test_empty_vulnerability_report_is_not_a_success(self):
        """Un scan sans paquet analysé ne fournit pas une preuve de contrôle."""
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.json"
            report.write_text('{"Results": []}')
            with self.assertRaisesRegex(ValueError, "Aucun paquet"):
                security.vulnerability_report(report)

    def test_vulnerability_report_counts_packages_and_alerts(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.json"
            report.write_text(json.dumps({"Results": [{
                "Packages": [{"Name": "fixture"}],
                "Vulnerabilities": [{"Severity": "HIGH"}, {"Severity": "CRITICAL"}],
            }]}))
            result = security.vulnerability_report(report)
            self.assertEqual((result["packages"], result["high"], result["critical"]), (1, 1, 1))

    def test_accepted_risk_requires_the_exact_cve_package_and_version(self):
        """L'acceptation ne s'étend ni à une autre CVE, ni à un autre paquet ou une autre version."""
        accepted = [{"id": "CVE-2026-111943", "package": "stdlib", "version": "v1.26.9"}]
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.json"
            issue = {"VulnerabilityID": "CVE-2026-111943", "PkgName": "stdlib",
                     "InstalledVersion": "v1.26.9", "Severity": "HIGH"}
            for change in ({}, {"VulnerabilityID": "CVE-2026-0001"}, {"PkgName": "other"},
                           {"InstalledVersion": "v1.26.8"}):
                report.write_text(json.dumps({"Results": [{"Packages": [{"Name": "stdlib"}],
                                                           "Vulnerabilities": [dict(issue, **change)]}]}))
                result = security.vulnerability_report(report, accepted)
                self.assertEqual(result["accepted"], 0 if change else 1)
                self.assertEqual(result["blocking"], 1 if change else 0)

    def test_risk_acceptance_is_bound_to_the_audited_artifact(self):
        """Le remplacement du binaire invalide l'acceptation même si ses métadonnées restent identiques."""
        import hashlib

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "terraform-provider-proxmox_v0.118.0"
            binary.write_bytes(b"audited fixture")
            entries = [{"id": "CVE-2026-111943", "package": "stdlib", "version": "v1.26.9"}]
            policy = {"reports": {"trivy-provider.json": entries},
                      "artifacts": {"trivy-provider.json": hashlib.sha256(binary.read_bytes()).hexdigest()}}
            self.assertEqual(security.accepted_risks("trivy-provider.json", root, policy), entries)
            self.assertEqual(security.accepted_risks("trivy-python.json", root, policy), [])
            binary.write_bytes(b"changed fixture")
            self.assertEqual(security.accepted_risks("trivy-provider.json", root, policy), [])

    def test_ci_allows_only_documented_risks_and_keeps_other_failures_blocking(self):
        """Le mode CI tolère une alerte connue, mais bloque une nouvelle alerte, un secret ou une erreur."""
        for scenario in ("known", "strict", "new", "secret", "scanner-error"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                shutil.copyfile(ROOT / "dependencies.json", root / "dependencies.json")
                (root / "terraform").mkdir()
                shutil.copyfile(ROOT / "terraform/.terraform.lock.hcl", root / "terraform/.terraform.lock.hcl")
                (root / ".github").mkdir()
                provider_version = re.search(r'\bversion\s*=\s*"(\d+\.\d+\.\d+)"',
                                             (root / "terraform/.terraform.lock.hcl").read_text())[1]
                provider_dir = root / f"terraform/.terraform/providers/registry.opentofu.org/bpg/proxmox/{provider_version}/linux_amd64"
                provider_dir.mkdir(parents=True)
                provider_binary = provider_dir / f"terraform-provider-proxmox_v{provider_version}"
                provider_binary.write_bytes(b"audited fixture")
                import hashlib

                accepted = {"reports": {"trivy-provider.json": [
                    {"id": "CVE-2026-111943", "package": "stdlib", "version": "v1.26.9"},
                ]}, "artifacts": {"trivy-provider.json": hashlib.sha256(provider_binary.read_bytes()).hexdigest()}}
                (root / ".github/security-accepted.json").write_text(json.dumps(accepted))

                def scan(command, **kwargs):
                    if command[0] == "git":
                        return subprocess.CompletedProcess([], 1)
                    if command[:2] == ["gitleaks", "dir"] and scenario == "secret":
                        return subprocess.CompletedProcess([], 1)
                    if "--output" in command:
                        report = root / command[command.index("--output") + 1]
                        result = {"Packages": [{"Name": "stdlib"}]}
                        if report.name == "trivy-provider.json":
                            if scenario == "scanner-error":
                                return subprocess.CompletedProcess([], 2)
                            result["Vulnerabilities"] = [{
                                "VulnerabilityID": "CVE-2026-0001" if scenario == "new" else "CVE-2026-111943",
                                "PkgName": "stdlib", "InstalledVersion": "v1.26.9", "Severity": "HIGH",
                            }]
                        report.write_text(json.dumps({"Results": [result]}))
                        return subprocess.CompletedProcess([], 1 if result.get("Vulnerabilities") else 0)
                    return subprocess.CompletedProcess([], 0)

                with (
                    patch.object(security, "ROOT", root),
                    patch.object(security.shutil, "which", return_value="/bin/tool"),
                    patch.object(security.subprocess, "run", side_effect=scan),
                    contextlib.redirect_stdout(io.StringIO()),
                    self.assertRaises(SystemExit) as raised,
                ):
                    security.main(allow_known=scenario != "strict")
                self.assertEqual(raised.exception.code, 0 if scenario == "known" else 1)

    @unittest.skipUnless(shutil.which("trivy"), "Trivy absent : installer les outils mise")
    def test_trivy_exception_scope_and_expiration(self):
        """Trivy exclut uniquement le chemin visé, jusqu'à expiration."""
        cve = "CVE-2025-68121"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            finding = {"VulnerabilityID": cve, "PkgName": "stdlib",
                       "InstalledVersion": "v1.24.6", "Severity": "CRITICAL",
                       "PkgIdentifier": {"PURL": "pkg:golang/stdlib@v1.24.6"}}
            results = []
            for target, version in (("usr/local/bin/gosu", "v1.24.6"),
                                    ("gitleaks", "v1.24.6")):
                identifier = {"PURL": f"pkg:golang/stdlib@{version}", "UID": target}
                issue = dict(finding, InstalledVersion=version,
                             PkgIdentifier=identifier)
                results.append({"Target": target, "Class": "lang-pkgs", "Type": "gobinary",
                                "Packages": [{"Name": "stdlib", "Version": version, "Identifier": identifier}],
                                "Vulnerabilities": [issue]})
            report = root / "input.json"
            report.write_text(json.dumps({"SchemaVersion": 2, "ArtifactName": "fixture",
                                          "ArtifactType": "filesystem", "Results": results}))
            ignores = (ROOT / ".trivyignore.yaml").read_text()
            for expiry, active in (((date.today() + timedelta(days=1)).isoformat(), [0, 1]),
                                   ("2000-01-01", [1, 1])):
                ignorefile = root / "ignore.yaml"
                ignorefile.write_text(re.sub(r"expired_at: \d{4}-\d{2}-\d{2}",
                                             "expired_at: " + expiry, ignores))
                output = root / "output.json"
                result = subprocess.run(
                    [shutil.which("trivy"), "convert", "--format", "json", "--exit-code", "1",
                     "--ignorefile", str(ignorefile), "--show-suppressed", "--output", str(output), str(report)],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 1, result.stderr)
                converted = json.loads(output.read_text())["Results"]
                self.assertEqual([len(r.get("Vulnerabilities", [])) for r in converted], active)
                self.assertEqual(sum(len(r.get("ExperimentalModifiedFindings", [])) for r in converted),
                                 1 if active[0] == 0 else 0)

    def test_gosu_exceptions_require_the_exact_audited_image(self):
        """Un autre digest ou un scan d'outil ne réutilise jamais les exceptions gosu."""
        image = security.GOSU_AUDITED_IMAGE
        self.assertEqual(security.ignorefile("image", image), ".trivyignore.yaml")
        self.assertEqual(security.ignorefile("image", image[:-1] + "0"), "")
        for scan in ("fs", "rootfs"):
            self.assertEqual(security.ignorefile(scan, image), "")

    def test_tool_exceptions_require_the_exact_binary_and_scan(self):
        """Une exclusion d'outil ne survit ni à un autre nom, ni à un autre contenu."""
        import hashlib

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "actionlint"
            binary.write_bytes(b"audited fixture")
            fingerprint = hashlib.sha256(binary.read_bytes()).hexdigest()
            with patch.dict(security.AUDITED_TOOL_BINARIES, {"actionlint": fingerprint}, clear=True):
                self.assertEqual(security.ignorefile("rootfs", "", binary), ".trivyignore.yaml")
                for scan in ("fs", "image"):
                    self.assertEqual(security.ignorefile(scan, "", binary), "")
                other = root / "provider"
                other.write_bytes(binary.read_bytes())
                self.assertEqual(security.ignorefile("rootfs", "", other), "")
                binary.write_bytes(b"updated fixture")
                self.assertEqual(security.ignorefile("rootfs", "", binary), "")
                binary.unlink()
                self.assertEqual(security.ignorefile("rootfs", "", binary), "")

    @unittest.skipUnless(shutil.which("trivy"), "Trivy absent : installer les outils mise")
    def test_trivy_tool_exception_paths_packages_and_expiration(self):
        """Trivy ne masque pas la même CVE dans un autre outil ou un autre paquet."""
        cases = (
            ("CVE-2026-111943", "actionlint", "stdlib", "v1.26.1"),
            ("CVE-2025-47913", "gitleaks", "golang.org/x/crypto", "v0.35.0"),
            ("CVE-2026-56864", "tofu", "golang.org/x/mod", "v0.39.0"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for cve, target, package, version in cases:
                results = []
                for path, name, installed in ((target, package, version), ("provider", package, version),
                                               (target, "unrelated", version), (target, package, version + "-test")):
                    identifier = {"PURL": f"pkg:golang/{name}@{installed}", "UID": f"{path}:{name}:{installed}"}
                    results.append({"Target": path, "Class": "lang-pkgs", "Type": "gobinary",
                                    "Packages": [{"Name": name, "Version": installed, "Identifier": identifier}],
                                    "Vulnerabilities": [{"VulnerabilityID": cve, "PkgName": name,
                                        "InstalledVersion": installed, "Severity": "HIGH",
                                        "PkgIdentifier": identifier}]})
                report = root / "input.json"
                report.write_text(json.dumps({"SchemaVersion": 2, "ArtifactName": "fixture",
                                              "ArtifactType": "filesystem", "Results": results}))
                for expiry, active in (((date.today() + timedelta(days=1)).isoformat(), [0, 1, 1, 1]),
                                       ("2000-01-01", [1, 1, 1, 1])):
                    ignorefile = root / "ignore.yaml"
                    ignorefile.write_text(re.sub(r"expired_at: \d{4}-\d{2}-\d{2}",
                                                 "expired_at: " + expiry, (ROOT / ".trivyignore.yaml").read_text()))
                    output = root / "output.json"
                    result = subprocess.run(
                        [shutil.which("trivy"), "convert", "--format", "json", "--exit-code", "1",
                         "--ignorefile", str(ignorefile), "--show-suppressed", "--output", str(output), str(report)],
                        capture_output=True, text=True, timeout=30,
                    )
                    self.assertEqual(result.returncode, 1, result.stderr)
                    converted = json.loads(output.read_text())["Results"]
                    self.assertEqual([len(r.get("Vulnerabilities", [])) for r in converted], active, cve)

    def test_suppressed_findings_are_counted_separately(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.json"
            report.write_text(json.dumps({"Results": [{
                "Packages": [{"Name": "fixture"}],
                "ExperimentalModifiedFindings": [{"Type": "vulnerability"}],
            }]}))
            result = security.vulnerability_report(report)
            self.assertEqual((result["high"], result["critical"], result["suppressed"]), (0, 0, 1))

    @unittest.skipUnless(shutil.which("gitleaks"), "Gitleaks absent : installer les outils mise")
    def test_private_config_is_local_only_and_force_added_secret_is_detected(self):
        """Un secret privé est ignoré localement, mais détecté dans un exemple ou l'index."""
        import hashlib

        fake = "ghp" + "_" + hashlib.sha256(b"local-config-test-only").hexdigest()[:36]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
            subprocess.run(["git", "init", "--quiet"], cwd=root, env=environment, check=True)
            (root / ".gitignore").write_text("databases.yml\n")
            (root / "databases.yml").write_text("token=" + fake)

            def scan(*arguments):
                return subprocess.run(
                    [shutil.which("gitleaks"), *arguments, "--redact", "--no-banner"],
                    cwd=root, env=environment, capture_output=True, text=True, timeout=15,
                )

            local_arguments = ("dir", ".", "--config", str(ROOT / ".gitleaks.toml"))
            self.assertEqual(scan(*local_arguments).returncode, 0)
            example = root / "databases.yml.example"
            example.write_text("token=" + fake)
            self.assertEqual(scan(*local_arguments).returncode, 1)
            example.unlink()
            subprocess.run(["git", "add", "-f", "databases.yml"],
                           cwd=root, env=environment, check=True)
            result = scan("git", ".", "--pre-commit", "--staged", "--config",
                          str(ROOT / ".github/gitleaks-history.toml"))
            self.assertEqual(result.returncode, 1)
            self.assertNotIn(fake, result.stdout + result.stderr)

    def test_all_scanners_run_even_when_one_fails(self):
        """Un secret détecté fait échouer le contrôle sans empêcher les autres scanners."""
        with tempfile.TemporaryDirectory() as temporary:
            shutil.copyfile(ROOT / "dependencies.json", Path(temporary) / "dependencies.json")
            (Path(temporary) / "terraform").mkdir()
            shutil.copyfile(ROOT / "terraform/.terraform.lock.hcl", Path(temporary) / "terraform/.terraform.lock.hcl")
            with (
                patch.object(security, "ROOT", Path(temporary)),
                patch.object(security.shutil, "which", return_value="/bin/tool"),
                patch.object(security.subprocess, "run") as run,
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaises(SystemExit) as raised,
            ):
                run.side_effect = lambda command, **kwargs: subprocess.CompletedProcess(
                    [], 1 if command[:2] == ["gitleaks", "dir"] else 0,
                )
                security.main()
            self.assertEqual(raised.exception.code, 1)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertIn(["trivy", "config"], [command[:2] for command in commands])
            self.assertTrue(any(".reports/trivy-python.json" in command for command in commands))
            self.assertTrue(any(".reports/trivy-provider.json" in command for command in commands))
            self.assertTrue(any(".reports/trivy-postgres.json" in command for command in commands))
            self.assertTrue(any(".reports/trivy-tool-tofu.json" in command for command in commands))
            self.assertIn("--redact", commands[2])
            self.assertIn(".github/gitleaks-history.toml", commands[3])
            self.assertIn("--staged", commands[4])

    def test_missing_scanner_is_an_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            shutil.copyfile(ROOT / "dependencies.json", Path(temporary) / "dependencies.json")
            (Path(temporary) / "terraform").mkdir()
            shutil.copyfile(ROOT / "terraform/.terraform.lock.hcl", Path(temporary) / "terraform/.terraform.lock.hcl")
            with (
                patch.object(security, "ROOT", Path(temporary)),
                patch.object(security.shutil, "which", return_value=None),
                patch.object(security.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)),
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaises(SystemExit) as raised,
            ):
                security.main()
            self.assertEqual(raised.exception.code, 1)

    def test_missing_tool_binary_cannot_produce_a_success(self):
        """Des rapports propres ne compensent pas l'absence d'un binaire à analyser."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copyfile(ROOT / "dependencies.json", root / "dependencies.json")
            (root / "terraform").mkdir()
            shutil.copyfile(ROOT / "terraform/.terraform.lock.hcl", root / "terraform/.terraform.lock.hcl")

            def scan(command, **kwargs):
                if command[0] == "git":
                    return subprocess.CompletedProcess([], 1)
                if "--output" in command:
                    (root / command[command.index("--output") + 1]).write_text(json.dumps({
                        "Results": [{"Packages": [{"Name": "fixture"}]}],
                    }))
                return subprocess.CompletedProcess([], 0)

            with (
                patch.object(security, "ROOT", root),
                patch.object(security.shutil, "which", side_effect=lambda name: None if name == "tofu" else "/bin/tool"),
                patch.object(security.subprocess, "run", side_effect=scan),
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaises(SystemExit) as raised,
            ):
                security.main()
            self.assertEqual(raised.exception.code, 1)
            self.assertTrue(json.loads((root / ".reports/dependencies-summary.json").read_text())["failed"])

    def test_stale_malformed_or_contradictory_report_is_not_a_success(self):
        """Un code zéro du scanner ne suffit pas face à un rapport absent, invalide ou vulnérable."""
        for scenario in ("stale", "malformed", "contradictory"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                shutil.copyfile(ROOT / "dependencies.json", root / "dependencies.json")
                (root / "terraform").mkdir()
                shutil.copyfile(ROOT / "terraform/.terraform.lock.hcl", root / "terraform/.terraform.lock.hcl")
                (root / ".reports").mkdir()
                selected = root / ".reports/trivy-python.json"
                clean = {"Results": [{"Packages": [{"Name": "fixture"}]}]}
                selected.write_text(json.dumps(clean))

                def scan(command, **kwargs):
                    if command[0] == "git":
                        return subprocess.CompletedProcess([], 1)
                    if "--output" in command:
                        report = root / command[command.index("--output") + 1]
                        if report != selected:
                            report.write_text(json.dumps(clean))
                        elif scenario == "malformed":
                            report.write_text("invalid JSON")
                        elif scenario == "contradictory":
                            report.write_text(json.dumps({"Results": [{
                                "Packages": [{"Name": "fixture"}],
                                "Vulnerabilities": [{"Severity": "HIGH"}],
                            }]}))
                    return subprocess.CompletedProcess([], 0)

                with (
                    patch.object(security, "ROOT", root),
                    patch.object(security.shutil, "which", return_value="/bin/tool"),
                    patch.object(security.subprocess, "run", side_effect=scan),
                    contextlib.redirect_stdout(io.StringIO()),
                    self.assertRaises(SystemExit) as raised,
                ):
                    security.main()
                self.assertEqual(raised.exception.code, 1)
                if scenario == "stale":
                    self.assertFalse(selected.exists())

    @unittest.skipUnless(shutil.which("gitleaks"), "Gitleaks absent : installer les outils mise")
    def test_history_scan_detects_accidentally_committed_archive(self):
        """Le scan d'historique détecte un faux secret commité dans tmp/."""
        import hashlib

        # Valeur synthétique, sans accès à un compte ; construite uniquement dans /tmp.
        fake = "ghp" + "_" + hashlib.sha256(b"iac-postgres-test-only").hexdigest()[:36]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")

            def git(*arguments):
                subprocess.run(["git", *arguments], cwd=root, env=environment,
                               capture_output=True, check=True, timeout=10)

            git("init", "--quiet")
            (root / "tmp").mkdir()
            (root / "tmp/archive.txt").write_text("token=" + fake)
            git("add", "tmp/archive.txt")
            git("-c", "user.name=Audit", "-c", "user.email=audit@example.invalid",
                "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
                "commit", "--quiet", "-m", "synthetic scanner fixture")
            report = root / "report.json"
            result = subprocess.run(
                [shutil.which("gitleaks"), "git", ".", "--redact",
                 "--config", str(ROOT / ".github/gitleaks-history.toml"),
                 "--report-format", "json", "--report-path", str(report)],
                cwd=root, env=environment, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 1)
            findings = json.loads(report.read_text())
            self.assertTrue(any(entry["File"] == "tmp/archive.txt" for entry in findings))
            self.assertNotIn(fake, result.stdout + result.stderr + report.read_text())


if __name__ == "__main__":
    unittest.main()
