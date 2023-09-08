#!/bin/bash

# Check if the OS is Ubuntu 22.04
if ! grep -q "Ubuntu 22.04" /etc/lsb-release; then
    echo "This script is only for Ubuntu 22.04"
    exit 1
fi

function install-docker {
    # Update System
    sudo apt update && sudo apt upgrade

    # Install dependencies
    sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

    # The following command retrieves the Docker GPG key for secure APT-based transactions
    echo "y" | curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor --yes -o /usr/share/keyrings/docker-archive-keyring.gpg

    # Adds the Docker APT repository to the system's software source list
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Update the package index again to fetch packages from the new repository
    sudo apt update

    # Verify the Docker version available for installation
    apt-cache policy docker-ce

    # Install Docker
    sudo apt install -y docker-ce

    # Add the current user to the Docker group
    sudo usermod -aG docker ${USER}

    # Switch to the current user session for the group addition to take effect
    su - ${USER} -c "cd $PWD && $(getent passwd $USER | cut -d: -f7)"
}

install-docker
