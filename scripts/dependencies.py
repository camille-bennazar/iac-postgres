"""Contrôler les versions, empreintes et sources des dépendances du projet."""

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
PLATFORM = "linux-x64"


def read_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(value: str, algorithm: str = "sha256") -> bool:
    length = {"sha256": 64, "sha512": 128}[algorithm]
    return isinstance(value, str) and re.fullmatch(f"{algorithm}:[0-9a-f]{{{length}}}", value) is not None


def check(root: Path = ROOT) -> dict:
    config = read_toml(root / "mise.toml")
    lock = read_toml(root / "mise.lock")
    pins = json.loads((root / "dependencies.json").read_text())
    python_version = config["tools"]["python"].split(".")
    require(read_toml(root / "ruff.toml")["target-version"] == "py" + "".join(python_version[:2]),
            "La cible Python de Ruff doit correspondre au Python du projet.")
    require(config.get("tool_config", {}).get("locked") is True, "mise doit imposer le mode locked.")
    require(lock.get("lockfile_version", 0) >= 3, "Format mise.lock insuffisant.")
    require(set(lock["tools"]) == set(config["tools"]), "Outils et verrou mise désynchronisés.")
    for name, request in config["tools"].items():
        version = request["version"] if isinstance(request, dict) else request
        require(re.fullmatch(r"\d+\.\d+\.\d+", version) is not None, f"Version non exacte : {name}.")
        entries = lock["tools"][name]
        require(len(entries) == 1 and entries[0]["version"] == version, f"Verrou périmé : {name}.")
        entry = entries[0]
        require(bool(entry.get("backend")), f"Backend absent : {name}.")
        if entry["backend"].startswith("pypi:"):
            graph = entry.get("uv", {})
            path = (root / graph.get("path", "")).resolve()
            require(path.is_relative_to((root / ".mise/locks").resolve()), f"Graphe hors dépôt : {name}.")
            require(digest(graph.get("digest", "")), f"Empreinte du graphe absente : {name}.")
            require((path / "pyproject.toml").is_file(), f"Projet Python verrouillé absent : {name}.")
            project = read_toml(path / "pyproject.toml")["project"]
            graph_lock = read_toml(path / "uv.lock")
            python_range = "==" + ".".join(python_version[:2]) + ".*"
            require(project.get("requires-python") == graph_lock.get("requires-python") == python_range,
                    f"Le graphe Python doit cibler {python_range} : {name}.")
            packages = graph_lock["package"]
            for package in packages:
                if "registry" not in package["source"]:
                    require("virtual" in package["source"], f"Source Python non autorisée : {name}.")
                    continue
                require(package["source"]["registry"] in {"https://pypi.org/simple/", "https://pypi.org/simple"},
                        "Index Python non autorisé.")
                require(bool(package.get("wheels")), f"Paquet sans wheel : {package['name']}.")
                for wheel in package["wheels"]:
                    require(digest(wheel.get("hash", "")), "Wheel sans SHA-256.")
                    source = urlsplit(wheel["url"])
                    require(source.scheme == "https" and source.hostname == "files.pythonhosted.org", "Source de wheel non autorisée.")
        else:
            artifact = entry.get(f"platforms.{PLATFORM}", {})
            require(digest(artifact.get("checksum", "")), f"SHA-256 absent : {name}.")
            source = urlsplit(artifact.get("url", ""))
            require(source.scheme == "https" and source.hostname in {"github.com", "conda.anaconda.org"}, f"Source non autorisée : {name}.")
    for package in lock.get("conda-packages", {}).get(PLATFORM, {}).values():
        require(digest(package.get("checksum", "")), "Dépendance Conda sans SHA-256.")
        require(package["url"].startswith("https://conda.anaconda.org/conda-forge/"), "Source Conda non autorisée.")
    image = pins["postgres"]["image"]
    require(re.fullmatch(r"postgres:17\.\d+-alpine3\.24@sha256:[0-9a-f]{64}", image) is not None, "Image PostgreSQL non épinglée.")
    debian = pins["debian"]
    require(re.fullmatch(r"\d{8}-\d+", debian["build"]) is not None, "Image Debian non datée.")
    expected = f"https://cloud.debian.org/images/cloud/trixie/{debian['build']}/{debian['filename']}"
    require(debian["url"] == expected and debian["build"] in debian["filename"], "Source Debian incohérente.")
    require(digest("sha512:" + debian["sha512"], "sha512"), "SHA-512 Debian absent.")
    require(digest("sha256:" + pins["mise"]["sha256_linux_x64"]), "SHA-256 mise absent.")
    provider_config = (root / "terraform/versions.tf").read_text()
    provider_lock = (root / "terraform/.terraform.lock.hcl").read_text()
    provider_version = re.search(r'\bversion\s*=\s*"(\d+\.\d+\.\d+)"', provider_config)
    require(provider_version is not None, "Provider non épinglé.")
    require(f'version     = "{provider_version[1]}"' in provider_lock, "Verrou du provider périmé.")
    require(bool(re.search(r'"zh:[0-9a-f]{64}"', provider_lock)), "Empreintes du provider absentes.")
    for name in ("ci", "security"):
        workflow = (root / f".github/workflows/{name}.yml").read_text()
        require(f"version: {pins['mise']['version']}" in workflow, "Version mise CI incohérente.")
        require(f"sha256: {pins['mise']['sha256_linux_x64']}" in workflow, "Empreinte mise CI incohérente.")
        require("install_args: --locked" in workflow, "Installation CI non verrouillée.")
        require(all(re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", ref) for ref in re.findall(r"uses:\s+(\S+)", workflow)), "Action GitHub non épinglée par SHA.")
    print(f"Dépendances : {len(config['tools'])} outils verrouillés, graphes Python, images et CI vérifiés.")
    return config


def check_tools(config: dict) -> None:
    commands = {
        "opentofu": ["tofu", "--version"], "python": [sys.executable, "--version"],
        "uv": ["uv", "--version"], "conda:make": ["make", "--version"],
        "ruff": ["ruff", "--version"], "shellcheck": ["shellcheck", "--version"],
        "actionlint": ["actionlint", "--version"], "gitleaks": ["gitleaks", "version"],
        "trivy": ["trivy", "--version"], "pypi:ansible-lint": ["ansible-lint", "--version"],
    }
    for name, command in commands.items():
        request = config["tools"][name]
        version = request["version"] if isinstance(request, dict) else request
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        require(result.returncode == 0 and re.search(rf"(?<![\d.]){re.escape(version)}(?![\d.])", output) is not None,
                f"Version exécutée incorrecte : {name} (attendu {version}). Activer les outils mise ou utiliser mise exec -- make <cible>.")
    # Ansible affiche la version de ansible-core, pas celle de la distribution ansible.
    entry = read_toml(ROOT / "mise.lock")["tools"]["ansible"][0]
    graph = read_toml(ROOT / entry["uv"]["path"] / "uv.lock")
    core = next(package["version"] for package in graph["package"] if package["name"] == "ansible-core")
    result = subprocess.run(["ansible-playbook", "--version"], capture_output=True, text=True, timeout=30)
    require(result.returncode == 0 and f"[core {core}]" in result.stdout.splitlines()[0], "Version ansible-core incorrecte.")
    print("Versions des exécutables : conformes aux versions verrouillées.")


def main() -> None:
    try:
        config = check()
        if "--tools" in sys.argv[1:]:
            check_tools(config)
    except (OSError, ValueError, KeyError, TypeError, StopIteration, subprocess.TimeoutExpired) as error:
        sys.exit(f"Contrôle des dépendances impossible : {error}")


if __name__ == "__main__":
    main()
