#!/bin/bash

# Exit on error
set -e

# Source the bash libraries
source "$(dirname "$0")/../../../libs/bash/source.sh"

# Handle environment validation and safety checks
if ! lib_handle_environment "$@"; then
    exit 1
fi

# -----------------------------------------------------------------------------------
#                                                                Global Configuration
# -----------------------------------------------------------------------------------
# List of namespaces we need for our deployment (default already exists)
NAMESPACES=("cloud" "manufacturing" "validation" "data")

# Namespace Configuration
CLOUD_NAMESPACE=cloud

# Timeout Configuration
DEPLOY_TIMEOUT="360s"
TEARDOWN_TIMEOUT="180s"

# File Paths
VAULT_VALUES_FILE_PATH="values/vault.yaml"
PLATFORM_OBSERVABILITY_VALUES_FILE_PATH="values/platform-obsv.yaml"
CHANNEL_OBSV_VALUES_FILE_PATH="values/channel-obsv-otel-collector-config.yaml"
BACKEND_VALUES_FILE_PATH="values/eks.yaml"

# -----------------------------------------------------------------------------------
#                                                                          Namespaces
# ---------------------------------------------------------------------------------*/
function create_namespaces() {
    for NAMESPACE in "${NAMESPACES[@]}"; do
        if kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
            echo "Namespace $NAMESPACE already exists."
        else
            echo "Creating namespace $NAMESPACE."
            kubectl create namespace "$NAMESPACE"
        fi
    done
}

function delete_namespaces() {
    for NAMESPACE in "${NAMESPACES[@]}"; do
        if kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
            echo "Deleting namespace $NAMESPACE..."
            kubectl delete namespace "$NAMESPACE"
        else
            echo "Namespace $NAMESPACE does not exist."
        fi
    done
}

# -----------------------------------------------------------------------------------
#                                                                             Secrets
# ---------------------------------------------------------------------------------*/
function apply_secrets() {
    echo "Applying secrets..."
}

function delete_secrets() {
    echo "Deleting secrets..."
}

# -----------------------------------------------------------------------------------
#                                                                               Vault
# --- -----------------------------------------------------------------------------*/
# Configuration
VAULT_DEPLOY_TIMEOUT=360s
VAULT_TEARDOWN_TIMEOUT=180s
VAULT_RELEASE_NAME="vault"
VAULT_VALUES_FILE_PATH="values/vault.yaml"
VAULT_ADDR="http://vault.cloud.svc.cluster.local:8200"
VAULT_ROOT_TOKEN=""
VAULT_LEADER_POD_NAME="vault-0"

# Vault KV paths and environment files
CLOUD_VAULT_KV_PATH="kv/config/cloud"
CLOUD_ENV_FILE=".env.cloud"
VALIDATION_VAULT_KV_PATH="kv/config/validation"
VALIDATION_ENV_FILE=".env.validation"
MANUFACTURING_VAULT_KV_PATH="kv/config/manufacturing"
MANUFACTURING_ENV_FILE=".env.manufacturing"

function __setup_policies() {
    cat <<EOF | kubectl exec -i $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault policy write cloud -
path "kv/config/cloud" {
  capabilities = ["read", "list"]
}
EOF

    cat <<EOF | kubectl exec -i $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault policy write manufacturing -
path "kv/config/manufacturing" {
  capabilities = ["read", "list"]
}
EOF

    cat <<EOF | kubectl exec -i $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault policy write validation -
path "kv/config/validation" {
  capabilities = ["read", "list"]
}
EOF
}

function __setup_approle() {
    # Cloud
    kubectl exec $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault write auth/approle/role/cloud token_policies="cloud" \
        secret_id_ttl=10m \
        token_ttl=20m \
        token_max_ttl=30m \
        secret_id_num_uses=10

    # Manufacturing
    kubectl exec $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault write auth/approle/role/manufacturing token_policies="manufacturing" \
        secret_id_ttl=10m \
        token_ttl=20m \
        token_max_ttl=30m \
        secret_id_num_uses=10

    # Validation
    kubectl exec $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault write auth/approle/role/validation token_policies="validation" \
        secret_id_ttl=10m \
        token_ttl=20m \
        token_max_ttl=30m \
        secret_id_num_uses=10
}

