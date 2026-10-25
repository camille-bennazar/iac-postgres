#!/usr/bin/env bash
# Charger avec : source scripts/auth.sh
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
    printf 'Utiliser : source scripts/auth.sh\n' >&2
    exit 1
fi

_iac_auth() {
    local token_id token_secret
    if ! read -r -p 'Identifiant du token [iac-postgres@pve!opentofu] : ' token_id; then
        printf '\nAuthentification annulée.\n' >&2
        return 1
    fi
    token_id=${token_id:-iac-postgres@pve!opentofu}
    if [[ ! $token_id =~ ^[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+![A-Za-z0-9_.-]+$ ]]; then
        printf 'Identifiant attendu : utilisateur@realm!nom-du-token.\n' >&2
        return 1
    fi
    if ! read -r -s -p 'Secret du token (value) : ' token_secret; then
        printf '\nAuthentification annulée.\n' >&2
        return 1
    fi
    printf '\n'
    if [[ -z $token_secret || $token_secret =~ [[:space:][:cntrl:]] ]]; then
        printf 'Secret vide ou contenant des espaces/caractères de contrôle.\n' >&2
        return 1
    fi
    export PROXMOX_VE_API_TOKEN="${token_id}=${token_secret}"
    printf 'Token chargé dans ce terminal. Retirer avec : unset PROXMOX_VE_API_TOKEN\n'
}

# Ne jamais tracer les lectures, les variables locales ou l'export du secret.
if [[ $- == *x* ]]; then
    set +x
    if _iac_auth; then
        unset -f _iac_auth
        set -x
        return 0
    else
        unset -f _iac_auth
        set -x
        return 1
    fi
else
    if _iac_auth; then
        unset -f _iac_auth
        return 0
    else
        unset -f _iac_auth
        return 1
    fi
fi
