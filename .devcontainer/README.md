# Concord Monorepo DevContainers

This folder contains the `devcontainer`s for the Concord Monorepo. There are a few containers, designed to be used in different scenarios (UI/UX, backend, firmware, etc.). 

This document explains how to build and push the containers to the registry.

## Building base container from scratch

This folder is setup as an `nx` project, making actions like building, pushing, and containerizing the containers easy. 

However, if you don't have access to the registry, you can build the base container manually.

To build the base container, ***from the root of the monorepo*** run the following command in your machine's terminal:

```bash
chmod +x .devcontainer/base/ctl.sh && ./.devcontainer/base/ctl.sh build
```

This will build the base container and save it to your local Docker registry. You can then `Reopen in Container` to use the base container.


## Create Multi-Platform Builder

From a devcontainer, you can create a multi-platform builder. This enables linux/amd64 and linux/arm64 builds, which are required for some of the containers.

```bash
nx run devcontainer:create-platform-builder
```

This will create the multi-platform builder if it doesn't exist, and setup the builder for use.

## Build

To build all the `devcontainers`, you can use the following command:

```bash
nx run devcontainer:build-all
```

This will build and save to your local Docker registry.

## Push

If you need to force push to the registry, you can push to the registry using the following command:

```bash
nx run devcontainer:push-all
```

This will push all the containers to the registry at `containers.ad.corekinect.com`.

It's ideal that the build server pushes to the registry, and it's not recommended to push from your local machine.

