# Review & Clean MTIB Server

Audit the MTIB server backend (Python gRPC service) for code quality, pattern violations, error handling, type safety, and protocol compliance.

Arguments: None (reviews entire MTIB server)

## Scope

Reviews the MTIB server implementation:
- `apps/edge/mtib-server/src/` - Core server implementation
- `apps/edge/mtib-server/tests/` - Test suite
- `libs/protocols/mtib/mtib.proto` - Protocol definitions

## Execution Strategy

Launch **parallel agents** (using the Task tool with `subagent_type: "general-purpose"`) for each review dimension. Each agent reads the relevant source files and reports findings. After all agents complete, compile a unified report and apply auto-fixable changes.

### Agent 1: gRPC Service Pattern Review

Read all service implementation files in `apps/edge/mtib-server/src/providers/` and verify:

1. **Service structure** - Each provider follows the pattern:
   - `__init__.py` - Exports provider class
   - `base.py` - Base class with common methods (if applicable)
   - Individual feature files - One per hardware feature

2. **gRPC method signatures** - All RPC methods:
   - Accept `request` and `context` parameters
   - Return appropriate protobuf message types
   - Use type hints: `def Method(self, request: RequestType, context: grpc.ServicerContext) -> ResponseType:`

3. **Error handling** - All gRPC methods:
   - Wrap operations in try/except
   - Set context status on errors: `context.set_code(grpc.StatusCode.INVALID_ARGUMENT)`
   - Set context details: `context.set_details(error_message)`
   - Log errors appropriately

4. **Logging** - All providers:
   - Use module-level logger: `logger = logging.getLogger(__name__)`
   - Log at appropriate levels (DEBUG, INFO, WARNING, ERROR)
   - Include context in log messages (node ID, operation, parameters)

5. **Resource cleanup** - Providers that manage hardware:
   - Implement cleanup methods
   - Release resources in finally blocks
   - Handle cleanup errors gracefully

**Reference files:**
- `apps/edge/mtib-server/src/providers/handlers/power.py`
- `apps/edge/mtib-server/src/providers/handlers/uart.py`

### Agent 2: Protocol Compliance Review

Read all provider implementations and compare against `libs/protocols/mtib/mtib.proto`:

1. **Message types** - All providers:
   - Use correct request/response message types from proto
   - Populate all required fields
   - Handle optional fields correctly (check for presence)

2. **Enum values** - All providers:
   - Use proto-defined enums (not magic numbers or strings)
   - Handle unknown enum values gracefully

3. **Streaming RPCs** - Providers with streaming:
   - Yield messages at appropriate intervals
   - Check `context.is_active()` before yielding
   - Handle client disconnection gracefully
   - Log stream lifecycle events

4. **Backward compatibility** - New fields:
   - Use optional fields for new features
   - Don't break existing clients
   - Version proto changes appropriately

**Reference:**
- `libs/protocols/mtib/mtib.proto`
- `apps/edge/mtib-server/src/providers/handlers/observability.py` (streaming example)

### Agent 3: Hardware Abstraction Review

Read all providers and verify proper hardware abstraction:

1. **Hardware access** - All providers:
   - Use abstraction layer (GPIO, I2C, SPI wrappers)
   - Never access `/dev/*` or `/sys/*` directly
   - Handle hardware-not-available errors gracefully

2. **Platform detection** - Providers that need platform-specific code:
   - Check platform at initialization
   - Provide mock/simulation mode for testing
   - Log platform detection results

3. **Error messages** - Hardware errors:
   - Include context (operation, channel, expected vs actual state)
   - Suggest remediation where possible
   - Don't expose internal file paths or sensitive data

4. **Configuration** - Hardware configuration:
   - Use environment variables or config files (not hardcoded)
   - Validate configuration at startup
   - Document all config options

**Reference files:**
- `apps/edge/mtib-server/src/shared/hardware.py`
- `apps/edge/mtib-server/src/providers/handlers/gpio.py`

### Agent 4: Type Safety & Code Quality Review

Read all Python files in `apps/edge/mtib-server/src/` and check:

