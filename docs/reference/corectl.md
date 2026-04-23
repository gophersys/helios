---
min_role: DEVELOPER
---
# corectl CLI

Command-line interface for Concord. Useful for scripting, CI builds, and quick lookups without opening the UI.

## Installation

```bash
pip install corectl --index-url https://pypi.concord.local/simple/
```

## Configuration

Point corectl at your Concord instance:

```bash
corectl config set api-url https://concord.local
corectl config set api-key <your-api-key>
```

Generate an API key from **Settings > API Keys** in the Concord UI.

## Commands

### Products

```bash
corectl products list                    # List all products
corectl products get <id>                # Get product details
```

### Builds

```bash
corectl builds list --product <id>       # List builds for a product
corectl builds trigger --product <id>    # Trigger a new build
corectl builds logs <id>                 # Stream build logs
```

### Validation

```bash
corectl validation runs list             # List validation runs
corectl validation runs get <id>         # Get run details
```
