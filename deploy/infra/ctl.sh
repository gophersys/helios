#!/bin/bash

# Exit on error
set -e

# Source the bash libraries
source "$(dirname "$0")/../../libs/bash/source.sh"

# Handle environment validation and safety checks
if ! lib_handle_environment "$@"; then
    exit 1
fi

function create_infrastructure() {
    echo "Creating infrastructure for $ENV environment..."

    # Apply node taints
    apply_node_taints

    # Environment specific setup
    case $ENV in
        staging)
            ;;
        production)
            ;;
        *)
            echo "Invalid environment: $ENV"
            exit 1
            ;;
    esac

    echo "Infrastructure created for $ENV environment."
}

# Node Lists - Add your node hostnames here
CLOUD_NODES=(
    "orangepizero3"
    # Add more cloud nodes here
)

MANUFACTURING_NODES=(
    "verdin-imx8mm-15005679"
    # Add more manufacturing nodes here
)

VALIDATION_NODES=(
    # Add validation nodes here
)

# Taint configurations
CLOUD_TAINT="role=cloud:NoSchedule"
MANUFACTURING_TAINT="role=manufacturing:NoSchedule"
VALIDATION_TAINT="role=validation:NoSchedule"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to apply taint and label to a node
apply_taint() {
    local node_name="$1"
    local taint="$2"
    local node_type="$3"
    
    print_status $BLUE "Applying $node_type taint and label to node: $node_name"
    
    # Apply the taint
    kubectl taint nodes "$node_name" "$taint" --overwrite
    if [ $? -eq 0 ]; then
        print_status $GREEN "✓ Successfully applied $node_type taint to $node_name"
    else
        print_status $RED "✗ Failed to apply $node_type taint to $node_name"
    fi
    
    # Apply the label (required for nodeSelector)
    kubectl label nodes "$node_name" "role=$node_type" --overwrite
    if [ $? -eq 0 ]; then
        print_status $GREEN "✓ Successfully applied $node_type label to $node_name"
    else
        print_status $RED "✗ Failed to apply $node_type label to $node_name"
    fi
}

# Function to remove taint and label from a node
remove_taint() {
    local node_name="$1"
    local taint="$2"
    local node_type="$3"
    
    print_status $BLUE "Removing $node_type taint and label from node: $node_name"
    
    # Remove the taint
    kubectl taint nodes "$node_name" "$taint"- --overwrite
    if [ $? -eq 0 ]; then
        print_status $GREEN "✓ Successfully removed $node_type taint from $node_name"
    else
        print_status $RED "✗ Failed to remove $node_type taint from $node_name"
    fi
    
    # Remove the label
    kubectl label nodes "$node_name" "role-$node_type"- --overwrite
    if [ $? -eq 0 ]; then
        print_status $GREEN "✓ Successfully removed $node_type label from $node_name"
    else
        print_status $RED "✗ Failed to remove $node_type label from $node_name"
    fi
}

# Function to apply taints to a node type
apply_node_type_taints() {
    local node_type="$1"
    local nodes_array="$2"
    local taint="$3"
    
    print_status $YELLOW "=== Applying $node_type taints ==="
    
    # Use eval to access the array passed as string
    eval "local nodes=(\${$nodes_array[@]})"
    
    for node in "${nodes[@]}"; do
        if [ -n "$node" ] && [[ ! "$node" =~ ^#.* ]]; then
            apply_taint "$node" "$taint" "$node_type"
        fi
    done
    echo ""
}

# Function to remove taints from a node type
remove_node_type_taints() {
    local node_type="$1"
    local nodes_array="$2"
    local taint="$3"
    
    print_status $YELLOW "=== Removing $node_type taints ==="
    
    # Use eval to access the array passed as string
    eval "local nodes=(\${$nodes_array[@]})"
    
    for node in "${nodes[@]}"; do
        if [ -n "$node" ] && [[ ! "$node" =~ ^#.* ]]; then
            remove_taint "$node" "$taint" "$node_type"
        fi
    done
    echo ""
}

function apply_node_taints() {
    echo "Applying node taints for $ENV environment..."
    apply_node_type_taints "cloud" "CLOUD_NODES" "$CLOUD_TAINT"
    apply_node_type_taints "manufacturing" "MANUFACTURING_NODES" "$MANUFACTURING_TAINT"
    apply_node_type_taints "validation" "VALIDATION_NODES" "$VALIDATION_TAINT"
}

function remove_node_taints() {
    echo "Removing node taints for $ENV environment..."
    remove_node_type_taints "cloud" "CLOUD_NODES" "$CLOUD_TAINT"
    remove_node_type_taints "manufacturing" "MANUFACTURING_NODES" "$MANUFACTURING_TAINT"
    remove_node_type_taints "validation" "VALIDATION_NODES" "$VALIDATION_TAINT"
}

function delete_infrastructure() {
    echo "Deleting infrastructure for $ENV environment..."

    # Remove node taints
    remove_node_taints

    # Environment specific setup
    case $ENV in
        staging)
            ;;
        production)
            ;;
        *)
            echo "Invalid environment: $ENV"
            exit 1
            ;;
    esac

    echo "Infrastructure deleted for $ENV environment."
}

function context_infrastructure() {
    echo "Updating context for $ENV environment..."
    
    # Switch based on the environment
    case $ENV in
        staging)
            echo "Updating context for $ENV environment..."

            # Use 
            ;;
        production)
            # Nothing to do here
            ;;
        *)
            echo "Invalid environment: $ENV"
            exit 1
            ;;
    esac

    echo "Context updated for $ENV environment."
}

function create_users() {
    echo "Creating users for $ENV environment..."
    kubectl apply -f roles/admin.yaml
}

function delete_users() {
    echo "Deleting users for $ENV environment..."
    kubectl delete -f roles/admin.yaml
}

function status_infrastructure() {
    echo "Status check for $ENV environment..."

     # Switch based on the environment
    case $ENV in
        staging)
            echo "Status check for $ENV environment..."
            ;;
        production)
            # Nothing to do here
            ;;
        *)
            echo "Invalid environment: $ENV"
            exit 1
            ;;
    esac

    echo "Status check for $ENV environment completed."
}

function main() {
    CLUSTER_NAME="beta-${ENV}-eks-cluster"
    REGION="us-west-2"

    if [ "$COMMAND" == "start" ]; then
        create_infrastructure
        # create_users
    elif [ "$COMMAND" == "update" ]; then
        create_infrastructure
        # create_users
    elif [ "$COMMAND" == "context" ]; then
        context_infrastructure
    elif [ "$COMMAND" == "status" ]; then
        status_infrastructure
    elif [ "$COMMAND" == "stop" ]; then
        # delete_users
        delete_infrastructure
    else
        echo "Invalid command: $COMMAND"
        exit 1
    fi
}

main "$@"