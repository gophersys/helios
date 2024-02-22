FROM ccr01.ad.corekinect.com/concord-dev-env:1.0

# -----------------------------------------------------------------------------------------------------
#                                                                                                Zephyr
# ---------------------------------------------------------------------------------------------------*/
# Runnineg DEBIAN_FRONTEND option will choose the default for any commands that require user input
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
RUN tar xvf zephyr-sdk-0.16.1_linux-x86_64.tar.xz > /dev/null
RUN rm -rf zephyr-sdk-0.16.1_linux-x86_64.tar.xz

# Run the Zephyr SDK bundle setup script
# The setup script asks for user input twice, so we use printf to send multiple y responses
WORKDIR /usr/home/zephyr-sdk-0.16.1
RUN printf "y\ny\n" | ./setup.sh

# # Perform the west init, this will be cached as a separate layer
RUN west init ~/zephyrproject && \ 
    cd ~/zephyrproject && \
    west update && \
    west zephyr-export

# Install additional Python dependencies 
RUN pip3 install --user -r ~/zephyrproject/zephyr/scripts/requirements.txt
RUN pip3 install --user -r ~/zephyrproject/bootloader/mcuboot/scripts/requirements.txt

# Espressif HAL requires WiFi and Bluetooth binary blobs in order work
WORKDIR /root/zephyrproject
RUN west blobs fetch hal_espressif

# Add OpenOCD binaries to the PATH
ENV PATH="/usr/home/zephyr-sdk-v0.16.1/sysroots/x86_64-pokysdk-linux/usr/bin:${PATH}"

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
RUN echo 'source /root/zephyrproject/zephyr/zephyr-env.sh' >> ~/.zshrc

# Serial terminal aliases
RUN echo "alias serial0='screen /dev/ttyACM0 921600'" >> ~/.zshrc
RUN echo "alias serial1='screen /dev/ttyACM1 921600'" >> ~/.zshrc
RUN echo "alias serial2='screen /dev/ttyACM2 921600'" >> ~/.zshrc
RUN echo "alias serial3='screen /dev/ttyUSB0 9600'"   >> ~/.zshrc