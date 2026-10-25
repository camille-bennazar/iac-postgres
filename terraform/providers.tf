# Le token est lu depuis PROXMOX_VE_API_TOKEN, sans être écrit dans les variables.
provider "proxmox" {
  endpoint = var.proxmox_endpoint
  insecure = var.proxmox_insecure
}
