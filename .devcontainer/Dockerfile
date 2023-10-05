FROM ubuntu:22.04

# Update System
RUN apt update && apt upgrade 

# Install global dependencies needed for downloading, installing & building software
RUN apt install -y curl git libc6-dev

# Setup shell
RUN apt install -y zsh
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
RUN chsh -s $(which zsh)

# Switch to zsh for all subsequent RUN commands
SHELL ["/usr/bin/zsh", "-c"]

# -----------------------------------------------------------------------------------------------------
#                                                                                                    Nx
# ---------------------------------------------------------------------------------------------------*/

# Install Node Version Manager and latest LTS release of Node.js
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash && \
    source ~/.zshrc && \
    nvm install v18.17.1 && \
    npm install -g npm@10.0.0 && \
    npm install -g nx

# -----------------------------------------------------------------------------------------------------
#                                                                                                    Go
# ---------------------------------------------------------------------------------------------------*/

# Install Go 1.20.1
RUN curl -LO "https://golang.org/dl/go1.20.1.linux-amd64.tar.gz" \
    && tar -C /usr/local -xzf go1.20.1.linux-amd64.tar.gz \
    && rm go1.20.1.linux-amd64.tar.gz

# Set up environment
ENV GOPATH /go
ENV PATH $GOPATH/bin:/usr/local/go/bin:$PATH
RUN mkdir -p "$GOPATH/src" "$GOPATH/bin" && chmod -R 777 "$GOPATH"

# -----------------------------------------------------------------------------------------------------
#                                                                                         Zephyr &  NCS
# ---------------------------------------------------------------------------------------------------*/

# From -> https://developer.nordicsemi.com/nRF_Connect_SDK/doc/latest/nrf/installation/installing.html

# Runnineg DEBIAN_FRONTEND option will choose the default for any commands that require user input
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git cmake ninja-build gperf \
    ccache dfu-util device-tree-compiler wget \
    python3-dev python3-pip python3-setuptools python3-tk python3-wheel xz-utils file \
    make gcc gcc-multilib g++-multilib libsdl2-dev libmagic1

# Install west and update PATH
RUN pip3 install --user west && \
    echo 'export PATH=~/.local/bin:"$PATH"' >> ~/.zshrc && \
    /bin/zsh -c "source ~/.zshrc"

# Update PATH to include user's local bin, so that we can use west in follow up RUN
ENV PATH="${PATH}:/root/.local/bin"

# Install the Zephyr SDK
WORKDIR /usr/home
RUN wget https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v0.16.1/zephyr-sdk-0.16.1_linux-x86_64.tar.xz
RUN wget -O - https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v0.16.1/sha256.sum | shasum --check --ignore-missing
RUN tar xf zephyr-sdk-0.16.1_linux-x86_64.tar.xz > /dev/null
RUN rm -rf zephyr-sdk-0.16.1_linux-x86_64.tar.xz

# Run the Zephyr SDK bundle setup script
# The setup script asks for user input twice, so we use printf to send multiple y responses
WORKDIR /usr/home/zephyr-sdk-0.16.1
RUN printf "y\ny\n" | ./setup.sh

# Create the ncs directory and set it as the working directory
RUN mkdir ncs
WORKDIR /ncs

# Perform the west init, this will be cached as a separate layer
RUN west init -m https://github.com/nrfconnect/sdk-nrf --mr v2.4.1 && \ 
    west update
    
# Modify the west.yml using the awk command to add espressif & nxp support
#
# Here's what the awk command does:
#   - /name-allowlist:/: Matches lines containing name-allowlist:.
#     getline: Fetches the next line.
#   - The inner while loop prints lines while they're less than " - hal_nxp" 
#     (since "hal_nxp" is the last entry alphabetically).
#   - Once we reach a line that is greater alphabetically than " - hal_nxp"
#     or an empty line (end of list), we print "hal_espressif" and "hal_nxp".
#   - > nrf/temp.yml: Writes the output to a temporary file.
#   - mv nrf/temp.yml nrf/west.yml: Replaces the original west.yml with our modified temporary file.
#
RUN awk '/name-allowlist:/{ \
        print; \
        getline; \
        while ($0 < "          - hal_nxp" && $1 != "") { \
            print; \
            getline; \
        }; \
        print "          - hal_espressif # Added by CoreKinect"; \
        print "          - hal_nxp # Added by CoreKinect"; \
        print "          - hal_stm32 # Added by CoreKinect"; \
        print; \
        next \
    }1' nrf/west.yml > nrf/temp.yml && \
    mv nrf/temp.yml nrf/west.yml

