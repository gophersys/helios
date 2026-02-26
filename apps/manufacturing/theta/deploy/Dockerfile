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
COPY apps/manufacturing/theta/setup.py setup.py
RUN pip install -e . && \
    pip cache purge

# -----------------------------------------------------------------------------------------------------
#                                                                                                   App  
# ---------------------------------------------------------------------------------------------------*/
WORKDIR /app

# Copy the libraries used by the app
COPY libs/python /libs/python

# Copy the protocols used by the app
COPY libs/protocols/mtib /libs/protocols/mtib

# Set the PYTHONPATH to include the libs directory
ENV PYTHONPATH="/libs:${PYTHONPATH}"
ENV PYTHONPATH="/libs/python/:${PYTHONPATH}"

# Import the paths to the python path
ENV PYTHONPATH="/libs:${PYTHONPATH}"

# Copy the app itself
COPY apps/manufacturing/theta/config config
COPY apps/manufacturing/theta/src src

# Keep the container running
CMD ["python3", "src/main.py"]