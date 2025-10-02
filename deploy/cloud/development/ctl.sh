#!/bin/bash

# Set the userpass credentials for loading env vars
export VAULT_ADDR_1="http://127.0.0.1:8200"
export VAULT_ADDR_2="http://vault:8200"
export VAULT_INIT_FILE="/vault/config/vault.hcl"

VAULT_USERNAME="service"
VAULT_PASSWORD="concord"

# Source the bash libraries
source "$(dirname "$0")/../../../libs/bash/source.sh"

# Vault KV paths and environment files
KV_PATH="kv/config/cloud"
KV_ENV_FILE=".env"

# ---------------------------------------------
#                                         Vault
# ---------------------------------------------

function main() {
    # Try each Vault address until one works
    for addr in "$VAULT_ADDR_1" "$VAULT_ADDR_2"; do
        echo "Trying to connect to Vault at: $addr"
        if lib_login_to_vault "$addr" "$VAULT_USERNAME" "$VAULT_PASSWORD"; then
            break
        fi
        echo "Failed to connect to $addr"
    done

    lib_create_kv_entries "$KV_PATH" "$KV_ENV_FILE"
}

main