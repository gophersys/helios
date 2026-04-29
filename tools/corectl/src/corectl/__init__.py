"""corectl — Concord platform CLI.

Resource-based CLI for managing the Concord IoT validation platform.

Commands follow the pattern: corectl <resource> <action> [options]

Resources:
    test        Validation test management (validate, run, package, upload)
    mtib        MTIB fixture management (list, status, probe) [future]
    mfg         Manufacturing operations (flash, personalize, post) [future]

Authentication:
    corectl auth login          Authenticate with Concord API
    corectl auth status         Show current auth status
"""

__version__ = "0.9.0"
