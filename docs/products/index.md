---
min_role: DEVELOPER
---
# Products

Every device in Concord starts as a product — the top-level object that ties a PCB design to its firmware source, build recipes, and validation pipeline. Alpha B0, for example, is one product with two targets (nRF52840 app processor, nRF9151 comms coprocessor), a linked Bitbucket repo, and a build matrix that produces both MFG and production hex files.

Once a product exists, the rest of the pipeline follows: [trigger builds](../builds/triggering-builds.md) from the linked repo, run validation against the output, and flash approved firmware in manufacturing.

Products break down into three parts:

**[Board revisions](board-revisions.md)** track PCB changes. When you respin a board — new sensors, different pin assignments, MCU swap — create a new revision so the right firmware variant gets built and validated against the right hardware.

**Targets** are the individual processors on the board. Each target has a chipset (nRF52840, nRF9151) and an AppID that maps to CFW filenames. A single revision can have multiple targets.

**[Firmware repos](firmware-repos.md)** point Concord at your source code. Link a Bitbucket repo, pick the branches to watch, and the build system handles the rest — polling for commits, compiling, and storing artifacts in MinIO.

**[Build matrix](build-matrix.md)** defines which firmware variants a product builds at each validation stage — label, firmware type, variant, and whether the output is HEX, CFW, or both.

**[Recipe editor](recipe-editor.md)** is the CodeMirror-based IDE for editing `build.sh` — the shell script that compiles firmware inside the build container.

**[Stage config](stage-config.md)** walks through the four-step wizard for configuring validation stages: target hardware, signing key, build recipe, and review.
