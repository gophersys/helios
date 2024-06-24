FROM ubuntu:22.04

# -----------------------------------------------------------------------------------------------------
#                                                                                                System
# ---------------------------------------------------------------------------------------------------*/
WORKDIR /

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

# -----------------------------------------------------------------------------------------------------
#                                                                                      App Dependencies
# ---------------------------------------------------------------------------------------------------*/

# By installing these first you save a lot of time when making changes to the source code
# and rebuilding the application
WORKDIR /app
COPY apps/manufacturing/sigma5/setup.py setup.py
RUN pip install -e . && \
    pip cache purge

# -----------------------------------------------------------------------------------------------------
#                                                                                                   App  
# ---------------------------------------------------------------------------------------------------*/
WORKDIR /app

# Copy the protocols used by the app
COPY libs/protos/cluster_test /libs/protos/cluster_test
COPY libs/protos/cluster_operator /libs/protos/cluster_operator
COPY libs/protos/mtib_runner /libs/protos/mtib_runner

# Import the paths to the python path
ENV PYTHONPATH="/libs:${PYTHONPATH}"

# Copy any assets we may need
COPY apps/manufacturing/sigma5/assets assets

# Copy the app itself
COPY apps/manufacturing/sigma5/config config
COPY apps/manufacturing/sigma5/src src

# Keep the container running
CMD ["python3", "src/main.py"]