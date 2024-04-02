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
COPY apps/fixtures/mtib_http_api/setup.py setup.py
RUN pip install -e . && \
    pip cache purge

# -----------------------------------------------------------------------------------------------------
#                                                                                                   App  
# ---------------------------------------------------------------------------------------------------*/
WORKDIR /app

# Copy the protocols used by the app
COPY libs/protos/mtib_cs_pi /libs/protos/mtib_cs_pi

# Import the paths to the python path
ENV PYTHONPATH="/libs:${PYTHONPATH}"

# Copy the app itself
COPY apps/fixtures/mtib_http_api/config config
COPY apps/fixtures/mtib_http_api/src src
COPY apps/fixtures/mtib_http_api/.env .env

# Keep the container running
CMD ["python3", "src/main.py"]