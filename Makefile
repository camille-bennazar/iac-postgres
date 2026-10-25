SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help
.NOTPARALLEL:

TOFU ?= tofu
PYTHON ?= python3
ANSIBLE_PLAYBOOK ?= ansible-playbook
export ARCHIVE PURGE_STATE

COMMANDS := setup check check-deps check-local test lint security init prepare-image plan apply \
	inventory configure deploy status clear restore clear-tmp
.PHONY: help auth $(COMMANDS)

help:
	@echo 'Préparer : setup | auth (instructions)'
	@echo 'Vérifier : check | check-deps | check-local | test | lint | security'
	@echo 'Utiliser : plan | apply | configure | deploy | status'
	@echo 'Maintenir : clear | restore ARCHIVE=<id> | clear-tmp [PURGE_STATE=1]'
	@echo 'Compléments : init | prepare-image | inventory'

auth:
	@echo 'Dans votre terminal Bash : source scripts/auth.sh'

# Le verrou couvre aussi les appels Make imbriqués et les terminaux concurrents.
ifneq ($(IAC_LOCKED),1)
$(COMMANDS):
	+@$(PYTHON) scripts/maintenance.py run $@ $(MAKE) --no-print-directory
else
setup:
	@$(PYTHON) scripts/local.py setup

check:
	@echo '[1/5] Dépendances verrouillées et versions exécutées'
	$(MAKE) check-deps
	@echo '[2/5] Format et validation OpenTofu'
	$(TOFU) -chdir=terraform fmt -check -recursive
	$(MAKE) init
	$(TOFU) -chdir=terraform validate
	@echo '[3/5] Tests OpenTofu avec provider simulé'
	@umask 077; $(TOFU) -chdir=terraform test
	@echo '[4/5] Ansible, Compose et tests locaux'
	$(MAKE) check-local
	@echo '[5/5] Analyse statique et documentation'
	$(MAKE) lint

check-deps:
	$(PYTHON) scripts/dependencies.py --tools

check-local:
	@echo '=== Syntaxe Ansible ==='
	@umask 077; $(ANSIBLE_PLAYBOOK) -i 'postgres,' --syntax-check ansible/deploy.yml
	@umask 077; $(ANSIBLE_PLAYBOOK) -i 'postgres,' --syntax-check ansible/status.yml
	@echo '=== Validation et rendu Compose ==='
	@umask 077; $(ANSIBLE_PLAYBOOK) -i localhost, ansible/check.yml
	$(MAKE) test

test:
	@umask 077; ANSIBLE_PLAYBOOK="$(ANSIBLE_PLAYBOOK)" $(PYTHON) scripts/test.py

lint:
	ruff check scripts tests
	ANSIBLE_HOME="$(CURDIR)/.ansible" ansible-lint --offline ansible
	shellcheck scripts/auth.sh
	actionlint .github/workflows/*.yml
	$(PYTHON) scripts/check_docs.py

security: check-deps init
	$(PYTHON) scripts/security.py $(SECURITY_FLAGS)

init:
	@umask 077; $(TOFU) -chdir=terraform init -input=false -lockfile=readonly

prepare-image: init
	@test -n "$${PROXMOX_VE_API_TOKEN:-}" || { echo 'Charger le token : source scripts/auth.sh' >&2; exit 1; }
	@umask 077; $(PYTHON) scripts/prepare_image.py "$(TOFU)"

plan: prepare-image
	@umask 077; $(TOFU) -chdir=terraform plan

apply: prepare-image
	@umask 077; $(TOFU) -chdir=terraform apply

inventory:
	@umask 077; $(TOFU) -chdir=terraform output -json ansible_inventory | $(PYTHON) scripts/local.py inventory

configure: inventory
	@umask 077; $(ANSIBLE_PLAYBOOK) ansible/deploy.yml

deploy:
	$(MAKE) apply
	$(MAKE) configure

status: inventory
	@umask 077; $(ANSIBLE_PLAYBOOK) ansible/status.yml

clear:
	@$(PYTHON) scripts/maintenance.py clear

restore:
	@$(PYTHON) scripts/maintenance.py restore

clear-tmp:
	@$(PYTHON) scripts/maintenance.py clear-tmp
endif
