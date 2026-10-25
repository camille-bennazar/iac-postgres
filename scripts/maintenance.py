"""Archiver les fichiers générés et sérialiser les commandes du projet (Linux)."""

import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_COMMANDS = {
    "check", "security", "init", "prepare-image", "plan", "apply", "inventory", "configure", "deploy", "status"
}
FIXED_PATHS = {"terraform/.terraform", ".ansible", "inventory.json", ".ruff_cache"}


class MaintenanceError(Exception):
    """Erreur affichable sans contenu privé."""


def safe_path(base: Path, relative: str) -> Path:
    """Refuser les traversées et tous les composants symboliques."""
    path = Path(relative)
    if not relative or path.is_absolute() or ".." in path.parts or path == Path("."):
        raise MaintenanceError("Chemin non autorisé.")
    current = base
    if current.is_symlink():
        raise MaintenanceError("Lien symbolique non autorisé.")
    for component in path.parts:
        current = current / component
        if current.is_symlink():
            raise MaintenanceError("Lien symbolique non autorisé.")
    return current


def generated(relative: str) -> bool:
    """Liste fermée des fichiers que le nettoyage a le droit de déplacer."""
    path = Path(relative)
    if any(part in {".git", ".agents", ".codex", ".aws", "tmp"} for part in path.parts):
        return False
    return (
        relative in FIXED_PATHS
        or path.name == "__pycache__"
        or (path.parent == Path("terraform") and (
            path.name in {"terraform.tfstate", "terraform.tfstate.backup"}
            or path.suffix in {".plan", ".tfplan"}
            or re.fullmatch(r"crash(?:\..+)?\.log", path.name) is not None
        ))
        or (path.parent == Path(".") and (
            path.suffix in {".plan", ".tfplan"}
            or re.fullmatch(r"crash(?:\..+)?\.log", path.name) is not None
        ))
    )


def ensure_tree(path: Path) -> None:
    """Les archives ne doivent contenir aucun lien symbolique."""
    if path.is_symlink():
        raise MaintenanceError("Lien symbolique non autorisé.")
    if path.is_dir():
        for directory, dirs, files in os.walk(path, followlinks=False):
            for name in dirs + files:
                if (Path(directory) / name).is_symlink():
                    raise MaintenanceError("Lien symbolique dans les fichiers générés.")


def archives() -> list[tuple[Path, dict]]:
    directory = safe_path(PROJECT_ROOT, "tmp")
    if not directory.exists():
        return []
    result = []
    for archive in sorted(directory.iterdir()):
        if archive.is_symlink() or not archive.is_dir():
            raise MaintenanceError("Contenu inattendu dans ./tmp/. Nettoyage refusé.")
        ensure_tree(archive)
        manifest = json.loads((archive / "manifest.json").read_text())
        if not isinstance(manifest, dict):
            raise MaintenanceError("Manifeste d'archive invalide.")
        entries = manifest.get("paths")
        if manifest.get("version") != 1 or not isinstance(entries, list):
            raise MaintenanceError("Manifeste d'archive invalide.")
        if any(not isinstance(entry, str) or not generated(entry) for entry in entries):
            raise MaintenanceError("Chemin d'archive non autorisé.")
        if len(entries) != len(set(entries)):
            raise MaintenanceError("Chemins d'archive dupliqués.")
        for entry in entries:
            safe_path(archive / "files", entry)
            safe_path(PROJECT_ROOT, entry)
        result.append((archive, manifest))
    return result


def archived_state() -> bool:
    return any(
        (archive / "files" / entry).exists()
        for archive, manifest in archives()
        for entry in manifest["paths"]
        if Path(entry).name in {"terraform.tfstate", "terraform.tfstate.backup"}
    )


def guard(command: str) -> None:
    if command in STATE_COMMANDS and archived_state():
        raise MaintenanceError("State archivé : lancer make restore ARCHIVE=<identifiant>.")


