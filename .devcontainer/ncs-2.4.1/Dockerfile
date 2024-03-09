FROM ccr01.ad.corekinect.com/concord-dev-env:1.6

# -----------------------------------------------------------------------------------------------------
#                                                                                         Zephyr &  NCS
# ---------------------------------------------------------------------------------------------------*/

# From -> https://developer.nordicsemi.com/nRF_Connect_SDK/doc/latest/nrf/installation/installing.html

# Set non-interactive frontend and configure timezone preemptively
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC

# Install your packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    git cmake ninja-build gperf \
    ccache dfu-util device-tree-compiler wget \
    python3-dev python3-pip python3-setuptools python3-tk python3-wheel xz-utils file \
    make gcc gcc-multilib g++-multilib libsdl2-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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
    
# Modify the west.yml using the awk command to add espressif, nxp & stm32 support
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

# Modify the anytree version in requirements-extras.txt
RUN sed -i 's/anytree*/anytree==2.8.0/' /ncs/zephyr/scripts/requirements-extras.txt

# Install additional Python dependencies 
RUN pip3 install --user -r zephyr/scripts/requirements.txt
RUN pip3 install --user -r nrf/scripts/requirements.txt
RUN pip3 install --user -r bootloader/mcuboot/scripts/requirements.txt

# Add OpenOCD binaries to the PATH
ENV PATH="/usr/home/zephyr-sdk-0.16.1/sysroots/x86_64-pokysdk-linux/usr/bin:${PATH}"

# We DONT Install udev rules, as passing a device to a container will automatically carry over its
# persimissions. Documentation on how to pass a device correctly to the container will be provided

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
#                                                                                                   End
# ---------------------------------------------------------------------------------------------------*/

# Fix git issues
RUN git config --global --add safe.directory /workspaces

# Set Zephyr environment
RUN echo 'source /ncs/zephyr/zephyr-env.sh' >> ~/.zshrc

# Serial terminal aliases
RUN echo "alias serial0='screen /dev/ttyACM0 921600'" >> ~/.zshrc
RUN echo "alias serial1='screen /dev/ttyACM1 921600'" >> ~/.zshrc
RUN echo "alias serial2='screen /dev/ttyACM2 921600'" >> ~/.zshrc