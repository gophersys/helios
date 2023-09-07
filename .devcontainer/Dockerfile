FROM ubuntu:22.04

WORKDIR /concord

# Update System
RUN apt update && apt upgrade 

# Curl and Git are used extensivel to setup system
RUN apt install -y curl git

# Setup shell
RUN apt install -y zsh
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
RUN chsh -s $(which zsh)

# # Install Node Version Manager
# RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash

# COPY . /concord/

# # Install VS Code (code-server)
# RUN curl -fsSL https://code-server.dev/install.sh | sh

# # Install VS Code extension
# RUN code-server --install-extension ms-python.python

# The command that keeps the container alive
CMD ["tail", "-f", "/dev/null"]