1. **Type hints** - All functions:
   - Have complete type hints (params and return)
   - Use proper types (not `Any` unless necessary)
   - Import types from `typing` module

2. **Dataclasses/TypedDict** - Structured data:
   - Use `@dataclass` or `TypedDict` for structured data
   - Define types in `shared/types.py`
   - Never use bare dicts for structured data

3. **Constants** - Magic numbers and strings:
   - Define at module top or in constants file
   - Use UPPER_CASE naming
   - Document units and ranges

4. **Docstrings** - All public functions:
   - Have docstrings describing purpose
   - Document parameters and return values
   - Include examples for complex functions

5. **Code style** - All files:
   - Follow PEP 8 (line length, naming conventions)
   - Use f-strings (not % or .format())
   - Avoid deeply nested code (max 3 levels)

**Tools to use:**
- Read files to check manually
- No external linters (just visual inspection)

### Agent 5: Error Handling & Resilience Review

Read all provider implementations and verify:

1. **Exception handling** - All methods:
   - Specific exceptions caught (not bare `except:`)
   - Cleanup in finally blocks
   - Errors logged before raising/returning

2. **gRPC error codes** - Appropriate status codes:
   - `INVALID_ARGUMENT` - Bad input parameters
   - `NOT_FOUND` - Resource doesn't exist
   - `UNAVAILABLE` - Hardware unavailable
   - `FAILED_PRECONDITION` - Operation not valid in current state
   - `INTERNAL` - Unexpected errors

3. **Retry logic** - Operations that can fail transiently:
   - Use exponential backoff
   - Limit retry attempts
   - Log retry attempts

4. **Validation** - Input validation:
   - Check request parameters before using
   - Validate ranges (channel numbers, voltage values)
   - Return clear error messages

5. **State management** - Stateful providers:
   - Handle concurrent requests safely
   - Clean up state on errors
   - Validate state transitions

**Reference:**
- `apps/edge/mtib-server/src/providers/handlers/analyzer.py` (complex state machine)

### Agent 6: Testing Coverage Review

Read all test files in `apps/edge/mtib-server/tests/` and check:

1. **Test coverage** - Every provider:
   - Has corresponding test file
   - Tests happy path
   - Tests error cases
   - Tests edge cases (boundary values, null inputs)

2. **Test structure** - All test files:
   - Use pytest fixtures
   - Clear test names (test_<what>_<when>_<expected>)
   - Arrange-Act-Assert pattern
   - Independent tests (no shared state)

3. **Mocking** - Tests that need hardware:
   - Mock hardware interfaces
   - Use test fixtures from `tests/mocks/`
   - Don't require real hardware to run

4. **Integration tests** - End-to-end tests:
   - Test full RPC call flow
   - Use real gRPC client
   - Verify protobuf serialization

5. **Test utilities** - Reusable test helpers:
   - Defined in `tests/conftest.py`
   - Well-documented
   - Avoid duplication

**Reference:**
- `apps/edge/mtib-server/tests/test_power.py`
- `apps/edge/mtib-server/tests/conftest.py`

## Output

After all agents complete, compile findings into a structured report:

```
## MTIB Server Review Report

### Critical (must fix)
- [ ] Finding with file:line reference

### gRPC Pattern Violations
- [ ] Missing error handling / incorrect status codes

### Protocol Compliance Issues
- [ ] Incorrect message types / missing required fields

### Hardware Abstraction Issues
- [ ] Direct hardware access / missing error handling

### Type Safety Issues
- [ ] Missing type hints / using Any

### Error Handling Issues
- [ ] Bare except / missing validation

### Testing Gaps
- [ ] Missing tests / poor coverage
```

Then apply auto-fixable changes (type hints, docstrings, simple error handling) and list what was fixed vs what needs manual review.

## Verification

After applying fixes, run:
```bash
cd apps/edge/mtib-server
# Type checking
python3 -m mypy src --strict --ignore-missing-imports

# Tests
PYTHONPATH=src:../../libs/python pytest tests/ -v

# Code quality
python3 -m flake8 src --max-line-length=100
```

All checks must pass clean.
