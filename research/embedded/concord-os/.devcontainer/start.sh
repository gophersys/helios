#!/bin/bash

if [ -z "$WORKDIR" ]
then
    echo "Work Directory is not set, exiting..."
    exit 1
fi

WORKSPACE_ROOT="$(dirname "$WORKDIR")"

# Check if machine is set otherwise exit
if [ -z "$MACHINE" ]
then
    echo "Please set MACHINE variable"
    exit 1
fi

# Verify required provisioning secrets are present before doing any heavy work.
# Bitbake will only catch this much later — during recipe parse / fetch — so we
# fail fast here with a clear list of what's missing instead.
SECRETS_DIR="$WORKSPACE_ROOT/meta-corekinect/secrets"
REQUIRED_SECRETS=(corekinect-root-ca.crt corekinect-sub-ca.crt k3s-server-url k3s-token)
MISSING_SECRETS=()
for s in "${REQUIRED_SECRETS[@]}"; do
    if [ ! -s "$SECRETS_DIR/$s" ]; then
        MISSING_SECRETS+=("$s")
    fi
done
if [ ${#MISSING_SECRETS[@]} -ne 0 ]; then
    echo "" >&2
    echo "[ERROR] Missing required provisioning secret(s) in $SECRETS_DIR:" >&2
    for s in "${MISSING_SECRETS[@]}"; do
        echo "  - $s" >&2
    done
    echo "" >&2
    echo "See meta-corekinect/secrets/README.md for how to obtain each file." >&2
    echo "The image cannot be built without these — aborting devcontainer startup." >&2
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

# Initialize if repo not yet initialized. We key off `.repo/manifests` rather
# than `.repo` itself, so a previous run that crashed after the repo tool was
# unpacked but before the manifest was fetched gets re-initialized cleanly.
if [ ! -d ".repo/manifests" ]; then
    echo "No initialized .repo/manifests found - running repo init"
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

# Initialize build environment. EULA=1 tells the Toradex setup-environment
# script to auto-accept the BSP EULA (it otherwise prompts interactively and
# spins forever when stdin is not a TTY — e.g. devcontainer postStartCommand).
if [ -z "$DISTRO"  ]
then
    EULA=1 MACHINE=$MACHINE BUILDDIRECTORY=$BDDIR source setup-environment $BDDIR
else
    EULA=1 DISTRO=$DISTRO MACHINE=$MACHINE BUILDDIRECTORY=$BDDIR source setup-environment $BDDIR
fi

# Detect a stale build/tmp left over from a previous workspace path (e.g.
# from before the umbrella-mirror devcontainer change). Bitbake bakes the
# absolute TMPDIR into build/tmp/saved_tmpdir and refuses to run when the
# current TMPDIR doesn't match. The tmp tree can't be reused once that
# happens, so just wipe it — sstate-cache and downloads (the expensive
# bits) are kept and the rebuild reuses them.
EXPECTED_TMPDIR="$WORKDIR/$BDDIR/tmp"
if [ -f "$EXPECTED_TMPDIR/saved_tmpdir" ]; then
    SAVED_TMPDIR=$(cat "$EXPECTED_TMPDIR/saved_tmpdir")
    if [ "$SAVED_TMPDIR" != "$EXPECTED_TMPDIR" ]; then
        echo "[start.sh] Stale build/tmp detected — workspace path changed."
        echo "           saved_tmpdir: $SAVED_TMPDIR"
        echo "           expected   : $EXPECTED_TMPDIR"
        echo "           wiping build/tmp and build/cache so bitbake re-inits cleanly"
        echo "           (sstate-cache and downloads are kept)"
        rm -rf "$EXPECTED_TMPDIR" "$WORKDIR/$BDDIR/cache"
    fi
fi

# Register this repo's meta-corekinect layer with bitbake. The Toradex
# manifest doesn't know about it (it lives outside torizon/, in the umbrella
# repo root), so bblayers.conf needs to be extended on every fresh build dir.
META_COREKINECT="$WORKDIR/../meta-corekinect"
if [ -d "$META_COREKINECT" ] && ! grep -q "meta-corekinect" $WORKDIR/$BDDIR/conf/bblayers.conf
then
    echo "Adding meta-corekinect layer to bblayers.conf..."
    (cd $WORKDIR/$BDDIR && bitbake-layers add-layer "$META_COREKINECT") || {
        echo "[ERROR] bitbake-layers add-layer meta-corekinect failed"
        exit 1
    }
fi

# Configure debug paths properly
if ! grep -q "DEBUG_PREFIX_MAP\|REPRODUCIBLE_BUILD" $WORKDIR/$BDDIR/conf/local.conf
then
    cat >> $WORKDIR/$BDDIR/conf/local.conf << 'EOL'
# Strip build paths from debug packages
# This maps the build-time paths (WORKDIR) to a standardized path in the debug packages
# This helps achieve reproducible builds and prevents leaking build system paths
DEBUG_PREFIX_MAP = "-fdebug-prefix-map=${WORKDIR}=/usr/src/debug/${PN}/${PV}"

# Enable reproducible build paths for debug info
# This ensures debug paths are consistent across builds, improving reproducibility
REPRODUCIBLE_BUILD_DEBUG_PATHS = "1"

# Maintain debug information in the output
# Ensures debug symbols are generated but properly managed
DEBUG_BUILD_OPTIONS = "-g"
EOL
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
        EULA=1 MACHINE=${MACHINE} DISTRO=${DISTRO} BUILDDIRECTORY=${BDDIR} source setup-environment ${BDDIR}
        # Restore our colorful PS1
        PS1="\$OLD_PS1"
    fi
fi

# Return to workspace directory
cd ${WORKDIR}/../

# Custom build targets info
echo "Available custom build targets:"
echo "   corekinect-mtib"
EOF

# Make sure the .bashrc has correct permissions
chown usersetup:usersetup /home/usersetup/.bashrc

update_tezi_overlays() {
    echo "WORKDIR is: $WORKDIR"
    CONF_FILE="$WORKDIR/layers/meta-toradex-nxp/conf/machine/verdin-imx8mm.conf"

    if [ -f "$CONF_FILE" ]; then
        # Remove only the DSI overlay from the overlays list, keep others
        sed -i -E 's/(TEZI_EXTERNAL_KERNEL_DEVICETREE_BOOT = ")([^"]*)verdin-imx8mm_dsi-to-hdmi_overlay\.dtbo ?([^"]*)"/\1\2\3"/' "$CONF_FILE"
        echo "Removed DSI overlay from TEZI_EXTERNAL_KERNEL_DEVICETREE_BOOT in $CONF_FILE"
    else
        echo "Error: $CONF_FILE not found at $CONF_FILE!"
        exit 1
    fi
}

update_tezi_overlays

# Exit successfully
exit 0