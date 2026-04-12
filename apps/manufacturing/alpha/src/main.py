"""Alpha manufacturing test entry point.

This module is the container entry point. It delegates to run.py which
wraps pytest with preflight checks and result reporting.

For local development, run directly:
    cd apps/manufacturing/alpha
    MOCK_MODE=1 python run.py
"""

import sys
from pathlib import Path

# Ensure the app root is importable (container layout may differ)
_app_root = Path(__file__).resolve().parent.parent
if str(_app_root) not in sys.path:
    sys.path.insert(0, str(_app_root))

from run import main

if __name__ == "__main__":
    main()
