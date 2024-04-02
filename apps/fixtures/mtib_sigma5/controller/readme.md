## Configuration

The application can be launched using the following command:

```bash
docker run -it --privileged \
-p 6969:6969 \
ccr01.ad.corekinect.com/mtib-http-api:latest
```
## Installation

Instructions for installing the application, including any prerequisites.

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
    cd cipher-
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