function __setup_k8s_auth() {
    # Get the Kubernetes API host from inside the Vault container
    KUBERNETES_API_HOST=$(kubectl exec $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- sh -c 'echo $KUBERNETES_PORT_443_TCP_ADDR')
    
    if [[ -z "$KUBERNETES_API_HOST" ]]; then
        echo "Error: Could not retrieve Kubernetes API host from inside the Vault container."
        exit 1
    fi
    
    echo "Kubernetes API host is: https://$KUBERNETES_API_HOST:443"

    # Configure the Kubernetes authentication method in Vault
    kubectl exec $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault write auth/kubernetes/config \
        kubernetes_host="https://$KUBERNETES_API_HOST:443"

    # Create an auth role for the Cloud namespace
    kubectl exec $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault write auth/kubernetes/role/cloud \
        bound_service_account_names=cloud \
        bound_service_account_namespaces=cloud \
        policies=cloud \
        ttl=10m
    
    # Create an auth role for the Manufacturing namespace
    kubectl exec $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault write auth/kubernetes/role/manufacturing \
        bound_service_account_names=manufacturing \
        bound_service_account_namespaces=manufacturing \
        policies=manufacturing \
        ttl=10m

    # Create an auth role for the Validation namespace
    kubectl exec $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault write auth/kubernetes/role/validation \
        bound_service_account_names=validation \
        bound_service_account_namespaces=validation \
        policies=validation \
        ttl=10m

    # Setup a service account for the Cloud namespace
    if kubectl get serviceaccount cloud --namespace cloud >/dev/null 2>&1; then
        echo "Service account 'cloud' already exists in cloud namespace."
    else
        echo "Creating service account 'cloud' in cloud namespace..."
        kubectl create serviceaccount cloud --namespace cloud
    fi

    # Setup a service account for the Manufacturing namespace
    if kubectl get serviceaccount manufacturing --namespace manufacturing >/dev/null 2>&1; then
        echo "Service account 'manufacturing' already exists in manufacturing namespace."
    else
        echo "Creating service account 'manufacturing' in manufacturing namespace..."
        kubectl create serviceaccount manufacturing --namespace manufacturing
    fi

    # Setup a service account for the Validation namespace
    if kubectl get serviceaccount validation --namespace validation >/dev/null 2>&1; then
        echo "Service account 'validation' already exists in validation namespace."
    else
        echo "Creating service account 'validation' in validation namespace..."
        kubectl create serviceaccount validation --namespace validation
    fi
}

function _setup_vault() {
    echo "Setting up roles"

    # Use the global root token here
    if [[ -z "$VAULT_ROOT_TOKEN" ]]; then
        echo "Error: VAULT_ROOT_TOKEN is not set."
        exit 1
    fi

    # Login using the root token
    kubectl exec --stdin=true --tty=true $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault login "$VAULT_ROOT_TOKEN"
    echo "Successfully logged into Vault using the root token."

    # Enable secrets engine (KV v2 to match Python client expectations)
    kubectl exec $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault secrets enable -version=2 -path=kv kv
    
    # Enable app role
    kubectl exec $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault auth enable approle

    # Enable Kubernetes auth
    kubectl exec $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault auth enable kubernetes

    # Enable PKI secrets engine
    kubectl exec $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault secrets enable pki

    __setup_policies
    __setup_approle
    __setup_k8s_auth
}   

function _create_kv_entries() {
    local vault_path=$1
    local env_file=$2

    # Check if the .env file exists
    if [ ! -f "$env_file" ]; then
        echo "Error: $env_file not found!"
        exit 1
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
        exit 1
    fi

    # Store the entire kv_pairs in Vault as a single entry
    echo "Storing all environment variables in Vault at $vault_path..."
    kubectl exec -ti $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault kv put "$vault_path" $kv_pairs

    # Check if the Vault command was successful
    if [ $? -ne 0 ]; then
        echo "Error: Failed to store environment variables in Vault."
        exit 1
    fi

    echo "Environment variables from $env_file have been successfully stored in Vault at $vault_path."
}

