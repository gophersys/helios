FROM ubuntu:22.04

# Update and install all necessary tools in one layer
RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    screen \
    iputils-ping \
    usbutils \
    && apt-get clean \ 
    && rm -rf /var/lib/apt/lists/* 

# ----------------------------------------------------------------------------------
#                                                            App python dependencies
# --------------------------------------------------------------------------------*/

WORKDIR /app

# By installing these first you save a lot of time when making changes to the source code
# and rebuilding the application
COPY apps/backend/operator/setup.py setup.py
RUN pip install -e . && \
    pip cache purge

# ----------------------------------------------------------------------------------
#                                                                                App
# --------------------------------------------------------------------------------*/
WORKDIR /app

# Copy the protocols used by the app
COPY libs/protos/cluster_test /libs/protos/cluster_test
COPY libs/protos/cluster_operator /libs/protos/cluster_operator

# Import the paths to the python path
ENV PYTHONPATH="/libs:${PYTHONPATH}"

# Copy the app itself
COPY apps/backend/operator/config config
COPY apps/backend/operator/src src

# Keep the container running
CMD ["python3", "src/main.py"]