## Configuration

The application can be launched using the following command:

```bash
docker run -it --privileged \
-v /dev/bus/usb:/dev/bus/usb \
-v /tmp/fw_files:/tmp \
-p 50051:50051 \
localhost/mtib-posix:1.0 \
/bin/bash
```

# cipher

A brief description of what cipher does and its purpose.

## Todo

[ ] Set the right branch in the setup.py for iface once iface is done

## Installation

Instructions for installing cipher, including any prerequisites.

### Development Setup
1. **Install python venv dependencies**
    ```bash
    apt install -y python3.10-venv
    ```
2. **Clone the repository**: 
    ```bash
    git clone git@bitbucket.org:corekinect/cipher-posix.git
    ```
3. **Navigate to the directory**: 
    ```bash
    cd cipher-posix
    ```
4. **Create a virtual environment**: 
    ```bash
    python3 -m venv .venv
    ```
5. **Activate the virtual environment**: 
    ```bash
    source .venv/bin/activate
    ```
6. **Install the package in editable mode for development**: 
    ```bash
    pip install -e .
    ```

## Usage

Examples of how to use `cipher` module.

## Contributing

Guidelines for how to report issues, propose changes, or submit Pull Requests.
