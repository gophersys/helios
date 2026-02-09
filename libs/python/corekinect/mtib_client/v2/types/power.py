from dataclasses import dataclass, field
from typing import List


@dataclass
class PowerStatus:
    """Current power channel status.

    Args:
        enabled: Whether the channel is active.
        voltage_v: Measured voltage in volts.
        current_ma: Measured current in milliamps.
        power_mw: Calculated power in milliwatts.
    """

    enabled: bool
    voltage_v: float
    current_ma: float
    power_mw: float


@dataclass
class PowerSample:
    """A single power measurement sample.

    Args:
        timestamp_s: Timestamp in seconds since epoch.
        timestamp_ns: Nanosecond component of timestamp.
        current_ua: Current in microamps.
        voltage_mv: Voltage in millivolts.
    """

    timestamp_s: int
    timestamp_ns: int
    current_ua: float
    voltage_mv: float


@dataclass
class PowerMeasurement:
    """Aggregated power measurement over a duration.

    Args:
        duration_s: Measurement duration in seconds.
        average_ua: Average current in microamps.
        min_ua: Minimum current in microamps.
        max_ua: Maximum current in microamps.
        energy_uj: Total energy in microjoules.
        sample_count: Number of samples taken.
        samples: Raw samples if requested.
    """

    duration_s: float
    average_ua: float
    min_ua: float
    max_ua: float
    energy_uj: float
    sample_count: int
    samples: List[PowerSample] = field(default_factory=list)