function _init_and_unseal_vault() {
    echo "Initializing and unsealing Vault..."

    # Define the temporary file path in /tmp
    TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
    DEPLOY_DIR="./deployments"
    DEPLOY_FILE="$DEPLOY_DIR/deploy-$TIMESTAMP.json"
    TMP_FILE="/tmp/init-output.json"
    VAULT_1_POD_NAME="vault-1"
    VAULT_2_POD_NAME="vault-2"

    # Initialize Vault and capture both stdout and stderr
    if ! kubectl exec --stdin=true --tty=true $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault operator init -format=json > "$TMP_FILE" 2> /tmp/kubectl_error.log; then
        echo "Error: Failed to initialize Vault."
        cat /tmp/kubectl_error.log
        rm -f "$TMP_FILE"
        exit 1
    fi

    # Check if initialization was successful by ensuring the file exists and has content
    if [[ ! -s "$TMP_FILE" ]]; then
        echo "Error: Initialization output is empty."
        cat /tmp/kubectl_error.log
        rm -f "$TMP_FILE"
        exit 1
    fi

    # Create the deployments directory if it doesn't exist
    if [[ ! -d "$DEPLOY_DIR" ]]; then
        echo "Directory $DEPLOY_DIR does not exist. Creating it..."
        mkdir -p "$DEPLOY_DIR"
    fi

    # Save the initialization output to the deployments directory with a timestamped filename
    cp "$TMP_FILE" "$DEPLOY_FILE"
    echo "Vault initialization output saved to $DEPLOY_FILE"

    # Extract unseal keys and root token using jq
    UNSEAL_KEY_1=$(jq -r '.unseal_keys_b64[0]' "$TMP_FILE")
    UNSEAL_KEY_2=$(jq -r '.unseal_keys_b64[1]' "$TMP_FILE")
    UNSEAL_KEY_3=$(jq -r '.unseal_keys_b64[2]' "$TMP_FILE")
    VAULT_ROOT_TOKEN=$(jq -r '.root_token' "$TMP_FILE")

    # Check if keys were successfully extracted
    if [[ -z "$UNSEAL_KEY_1" || -z "$UNSEAL_KEY_2" || -z "$UNSEAL_KEY_3" || -z "$VAULT_ROOT_TOKEN" ]]; then
        echo "Error: Failed to extract unseal keys or root token."
        rm -f "$TMP_FILE"
        exit 1
    fi

    echo "Vault initialized successfully. Unsealing Vault..."

    # Unseal Vault with the extracted unseal keys and capture any errors
    for UNSEAL_KEY in "$UNSEAL_KEY_1" "$UNSEAL_KEY_2" "$UNSEAL_KEY_3"; do
        if ! kubectl exec --stdin=true --tty=true $VAULT_LEADER_POD_NAME -n $CLOUD_NAMESPACE -- vault operator unseal "$UNSEAL_KEY" 2> /tmp/kubectl_error.log; then   
            echo "Error: Failed to unseal Vault with unseal key $UNSEAL_KEY."
            cat /tmp/kubectl_error.log
            rm -f "$TMP_FILE"
            exit 1
        fi
    done

    echo "Vault has been successfully unsealed."

    # Clean up: Delete the temporary files
    rm -f "$TMP_FILE" /tmp/kubectl_error.log
    echo "Temporary files deleted."

    # Check if we're in HA mode before joining additional pods
    if grep -q "ha:" "$VAULT_VALUES_FILE_PATH" && grep -A1 "ha:" "$VAULT_VALUES_FILE_PATH" | grep -q "enabled: true"; then
        echo "Joining additional pods to HA cluster..."
        kubectl exec -ti $VAULT_1_POD_NAME -n $CLOUD_NAMESPACE -- vault operator raft join http://vault-0.vault-internal:8200
        kubectl exec -ti $VAULT_2_POD_NAME -n $CLOUD_NAMESPACE -- vault operator raft join http://vault-0.vault-internal:8200
        echo "High Availability Vault cluster was successfully created"
    else
        echo "Standalone Vault deployment completed successfully"
    fi
}

