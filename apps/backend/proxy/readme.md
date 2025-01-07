# Concord HTTP Proxy Server 

## TODO
- Install the supabase, prisma and openapi dependencies in the dev container
- Create nx actions (setup, build, push, docs)
- Create libraries
    - Logging
    - Config Helper
- Database
    - Setup supabase
    - Setup prisma
    - Setup seed
- Docs
    [x] openapi take many .yaml to single yaml
    - Generate clients for preferred languages 
- Routes
- Permissions and Roles

## Table of Contents
1. [Introduction](#introduction)
2. [Features](#features)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [API Endpoints](#api-endpoints)
7. [Contributing](#contributing)
8. [License](#license)


## Introduction
This application is an HTTP server designed to handle all requests to the concord testing backend. It is built using the Flask framework and provides endpoints for [storage, healthcheck, etc.]. The server is designed to be modular, extendable, and easy to set up for both development and production environments.

## Installation
### Prerequisites
- **Python 3.x** or **Node.js** (depending on your codebase)
- **Package manager**: (pip, npm, etc.)
- **Database**: If applicable


## Installation

Instructions for installing cipher, including any prerequisites.
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
# Database

## Validation Tables
### Platform
A platform will be a product, such as **sigma5** or **alpha**.

[ ] Platform
[ ] HardwareVersion
[ ] FirmwareVersion
[ ] SocketServerVersion
[ ] Host
[ ] Test
[ ] TestExecutions
[ ] TestResults
[ ] Cluster
[ ] Node
[ ] Deployment




# Known issue