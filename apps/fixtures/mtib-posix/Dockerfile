# Use an official Python runtime as a parent image
FROM python:3.8-slim

# Install any dependencies needed
RUN apt-get update && apt-get install -y \
    curl \
    udev \
    libusb-1.0-0 \
    usbutils \
    libxrender1 \
    libxcb-render0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-randr0 \
    libxcb-xfixes0 \
    libxcb-sync1 \
    libxcb-shm0 \
    libxcb-icccm4 \
    libxcb-keysyms1 \
    libxcb-image0 \
    libxkbcommon0 \
    libxkbcommon-x11-0 \
    libfontconfig1 \
    libfreetype6 \
    libxext6 \
    libx11-6 \
    libxcb1 \
    libx11-xcb1 \
    libsm6 \
    libice6 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Setup NRF tools
# WORKDIR /tmp
# RUN curl -LO https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/desktop-software/nrf-command-line-tools/sw/versions-10-x-x/10-23-2/nrf-command-line-tools_10.23.2_arm64.deb 
# RUN dpkg -i nrf-command-line-tools_10.23.2_arm64.deb

# Mock udevadm to bypass the post-install script issue.
RUN ln -s /bin/true /usr/local/bin/udevadm

# Install JLink package
RUN dpkg -i /opt/nrf-command-line-tools/share/JLink_Linux_V788j_arm64.deb || true

# Remove udev mock
RUN rm /usr/local/bin/udevadm

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /usr/src/app
# COPY . .

# Install any needed packages specified in requirements.txt
# RUN pip install -e .

# Keep the container running
# CMD ["python3", "server/server.py"]