"""Validation framework conftest — registers the Concord Reporter plugin.

Product-specific test fixtures and tests have moved to their respective
app directories (e.g., apps/validation/alpha/). This stub remains so
the reporter plugin is available when running from a product app.
"""

# Auto-discover the Concord Reporter plugin (opt-in via CONCORD_RUN_ID env var).
pytest_plugins = ["corekinect.test.reporter"]
