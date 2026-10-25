mock_provider "proxmox" {
  mock_resource "proxmox_download_file" {
    defaults = {
      id = "local:import/debian-13-genericcloud-amd64-20261021-2638.qcow2"
    }
  }
}

variables {
  proxmox_endpoint = "https://pve.example.net:8006/"
  node_name        = "pve"
  image_storage    = "local"
  disk_storage     = "local-lvm"
  vm_id            = 200
  ipv4_address     = "192.168.1.50/24"
  ipv4_gateway     = "192.168.1.1"
  dns_servers      = ["192.168.1.1"]
  ssh_public_key   = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA test"
}

run "valid_configuration" {
  command = plan
  assert {
    condition     = output.ansible_inventory.all.children.postgres.hosts.database_vm.ansible_host == "192.168.1.50"
    error_message = "L'inventaire doit utiliser l'IPv4 configurée sans CIDR."
  }
  assert {
    condition = (
      proxmox_download_file.debian.checksum == local.debian_image.sha512 &&
      proxmox_download_file.debian.checksum_algorithm == "sha512" &&
      proxmox_download_file.debian.url == local.debian_image.url
    )
    error_message = "Le téléchargement Debian doit vérifier l'empreinte épinglée."
  }
}

run "placeholder_ssh_key" {
  command = plan
  variables {
    ssh_public_key = "ssh-ed25519 REMPLACER_PAR_VOTRE_CLE_PUBLIQUE"
  }
  expect_failures = [var.ssh_public_key]
}

run "invalid_ssh_key_characters" {
  command = plan
  variables {
    ssh_public_key = "ssh-ed25519 AAAA_invalid"
  }
  expect_failures = [var.ssh_public_key]
}

run "ipv6_dns_rejected" {
  command = plan
  variables {
    dns_servers = ["2001:db8::1"]
  }
  expect_failures = [var.dns_servers]
}

run "empty_dns_rejected" {
  command = plan
  variables {
    dns_servers = []
  }
  expect_failures = [var.dns_servers]
}

run "public_vm_address_rejected" {
  command = plan
  variables {
    ipv4_address = "203.0.113.50/24"
  }
  expect_failures = [var.ipv4_address]
}

run "invalid_gateway_rejected" {
  command = plan
  variables {
    ipv4_gateway = "not-an-ip"
  }
  expect_failures = [var.ipv4_gateway]
}

run "placeholder_vm_address_rejected" {
  command = plan
  variables {
    ipv4_address = "REMPLACER_IPV4_VM/PREFIXE"
  }
  expect_failures = [var.ipv4_address]
}

run "placeholder_gateway_rejected" {
  command = plan
  variables {
    ipv4_gateway = "REMPLACER_PASSERELLE"
  }
  expect_failures = [var.ipv4_gateway]
}

run "placeholder_dns_rejected" {
  command = plan
  variables {
    dns_servers = ["REMPLACER_DNS"]
  }
  expect_failures = [var.dns_servers]
}

run "proxmox_ip_collision_rejected" {
  command = plan
  variables {
    proxmox_endpoint = "https://192.168.1.50:8006/"
  }
  expect_failures = [var.ipv4_address]
}

run "distinct_proxmox_ip_accepted" {
  command = plan
  variables {
    proxmox_endpoint = "https://192.168.1.151:8006/"
  }
}

run "fractional_resources_rejected" {
  command = plan
  variables {
    vm_id     = 200.5
    cpu_cores = 1.5
    memory_mb = 1024.5
    disk_gb   = 8.5
  }
  expect_failures = [var.vm_id, var.cpu_cores, var.memory_mb, var.disk_gb]
}

run "root_account_rejected" {
  command = plan
  variables {
    ssh_user = "root"
  }
  expect_failures = [var.ssh_user]
}

run "http_endpoint_rejected" {
  command = plan
  variables {
    proxmox_endpoint = "http://pve.example.net:8006/"
  }
  expect_failures = [var.proxmox_endpoint]
}
