#!/usr/bin/env bash
#
# SSH Config Automation with "Update" functionality
#

KEYS_DIR="$HOME/.ssh/keys/machines"
CONFIG_FILE="$HOME/.ssh/config"

# Exit on any error
set -e

# Color codes
RED='\033[0;31m'
NC='\033[0m' # No Color

# Initialize cleanup tracking arrays
declare -a TEMP_FILES=()
declare -a CREATED_KEYS=()
declare -a KNOWN_HOSTS_REMOVED=()
declare -a REMOTE_KEYS_MODIFIED=()
declare -a CONFIG_BACKUPS=()

function show_usage() {
    echo "Usage: $0 <command>"
    echo "Commands:"
    echo "  create    Create a new SSH configuration"
    echo "  delete    Delete an existing SSH configuration"
    exit 1
}

function cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
      echo -e "${RED}Error detected (exit code: $exit_code). Running cleanup...${NC}"
      
      # Clean up temporary files
      for file in "${TEMP_FILES[@]}"; do
          if [ -f "$file" ]; then
              echo -e "${RED}Removing temporary file: $file${NC}"
              rm -f "$file"
          fi
      done

      # Clean up config backups
      for backup in "${CONFIG_BACKUPS[@]}"; do
          if [ -f "$backup" ]; then
              echo -e "${RED}Removing config backup: $backup${NC}"
              rm -f "$backup"
          fi
      done

      # In case of failure during key creation, remove partial keys
      for key in "${CREATED_KEYS[@]}"; do
          if [ -f "$key" ]; then
              echo -e "${RED}Removing incomplete key: $key${NC}"
              rm -f "$key" "${key}.pub"
          fi
      done

      # Restore known_hosts entries if needed
      for host in "${KNOWN_HOSTS_REMOVED[@]}"; do
          if [ -f "$HOME/.ssh/known_hosts.old" ]; then
              echo -e "${RED}Restoring known_hosts entry for: $host${NC}"
              cp "$HOME/.ssh/known_hosts.old" "$HOME/.ssh/known_hosts"
          fi
      done

      # Restore remote authorized_keys if needed
      for entry in "${REMOTE_KEYS_MODIFIED[@]}"; do
          IFS=':' read -r user host keyfile <<< "$entry"
          echo -e "${RED}Attempting to restore authorized_keys backup for $user@$host${NC}"
          ssh -o StrictHostKeyChecking=no "$user@$host" '
              if [ -f ~/.ssh/authorized_keys.bak ]; then
                  cp ~/.ssh/authorized_keys.bak ~/.ssh/authorized_keys
                  rm ~/.ssh/authorized_keys.bak
              fi
          ' 2>/dev/null || true
      done
    fi
}

# Set trap to call cleanup on script exit
trap cleanup EXIT

function check_existing_config() {
    local alias="$1"
    local hostname="$2"
    
    if grep -qE "^[Hh]ost\s+$alias\b" "$CONFIG_FILE" 2>/dev/null; then
        HOST_ALIAS_EXISTS=true
    fi
    if grep -qE "^\s*HostName\s+$hostname\b" "$CONFIG_FILE" 2>/dev/null; then
        HOST_HOSTNAME_EXISTS=true
    fi
}

function handle_existing_config() {
    local alias="$1"
    local hostname="$2"
    local ssh_user="$3"
    local key_path="$4"
    
    echo "======================================================="
    echo "WARNING: An entry for alias '$alias' or hostname '$hostname'"
    echo "already exists in $CONFIG_FILE."
    echo "This script can remove that entry, remove old host keys, and"
    echo "delete remote authorized_keys if you want to re-flash everything."
    echo "======================================================="

    read -rp "Do you want to update/replace the existing configuration? (y/n) " ANSWER
    if [[ "$ANSWER" =~ ^[Yy]$ ]]; then
        remove_existing_config "$alias" "$hostname"
        remove_known_hosts "$hostname"
        remove_remote_authorized_keys "$ssh_user" "$hostname" "$key_path"
        echo "All old data cleared. We will now proceed with a fresh setup."
    else
        echo "Exiting without changes..."
        exit 0
    fi
}

function backup_config() {
    local backup_file="$CONFIG_FILE.bak.$(date +%s)"
    cp "$CONFIG_FILE" "$backup_file"
    CONFIG_BACKUPS+=("$backup_file")
}

function remove_existing_config() {
    local alias="$1"
    local hostname="$2"
    
    echo "Ok, removing old config block(s) for alias '$alias' or host '$hostname'..."
    backup_config
    sed -i.bak -e "/^[Hh]ost\s\+$alias\b/,/^[Hh]ost\b/ {d}" "$CONFIG_FILE"
    TEMP_FILES+=("$CONFIG_FILE.bak")
}

function remove_known_hosts() {
    local hostname="$1"
    echo "Removing $hostname from known_hosts..."
    KNOWN_HOSTS_REMOVED+=("$hostname")
    ssh-keygen -R "$hostname" 2>/dev/null || true
}

function remove_remote_authorized_keys() {
    local ssh_user="$1"
    local hostname="$2"
    local key_path="$3"
    
    if [ ! -f "${key_path}.pub" ]; then
        echo "Warning: Public key file ${key_path}.pub not found, skipping remote authorized_keys cleanup"
        return
    fi

    # Track this modification for potential rollback
    REMOTE_KEYS_MODIFIED+=("$ssh_user:$hostname:$key_path")

    # Get the content of our public key file, escape special characters for sed
    local pub_key_content
    pub_key_content=$(sed 's/[]\/$*.^[]/\\&/g' "${key_path}.pub")
    
    # Use SSH to remove only the specific key line from authorized_keys
    ssh -o StrictHostKeyChecking=no "$ssh_user@$hostname" "
        if [ -f ~/.ssh/authorized_keys ]; then
            cp ~/.ssh/authorized_keys ~/.ssh/authorized_keys.bak
            sed -i '/${pub_key_content}/d' ~/.ssh/authorized_keys
        fi
    " || {
        echo "Warning: Could not remove key from remote authorized_keys. Possibly no password-based login?"
        return
    }
    
    echo "Successfully removed key from remote authorized_keys file"
}

