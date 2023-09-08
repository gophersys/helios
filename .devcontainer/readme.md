# Getting Started
There are 3 requirements that must be satisfiesd by the development machine in order to get started:

    1. VS Code
    2. Windows Subsystem for Linux (WSL2)
    2. Docker 

# Installing VS Code
Download and install from the [official website](https://code.visualstudio.com/download)

# Installing WSL
Please follow the [official docs](https://learn.microsoft.com/en-us/windows/wsl/setup/environment)

This will install Ubunut 22.04, which is what the DevOps team recommends & uses as a development environment. If you use prefer other flavors of Linux, the DevOps team will **not** provide any support if things break. 

## Configuring Resources (Not Required)
WSL2 will automatically allocated about 1/2 of your host resources. It is recommended you change this to allocated about 3/4 of your resources, [follow this link](https://learn.microsoft.com/en-us/windows/wsl/wsl-config) to find out more. You're looking to edit your ***global*** .wslconfig.

# Installing Docker
Although there's an option to install the [Docker Desktop App](https://www.docker.com/products/docker-desktop/), it is highly recommended you install the docker daemon and tools natively on WSL2. 

The script ***'install-docker.sh'*** under the **'.devcontainer/assets/'** folder will install Docker and all needed dependencies for you. 

## Note
Run these commands from the root folder of the monorepo *concord/*

1. Provide execution permissions to the script:
    ```bash
    chmod +x .devcontainer/assets/install-docker.sh
    ```
3. Run the script:
    ```bash
    bash .devcontainer/assets/install-docker.sh 
    ```
4. Once the installation is complete, you can verify the Docker installation with:
    ```bash
    docker --version
    ```

# Requirements

- Access hardware (USB ports) for flashing from within container
- Must launch environment using docker-compose for simplicity
- Must allow for seamless networking with the external host network
- Must have VSCode configuration "out of the box"

# Questions
- What does a DevOps engineer need installed in their machine initially to make the monorepo itself?

- How do I install VSCode dependencies from the DockerFile itself? In other words, how do I deploy a VSCode server inside the container with all the needed dependencies already installed? How much size will this add?

- How do I make the terminal look pretty and not just an ugly and blank bash terminal

- How do I add credentials to the docker-compose

# Resources
https://www.youtube.com/watch?v=0H2miBK_gAk
https://code.visualstudio.com/docs/devcontainers/create-dev-container
https://github.com/alfredodeza/devcontainer-python-template/blob/main/.devcontainer/devcontainer.json