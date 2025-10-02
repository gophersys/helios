#!/bin/bash

# Function to login to Vault with retry logic
# Usage: lib_login_to_vault [vault_addr] [username] [password]
function lib_login_to_vault() {
    local vault_addr=${1:-"http://127.0.0.1:8200"}
    local username=${2:-"service"}
    local password=${3:-"iotea"}
    
    # Export VAULT_ADDR to ensure all vault commands use the correct address
    export VAULT_ADDR="$vault_addr"
    
    # Wait for Vault to be online and ready
    while ! wget -q --spider "$vault_addr/sys/health"; do
        echo "Waiting for Vault to come online..."
        sleep 2
    done

    echo "Vault server is online"

    # Wait for Vault to be unsealed
    IS_VAULT_SEALED=true
    while $IS_VAULT_SEALED; do
        echo "Waiting for Vault to be ready..."
        NEW_SEALED_STATUS=$(vault status -format=json 2>/dev/null | jq -r '.sealed')
        if [ "$NEW_SEALED_STATUS" = "true" ]; then
            echo "Vault is still sealed."
            sleep 2
        else
            echo "Vault is ready."
            IS_VAULT_SEALED=false
        fi
    done

    # Retry authentication a few times if it fails
    for i in {1..5}; do
        echo "Authenticating with Vault (attempt $i)..."
        VAULT_TOKEN=$(curl -s --request POST --data "{\"password\": \"$password\"}" "$vault_addr/v1/auth/userpass/login/$username" | jq -r '.auth.client_token')

        if [ -z "$VAULT_TOKEN" ] || [ "$VAULT_TOKEN" = "null" ]; then
            echo "Failed to authenticate with Vault, retrying in 5 seconds..."
            sleep 5
        else
            echo "Authenticated successfully."
            break
        fi

        # After 5 attempts, exit if authentication still fails
        if [ "$i" -eq 5 ]; then
            echo "Error: Unable to authenticate with Vault after 5 attempts."
            return 1
        fi
    done

    # Login with the retrieved token
    vault login "$VAULT_TOKEN"

    # Verify the token is valid and retry if necessary
    for i in {1..5}; do
        if ! vault token lookup > /dev/null 2>&1; then
            echo "Error authenticating: invalid token, retrying in 5 seconds..."
            sleep 5
        else
            echo "Vault token is valid."
            return 0
        fi

        if [ "$i" -eq 5 ]; then
            echo "Error: Vault token is invalid after 5 attempts."
            return 1
        fi
    done
}

# Function to create KV entries in Vault from an env file
# Usage: lib_create_kv_entries vault_path env_file
function lib_create_kv_entries() {
    local vault_path=$1
    local env_file=$2

    # Check if the .env file exists
    if [ ! -f "$env_file" ]; then
        echo "Error: $env_file not found!"
        return 1
    fi

    # Initialize an empty string to hold key-value pairs
    kv_pairs=""

    # Loop through each line in the .env file
    while IFS='=' read -r key value || [ -n "$key" ]; do
        # Skip comments and empty lines
        [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue

        # Trim leading/trailing whitespace from key and value
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)

        # Remove surrounding quotes from the value, if present
        if [[ "$value" =~ ^\".*\"$ ]]; then
            value=$(echo "$value" | sed 's/^"//' | sed 's/"$//')
        fi

        # Append each key-value pair to the kv_pairs string in the correct format
        kv_pairs="$kv_pairs $key=\"$value\""
    done < "$env_file"

    # If no valid key-value pairs were found, exit
    if [ -z "$kv_pairs" ]; then
        echo "No valid environment variables found in $env_file."
        return 1
    fi

    # Store the entire kv_pairs in Vault as a single entry
    echo "Storing all environment variables in Vault at $vault_path..."
    vault kv put "$vault_path" $kv_pairs

    # Check if the Vault command was successful
    if [ $? -ne 0 ]; then
        echo "Error: Failed to store environment variables in Vault."
        return 1
    fi

    echo "Environment variables from $env_file have been successfully stored in Vault at $vault_path."
    return 0
} 