"""Vérifier les releases officielles stables, puis notifier les corrections rescannées."""

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from security import vulnerability_report

ROOT = Path(__file__).resolve().parent.parent
TARGETS = {
    "provider": ("bpg/terraform-provider-proxmox", "terraform-provider-proxmox_{version}_linux_amd64.zip", "trivy-provider.json"),
    "tofu": ("opentofu/opentofu", "tofu_{version}_linux_amd64.tar.gz", "trivy-tool-tofu.json"),
    "gitleaks": ("gitleaks/gitleaks", "gitleaks_{version}_linux_x64.tar.gz", "trivy-tool-gitleaks.json"),
}
RELEASE_TARGETS = frozenset({"provider", "tofu"})
MAX_ARCHIVE = 256 * 1024 * 1024
MAX_BINARY = 512 * 1024 * 1024


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, *args, **kwargs):
        redirected = super().redirect_request(request, *args, **kwargs)
        if redirected is not None:
            if urllib.parse.urlsplit(redirected.full_url).scheme != "https":
                raise ValueError("Redirection non HTTPS refusée")
            redirected.remove_header("Authorization")
        return redirected


def download(url: str, limit: int = 2 * 1024 * 1024) -> bytes:
    headers = {"User-Agent": "iac-postgres-patch-watch"}
    if urllib.parse.urlsplit(url).netloc == "api.github.com" and os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.build_opener(PublicRedirect()).open(request, timeout=60) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Téléchargement trop volumineux")
    return data


def version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
    if match is None:
        raise ValueError("Version non stable")
    return tuple(map(int, match.groups()))


def latest_stable(repo: str) -> dict:
    release = json.loads(download(f"https://api.github.com/repos/{repo}/releases/latest"))
    if release["draft"] or release["prerelease"]:
        raise ValueError("Release non stable")
    version(release["tag_name"])
    return release


def extract_binary(data: bytes, archive_name: str, component: str, destination: Path) -> Path:
    pattern = r"terraform-provider-proxmox_v\d+\.\d+\.\d+(?:_x\d+)?" if component == "provider" else re.escape(component)
    if archive_name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = [m for m in archive.infolist() if re.fullmatch(pattern, m.filename) and not m.is_dir()]
            if len(members) != 1 or members[0].file_size > MAX_BINARY:
                raise ValueError("Exécutable ZIP absent ou invalide")
            content = archive.read(members[0])
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            members = [m for m in archive.getmembers() if re.fullmatch(pattern, m.name) and m.isfile()]
            if len(members) != 1 or members[0].size > MAX_BINARY:
                raise ValueError("Exécutable TAR absent ou invalide")
            with archive.extractfile(members[0]) as member:
                content = member.read(MAX_BINARY + 1)
    if len(content) > MAX_BINARY or not content.startswith(b"\x7fELF"):
        raise ValueError("Exécutable ELF absent ou invalide")
    path = destination / component
    path.write_bytes(content)  # Analyse statique uniquement ; jamais exécuté ni installé.
    path.chmod(0o700)  # Trivy identifie les ELF Go à partir du mode exécutable.
    return path


def findings(path: Path, all_severities: bool = False) -> set[str]:
    vulnerability_report(path)  # Un rapport sans paquets ne constitue pas une preuve.
    return {v["VulnerabilityID"] for result in json.loads(path.read_text())["Results"]
            for v in result.get("Vulnerabilities", []) if all_severities or v["Severity"] in {"HIGH", "CRITICAL"}}


def check_candidate(component: str, current: str, baseline: Path, reports: Path) -> dict | None:
    tracked = findings(baseline)
    if not tracked and component not in RELEASE_TARGETS:
        return None
    repo, template, _ = TARGETS[component]
    release = latest_stable(repo)
    tag = release["tag_name"]
    if version(tag) <= version(current):
        return None
    candidate = tag.removeprefix("v")
    name = template.format(version=candidate)
    asset = next(a for a in release["assets"] if a["name"] == name)
    url = asset["browser_download_url"]
    expected_url = f"https://github.com/{repo}/releases/download/{tag}/{name}"
    if url != expected_url or not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.get("digest") or ""):
        raise ValueError("Source officielle ou SHA-256 absent")
    data = download(url, MAX_ARCHIVE)
    if "sha256:" + hashlib.sha256(data).hexdigest() != asset["digest"]:
        raise ValueError("Empreinte de l'artefact incorrecte")
    report = reports / f"patch-{component}.json"
    report.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="iac-patch-") as temporary:
        binary = extract_binary(data, name, component, Path(temporary))
        result = subprocess.run([
            "trivy", "rootfs", "--scanners", "vuln", "--pkg-types", "library", "--ignorefile", "",
            "--exit-code", "0", "--format", "json", "--output", str(report), str(binary),
        ], capture_output=True, text=True, timeout=300)
        if result.returncode:
            raise ValueError("Échec du scan de la release candidate")
    remaining = findings(report, all_severities=True)
    return {"component": component, "repository": repo, "current": current, "candidate": candidate,
            "url": f"https://github.com/{repo}/releases/tag/{tag}", "digest": asset["digest"],
            "fixed_cves": sorted(tracked - remaining), "remaining_cves": len(findings(report))}