function deploy_vault() {
    # Determine vault mode and expected pods based on configuration
    local vault_mode="standalone"
    local expected_pods="vault-0"
    
    # Check if HA is enabled in the values file
    if grep -q "ha:" "$VAULT_VALUES_FILE_PATH" && grep -A1 "ha:" "$VAULT_VALUES_FILE_PATH" | grep -q "enabled: true"; then
        vault_mode="ha"
        expected_pods="vault-0 vault-1 vault-2"
    fi
    
    echo "Detected Vault mode: $vault_mode"
    echo "Expected pods: $expected_pods"
    
    # Check if vault pods exist and are ready
    local pods_exist=false
    local pods_ready=false
    
    if kubectl get pods -n $CLOUD_NAMESPACE $expected_pods >/dev/null 2>&1; then
        pods_exist=true
        echo "Checking if all Vault pods are ready..."
        
        if kubectl wait --namespace $CLOUD_NAMESPACE \
            --for=condition=ready pod/$expected_pods \
            --timeout=$VAULT_DEPLOY_TIMEOUT; then
            pods_ready=true
            echo "Vault is already deployed and ready."
        else
            echo "Existing Vault pods found but not ready. Proceeding with redeployment..."
        fi
    else
        echo "No existing Vault deployment found. Proceeding with fresh deployment..."
    fi
    
    # Deploy or update Vault
    echo "Deploying Vault..."
    
    # Add the Hashicorp Vault helm repo and update
    helm repo add hashicorp https://helm.releases.hashicorp.com
    helm repo update

    # Deploy/update the chart
    helm upgrade --install $VAULT_RELEASE_NAME hashicorp/vault \
        --namespace $CLOUD_NAMESPACE \
        --create-namespace \
        --values $VAULT_VALUES_FILE_PATH \
        --timeout $VAULT_DEPLOY_TIMEOUT \
        --wait

    # Wait for pods to be ready (only if not already ready)
    if [ "$pods_ready" = false ]; then
        echo "Waiting for $expected_pods to be ready..."
        kubectl wait --namespace $CLOUD_NAMESPACE \
            --for=condition=ready pod/$expected_pods \
            --timeout=$VAULT_DEPLOY_TIMEOUT
    fi

    # Initialize and setup Vault (only for new deployments)
    if [ "$pods_ready" = false ]; then
        echo "Initializing and setting up Vault..."
        _init_and_unseal_vault
        _setup_vault
    else
        echo "Vault already initialized. Updating configuration..."
        
        # Get the latest deployment file for existing deployments
        if [ -d "./deployments" ] && [ "$(ls -A ./deployments/deploy-*.json 2>/dev/null)" ]; then
            LATEST_DEPLOY_FILE=$(ls -t ./deployments/deploy-*.json | head -n1)
            echo "Found deployment file: $LATEST_DEPLOY_FILE"
            VAULT_ROOT_TOKEN=$(jq -r '.root_token' "$LATEST_DEPLOY_FILE")
            
            # Login to vault using the root token
            kubectl exec -n $CLOUD_NAMESPACE $VAULT_LEADER_POD_NAME -- vault login "$VAULT_ROOT_TOKEN"
            
            # Update policies
            __setup_policies
        else
            echo "Warning: No deployment files found in ./deployments/"
            echo "Vault appears to be initialized but deployment files are missing."
            echo "Skipping policy updates - Vault configuration may need manual intervention."
        fi
    fi

    # Upload all the needed environment variables
    _create_kv_entries "$CLOUD_VAULT_KV_PATH" "$CLOUD_ENV_FILE"
    _create_kv_entries "$MANUFACTURING_VAULT_KV_PATH" "$MANUFACTURING_ENV_FILE"
    _create_kv_entries "$VALIDATION_VAULT_KV_PATH" "$VALIDATION_ENV_FILE"
}

function teardown_vault() {
    echo "Tearing down Vault..."

    # Uninstall the Helm release
    if helm list -n "$CLOUD_NAMESPACE" | grep -q "$VAULT_RELEASE_NAME"; then
        echo "Uninstalling Helm release $VAULT_RELEASE_NAME from namespace $CLOUD_NAMESPACE..."
        helm uninstall "$VAULT_RELEASE_NAME" --namespace "$CLOUD_NAMESPACE"
    else
        echo "Helm release $VAULT_RELEASE_NAME not found in namespace $CLOUD_NAMESPACE."
    fi

    # Delete the namespace if it exists
    if kubectl get namespace "$CLOUD_NAMESPACE" >/dev/null 2>&1; then
        echo "Deleting namespace $CLOUD_NAMESPACE..."
        kubectl delete namespace "$CLOUD_NAMESPACE"
    else
        echo "Namespace $CLOUD_NAMESPACE does not exist."
    fi

    echo "Vault teardown complete."
}

# -----------------------------------------------------------------------------------
#                                                                               Cloud
# ---------------------------------------------------------------------------------*/

# Configuration
CONCORD_CLOUD_RELEASE_NAME=concord-cloud
CONCORD_CLOUD_DEPLOY_TIMEOUT=360s
CONCORD_CLOUD_TEARDOWN_TIMEOUT=180s

# File paths for local and production
VALUES_FILE_PATH="values/eks.yaml"

