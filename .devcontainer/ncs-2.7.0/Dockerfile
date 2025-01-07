FROM containers.ad.corekinect.com/concord-base:latest

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
    make gcc gcc-multilib g++-multilib libsdl2-dev expect \
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
RUN wget https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v0.16.8/zephyr-sdk-0.16.8_linux-x86_64_minimal.tar.xz
RUN wget -O - https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v0.16.8/sha256.sum | shasum --check --ignore-missing
RUN tar xf zephyr-sdk-0.16.8_linux-x86_64_minimal.tar.xz > /dev/null
RUN rm -rf zephyr-sdk-0.16.8_linux-x86_64_minimal.tar.xz

# Run the Zephyr SDK bundle setup script using expect
WORKDIR /usr/home/zephyr-sdk-0.16.8
RUN expect -c ' \
    log_user 1; \
    spawn ./setup.sh; \
    expect "Install toolchains for all targets" { send "n\r" }; \
    expect "Install '\''aarch64-zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''arc64-zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''arc-zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''arm-zephyr-eabi'\'' toolchain" { send "y\r" }; \
    expect "Install '\''microblazeel-zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''mips-zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''nios2-zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''riscv64-zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''sparc-zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''x86_64-zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''xtensa-dc233c_zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''xtensa-espressif_esp32_zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''xtensa-espressif_esp32s2_zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''xtensa-espressif_esp32s3_zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''xtensa-intel_ace15_mtpm_zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''xtensa-intel_tgl_adsp_zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''xtensa-mtk_mt8195_adsp_zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''xtensa-nxp_imx_adsp_zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''xtensa-nxp_imx8m_adsp_zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''xtensa-nxp_imx8ulp_adsp_zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''xtensa-nxp_rt500_adsp_zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''xtensa-nxp_rt600_adsp_zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install '\''xtensa-sample_controller_zephyr-elf'\'' toolchain" { send "n\r" }; \
    expect "Install host tools" { send "y\r" }; \
    expect "Register Zephyr SDK CMake package" { send "y\r" }; \
    expect eof; \
    '

# Create the ncs directory and set it as the working directory
RUN mkdir ncs
WORKDIR /ncs

# Perform the west init, this will be cached as a separate layer
RUN west init -m https://github.com/nrfconnect/sdk-nrf --mr v2.7.0 && \ 
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
ENV PATH="/usr/home/zephyr-sdk-0.16.8/sysroots/x86_64-pokysdk-linux/usr/bin:${PATH}"

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
