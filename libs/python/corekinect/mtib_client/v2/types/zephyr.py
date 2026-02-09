from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ZephyrThread:
    """A Zephyr RTOS thread.

    Args:
        id: Thread ID.
        name: Thread name.
        state: Thread state enum value.
        priority: Thread priority.
        stack_size: Total stack size in bytes.
        stack_used: Used stack size in bytes.
        cycles: CPU cycles consumed.
    """

    id: int
    name: str
    state: int
    priority: int
    stack_size: int = 0
    stack_used: int = 0
    cycles: int = 0


@dataclass
class ZephyrLogEntry:
    """A Zephyr log message.

    Args:
        timestamp_s: Timestamp seconds.
        timestamp_ns: Timestamp nanoseconds.
        level: Log level enum value.
        module: Logging module name.
        message: Log message text.
        file: Source file path.
        line: Source line number.
    """

    timestamp_s: int
    timestamp_ns: int
    level: int
    module: str
    message: str
    file: str = ""
    line: int = 0


@dataclass
class ZephyrShellResult:
    """Result of a Zephyr shell command.

    Args:
        output: Command output text.
        return_code: Shell command return code.
    """

    output: str
    return_code: int


@dataclass
class ZephyrDevicetreeNode:
    """A node in the Zephyr devicetree.

    Args:
        path: Node path (e.g. '/soc/uart@40002000').
        compatible: Compatible string.
        label: Node label.
        status: Node status ('okay', 'disabled').
        properties: Key-value node properties.
        children: Child nodes.
    """

    path: str
    compatible: str = ""
    label: str = ""
    status: str = ""
    properties: Dict[str, str] = field(default_factory=dict)
    children: List["ZephyrDevicetreeNode"] = field(default_factory=list)


@dataclass
class TestResult:
    """Result of a single test case.

    Args:
        name: Test case name.
        status: Test status enum value.
        duration_s: Test duration in seconds.
        message: Status message or failure reason.
        log: Full test log output.
    """

    name: str
    status: int
    duration_s: float
    message: str = ""
    log: str = ""


@dataclass
class TwisterResult:
    """Result of a Twister test run.

    Args:
        results: Individual test results.
        full_log: Complete Twister log output.
    """

    results: List[TestResult] = field(default_factory=list)
    full_log: str = ""
