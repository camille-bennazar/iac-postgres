# Accès Proxmox

variable "proxmox_endpoint" {
  type        = string
  description = "URL HTTPS de l'API Proxmox, par exemple https://pve.example.net:8006/."

  validation {
    condition     = startswith(var.proxmox_endpoint, "https://")
    error_message = "L'API Proxmox doit utiliser HTTPS."
  }
}

variable "proxmox_insecure" {
  type        = bool
  default     = false
  description = "Désactive explicitement la vérification du certificat Proxmox."
}

variable "node_name" {
  type        = string
  description = "Nom du nœud Proxmox hébergeant la VM et l’image Debian."
}

# Stockages

variable "image_storage" {
  type        = string
  description = "Stockage autorisant le contenu import."
}

variable "disk_storage" {
  type        = string
  description = "Stockage des disques VM et cloud-init."
}

# Identité et ressources de la VM

variable "vm_id" {
  type        = number
  description = "Identifiant de la VM dans Proxmox."

  validation {
    condition     = var.vm_id >= 100 && var.vm_id <= 999999999 && floor(var.vm_id) == var.vm_id
    error_message = "L'ID VM doit être un entier entre 100 et 999999999."
  }
}

variable "vm_name" {
  type        = string
  description = "Nom de la VM dans Proxmox."
  default     = "iac-postgres"
}

variable "cpu_cores" {
  type        = number
  description = "Nombre de cœurs CPU alloués à la VM."
  default     = 2

  validation {
    condition     = var.cpu_cores >= 1 && floor(var.cpu_cores) == var.cpu_cores
    error_message = "Le nombre de CPU doit être un entier positif."
  }
}

variable "memory_mb" {
  type        = number
  description = "Mémoire allouée à la VM, en Mio."
  default     = 4096

  validation {
    condition     = var.memory_mb >= 1024 && floor(var.memory_mb) == var.memory_mb
    error_message = "Prévoir au moins 1024 Mio de RAM."
  }
}

variable "disk_gb" {
  type        = number
  description = "Taille du disque de la VM, en Gio."
  default     = 40

  validation {
    condition     = var.disk_gb >= 8 && floor(var.disk_gb) == var.disk_gb
    error_message = "Prévoir un disque d'au moins 8 Gio."
  }
}

# Réseau

variable "bridge" {
  type        = string
  description = "Bridge Proxmox auquel connecter la VM."
  default     = "vmbr0"
}

variable "ipv4_address" {
  type        = string
  description = "Adresse IPv4 privée fixe avec préfixe CIDR."

  validation {
    condition = can(cidrnetmask(var.ipv4_address)) && can(regex(
      "^(10\\.|192\\.168\\.|172\\.(1[6-9]|2[0-9]|3[01])\\.)", var.ipv4_address
    ))
    error_message = "Utiliser une IPv4 privée RFC1918 au format CIDR."
  }

  validation {
    condition = split("/", var.ipv4_address)[0] != try(
      regex("^https://([^/:]+)", var.proxmox_endpoint)[0], ""
    )
    error_message = "L'IPv4 de la VM doit être différente de l'IPv4 de l'hôte Proxmox."
  }
}

variable "ipv4_gateway" {
  type        = string
  description = "Adresse IPv4 de la passerelle de la VM."

  validation {
    condition     = can(cidrnetmask("${var.ipv4_gateway}/32"))
    error_message = "La passerelle doit être une adresse IPv4."
  }
}

variable "dns_servers" {
  type        = list(string)
  description = "Adresses IPv4 des serveurs DNS de la VM."

  validation {
    condition     = length(var.dns_servers) > 0 && alltrue([for ip in var.dns_servers : can(cidrnetmask("${ip}/32"))])
    error_message = "Fournir au moins une adresse de serveur DNS."
  }
}

# Accès SSH

variable "ssh_user" {
  type        = string
  description = "Compte cloud-init non root utilisé par Ansible pour accéder à la VM."
  default     = "debian"

  validation {
    condition     = can(regex("^[a-z_][a-z0-9_-]{0,31}$", var.ssh_user)) && var.ssh_user != "root"
    error_message = "Utiliser un nom de compte Linux non root."
  }
}

variable "ssh_public_key" {
  type        = string
  description = "Contenu de la clé publique OpenSSH ; clé privée via ssh-agent ou ANSIBLE_PRIVATE_KEY_FILE."

  validation {
    condition     = can(regex("^(ssh-ed25519|ssh-rsa|ecdsa-sha2-[^ ]+) [A-Za-z0-9+/]+={0,2}( [^\\r\\n]*)?$", trimspace(var.ssh_public_key)))
    error_message = "Fournir une clé publique OpenSSH."
  }
}
