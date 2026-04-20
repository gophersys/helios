# The test framework auto-wires slot binding, MTIB clients, asset-set
# fixtures, report helpers, and mfg_stage markers via this plugin. Keep
# this file one line — don't paper over framework issues by adding
# project-level hooks here.
pytest_plugins = ["corekinect.test.autoconf"]