def candidates() -> list[Path]:
    paths = []
    for directory, dirs, files in os.walk(PROJECT_ROOT, followlinks=False):
        parent = Path(directory)
        dirs[:] = [name for name in dirs if name not in {
            ".git", ".agents", ".codex", ".aws", "tmp"
        }]
        for name in list(dirs) + files:
            path = parent / name
            relative = path.relative_to(PROJECT_ROOT).as_posix()
            if generated(relative):
                safe_path(PROJECT_ROOT, relative)
                ensure_tree(path)
                paths.append(path)
                if name in dirs:
                    dirs.remove(name)
    return sorted(paths)


def clear() -> None:
    if (PROJECT_ROOT / "terraform/.terraform.tfstate.lock.info").exists():
        raise MaintenanceError("Verrou OpenTofu présent : nettoyage refusé.")
    archives()  # Vérifier les archives existantes avant tout déplacement.
    paths = candidates()
    if not paths:
        print("Aucun fichier généré à archiver.")
        return
    temporary = safe_path(PROJECT_ROOT, "tmp")
    temporary.mkdir(mode=0o700, exist_ok=True)
    temporary.chmod(0o700)
    archive = Path(tempfile.mkdtemp(prefix="archive-", dir=temporary))
    entries = [path.relative_to(PROJECT_ROOT).as_posix() for path in paths]
    manifest = archive / "manifest.json"
    # Écrit avant les déplacements : une opération interrompue reste restaurable.
    manifest.write_text(json.dumps({"version": 1, "paths": entries}, indent=2) + "\n")
    manifest.chmod(0o600)
    for source, relative in zip(paths, entries, strict=True):
        destination = archive / "files" / relative
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.replace(source, destination)
        if destination.is_file():
            destination.chmod(0o600)
    print(f"Archivés : {len(entries)} chemins dans ./tmp/{archive.name}/")
    print(f"Restaurer : make restore ARCHIVE={archive.name}")


def restore(identifier: str) -> None:
    available = archives()
    if not identifier:
        print("Archives disponibles :")
        for archive, _ in available:
            print(f"  {archive.name}")
        print("Utiliser : make restore ARCHIVE=<identifiant>")
        return
    selected = [(archive, manifest) for archive, manifest in available if archive.name == identifier]
    if not selected:
        raise MaintenanceError("Archive inconnue.")
    archive, manifest = selected[0]
    moves = []
    for entry in manifest["paths"]:
        source = safe_path(archive / "files", entry)
        destination = safe_path(PROJECT_ROOT, entry)
        if source.exists():
            if destination.exists():
                raise MaintenanceError(f"Restauration refusée : {entry} existe déjà.")
            moves.append((source, destination))
        elif not destination.exists():
            raise MaintenanceError("Archive incomplète : fichier absent aux deux emplacements.")
    for source, destination in moves:
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.replace(source, destination)
    shutil.rmtree(archive)
    print(f"Archive restaurée : {identifier} ({len(moves)} chemins).")


def clear_tmp(force: bool = False) -> None:
    if archived_state() and not force:
        raise MaintenanceError(
            "State encore archivé : restaurer avant clear-tmp. "
            "PURGE_STATE=1 force sa perte définitive de suivi."
        )
    temporary = safe_path(PROJECT_ROOT, "tmp")
    if temporary.exists():
        shutil.rmtree(temporary)
    print("Archives temporaires supprimées.")


@contextmanager
def project_lock():
    path = safe_path(PROJECT_ROOT, ".project.lock")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise MaintenanceError("Une autre commande du projet est en cours.") from None
        yield


def main() -> None:
    os.umask(0o077)
    try:
        operation = sys.argv[1]
        if operation == "run":
            command = sys.argv[2]
            with project_lock():
                guard(command)
                environment = dict(os.environ, IAC_LOCKED="1")
                result = subprocess.run(sys.argv[3:] + [command], env=environment)
                sys.exit(result.returncode)
        elif operation == "clear":
            clear()
        elif operation == "restore":
            restore(os.environ.get("ARCHIVE", ""))
        elif operation == "clear-tmp":
            clear_tmp(os.environ.get("PURGE_STATE") == "1")
        else:
            raise MaintenanceError("Commande de maintenance inconnue.")
    except MaintenanceError as error:
        sys.exit(str(error))
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        sys.exit("Maintenance impossible : vérifier les fichiers et les permissions.")


if __name__ == "__main__":
    main()
