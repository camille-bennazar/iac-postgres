"""Préparer les configurations locales et générer l'inventaire Ansible."""

import ipaddress
import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def setup() -> None:
    """Copier les exemples manquants et protéger les configurations existantes."""
    for relative_path in ("terraform/terraform.tfvars", "databases.yml"):
        destination = PROJECT_ROOT / relative_path
        if destination.is_symlink() or destination.parent.is_symlink():
            raise ValueError("Lien symbolique non autorisé")
        try:
            descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            destination.chmod(0o600)
            print(f"Conservé : {relative_path}")
        else:
            example = PROJECT_ROOT / f"{relative_path}.example"
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(example.read_bytes())
            print(f"Créé : {relative_path} (à personnaliser)")


def inventory() -> None:
    """Remplacer l'inventaire uniquement après validation de la sortie OpenTofu."""
    data = json.load(sys.stdin)
    hosts = data["all"]["children"]["postgres"]["hosts"]
    if not isinstance(hosts, dict) or not hosts:
        raise ValueError("Sortie OpenTofu sans adresse de VM")
    for host in hosts.values():
        if not isinstance(host, dict) or not isinstance(host.get("ansible_host"), str):
            raise ValueError("Hôte d'inventaire invalide")
        ipaddress.IPv4Address(host["ansible_host"])
    temporary_directory = PROJECT_ROOT / ".ansible"
    if temporary_directory.is_symlink() or (PROJECT_ROOT / "inventory.json").is_symlink():
        raise ValueError("Lien symbolique non autorisé")
    temporary_directory.mkdir(mode=0o700, exist_ok=True)
    temporary_directory.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(dir=temporary_directory)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, PROJECT_ROOT / "inventory.json")
    finally:
        Path(temporary).unlink(missing_ok=True)
    print("Inventaire généré depuis les sorties OpenTofu.")


def main() -> None:
    """Exécuter l'opération locale demandée par le Makefile."""
    try:
        {"setup": setup, "inventory": inventory}[sys.argv[1]]()
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        sys.exit(
            "Opération locale impossible : vérifier la configuration "
            "et les sorties OpenTofu."
        )


if __name__ == "__main__":
    main()
