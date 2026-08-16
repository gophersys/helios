# Contributing to corekinect/test

Standards for writing and maintaining the validation test framework.

## The 7 Rules

### 1. Type Annotations

- **All** public method parameters and return types must be annotated
- Use `Optional[X]` for parameters with `None` default — never `x: int = None`
- Use `Tuple[X, Y]` not bare `tuple`
- Use `Set[str]` not bare `set`
- Private/nested functions: annotate parameters at minimum
- Logger parameters: `logger: Optional[Any] = None`

### 2. Error Handling

- Use structured error types from `corekinect.test.errors`:
  - `ConfigError` — profile, manifest, environment config
  - `HardwareError` — MTIB, power, GPIO, flash failures
  - `FirmwareError` — boot, version mismatch, CFW parsing
  - `CloudError` — CoreCloud API, FUOTA delivery
  - `ValidationTimeoutError` — any polling timeout
- **Never** use `pytest.fail()` in library code
- **Never** use `assert` for runtime validation (asserts can be stripped with `-O`)
- **Never** silently swallow exceptions — always log at `warning` minimum
- Test helpers (`assertions.py`) may use `assert` — that's their purpose

### 3. Logging

- Every module that does work: `log = Logger(log_name="module_name")`
- Classes with optional logger: `self._log = logger or log`
- **Never** use `print()` — always use `log.info()` / `log.warning()` / `log.error()`
- Use `%s` style formatting for Logger calls (not f-strings)

### 4. Docstrings

- **Module**: narrative description + Usage example block
- **Class**: one-paragraph description. Include `Args:` in `__init__` docstring if >2 params
- **Public methods**: Google style with `Args:`, `Returns:`, `Raises:` sections
- **Private methods**: one-liner is fine
- **Nested functions**: one-liner at minimum

### 5. Imports

- Order: stdlib → third-party → local, alphabetical within each group
- One blank line between groups
- No duplicate imports, no unused imports
- No local/inline imports unless truly conditional (`try: import minio`)

### 6. Naming

- No single-letter variables in public code (`m` → `manifest`, `t` → `target_info`)
- Constants: `UPPER_CASE` at module level
- Private: `_leading_underscore`
- Nested functions: no leading underscore (already private by scope)

### 7. Return Patterns

- Raise on failure (don't return None when None would be ambiguous)
- `Optional[X]` return only when "not found" is a valid non-error case
- Never return different types based on a parameter

## Adding a New Module

1. Create `libs/python/corekinect/test/your_module.py`
2. Follow the 7 rules above
3. Add exports to `__init__.py` in the appropriate section (Core, Hardware, Artifacts, FUOTA, Pytest)
4. Add to `__all__` matching the import order
5. Write unit tests in `tests/test_your_module.py`
6. If the module has dependencies that need stubbing, add stubs to `tests/stubs.py`

### Module template

```python
"""One-line description.

Longer explanation of what this module does, why it exists,
and how it fits into the framework.

Usage:
    from corekinect.test.your_module import YourClass

    obj = YourClass(config)
    result = obj.do_thing()
"""

from typing import Any, Dict, List, Optional

from corekinect.test.errors import ConfigError
from corekinect.utils import Logger

log = Logger(log_name="your_module")


class YourClass:
    """One-paragraph description.

    Args:
        config: Configuration dict.
        logger: Optional logger. Defaults to module logger.
    """

    def __init__(self, config: Dict[str, Any], logger: Optional[Any] = None):
        self._config = config
        self._log = logger or log

    def do_thing(self) -> str:
        """Do the thing.

        Returns:
            Result string.

        Raises:
            ConfigError: If config is invalid.
        """
        if "required_key" not in self._config:
            raise ConfigError("required_key missing from config")
        self._log.info("Doing the thing")
        return "done"
```

## Adding a Test Stub

Test stubs go in `tests/stubs.py`. They follow the `ProgrammableTestBed` pattern:

- Configurable return values (set before test runs)
- Event recording (verify what was called)
- No I/O, no network, no hardware
- Same interface as the real class

```python
class StubYourDependency:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self._return_value = "default"

    def set_return_value(self, value: str) -> "StubYourDependency":
        self._return_value = value
        return self

    def some_method(self, arg: str) -> str:
        self.events.append({"action": "some_method", "arg": arg})
        return self._return_value
```

## Running Tests

```bash
# From repo root:
PYTHONPATH=libs/python:libs:libs/protocols python3 -m pytest \
    libs/python/corekinect/test/tests/ -v

# Specific module:
PYTHONPATH=libs/python:libs:libs/protocols python3 -m pytest \
    libs/python/corekinect/test/tests/test_stage_assets.py -v

# With coverage:
PYTHONPATH=libs/python:libs:libs/protocols python3 -m pytest \
    libs/python/corekinect/test/tests/ --cov=corekinect.test --cov-report=term-missing
```

## Version Policy

- Version in `pyproject.toml` and `__init__.py.__version__`
- Both must match
- Bump on every merge to main that changes framework code
- Semver: breaking change = major, new feature = minor, fix = patch
