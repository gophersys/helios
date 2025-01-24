#!/bin/bash

if [ -z "$WORKDIR" ]
then
    echo "Work Directory is not set, exiting..."
    exit 1
fi

# Check if machine is set otherwise exit
if [ -z "$MACHINE" ]
then
    echo "Please set MACHINE variable"
    exit 1
fi

# Check if default build directory is setup
if [ -z "$BDDIR" ]
then
    BDDIR=build
fi

# Check if branch is passed as argument
if [ -z "$BRANCH" ]
then
    BRANCH=scarthgap-7.x.y
fi

if [ -z "$MANIFEST" ]
then
    MANIFEST=torizon/default.xml
fi

# Configure Git if not configured
if [ ! $(git config --global --get user.email) ]; then
    git config --global user.email "you@example.com"
    git config --global user.name "Your Name"
    git config --global color.ui false
fi

# Create a directory for yocto setup
mkdir -p $WORKDIR
cd $WORKDIR

# Initialize if repo not yet initialized
if [ ! -d ".repo" ]; then
    echo "No .repo directory found - first time initialization"
    repo init -u https://git.toradex.com/toradex-manifest.git -b $BRANCH -m $MANIFEST
    echo "Running initial repo sync..."
    repo sync -q || { echo "[ERROR] Initial repo sync failed"; exit 1; }
else
    echo "Repo directory exists, checking status..."
    REPO_STATUS=$(repo status 2>/dev/null | cat)
    # Check if any repos are missing and sync if needed
    if echo "$REPO_STATUS" | grep -q "missing"
    then
        echo "Missing repositories detected, running repo sync..."
        repo sync -q || { echo "[ERROR] Repo sync failed"; exit 1; }
    else
        echo "All repositories present and accounted for."
    fi
fi

# Initialize build environment
if [ -z "$DISTRO"  ]
then
    MACHINE=$MACHINE BUILDDIRECTORY=$BDDIR source setup-environment $BDDIR
else
    DISTRO=$DISTRO MACHINE=$MACHINE BUILDDIRECTORY=$BDDIR source setup-environment $BDDIR
fi

# Accept Freescale/NXP EULA
if ! grep -q ACCEPT_FSL_EULA $WORKDIR/$BDDIR/conf/local.conf
then
    echo 'You have to accept freescale EULA. Read it carefully and then accept it.'
    echo 'Press "space" to scroll down and "q" to exit'
    sleep 3
    less $WORKDIR/layers/meta-freescale/EULA
    while true; do
        read -p "Do you accept the EULA? [y/n] " yn
        case $yn in
            [Yy]* ) echo 'EULA accepted'
                echo 'ACCEPT_FSL_EULA="1"' >> $WORKDIR/$BDDIR/conf/local.conf
                break;;
            [Nn]* ) exit;;
            * ) echo "Please answer yes or no.";;
        esac
    done    
fi

# Set up the environment for all future shells
cat > /home/usersetup/.bashrc << EOF
# Default bash configuration
if [ -f /etc/bash.bashrc ]; then
    . /etc/bash.bashrc
fi

# Set up colorful PS1 prompt
export PS1='\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '

# Enable color support
alias ls='ls --color=auto'
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'

# Yocto/BitBake environment setup
if [ -d "${WORKDIR}" ]; then
    cd ${WORKDIR}
    if [ -f "setup-environment" ]; then
        echo "Setting up Yocto build environment..."
        # Save current PS1
        OLD_PS1="\$PS1"
        MACHINE=${MACHINE} DISTRO=${DISTRO} BUILDDIRECTORY=${BDDIR} source setup-environment ${BDDIR}
        # Restore our colorful PS1
        PS1="\$OLD_PS1"
    fi
fi

# Return to workspace directory
cd ${WORKDIR}

# Custom build targets info
echo "Available custom build targets:"
echo "   corekinect-mtib-dev"
echo "   corekinect-mtib-k8s"
EOF

# Make sure the .bashrc has correct permissions
chown usersetup:usersetup /home/usersetup/.bashrc

# Exit successfully
exit 0