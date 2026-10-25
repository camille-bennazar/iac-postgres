resource "proxmox_virtual_environment_vm" "postgres" {
  node_name       = var.node_name
  vm_id           = var.vm_id
  name            = var.vm_name
  description     = "PostgreSQL Docker — géré par OpenTofu et Ansible"
  started         = true
  on_boot         = true
  stop_on_destroy = true
  scsi_hardware   = "virtio-scsi-single"

  # L'image cloud ne fournit pas nécessairement qemu-guest-agent.
  agent {
    enabled = false
  }

  cpu {
    cores = var.cpu_cores
    type  = "x86-64-v2-AES"
  }

  memory {
    dedicated = var.memory_mb
  }

  disk {
    datastore_id = var.disk_storage
    interface    = "scsi0"
    import_from  = proxmox_download_file.debian.id
    size         = var.disk_gb
    iothread     = true
    discard      = "on"
  }

  network_device {
    bridge = var.bridge
    model  = "virtio"
  }

  operating_system {
    type = "l26"
  }

  serial_device {}

  initialization {
    datastore_id = var.disk_storage

    dns {
      servers = var.dns_servers
    }

    ip_config {
      ipv4 {
        address = var.ipv4_address
        gateway = var.ipv4_gateway
      }
    }

    user_account {
      username = var.ssh_user
      keys     = [trimspace(var.ssh_public_key)]
    }
  }
}
