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
    iputils-ping \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------------------------------
#                                                                                      App Dependencies
# ---------------------------------------------------------------------------------------------------*/

# By installing these first you save a lot of time when making changes to the source code
# and rebuilding the application
WORKDIR /app
COPY apps/validation/alpha/setup.py setup.py
RUN pip install -e . && \
    pip cache purge

# -----------------------------------------------------------------------------------------------------
#                                                                                                   App
# ---------------------------------------------------------------------------------------------------*/
WORKDIR /app

# Copy the protocols used by the app
COPY libs/protocols /libs/protocols

# Copy the corekinect python library
COPY libs/python /libs/python

# Import the paths to the python path
ENV PYTHONPATH="/libs:/libs/python:/libs/protocols"

# Copy the test app
COPY apps/validation/alpha/fixtures fixtures
COPY apps/validation/alpha/tests tests
COPY apps/validation/alpha/conftest.py conftest.py
COPY apps/validation/alpha/pytest.ini pytest.ini

# Copy firmware artifacts (defaults — can be overridden via volume mount)
# Manufacturing build = "debug", Production build = "release"
COPY apps/firmware/products/alpha/artifacts/alpha_mfg_fw/alpha_b0/app_nrf52840.hex /firmware/alpha_debug_nrf52840.hex
COPY apps/firmware/products/alpha/artifacts/alpha_mfg_fw/alpha_b0/comms_nrf9151.hex /firmware/alpha_debug_nrf9151.hex
COPY apps/firmware/products/alpha/artifacts/alpha_fw/alpha_b0/app_nrf52840.hex /firmware/alpha_release_nrf52840.hex
COPY apps/firmware/products/alpha/artifacts/alpha_fw/alpha_b0/comms_nrf9151.hex /firmware/alpha_release_nrf9151.hex
COPY apps/manufacturing/alpha/assets/mfw_nrf91x1_2.0.2.zip /firmware/mfw_nrf91x1_2.0.2.zip

CMD ["python3", "-m", "pytest", "-v", "-s"]
