# machines

No machines enrolled yet. See `machines/CONVENTIONS.md` for how to add one:

1. Pick a template from `machines/templates/`.
2. Scaffold with `bash machines/ctl.sh new-host <template> <host-name>`.
3. Edit `machines/hosts/<host-name>/identity.yaml` with the real values.
4. Run `bash ctl.sh generate-index` from the infrastructure root to
   regenerate this index.

This file is auto-generated — do not edit manually.