# Perform west update and zephyr-export
RUN west update && \
    west zephyr-export

# Install additional Python dependencies 
RUN pip3 install --user -r zephyr/scripts/requirements.txt
RUN pip3 install --user -r nrf/scripts/requirements.txt
RUN pip3 install --user -r bootloader/mcuboot/scripts/requirements.txt

# We DONT Install udev rules, as passing a device to a container will automatically carry over its
# persimissions. Documentation on how to pass a device correctly to the container will be provided

# -----------------------------------------------------------------------------------------------------
#                                                                                                 JLink
# ---------------------------------------------------------------------------------------------------*/

WORKDIR /tmp

# Install dependencies first
RUN apt update && \
    apt install -y \
    libxcb-render0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-icccm4 \
    libxcb-keysyms1 \
    libxcb-image0 \
    libxkbcommon-x11-0 \
    udev 

# Mock udevadm to bypass the post-install script issue.
RUN ln -s /bin/true /usr/local/bin/udevadm

# Download and install JLink package
RUN curl -d "accept_license_agreement=accepted&submit=Download+software" -X POST -O "https://www.segger.com/downloads/jlink/JLink_Linux_x86_64.deb" && \
    dpkg -i JLink_Linux_x86_64.deb || true && \
    rm JLink_Linux_x86_64.deb

# Setup config folder to avoid "Terms of Use" pop up window of JLink on every board flash
COPY ./assets/segger /root/.config/SEGGER

# Remove udev mock
RUN rm /usr/local/bin/udevadm

# -----------------------------------------------------------------------------------------------------
#                                                                                         nRF CLI Tools
# ---------------------------------------------------------------------------------------------------*/

# Get .deb package and install
RUN curl -o nrf-cli-tools.deb "https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/desktop-software/nrf-command-line-tools/sw/versions-10-x-x/10-23-0/nrf-command-line-tools_10.23.0_amd64.deb" && \
    dpkg -i nrf-cli-tools.deb || true && \
    apt install -f -y && \
    rm nrf-cli-tools.deb

# Clean registry after install to minimize size
RUN apt clean && \
    rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------------------------------
#                                                                                     Fix Locales Issue
# ---------------------------------------------------------------------------------------------------*/

#TODO: document me
# 1. Install necessary packages
# - locales: This package is required to set up and generate locales in Debian/Ubuntu.
RUN apt update && apt install -y locales

# 2. Generate the desired locale (en_US.UTF-8 in this example)
# The locale-gen command reads the /etc/locale.gen file to determine which locales to generate.
# Uncommenting a specific locale in this file and then running locale-gen will generate that locale.
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen

# 3. Set the locale environment variables for the container
# Setting these environment variables will ensure that processes run in the container use the desired locale.
# This can prevent issues with software that expects specific locales.
ENV LANG=en_US.UTF-8  
ENV LANGUAGE=en_US:en  
ENV LC_ALL=en_US.UTF-8 

# -----------------------------------------------------------------------------------------------------
#                                                                                           Other tools
# ---------------------------------------------------------------------------------------------------*/

WORKDIR /

# Serial terminal
RUN apt update && apt install -y minicom

# Go tools
RUN go install -v golang.org/x/tools/gopls@latest

# Net tools
RUN apt install -y net-tools iputils-ping

# Add OpenOCD binaries to the PATH
ENV PATH="/usr/home/zephyr-sdk-0.16.1/sysroots/x86_64-pokysdk-linux/usr/bin:${PATH}"

# -----------------------------------------------------------------------------------------------------
#                                                                                                   End
# ---------------------------------------------------------------------------------------------------*/
# Source the environment
RUN echo 'source /ncs/zephyr/zephyr-env.sh' >> ~/.zshrc
RUN echo "alias serial='minicom -D /dev/ttyACM0 -b 921600'" >> ~/.zshrc
CMD ["tail", "-f", "/dev/null"]