def check() -> None:
    reports = ROOT / ".reports"
    config = tomllib.loads((ROOT / "mise.toml").read_text())
    provider = re.search(r'\bversion\s*=\s*"(\d+\.\d+\.\d+)"', (ROOT / "terraform/.terraform.lock.hcl").read_text())[1]
    versions = {"provider": provider, "tofu": config["tools"]["opentofu"], "gitleaks": config["tools"]["gitleaks"]}
    candidates, errors = [], []
    for component, (_, _, name) in TARGETS.items():
        try:
            candidate = check_candidate(component, versions[component], reports / name, reports)
            if candidate:
                candidates.append(candidate)
        except (OSError, ValueError, KeyError, TypeError, StopIteration, subprocess.SubprocessError,
                tarfile.TarError, zipfile.BadZipFile) as error:
            # Ne pas imprimer les URL signées ni les jetons éventuellement contenus dans une exception.
            errors.append(f"{component} : contrôle incomplet ({type(error).__name__})")
    (reports / "patch-watch.json").write_text(json.dumps({"candidates": candidates, "errors": errors}, indent=2) + "\n")
    lines = ["### Versions et correctifs officiels stables", "",
             "Les nouvelles versions ont été vérifiées et rescannées. Seules les CVE indiquées ne sont plus détectées ; mise à jour manuelle requise.", ""]
    lines.extend(f"- [{c['component']} {c['candidate']}]({c['url']}) : {', '.join(c['fixed_cves']) or 'aucune CVE suivie résolue'}."
                 for c in candidates)
    if not candidates:
        lines.append("Aucune nouvelle version stable ou correction de CVE à signaler dans le périmètre de la veille.")
    lines.extend(errors)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as summary:
            summary.write("\n".join(lines) + "\n")
    if errors:
        sys.exit("Veille incomplète ; consulter patch-watch.json.")
    print("Veille terminée ; aucune dépendance installée ou modifiée.")


def send_discord(content: str, webhook: str) -> None:
    if not re.fullmatch(r"https://discord\.com/api(?:/v\d+)?/webhooks/\d+/[A-Za-z0-9_-]+", webhook):
        sys.exit("Secret Discord invalide ; URL non affichée.")
    repository, run_id = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_RUN_ID")
    if repository and run_id:
        content += f"\nExécution : https://github.com/{repository}/actions/runs/{run_id}"
    payload = json.dumps({"content": content[:1900], "allowed_mentions": {"parse": []}}).encode()
    request = urllib.request.Request(webhook + "?wait=true", data=payload,
                                     headers={"Content-Type": "application/json", "User-Agent": "iac-postgres-patch-watch"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
            if response.status != 200:
                raise ValueError("Réponse Discord inattendue")
    except (OSError, ValueError):
        sys.exit("Échec de notification Discord ; URL non affichée, nouvel essai au prochain lancement.")


def notify() -> None:
    report = json.loads((ROOT / ".reports/patch-watch.json").read_text())
    if report["errors"]:
        sys.exit("Veille incomplète : aucune notification de réussite envoyée.")
    candidates = report["candidates"]
    state_path = ROOT / ".cache/patch-watch-notifications.json"
    sent = json.loads(state_path.read_text()) if state_path.exists() else []
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook:
        print("::warning::Secret DISCORD_WEBHOOK_URL absent ; résultat de veille non envoyé.")
        return
    notifications = 0
    for candidate in candidates:
        if not candidate["fixed_cves"] and candidate["component"] not in RELEASE_TARGETS:
            continue
        identity = {name: candidate[name] for name in ("component", "current", "candidate", "digest", "fixed_cves")}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        if key in sent:
            continue
        if candidate["fixed_cves"]:
            content = (f"Correctif officiel stable disponible : {candidate['component']} {candidate['candidate']} "
                       f"(version épinglée : {candidate['current']}).\n"
                       f"CVE suivies non détectées après scan : {', '.join(candidate['fixed_cves'])}.")
        else:
            content = (f"Nouvelle version stable disponible : {candidate['component']} {candidate['candidate']} "
                       f"(version épinglée : {candidate['current']}).\n"
                       "Aucune correction des CVE suivies n'est confirmée par ce scan.")
        content += (f"\nCVE HIGH/CRITICAL encore détectées : {candidate['remaining_cves']}.\n"
                    f"{candidate['url']}\nMise à jour manuelle et validation nécessaires.")
        send_discord(content, webhook)
        sent.append(key)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(sent[-512:]) + "\n")
        notifications += 1
        print(f"Notification envoyée : {candidate['component']} {candidate['candidate']}.")
    if not notifications:
        content = "Veille iac-postgres terminée avec succès.\nAucune nouvelle version stable ni nouveau correctif à notifier dans le périmètre de la veille."
        if any(candidate["fixed_cves"] or candidate["component"] in RELEASE_TARGETS for candidate in candidates):
            content += "\nLes versions et correctifs déjà signalés restent à examiner et à appliquer manuellement."
        content += "\nLes vulnérabilités connues ne sont pas pour autant corrigées."
        send_discord(content, webhook)
        print("Confirmation de veille envoyée : aucune nouveauté à notifier.")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "notify"))
    command = parser.parse_args().command
    check() if command == "check" else notify()
