output "ansible_inventory" {
  description = "Inventaire JSON consommé directement par Make."
  value = {
    all = {
      children = {
        postgres = {
          hosts = {
            database_vm = {
              ansible_host               = split("/", proxmox_virtual_environment_vm.postgres.initialization[0].ip_config[0].ipv4[0].address)[0]
              ansible_user               = var.ssh_user
              ansible_python_interpreter = "/usr/bin/python3"
            }
          }
        }
      }
    }
  }
}
