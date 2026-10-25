"""Réutiliser une image présente sur Proxmox, sinon laisser OpenTofu la télécharger."""

import json
import os
import ssl
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

TERRAFORM_DIR = Path(__file__).resolve().parent.parent / "terraform"
RESOURCE = "proxmox_download_file.debian"


class ImageError(Exception):
    """Erreur de préparation dont le message peut être affiché sans secret."""


class NoRedirect(HTTPRedirectHandler):
    """Empêcher la transmission du token vers une URL de redirection."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Ne jamais transmettre le token Proxmox à une autre URL.
        raise ImageError("Redirection HTTP inattendue ; vérifier l'URL configurée.")


def run_tofu(
    tofu: str,
    *arguments: str,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """Exécuter OpenTofu dans son dossier sans exposer ses sorties en cas d'erreur."""
    result = subprocess.run(
        [tofu, *arguments],
        cwd=TERRAFORM_DIR,
        input=input_text,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode:
        raise ImageError(
            f"Commande OpenTofu {arguments[0]} impossible (code {result.returncode}) ; "
            "vérifier init et la configuration."
        )
    return result.stdout


def configuration(tofu: str) -> dict:
    """Lire les paramètres effectifs de l'image et de l'accès Proxmox."""
    # Lire les valeurs réellement résolues par OpenTofu, sans parser ni modifier
    # terraform.tfvars, et sans placer le token dans la configuration ou les logs.
    expression = '''jsonencode({
      endpoint = var.proxmox_endpoint
      insecure = var.proxmox_insecure
      node = var.node_name
      storage = var.image_storage
      image = local.debian_image
    })'''
    output = run_tofu(tofu, "console", "-no-color", input_text=expression)
    # La console renvoie une chaîne JSON contenant l'objet encodé par jsonencode.
    return json.loads(json.loads(output))


def fetch(
    url: str,
    *,
    token: str | None = None,
    insecure: bool = False,
) -> tuple[dict, bytes]:
    """Lire une réponse HTTPS sans redirection ni affichage de son contenu."""
    if urlsplit(url).scheme != "https":
        raise ImageError("Les téléchargements et l'API doivent utiliser HTTPS.")
    context = ssl.create_default_context()
    if insecure:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    headers = {"Authorization": f"PVEAPIToken={token}"} if token else {}
    request = Request(url, headers=headers)
    opener = build_opener(NoRedirect(), HTTPSHandler(context=context))
    try:
        with opener.open(request, timeout=60) as response:
            return dict(response.headers), response.read()
    except HTTPError as error:
        raise ImageError(
            f"Requête HTTPS refusée (HTTP {error.code}) ; "
            "vérifier les permissions ou l'URL."
        ) from None
    except (URLError, TimeoutError, OSError):
        raise ImageError("Connexion HTTPS impossible ; vérifier le réseau et les certificats.") from None


def managed_resources(tofu: str) -> set[str]:
    """Lister les adresses suivies si un state local existe."""
    if not (TERRAFORM_DIR / "terraform.tfstate").is_file():
        return set()
    return set(run_tofu(tofu, "state", "list").splitlines())


def prepare(tofu: str) -> None:
    """Adopter l'image existante ou laisser le provider effectuer le téléchargement."""
    config = configuration(tofu)
    token = os.environ.get("PROXMOX_VE_API_TOKEN")
    if not token:
        raise ImageError("Définir PROXMOX_VE_API_TOKEN.")
    api_path = "/api2/json/nodes/{}/storage/{}/content?content=import".format(
        quote(config["node"], safe=""),
        quote(config["storage"], safe=""),
    )
    api_url = config["endpoint"].rstrip("/") + api_path
    _, payload = fetch(
        api_url,
        token=token,
        insecure=config["insecure"],
    )
    try:
        response = json.loads(payload)
        files = response["data"]
        if not isinstance(files, list) or any(not isinstance(entry, dict) for entry in files):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ImageError("Réponse de stockage Proxmox invalide ; aucun import effectué.") from None
    volume = f'{config["storage"]}:import/{config["image"]["filename"]}'
    if not any(entry.get("volid") == volume for entry in files):
        print("Image absente : OpenTofu effectuera le téléchargement via l'API.")
        return

    managed = managed_resources(tofu)
    if RESOURCE in managed:
        print("Image déjà suivie dans le state ; réutilisation.")
        return
    raise ImageError(
        "Image déjà présente mais non suivie : adoption automatique refusée. "
        "Vérifier son empreinte SHA-512 et son origine avant un import manuel, "
        "ou choisir un stockage sans conflit."
    )


def main() -> None:
    """Préparer l'image avec le binaire OpenTofu fourni, ou tofu par défaut."""
    try:
        prepare(sys.argv[1] if len(sys.argv) > 1 else "tofu")
    except (ImageError, ValueError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        # Aucun corps HTTP, contenu de fichier, argument privé ou token n'est affiché.
        if isinstance(error, ImageError):
            message = str(error)
        else:
            message = "Vérification de l'image impossible ; réponse ou configuration invalide."
        sys.exit(message)


if __name__ == "__main__":
    main()
