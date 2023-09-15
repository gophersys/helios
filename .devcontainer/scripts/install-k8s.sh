#!/bin/bash

# Check if the OS is Ubuntu 22.04
if ! grep -q "Ubuntu 22.04" /etc/lsb-release; then
    echo "This script is only for Ubuntu 22.04"
    exit 1
fi

# Kubernetes requires a container runtime. We choose Docker.
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
    sudo apt install -y docker-ce docker-ce-cli containerd.io

    # Add the current user to the Docker group
    sudo usermod -aG docker ${USER}

    # Login again to apply change
}

# Swap needs to be disabled as Kubernetes schedules pods based on the assumption that the declared memory is RAM
function disable-swap {
    # Comment out the line related to swap in the 'file system table', ensuring that swap doesn't get enabled after a reboot.
    sudo sed -i '/\<swap\>/ s/^\(.*\)$/#\1/g' /etc/fstab

    # Immediately disable swap.
    sudo swapoff -a
}

# Enable necessary kernel modules and configurations for Kubernetes networking.
function setup-network {

    # Load the br_netfilter module:
    # This module ensures the Linux kernel will process bridge traffic with iptables.
    echo "br_netfilter" | sudo tee /etc/modules-load.d/k8s.conf > /dev/null

    # Set sysctl parameters for bridge traffic:
    # These settings ensure that traffic passing through the bridge is subjected to iptables rules.
    # This is crucial for Kubernetes network policies and services to function correctly.
    echo -e "net.bridge.bridge-nf-call-ip6tables = 1\nnet.bridge.bridge-nf-call-iptables = 1" | sudo tee /etc/sysctl.d/k8s.conf > /dev/null

    # Apply the sysctl settings immediately
    sudo sysctl --system
}

# Install kubelet, kubeadm and kubectl from Kubernetes apt repo
function install-kubectl {
    # Install packages needed to use the Kubernetes apt repository
    sudo apt-get install -y apt-transport-https ca-certificates curl

    # Download the Google Cloud public signing key
    sudo curl -fsSLo /usr/share/keyrings/kubernetes-archive-keyring.gpg https://dl.k8s.io/apt/doc/apt-key.gpg

    # Add the Kubernetes apt repository
    echo "deb [signed-by=/usr/share/keyrings/kubernetes-archive-keyring.gpg] https://apt.kubernetes.io/ kubernetes-xenial main" | sudo tee /etc/apt/sources.list.d/kubernetes.list

    # Update apt package index, install kubelet, kubeadm and kubectl, and pin their version:
    sudo apt-get update -y
    sudo apt install -y kubelet kubeadm kubectl
    sudo apt-mark hold kubelet kubeadm kubectl

    # Issue fix, acquired from the link below. Fixes erros on 'sudo kubeadm init'
    # https://github.com/containerd/containerd/issues/8139#issuecomment-1491536705

    # Check for disabled_plugins and replace only if found
    if grep -q 'disabled_plugins = \["cri"\]' /etc/containerd/config.toml; then
        sudo sed -i 's/disabled_plugins = \["cri"\]/enabled_plugins = \["cri"\]/g' /etc/containerd/config.toml
    fi

    # Check if the plugins configuration already exists, if not, append it
    if ! grep -q '\[plugins."io.containerd.grpc.v1.cri".containerd\]' /etc/containerd/config.toml; then
        echo '[plugins."io.containerd.grpc.v1.cri".containerd]' | sudo tee -a /etc/containerd/config.toml
    fi

    # Check if the endpoint configuration already exists, if not, append it
    if ! grep -q 'endpoint = "unix:///var/run/containerd/containerd.sock"' /etc/containerd/config.toml; then
        echo '  endpoint = "unix:///var/run/containerd/containerd.sock"' | sudo tee -a /etc/containerd/config.toml
    fi

    # Restart service we just made changes to
    sudo systemctl restart containerd
}

#TODO: DO NOT USE THIS FUNCTION YET, IT DOES NOT WORK PROPERLY IN UBUNTU 22.04 SERVER MUST STILL FIGURE OUT WHY
function install-k8s {
    install-docker
    disable-swap
    setup-network
    install-kubectl 

    echo "Please reload ssh session/terminal for changes to take effect"
}

function uninstall-k8s {
    sudo apt-get purge kubelet kubeadm kubectl
    sudo rm /etc/apt/sources.list.d/kubernetes.list
    sudo rm /usr/share/keyrings/kubernetes-archive-keyring.gpg

    sudo sed -i '/\[plugins."io.containerd.grpc.v1.cri".containerd\]/d' /etc/containerd/config.toml
    sudo sed -i '/  endpoint = "unix:\/\/\/var\/run\/containerd\/containerd.sock"/d' /etc/containerd/config.toml
    sudo sed -i 's/enabled_plugins = \["cri"\]/disabled_plugins = \["cri"\]/g' /etc/containerd/config.toml

    sudo systemctl restart containerd
    sudo rm /etc/sysctl.d/k8s.conf
    sudo rm /etc/modules-load.d/k8s.conf
    sudo sysctl --system
    sudo swapon -a
    sudo sed -i '/\<swap\>/ s/^#\(.*\)$/\1/g' /etc/fstab
}

function uninstall-docker {
    sudo apt-get purge docker-ce docker-ce-cli containerd.io
    sudo rm -rf /var/lib/docker
    sudo rm -rf /var/lib/containerd
}

function install-microk8s {
    NODE_TYPE=$1  # Capture the first argument passed to the function
    
    install-docker

    # Determine firewall rules based on node type
    sudo apt install -y firewalld
    if [ "$NODE_TYPE" == "control-plane" ]; then
        sudo firewall-cmd --add-port={25000/tcp,16443/tcp,12379/tcp,10250/tcp,10255/tcp,10257/tcp,10259/tcp} --permanent
    elif [ "$NODE_TYPE" == "worker" ]; then
        sudo firewall-cmd --add-port={25000/tcp,10250/tcp,10255/tcp} --permanent
    else
        echo "Invalid node type specified. Please use either 'control-plane' or 'worker'."
        return 1  # Exit the function early with an error status
    fi

    # Reload
    sudo firewall-cmd --reload

    sudo snap install microk8s --classic --channel=1.28
    sudo usermod -a -G microk8s $USER
    sudo chown -f -R $USER ~/.kube

    # Add kubectl alias to bashrc
    echo "# MicroK8s" >> ~/.bashrc
    echo "alias kubectl='microk8s kubectl'" >> ~/.bashrc

    # Reload shell to apply changes
    su - $USER
}

# ./setup-k8s control-plane  # For control plane
# ./setup-k8s worker         # For worker
install-microk8s $1
