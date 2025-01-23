#!/bin/bash

WDIR=/workdir

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
mkdir -p $WDIR
cd $WDIR

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
if ! grep -q ACCEPT_FSL_EULA $WDIR/$BDDIR/conf/local.conf
then
    echo 'You have to accept freescale EULA. Read it carefully and then accept it.'
    echo 'Press "space" to scroll down and "q" to exit'
    sleep 3
    less $WDIR/layers/meta-freescale/EULA
    while true; do
        read -p "Do you accept the EULA? [y/n] " yn
        case $yn in
            [Yy]* ) echo 'EULA accepted'
                echo 'ACCEPT_FSL_EULA="1"' >> $WDIR/$BDDIR/conf/local.conf
                break;;
            [Nn]* ) exit;;
            * ) echo "Please answer yes or no.";;
        esac
    done    
fi

# Set up the environment for all future shells
cat >> /home/usersetup/.bashrc << EOF

# Yocto/BitBake environment setup
if [ -f "${WDIR}/${BDDIR}/conf/local.conf" ]; then
    echo "Setting up Yocto build environment..."
    cd ${WDIR}
    MACHINE=${MACHINE} DISTRO=${DISTRO} BUILDDIRECTORY=${BDDIR} source setup-environment ${BDDIR}

    echo "Or alternatively, you can build the custom Corekinect targets:"
    echo "   corekinect-mtib-dev"
    echo "   corekinect-mtib-k8s"
fi
EOF

# Make sure the .bashrc has correct permissions
chown usersetup:usersetup /home/usersetup/.bashrc

# Exit successfully
exit 0