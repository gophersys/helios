---
name: devcontainer
description: Own the cloud devcontainer, its lifecycle, and the host entrypoint.
---

Own `.devcontainer` and `scripts/devcontainer`. Keep `devcontainer cloud` as the
host entry and Nx as the container interface. Test entry, mounts, tools, and
Docker behavior with `nx check devcontainer`. For performance work, compare the
same lifecycle command before and after the change.
