# Inspired by https://github.com/torizon/torizon-image-build-env/tree/master
FROM crops/poky:debian-12

USER root

# Add usersetup to sudoers with NOPASSWD
RUN echo "usersetup ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Set bash as default shell
RUN chsh -s /bin/bash root && \
    chsh -s /bin/bash usersetup

# For Dockerfile commands
SHELL ["/bin/bash", "-c"]

# Install packages
RUN apt-get update && apt-get install --no-install-recommends --no-install-suggests -y \
    curl \
    default-jre \
    vim \
    git-lfs \
    python3-gi \
    gir1.2-ostree-1.0 \
    python3-requests \
    device-tree-compiler \
    && rm -rf /var/lib/apt/lists/*

# Install repo
RUN curl https://commondatastorage.googleapis.com/git-repo-downloads/repo > /bin/repo && chmod a+x /bin/repo

USER usersetup