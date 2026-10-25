locals {
  debian_image = jsondecode(file("${path.module}/../dependencies.json")).debian
}

resource "proxmox_download_file" "debian" {
  node_name          = var.node_name
  datastore_id       = var.image_storage
  content_type       = "import"
  file_name          = local.debian_image.filename
  url                = local.debian_image.url
  overwrite          = false
  verify             = true
  checksum           = local.debian_image.sha512
  checksum_algorithm = "sha512"

  lifecycle {
    # L'import ne peut pas retrouver l'URL d'origine. Conserver le fichier
    # existant sans forcer son remplacement après import.
    ignore_changes = [url]
  }
}
