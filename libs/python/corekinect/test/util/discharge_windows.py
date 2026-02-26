from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple, TypeVar
import pandas as pd

MsgObjType = TypeVar("MsgObjType")


@dataclass(frozen=True)
class DischargeWindow:
    """
    Represents a single discharge window for a device.

    start_time / end_time:
        Timestamps of first/last message in the window.
    start_voltage / end_voltage:
        Battery readings at the edges of the window.
    start_index / end_index:
        Optional indices (per-device) for debugging / plotting.
    terminated_by:
        One of:
            - "charger"
            - "voltage_increase"
            - "low_voltage"
            - "inactivity_timeout"
            - "open_ended"  (no clear close condition in data)
    """

    device_id: Any
    start_time: datetime
    end_time: datetime
    duration: timedelta
    start_voltage: Optional[float]
    end_voltage: Optional[float]
    start_index: int
    end_index: int
    terminated_by: str


def detect_discharge_windows(
    data: Iterable[MsgObjType] | pd.DataFrame,
    *,
    device_id_field: str = "device_id",
    time_field: str = "time_of_record",
    update_reason_field: str = "update_reason",
    on_charger_field: str = "on_charger",
    batt_voltage_field: str = "batt_voltage",
    # Discharge logic parameters
    start_update_reasons: Tuple[int, ...] = (5, 2),
    full_batt_threshold: float = 3450.0,
    low_batt_threshold: float = 2800.0,
    voltage_increase_threshold: float = 1000.0,
    inactivity_timeout: timedelta = timedelta(hours=1.5),
    # Behavior flags
    min_duration: timedelta = timedelta(minutes=10),
    min_voltage_drop: float = 50.0,
    require_prev_on_charger: bool = True,
    sort: bool = True,
) -> Dict[Any, List[DischargeWindow]]:
    """
    Detect discharge windows for each device based on message stream or DataFrame.

    Discharge window definition (in code terms):

    - A window *starts* when:
        * current update_reason in `start_update_reasons`
        * battery_voltage >= full_batt_threshold
        * and (optionally) the previous message for that device had on_charger == True,
          indicating we are coming off a charge (require_prev_on_charger).

    - A window *continues* as long as:
        * no message in the window has on_charger == True, AND
        * there is no significant voltage increase vs last sample
          (delta_v < voltage_increase_threshold), AND
        * we haven't gone idle longer than `inactivity_timeout`.

      Update reasons other than 5/2 are tolerated; they don't *by themselves*
      terminate the window unless they violate the above rules.

    - A window *ends* when:
        * on_charger == True           -> terminated_by="charger"
        * voltage increase >= threshold -> terminated_by="voltage_increase"
        * battery voltage <= low_batt_threshold -> terminated_by="low_voltage"
        * time gap between messages > inactivity_timeout -> terminated_by="inactivity_timeout"

    - If a window is still open at the end of the dataset and none of the hard
      termination conditions fired, it is closed at the last message time with
      terminated_by="open_ended".

    Args:
        data:
            Either an iterable of message objects (e.g. PositionMsgV6 instances),
            or a pandas.DataFrame with appropriately named columns.
        device_id_field:
            Attribute/column name for device id.
        time_field:
            Attribute/column name for message timestamp.
        update_reason_field:
            Attribute/column name for update reason (int).
        on_charger_field:
            Attribute/column name for charger flag (bool-ish).
        batt_voltage_field:
            Attribute/column name for battery voltage (float/int).
        start_update_reasons:
            Update_reason values that indicate a candidate start of discharge.
        full_batt_threshold:
            Battery voltage at or above which we consider "full-ish".
        low_batt_threshold:
            Battery voltage at or below which we consider "discharged".
        voltage_increase_threshold:
            Voltage bump between samples that indicates charging started.
        inactivity_timeout:
            Max allowed time between messages during a discharge window before
            we consider the device to have "died" (timeout termination).
        require_prev_on_charger:
            If True, only start a discharge window if the *previous* message
            for that device had on_charger == True.
        sort:
            If True, sort by (device_id_field, time_field). If False, assume
            input is already ordered per device.

    Returns:
        Dict[device_id, List[DischargeWindow]]
    """

    # --------------------|  Normalize to grouped, ordered rows  |--------------------

    windows_by_device: Dict[Any, List[DischargeWindow]] = {}

    # --------------------|  Normalise input to per-device rows  |--------------------
    is_dataframe = pd is not None and isinstance(data, pd.DataFrame)

    if is_dataframe:
        df = data  # type: ignore[assignment]
        if sort:
            df = df.sort_values([device_id_field, time_field])

        per_device_iter: List[Tuple[Any, List[Any]]] = []
        for dev_id, group in df.groupby(device_id_field, sort=False):
            per_device_iter.append(
                (
                    dev_id,
                    list(group.itertuples(index=False, name="Row")),
                )
            )

        def get_row_values(row: Any) -> Tuple[Any, datetime, int, bool, Optional[float]]:
            return (
                getattr(row, device_id_field),
                getattr(row, time_field),
                getattr(row, update_reason_field),
                bool(getattr(row, on_charger_field)),
                getattr(row, batt_voltage_field),
            )

    else:
        objs = list(data)  # type: ignore[arg-type]
        if not objs:
            return windows_by_device

        if sort:
            objs.sort(
                key=lambda o: (
                    getattr(o, device_id_field),
                    getattr(o, time_field),
                )
            )

        per_device_map: Dict[Any, List[Any]] = {}
        for obj in objs:
            dev_id = getattr(obj, device_id_field)
            per_device_map.setdefault(dev_id, []).append(obj)

        per_device_iter = list(per_device_map.items())

        def get_row_values(row: Any) -> Tuple[Any, datetime, int, bool, Optional[float]]:
            return (
                getattr(row, device_id_field),
                getattr(row, time_field),
                getattr(row, update_reason_field),
                bool(getattr(row, on_charger_field)),
                getattr(row, batt_voltage_field),
            )

    # --------------------|  Main per-device pass  |--------------------
    for device_id, rows in per_device_iter:
        device_windows: List[DischargeWindow] = []

        window_open = False
        start_time: Optional[datetime] = None
        start_voltage: Optional[float] = None
        start_index: int = -1

        last_time: Optional[datetime] = None
        last_voltage: Optional[float] = None
        last_on_charger: Optional[bool] = None

        for idx, row in enumerate(rows):
            _, current_time, update_reason, on_charger, voltage = get_row_values(row)
            if current_time is None:
                continue

            # Inactivity timeout while window is open
            if window_open and last_time is not None:
                gap = current_time - last_time
                if gap > inactivity_timeout:
                    # Candidate window end at last_time
                    end_time = last_time
                    end_voltage = last_voltage
                    duration = end_time - start_time  # type: ignore[operator]

                    # --------------------|  Discharge quality filter  |--------------------
                    if (
                        start_voltage is not None
                        and end_voltage is not None
                        and duration >= min_duration
                        and (start_voltage - end_voltage) >= min_voltage_drop
                        and start_voltage >= full_batt_threshold
                    ):
                        device_windows.append(
                            DischargeWindow(
                                device_id=device_id,
                                start_time=start_time,  # type: ignore[arg-type]
                                end_time=end_time,
                                duration=duration,
                                start_voltage=start_voltage,
                                end_voltage=end_voltage,
                                start_index=start_index,
                                end_index=idx - 1,
                                terminated_by="inactivity_timeout",
                            )
                        )

                    window_open = False
                    start_time = None
                    start_voltage = None
                    start_index = -1

            # Decide whether to start a window
            if not window_open:
                is_start_reason = update_reason in start_update_reasons
                is_fullish = (voltage is not None) and (voltage >= full_batt_threshold)
                not_on_charger = not on_charger

                can_start = False
                if is_start_reason and is_fullish and not_on_charger:
                    if not require_prev_on_charger:
                        can_start = True
                    else:
                        if last_on_charger is True:
                            can_start = True

                if can_start:
                    window_open = True
                    start_time = current_time
                    start_voltage = voltage
                    start_index = idx

                    last_time = current_time
                    last_voltage = voltage
                    last_on_charger = on_charger
                    continue

            # If window is open, check charger / voltage / low-voltage termination
            if window_open:
                terminated: Optional[str] = None

                if on_charger:
                    terminated = "charger"
                elif (
                    last_voltage is not None
                    and voltage is not None
                    and (voltage - last_voltage) >= voltage_increase_threshold
                ):
                    terminated = "voltage_increase"
                elif voltage is not None and voltage <= low_batt_threshold:
                    terminated = "low_voltage"

                if terminated is not None:
                    end_time = current_time
                    end_voltage = voltage
                    duration = end_time - start_time  # type: ignore[operator]

                    # --------------------|  Discharge quality filter  |--------------------
                    if (
                        start_voltage is not None
                        and end_voltage is not None
                        and duration >= min_duration
                        and (start_voltage - end_voltage) >= min_voltage_drop
                        and start_voltage >= full_batt_threshold
                    ):
                        device_windows.append(
                            DischargeWindow(
                                device_id=device_id,
                                start_time=start_time,  # type: ignore[arg-type]
                                end_time=end_time,
                                duration=duration,
                                start_voltage=start_voltage,
                                end_voltage=end_voltage,
                                start_index=start_index,
                                end_index=idx,
                                terminated_by=terminated,
                            )
                        )

                    window_open = False
                    start_time = None
                    start_voltage = None
                    start_index = -1
                else:
                    # Still inside window, update running state
                    last_time = current_time
                    last_voltage = voltage
                    last_on_charger = on_charger
                    continue

            # No open window; just bump last_* state
            last_time = current_time
            last_voltage = voltage
            last_on_charger = on_charger

        # Handle open-ended window
        if window_open and start_time is not None and last_time is not None:
            end_time = last_time
            end_voltage = last_voltage
            duration = end_time - start_time

            if (
                start_voltage is not None
                and end_voltage is not None
                and duration >= min_duration
                and (start_voltage - end_voltage) >= min_voltage_drop
                and start_voltage >= full_batt_threshold
            ):
                device_windows.append(
                    DischargeWindow(
                        device_id=device_id,
                        start_time=start_time,
                        end_time=end_time,
                        duration=duration,
                        start_voltage=start_voltage,
                        end_voltage=end_voltage,
                        start_index=start_index,
                        end_index=len(rows) - 1,
                        terminated_by="open_ended",
                    )
                )

        if device_windows:
            windows_by_device[device_id] = device_windows

    return windows_by_device
