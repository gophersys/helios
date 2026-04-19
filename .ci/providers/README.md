# infrastructure .ci/providers

Source of truth for every CI-system shim. No providers wired yet.

Pattern (documented in `brain/.claude/rules/operations/ci-patterns.md`):

1. Create `<provider>/` with its native-format pipeline files.
2. Symlink the provider's hardcoded path (e.g., `.github/workflows/`)
   back into this folder.
3. Provider YAMLs are thin — checkout + devcontainer + `bash .ci/ctl.sh
   <verb>`.
