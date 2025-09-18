#!/bin/bash

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Start the container
start_container() {
    log_info "Starting the container"

    # Install dependencies
    yarn
}

# Create action for the devcontainers
create_action() {
    log_info "Creating action for the devcontainers"

    # Check if CONCORD_MONOREPO_ROOT is set to the correct path
    if [ "$CONCORD_MONOREPO_ROOT" = "/path/to/concord" ]; then
        echo "Error: CONCORD_MONOREPO_ROOT is set to the default value inside the file `.devcontainer/.env`. Please set it to the correct path in your filesystem."
        exit 1
    fi

    # Install dependencies
    yarn

    # Create the platform builders
    nx run devcontainer:create-platform-builder
}

# Show help
show_help() {
    echo "Concord DevContainer Control Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  create    Create action for the devcontainers"
    echo "  start     Start action for the devcontainers"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 create     # Create action for devcontainers"
    echo "  $0 start      # Start action for devcontainers"
    echo ""
    echo "The script will automatically:"
    echo "  - Extract git information (branch, commit, dirty status, creator email)"
    echo "  - Create the platform builders if it doesn't exist"
    echo "  - Start the devcontainers"
}

# Main script logic
main() {
    case "${1:-help}" in
        "create")
            create_action
            ;;
        "start")
            start_container
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
