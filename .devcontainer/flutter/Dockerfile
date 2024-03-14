FROM ccr01.ad.corekinect.com/concord-dev-env:1.6

# -----------------------------------------------------------------------------------------------------
#                                                                                     Fix Locales Issue
# ---------------------------------------------------------------------------------------------------*/
# This package is required to set up and generate locales in Debian/Ubuntu.
RUN apt update && apt install -y locales

# The locale-gen command reads the /etc/locale.gen file to determine which locales to generate.
# Uncommenting a specific locale in this file and then running locale-gen will generate that locale.
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen

# Setting these environment variables will ensure that processes run in the container use the desired locale.
# This can prevent issues with software that expects specific locales.
ENV LANG=en_US.UTF-8  
ENV LANGUAGE=en_US:en  
ENV LC_ALL=en_US.UTF-8 

# -----------------------------------------------------------------------------------------------------
#                                                                                               Flutter
# ---------------------------------------------------------------------------------------------------*/

WORKDIR /tmp

# Install Flutter dependencies
RUN apt update && apt install -y --no-install-recommends \
    bash \
    curl \
    file \
    unzip \
    xz-utils \
    zip \
    libglu1-mesa \
    cmake \
    ninja-build \
    build-essential \
    libstdc++6 \
    libglu1-mesa-dev \
    clang \
    pkg-config \
    libgtk-3-dev \      
    libblkid-dev \      
    liblzma-dev \       
    libgcrypt-dev \      
    libsoup2.4-dev    

# Download and set up Flutter
RUN curl -LO https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_3.19.3-stable.tar.xz && \
    tar xf flutter_linux_3.19.3-stable.tar.xz && \
    rm flutter_linux_3.19.3-stable.tar.xz

# Add Flutter to the PATH in .bashrc and .zshrc
RUN echo 'export PATH="$PATH:/tmp/flutter/bin"' >> $HOME/.bashrc && \
    echo 'export PATH="$PATH:/tmp/flutter/bin"' >> $HOME/.zshrc

# Add Flutter to the current shell's PATH
ENV PATH="$PATH:/tmp/flutter/bin"

# Precache Flutter artifacts
RUN flutter precache 

# Enable Linux Desktop dev
RUN flutter config --enable-linux-desktop

# Configure git to consider the Flutter directory as safe
RUN git config --global --add safe.directory /tmp/flutter


# -----------------------------------------------------------------------------------------------------
#                                                                                                   End
# ---------------------------------------------------------------------------------------------------*/

# Fix git issues
RUN git config --global --add safe.directory /workspaces