"""Vérifier la veille sans réseau ni message Discord réel."""

import contextlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    import watch_patches as watch


def report(path, ids):
    path.write_text(json.dumps({"Results": [{"Packages": [{"Name": "fixture"}],
        "Vulnerabilities": [{"VulnerabilityID": cve, "Severity": "HIGH"} for cve in ids]}]}))


def archive_bytes(name="gitleaks", kind=tarfile.REGTYPE):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        entry = tarfile.TarInfo(name)
        entry.type = kind
        entry.linkname = "outside"
        content = b"\x7fELFtest-only"
        entry.size = len(content) if kind == tarfile.REGTYPE else 0
        archive.addfile(entry, io.BytesIO(content))
    return output.getvalue()


class WatchTests(unittest.TestCase):
    def test_download_redirects_never_forward_the_github_token(self):
        request = watch.urllib.request.Request("https://api.github.com/example", headers={"Authorization": "Bearer fixture"})
        handler = watch.PublicRedirect()
        redirected = handler.redirect_request(request, None, 302, "Found", {}, "https://release-assets.githubusercontent.com/asset")
        self.assertIsNone(redirected.get_header("Authorization"))
        with self.assertRaises(ValueError):
            handler.redirect_request(request, None, 302, "Found", {}, "http://example.invalid/asset")

    def test_only_stable_published_releases_are_considered(self):
        releases = [
            {"tag_name": "v1.2.3", "draft": False, "prerelease": False},
            {"tag_name": "v2.0.0", "draft": False, "prerelease": True},
            {"tag_name": "v3.0.0", "draft": True, "prerelease": False},
            {"tag_name": "v4.0.0-rc.1", "draft": False, "prerelease": False},
        ]
        for release in releases:
            with self.subTest(tag=release["tag_name"]), \
                 patch.object(watch, "download", return_value=json.dumps(release).encode()):
                if release["tag_name"] == "v1.2.3":
                    self.assertEqual(watch.latest_stable("example/repo")["tag_name"], "v1.2.3")
                else:
                    with self.assertRaises(ValueError):
                        watch.latest_stable("example/repo")

    def test_unchanged_version_or_clean_baseline_never_downloads_an_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = root / "baseline.json"
            for ids in ([], ["CVE-2026-0001"]):
                report(baseline, ids)
                with patch.object(watch, "latest_stable", return_value={"tag_name": "v8.30.1"}), \
                     patch.object(watch, "download") as download:
                    self.assertIsNone(watch.check_candidate("gitleaks", "8.30.1", baseline, root))
                    download.assert_not_called()

    def test_candidate_needs_verified_artifact_and_a_complete_scan(self):
        import hashlib

        data = archive_bytes()
        asset = {"name": "gitleaks_8.30.2_linux_x64.tar.gz", "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
                 "browser_download_url": "https://github.com/gitleaks/gitleaks/releases/download/v8.30.2/gitleaks_8.30.2_linux_x64.tar.gz"}
        release = {"tag_name": "v8.30.2", "assets": [asset]}
        for scenario in ("partial-fix", "no-fix", "downgraded", "checksum", "source", "missing-digest", "scan-error", "empty"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                baseline = root / "baseline.json"
                report(baseline, ["CVE-2026-0001", "CVE-2026-0002"])
                candidate = dict(asset)
                if scenario == "checksum":
                    candidate["digest"] = "sha256:" + "0" * 64
                if scenario == "source":
                    candidate["browser_download_url"] = "https://example.invalid/asset"
                if scenario == "missing-digest":
                    candidate["digest"] = None

                def scan(command, **kwargs):
                    output = Path(command[command.index("--output") + 1])
                    self.assertEqual(Path(command[-1]).read_bytes(), b"\x7fELFtest-only")
                    self.assertTrue(Path(command[-1]).stat().st_mode & 0o100)
                    self.assertEqual(command[command.index("--ignorefile") + 1], "")
                    if scenario == "scan-error":
                        return subprocess.CompletedProcess([], 1)
                    if scenario == "empty":
                        output.write_text('{"Results": []}')
                    else:
                        report(output, ["CVE-2026-0002"] + (["CVE-2026-0001"] if scenario in {"no-fix", "downgraded"} else []))
                        if scenario == "downgraded":
                            data = json.loads(output.read_text())
                            data["Results"][0]["Vulnerabilities"][1]["Severity"] = "MEDIUM"
                            output.write_text(json.dumps(data))
                    return subprocess.CompletedProcess([], 0)

                with (
                    patch.object(watch, "latest_stable", return_value=dict(release, assets=[candidate])),
                    patch.object(watch, "download", return_value=data),
                    patch.object(watch.subprocess, "run", side_effect=scan),
                ):
                    if scenario in {"partial-fix", "no-fix", "downgraded"}:
                        result = watch.check_candidate("gitleaks", "8.30.1", baseline, root)
                        self.assertEqual(result["fixed_cves"], ["CVE-2026-0001"] if scenario == "partial-fix" else [])
                    else:
                        with self.assertRaises(ValueError):
                            watch.check_candidate("gitleaks", "8.30.1", baseline, root)

    def test_new_tool_release_is_scanned_even_without_active_cves(self):
        """OpenTofu et le provider sont suivis même si leur version épinglée n'a aucune CVE active."""
        import hashlib

        for component in ("tofu", "provider"):
            with self.subTest(component=component), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                baseline = root / "baseline.json"
                report(baseline, [])
                if component == "provider":
                    output = io.BytesIO()
                    with zipfile.ZipFile(output, "w") as archive:
                        archive.writestr("terraform-provider-proxmox_v1.2.4", b"\x7fELFtest-only")
                    data = output.getvalue()
                else:
                    data = archive_bytes("tofu")
                repo, template, _ = watch.TARGETS[component]
                name = template.format(version="1.2.4")
                asset = {"name": name, "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
                         "browser_download_url": f"https://github.com/{repo}/releases/download/v1.2.4/{name}"}

                def scan(command, **kwargs):
                    report(Path(command[command.index("--output") + 1]), ["CVE-2026-0001"])
                    return subprocess.CompletedProcess([], 0)

                with patch.object(watch, "latest_stable", return_value={"tag_name": "v1.2.4", "assets": [asset]}), \
                     patch.object(watch, "download", return_value=data), \
                     patch.object(watch.subprocess, "run", side_effect=scan) as scanner:
                    candidate = watch.check_candidate(component, "1.2.3", baseline, root)
                scanner.assert_called_once()
                self.assertEqual(candidate["fixed_cves"], [])
                self.assertEqual(candidate["remaining_cves"], 1)

    def test_unchanged_tool_release_is_not_downloaded_without_active_cves(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = root / "baseline.json"
            report(baseline, [])
            with patch.object(watch, "latest_stable", return_value={"tag_name": "v1.2.3"}), \
                 patch.object(watch, "download") as download:
                self.assertIsNone(watch.check_candidate("tofu", "1.2.3", baseline, root))
                download.assert_not_called()

    def test_archive_paths_and_links_cannot_escape_the_temporary_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            for name, kind in (("../../gitleaks", tarfile.REGTYPE), ("gitleaks", tarfile.SYMTYPE)):
                with self.assertRaises(ValueError):
                    watch.extract_binary(archive_bytes(name, kind), "fixture.tar.gz", "gitleaks", Path(temporary))

    def test_patch_alert_is_deduplicated_but_success_is_still_notified(self):
        candidate = {"component": "gitleaks", "current": "8.30.1", "candidate": "8.30.2",
                     "digest": "sha256:" + "0" * 64, "fixed_cves": ["CVE-2026-0001"],
                     "remaining_cves": 1, "url": "https://github.com/gitleaks/gitleaks/releases/tag/v8.30.2"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".reports").mkdir()
            (root / ".reports/patch-watch.json").write_text(json.dumps({"candidates": [candidate], "errors": []}))
            opener = MagicMock()
            opener.open.return_value.__enter__.return_value.status = 200
            with patch.object(watch, "ROOT", root), patch.object(watch.urllib.request, "build_opener", return_value=opener), \
                 patch.dict(watch.os.environ, {"DISCORD_WEBHOOK_URL": ""}), contextlib.redirect_stdout(io.StringIO()):
                watch.notify()
                opener.open.assert_not_called()
                self.assertFalse((root / ".cache/patch-watch-notifications.json").exists())
            with patch.object(watch, "ROOT", root), patch.object(watch.urllib.request, "build_opener", return_value=opener), \
                 patch.dict(watch.os.environ, {"DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123/test"}), \
                 contextlib.redirect_stdout(io.StringIO()):
                opener.open.side_effect = OSError("not printed")
                with self.assertRaises(SystemExit):
                    watch.notify()
                self.assertFalse((root / ".cache/patch-watch-notifications.json").exists())
                opener.open.side_effect = None
                opener.reset_mock()
                watch.notify()
                watch.notify()
                self.assertEqual(opener.open.call_count, 2)
                request = opener.open.call_args_list[0].args[0]
                self.assertEqual(json.loads(request.data)["allowed_mentions"], {"parse": []})
                self.assertTrue(request.full_url.endswith("?wait=true"))
                self.assertIn("Correctif officiel stable disponible", json.loads(request.data)["content"])
                confirmation = json.loads(opener.open.call_args_list[1].args[0].data)["content"]
                self.assertIn("terminée avec succès", confirmation)
                self.assertIn("correctifs déjà signalés", confirmation)
                self.assertEqual(len(json.loads((root / ".cache/patch-watch-notifications.json").read_text())), 1)

    def test_success_without_a_patch_is_notified_on_every_run(self):
        """Une veille réussie sans correctif envoie une confirmation et le lien du run, sans cache."""
        for candidates in ([], [{"component": "gitleaks", "fixed_cves": []}]):
            with self.subTest(candidates=candidates), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / ".reports").mkdir()
                (root / ".reports/patch-watch.json").write_text(json.dumps({"candidates": candidates, "errors": []}))
                opener = MagicMock()
                opener.open.return_value.__enter__.return_value.status = 200
                with patch.object(watch, "ROOT", root), \
                     patch.object(watch.urllib.request, "build_opener", return_value=opener), \
                     patch.dict(watch.os.environ, {"DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123/test",
                                                  "GITHUB_REPOSITORY": "example/repo", "GITHUB_RUN_ID": "42"}), \
                     contextlib.redirect_stdout(io.StringIO()):
                    watch.notify()
                    watch.notify()
                self.assertEqual(opener.open.call_count, 2)
                payload = json.loads(opener.open.call_args.args[0].data)
                self.assertIn("Aucune nouvelle version stable ni nouveau correctif", payload["content"])
                self.assertIn("https://github.com/example/repo/actions/runs/42", payload["content"])
                self.assertEqual(payload["allowed_mentions"], {"parse": []})
                self.assertFalse((root / ".cache/patch-watch-notifications.json").exists())

    def test_stable_release_and_later_confirmed_fix_have_distinct_notifications(self):
        """Une version est annoncée une fois ; une correction confirmée plus tard est signalée sans doublon."""
        for component in ("tofu", "provider"):
            with self.subTest(component=component), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / ".reports").mkdir()
                candidate = {"component": component, "current": "1.2.3", "candidate": "1.2.4",
                             "digest": "sha256:" + "0" * 64, "fixed_cves": [], "remaining_cves": 1,
                             "url": f"https://github.com/{watch.TARGETS[component][0]}/releases/tag/v1.2.4"}
                path = root / ".reports/patch-watch.json"
                path.write_text(json.dumps({"candidates": [candidate], "errors": []}))
                opener = MagicMock()
                opener.open.return_value.__enter__.return_value.status = 200
                with patch.object(watch, "ROOT", root), \
                     patch.object(watch.urllib.request, "build_opener", return_value=opener), \
                     patch.dict(watch.os.environ, {"DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123/test"}), \
                     contextlib.redirect_stdout(io.StringIO()):
                    watch.notify()
                    watch.notify()
                    candidate["fixed_cves"] = ["CVE-2026-0001"]
                    path.write_text(json.dumps({"candidates": [candidate], "errors": []}))
                    watch.notify()
                messages = [json.loads(call.args[0].data)["content"] for call in opener.open.call_args_list]
                self.assertEqual(len(messages), 3)
                self.assertIn("Nouvelle version stable disponible", messages[0])
                self.assertIn("Aucune correction", messages[0])
                self.assertIn("terminée avec succès", messages[1])
                self.assertIn("Correctif officiel stable disponible", messages[2])

    def test_incomplete_watch_never_sends_a_success_confirmation(self):
        """Un rapport de veille incomplet ne peut pas être présenté comme une réussite."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".reports").mkdir()
            (root / ".reports/patch-watch.json").write_text(json.dumps({
                "candidates": [], "errors": ["provider : contrôle incomplet"],
            }))
            with patch.object(watch, "ROOT", root), \
                 patch.object(watch.urllib.request, "build_opener") as opener, \
                 self.assertRaisesRegex(SystemExit, "Veille incomplète"):
                watch.notify()
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
