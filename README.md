# Concord Monorepo

Hello World!

This repository contains the Concord monorepo. It is a collection of applications, libraries, deployments,and tools that are used to build the Concord System.

***If you need to make changes to the backend, the frontend, or the shared libraries, you are in the right place.***

# Getting Started
The following requirements must be satisfied by your development machine in order to get started:

- Have VS Code installed
- Have Windows Subsystem for Linux (WSL2) installed
- Have Docker installed in same environment as WSL2
- Have the monorepo (this repository) `--recursive` cloned to your development machine

# Setup your workstation for development
Use the `devcontainer` feature of VS Code to develop in a containerized environment. This will allow you to develop in a consistent environment with all the necessary dependencies installed.

- `base`: This is the base devcontainer that contains the necessary dependencies for all the other devcontainers. Use if working on the backend. Python, K8s, etc.
- `mtib`: This is the devcontainer for the MTIB application. Use if working on the MTIB server application. ***This environment runs on the MTIB hardware. (arm64)***
- `ncs`: This is the devcontainer for the NCS firmware. Use if working on zephyr firmware. `nordic`, `espressif`, `nxp`, `stm32` support is included.
- `ui`: This is the devcontainer for the Manufacturing UI. Use if working on the Frontend UI.

To find out more about the devcontainers, please refer to the [devcontainer README](.devcontainer/README.md) file.

# Understanding the monorepo
The monorepo is a collection of applications, libraries, deployments, and tools that are used to build the Concord System. Read more about the monorepo in the [monorepo README](docs/monorepo.md) file.

The monorepo is organized into the following folders:

## Important folders
- `.devcontainer`: Development containers for all use cases. Refer to the [devcontainer README](.devcontainer/README.md) for more information.
- `apps`: Anything that is considered a software application, from firmware to ui/ux, as well as tests and backend services. Refer to the [apps README](apps/README.md) for more information.
- `deploy`: Infrastructure as code, k8s deployments, helm charts, etc. Refer to the [deploy README](deploy/README.md) for more information.
- `docs`: Useful diagrams, in depth documentation, etc. Refer to the [docs README](docs/README.md) for more information.
- `libs`: Libraries that are used to build the Concord System. Zephyr, Python, Network protocols, etc. Refer to the [libs README](libs/README.md) for more information.
- `prisma`: Prisma schema for the database. Refer to the [prisma README](prisma/README.md) for more information.
- `tools`: Tools that are used with the Concord System. Scripts, etc. Refer to the [tools README](tools/README.md) for more information.

## Important files
- `README.md`: This file. High level overview of the monorepo.

## Not so important folders
- `.nx, .yarn`: Contains [nx](https://nx.dev/) and [yarn](https://yarnpkg.com/) workspaces that are used to build the Concord System. Don't touch this folder.
- `node_modules`: node.js dependencies. Don't touch this folder.

## Not so important files
- `.editorconfig`: Used for formatting TypeScript code. Set and forget.
- `.gitattributes`: Used for git to ignore certain files. Set and forget.
- `.gitmodules`: Used for git to pull in submodules. Set and forget.
- `.gitignore`: Used for git to ignore certain files. Set and forget.
- `.yarnrc.yml`: Used for yarn to ignore certain files. Set and forget.
- `nx.json`: Contains the configuration for the nx workspaces.
- `package.json`: Contains the node.js dependencies. Don't touch this file.
- `yarn.lock`: Contains the dependencies for the yarn workspaces.

# Contributing

If using one of the `devcontainers` (highly recommended), auto-formatting and auto-highlighting should work out of the box for Python and Zephyr projects.

If you have any questions, please reach out.