function setup_ssh_key() {
    local key_path="$1"
    local ssh_user="$2"
    local hostname="$3"
    
    # Track this key in case we need to clean it up
    CREATED_KEYS+=("$key_path")
    
    if [ -f "$key_path" ]; then
        echo "Key '$key_path' already exists; not generating a new one."
    else
        echo "Generating a new Ed25519 key pair at: $key_path"
        ssh-keygen -t ed25519 -f "$key_path" -C "$ssh_user@$hostname"
    fi
    chmod 600 "$key_path"
}

function copy_public_key() {
    local key_path="$1"
    local ssh_user="$2"
    local hostname="$3"
    
    echo "Copying public key to $ssh_user@$hostname..."
    ssh-copy-id -i "$key_path.pub" "$ssh_user@$hostname"
}

function append_ssh_config() {
    local alias="$1"
    local hostname="$2"
    local ssh_user="$3"
    local key_path="$4"
    
    cat <<EOF >> "$CONFIG_FILE"

Host $alias
    HostName $hostname
    User $ssh_user
    IdentityFile $key_path
EOF

    echo
    echo "========================="
    echo "New SSH config entry:"
    echo "-------------------------"
    echo "Host $alias"
    echo "    HostName $hostname"
    echo "    User $ssh_user"
    echo "    IdentityFile $key_path"
    echo "-------------------------"
    echo "You can now connect using: ssh $alias"
    echo "========================="
}

function delete_configuration() {
    echo "==== SSH Config Deletion ===="
    read -rp "Enter the alias to delete: " ALIAS

    # Check if alias exists in config
    if ! grep -qE "^[Hh]ost\s+$ALIAS\b" "$CONFIG_FILE"; then
        echo "Error: Alias '$ALIAS' not found in $CONFIG_FILE"
        exit 1
    fi

    # Get hostname and user from existing config
    HOSTNAME=$(grep -A2 "^[Hh]ost\s\+$ALIAS\b" "$CONFIG_FILE" | grep "HostName" | awk '{print $2}')
    SSH_USER=$(grep -A3 "^[Hh]ost\s\+$ALIAS\b" "$CONFIG_FILE" | grep "User" | awk '{print $2}')
    KEY_PATH=$(grep -A4 "^[Hh]ost\s\+$ALIAS\b" "$CONFIG_FILE" | grep "IdentityFile" | awk '{print $2}')

    echo "Found configuration:"
    echo "  Hostname: $HOSTNAME"
    echo "  User: $SSH_USER"
    echo "  Key: $KEY_PATH"

    read -rp "Are you sure you want to delete this configuration? (y/n) " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo "Deletion cancelled."
        exit 0
    fi

    # Remove specific key from remote authorized_keys
    echo "Removing specific key from remote authorized_keys..."
    remove_remote_authorized_keys "$SSH_USER" "$HOSTNAME" "$KEY_PATH"

    # Remove local key files
    echo "Removing local key files..."
    rm -f "$KEY_PATH" "$KEY_PATH.pub"

    # Remove from known_hosts
    remove_known_hosts "$HOSTNAME"

    # Remove config entry
    echo "Removing SSH config entry..."
    remove_existing_config "$ALIAS" "$HOSTNAME"

    echo "Configuration for '$ALIAS' has been completely removed."
}

function create_configuration() {
    mkdir -p "$KEYS_DIR"
    chmod 700 "$HOME/.ssh" 2>/dev/null
    chmod 700 "$KEYS_DIR" 2>/dev/null

    echo "==== SSH Config Creation ===="

    read -rp "Enter an alias for this host (e.g., myserver): " ALIAS
    read -rp "Enter HostName (e.g., myserver.domain.com or 192.168.1.10): " HOSTNAME

    # Default user = msegura@ad.corekinect.com
    DEFAULT_USER="msegura@ad.corekinect.com"
    read -rp "Enter SSH username (default is $DEFAULT_USER): " SSH_USER
    SSH_USER="${SSH_USER:-$DEFAULT_USER}"

    read -rp "Enter a name for the SSH key file (e.g., myserver_ed25519): " KEY_NAME
    KEY_PATH="$KEYS_DIR/$KEY_NAME"

    check_existing_config "$ALIAS" "$HOSTNAME"

    if $HOST_ALIAS_EXISTS || $HOST_HOSTNAME_EXISTS; then
        handle_existing_config "$ALIAS" "$HOSTNAME" "$SSH_USER" "$KEY_PATH"
    fi

    setup_ssh_key "$KEY_PATH" "$SSH_USER" "$HOSTNAME"
    copy_public_key "$KEY_PATH" "$SSH_USER" "$HOSTNAME"
    append_ssh_config "$ALIAS" "$HOSTNAME" "$SSH_USER" "$KEY_PATH"
}

function main() {
    # Initialize these variables as false
    HOST_ALIAS_EXISTS=false
    HOST_HOSTNAME_EXISTS=false

    if [ $# -ne 1 ]; then
        show_usage
    fi

    case "$1" in
        "create")
            create_configuration
            ;;
        "delete")
            delete_configuration
            ;;
        *)
            show_usage
            ;;
    esac
}

# Execute main function
main "$@"

