#!/bin/bash

# Function to validate environment parameter
# Usage: validate_environment
# Returns: 0 if valid, 1 if invalid
function lib_validate_environment() {
    if [ -z "$ENV" ]; then
        echo "Error: --env parameter is required (staging or production)"
        return 1
    fi

    if [ "$ENV" != "staging" ] && [ "$ENV" != "production" ] && [ "$ENV" != "local" ]; then
        echo "Error: --env must be either 'staging', 'production', or 'local'"
        return 1
    fi

    return 0
}

# Function to perform production safety check
# Usage: lib_check_production_safety
# Returns: 0 if confirmed, 1 if cancelled
function lib_check_production_safety() {
    if [[ "$ENV" == "production" ]]; then
        echo -e "\033[1;31m"  # Start red bold text
        echo "╔════════════════════ WARNING ════════════════════╗"
        echo "║                                                 ║"
        echo "║        PRODUCTION ENVIRONMENT DETECTED          ║"
        echo "║                                                 ║"
        echo "║   You are about to modify the PRODUCTION        ║"
        echo "║   environment. This action cannot be undone.    ║"
        echo "║                                                 ║"
        echo "╚═════════════════════════════════════════════════╝"
        echo -e "\033[0m"  # Reset text formatting
        echo "Type 'yes' to continue:"
        
        read -r confirmation
        if [[ $confirmation != "yes" ]]; then
            echo "Operation cancelled"
            return 1
        fi
    fi
    return 0
}

# Function to parse environment from command line arguments
# Usage: parse_environment "$@"
# Sets: ENV and COMMAND variables
function lib_parse_environment() {
    ENV=""
    while [[ $# -gt 0 ]]; do
        case $1 in
            --env=*)
                ENV="${1#*=}"
                shift
                ;;
            *)
                COMMAND="$1"
                shift
                ;;
        esac
    done
}

# Main function to handle all environment-related checks
# Usage: handle_environment "$@"
# Returns: 0 if all checks pass, 1 if any check fails
function lib_handle_environment() {
    lib_parse_environment "$@"
    
    if ! lib_validate_environment; then
        return 1
    fi
    
    if ! lib_check_production_safety; then
        return 1
    fi
    
    return 0
}