function deploy_concord_cloud() {
    echo "Deploying Concord Cloud Helm Chart..."

    # Check if .env file exists, if not, prompt the user and exit
    if [[ ! -f .env ]]; then
        echo ".env file not found. Please create one by copying .env.example and filling in the values."
        exit 1
    fi

    # Source the .env file
    source .env

    # Set image tag based on environment
    local IMAGE_TAG="latest"
    if [[ "$ENV" == "staging" ]]; then
        IMAGE_TAG="staging"
    fi

    # Function to clean up failed releases and their secrets
    cleanup_failed_release() {
        local release_name=$1
        local namespace=$2
        
        echo "Cleaning up failed release $release_name..."
        
        # Delete the release
        helm uninstall "$release_name" -n "$namespace" --wait || true
        
        # Find and delete associated secrets
        local secrets=$(kubectl get secrets -n "$namespace" -l "owner=helm,status=failed" -o name | grep "$release_name" || true)
        if [ ! -z "$secrets" ]; then
            echo "Found failed release secrets, deleting..."
            echo "$secrets" | xargs -r kubectl delete -n "$namespace"
        fi
        
        # Wait a moment to ensure cleanup is complete
        sleep 5
    }

    # Check if the release exists and is properly deployed
    if helm list -n "$CLOUD_NAMESPACE" | grep -q "$CLOUD_RELEASE_NAME" && \
       helm status "$CLOUD_RELEASE_NAME" -n "$CLOUD_NAMESPACE" >/dev/null 2>&1 && \
       helm history "$CLOUD_RELEASE_NAME" -n "$CLOUD_NAMESPACE" | grep -q "deployed"; then
        echo "Upgrading existing release $CLOUD_RELEASE_NAME..."
        helm upgrade "$CLOUD_RELEASE_NAME" . \
            --namespace "$CLOUD_NAMESPACE" \
            --values "$VALUES_FILE_PATH" \
            --set global.env.ENVIRONMENT="$ENV" \
            --set http-api.image.tag="$IMAGE_TAG" \
            --set orchestrator.image.tag="$IMAGE_TAG" \
            --timeout $CLOUD_DEPLOY_TIMEOUT \
            --wait
    else
        # Clean up any existing failed or stuck release
        cleanup_failed_release "$CLOUD_RELEASE_NAME" "$CLOUD_NAMESPACE"
        
        echo "Installing new release $CLOUD_RELEASE_NAME..."
        helm install "$CLOUD_RELEASE_NAME" . \
            --namespace "$CLOUD_NAMESPACE" \
            --create-namespace \
            --values "$VALUES_FILE_PATH" \
            --set global.env.ENVIRONMENT="$ENV" \
            --set http-api.image.tag="$IMAGE_TAG" \
            --set orchestrator.image.tag="$IMAGE_TAG" \
            --timeout $CLOUD_DEPLOY_TIMEOUT \
            --wait
    fi
}

function teardown_cloud() {
    # Check if the Helm release exists
    if ! helm list -n $CLOUD_NAMESPACE | grep -qw $CLOUD_RELEASE_NAME; then
        echo "Release $CLOUD_RELEASE_NAME does not exist in namespace $CLOUD_NAMESPACE."
        echo "Cloud teardown process completed."
        return
    fi

    # If the release exists, proceed with deletion
    echo "Tearing down $CLOUD_RELEASE_NAME in $CLOUD_NAMESPACE namespace..."

    helm delete $CLOUD_RELEASE_NAME -n $CLOUD_NAMESPACE \
        --timeout $CLOUD_TEARDOWN_TIMEOUT \
        --wait

    echo "Cloud teardown process completed."
}

# -----------------------------------------------------------------------------------
#                                                                                Main
# ---------------------------------------------------------------------------------*/

function main() {
    # Run the script based on command and environment
    case $COMMAND in
        start)
            create_namespaces
            apply_secrets
            deploy_vault
            deploy_concord_cloud
            ;;
        status)
            echo "Status check for $ENV environment not implemented"
            ;;
        update)
            apply_secrets
            deploy_vault
            deploy_concord_cloud
            ;;
        stop)
            # teardown_concord_cloud
            teardown_vault
            delete_secrets
            delete_namespaces
            ;;
        *)
            echo "Error: Unknown command $COMMAND"
            exit 1
            ;;
    esac
}

# Execute main function with all arguments
main "$@"