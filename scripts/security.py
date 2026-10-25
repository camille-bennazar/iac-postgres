"""Lancer tous les scanners et conserver des rapports sans secrets affichés."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# L'analyse des symboles porte sur ce contenu immuable, pas sur toute image gosu.
GOSU_AUDITED_IMAGE = "postgres:17.11-alpine3.24@sha256:eee6c6e1b0894fa4fe0075eb054af9fd1cf39a35321c2d4110626cfe506411fb"
# Empreintes des exécutables Linux amd64 examinés, après extraction des archives.
# Une mise à jour réactive les alertes jusqu'à la prochaine analyse documentée.
AUDITED_TOOL_BINARIES = {
    "actionlint": "c872d6db8c6bf83a8eaa704fc93999f027d55dffbc63b8a6abdccb47df5f4cd4",
    "gitleaks": "88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509",
    "tofu": "949061cbb3c3d4558928ca9a459a5052b8c5e5545d17656f33316d2e3bc335f2",
}


def accepted_risks(report: str, target: Path, policy: dict) -> list[dict]:
    entries = policy.get("reports", {}).get(report, [])
    if not entries:
        return []
    if target.is_dir():
        binaries = list(target.glob("terraform-provider-proxmox_v*"))
        if len(binaries) != 1:
            return []
        target = binaries[0]
    if target.is_file():
        with target.open("rb") as binary:
            actual = hashlib.file_digest(binary, "sha256").hexdigest()
        if actual == policy["artifacts"].get(report):
            return entries
    return []


def ignorefile(scan: str, image: str, executable: Path | None = None) -> str:
    if scan == "image" and image == GOSU_AUDITED_IMAGE:
        return ".trivyignore.yaml"
    if scan == "rootfs" and executable is not None:
        expected = AUDITED_TOOL_BINARIES.get(executable.name)
        if expected and executable.is_file():
            with executable.open("rb") as binary:
                if hashlib.file_digest(binary, "sha256").hexdigest() == expected:
                    return ".trivyignore.yaml"
    return ""


def vulnerability_report(path: Path, accepted: list[dict] = ()) -> dict:
    results = json.loads(path.read_text()).get("Results", [])
    packages = sum(len(entry.get("Packages", [])) for entry in results)
    if not packages:
        raise ValueError("Aucun paquet analysé")
    issues = [issue for entry in results for issue in entry.get("Vulnerabilities", [])]
    accepted_keys = {(entry["id"], entry["package"], entry["version"]) for entry in accepted}
    relevant = [issue for issue in issues if issue["Severity"] in {"HIGH", "CRITICAL"}]
    allowed = sum((issue["VulnerabilityID"], issue["PkgName"], issue["InstalledVersion"]) in accepted_keys
                  for issue in relevant) if accepted_keys else 0
    return {
        "report": path.name,
        "packages": packages,
        "high": sum(issue["Severity"] == "HIGH" for issue in issues),
        "critical": sum(issue["Severity"] == "CRITICAL" for issue in issues),
        "suppressed": sum(len(entry.get("ExperimentalModifiedFindings", [])) for entry in results),
        "accepted": allowed,
        "blocking": len(relevant) - allowed,
    }


def main(allow_known: bool = False) -> None:
    os.umask(0o077)
    reports = ROOT / ".reports"
    if reports.is_symlink():
        sys.exit("Le dossier de rapports ne doit pas être un lien symbolique.")
    reports.mkdir(mode=0o700, exist_ok=True)
    if any(path.is_symlink() for path in reports.iterdir()):
        sys.exit("Les rapports ne doivent pas être des liens symboliques.")
    try:
        image = json.loads((ROOT / "dependencies.json").read_text())["postgres"]["image"]
        provider_lock = (ROOT / "terraform/.terraform.lock.hcl").read_text()
        provider_version = re.search(r'\bversion\s*=\s*"(\d+\.\d+\.\d+)"', provider_lock)[1]
        accepted = json.loads((ROOT / ".github/security-accepted.json").read_text()) if allow_known else {}
    except (OSError, ValueError, KeyError, TypeError):
        sys.exit("Référence PostgreSQL ou verrou du provider absent ou invalide.")
    commands = [
        ["gitleaks", "dir", ".", "--redact", "--report-format", "json",
         "--report-path", ".reports/gitleaks-files.json"],
        ["trivy", "config", "--severity", "HIGH,CRITICAL", "--exit-code", "1",
         "--format", "json", "--output", ".reports/trivy.json",
         "--skip-dirs", "tmp,.reports,.git,terraform/.terraform,.ansible", "."],
        ["trivy", "fs", "--scanners", "vuln", "--pkg-types", "library",
         "--severity", "HIGH,CRITICAL", "--exit-code", "1", "--format", "json",
         "--output", ".reports/trivy-python.json", ".mise/locks"],
        ["trivy", "rootfs", "--scanners", "vuln", "--pkg-types", "library",
         "--severity", "HIGH,CRITICAL", "--exit-code", "1", "--format", "json",
         "--output", ".reports/trivy-provider.json",
         f"terraform/.terraform/providers/registry.opentofu.org/bpg/proxmox/{provider_version}/linux_amd64"],
        ["trivy", "image", "--image-src", "remote", "--platform", "linux/amd64",
         "--scanners", "vuln", "--severity", "HIGH,CRITICAL", "--exit-code", "1",
         "--format", "json", "--output", ".reports/trivy-postgres.json", image],
    ]
    missing_tools = []
    for tool in ("tofu", "actionlint", "gitleaks", "trivy"):
        executable = shutil.which(tool)
        if executable:
            commands.append([
                "trivy", "rootfs", "--scanners", "vuln", "--pkg-types", "library",
                "--severity", "HIGH,CRITICAL", "--exit-code", "1", "--format", "json",
                "--output", f".reports/trivy-tool-{tool}.json", str(Path(executable).resolve()),
            ])
        else:
            missing_tools.append(tool)
    repository = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT, capture_output=True,
    )
    if repository.returncode == 0:
        commands.insert(1, ["gitleaks", "git", ".", "--pre-commit", "--staged", "--redact",
                            "--config", ".github/gitleaks-history.toml",
                            "--report-format", "json", "--report-path", ".reports/gitleaks-staged.json"])
    history = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"], cwd=ROOT, capture_output=True,
    )
    if history.returncode == 0:
        commands.insert(1, ["gitleaks", "git", ".", "--redact", "--log-opts=--all",
                            "--config", ".github/gitleaks-history.toml",
                            "--report-format", "json", "--report-path", ".reports/gitleaks-history.json"])
    else:
        print("Historique Git indisponible : scan des fichiers uniquement.", flush=True)
    for tool in missing_tools:
        print(f"Binaire à analyser absent : {tool} (installer les outils mise).", flush=True)
    failed = bool(missing_tools)
    summaries = []
    for command in commands:
        if command[0] == "trivy" and command[1] in {"fs", "rootfs", "image"}:
            command[2:2] = ["--ignorefile", ignorefile(command[1], image, Path(command[-1])), "--show-suppressed"]
        if not shutil.which(command[0]):
            print(f"Manquant : {command[0]} (installer les outils mise).", flush=True)
            failed = True
            continue
        report_option = "--output" if command[0] == "trivy" else "--report-path"
        if report_option in command:
            (ROOT / command[command.index(report_option) + 1]).unlink(missing_ok=True)
        print(f"=== {' '.join(command[:2])} ===", flush=True)
        result = subprocess.run(command, cwd=ROOT)
        scan_failed = result.returncode != 0
        if command[0] == "trivy" and command[1] in {"fs", "rootfs", "image"} and result.returncode in {0, 1}:
            report = ROOT / command[command.index("--output") + 1]
            try:
                entries = accepted_risks(report.name, ROOT / command[-1], accepted) if allow_known else []
                summary = vulnerability_report(report, entries)
                summaries.append(summary)
                if summary["accepted"] and not summary["blocking"]:
                    scan_failed = False
                else:
                    scan_failed |= bool(summary["blocking"])
                print(
                    f"Paquets : {summary['packages']} ; HIGH : {summary['high']} ; "
                    f"CRITICAL : {summary['critical']} ; non applicables : {summary['suppressed']} ; "
                    f"risques acceptés : {summary['accepted']} ; bloquantes : {summary['blocking']}", flush=True,
                )
                if summary["accepted"]:
                    print(f"::warning::{report.name} : {summary['accepted']} vulnérabilités connues acceptées ; voir docs/securite.md.", flush=True)
            except (OSError, ValueError, TypeError, KeyError):
                print("ÉCHEC : rapport absent ou aucun paquet analysé ; contrôle non validé.", flush=True)
                scan_failed = True
        failed |= scan_failed
        print(f"Résultat : {'ÉCHEC' if scan_failed else 'OK'}", flush=True)
    (reports / "dependencies-summary.json").write_text(json.dumps({"failed": failed, "scans": summaries}, indent=2) + "\n")
    lines = ["### Sécurité", "", "Les risques acceptés restent présents dans les rapports.", "",
             "| Rapport | HIGH | CRITICAL | Non applicables | Acceptées | Bloquantes |",
             "| --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {s['report']} | {s['high']} | {s['critical']} | {s['suppressed']} | {s['accepted']} | {s['blocking']} |"
                 for s in summaries)
    lines.extend(["", f"Contrôle : {'ÉCHEC' if failed else 'réussi avec les risques connus ci-dessus' if any(s['accepted'] for s in summaries) else 'réussi'}.\n"])
    (reports / "security-summary.md").write_text("\n".join(lines))
    print("Rapports : .reports/ (ignoré par Git).", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-known", action="store_true", help="Tolérer uniquement les risques documentés de .github/security-accepted.json")
    main(parser.parse_args().allow_known)
