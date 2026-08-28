from corekinect.core_cloud.messages import PositionMsgV6
import math
import pandas as pd
import pytest
from pathlib import Path
from dataclasses import fields
from typing import Annotated, get_args, get_origin, get_type_hints

from corekinect.core_cloud.messages import PositionMsgV6
from corekinect.utils import Logger
from corekinect.core_cloud.unified_core.db_map import db_translation, SCHEMA_BY_ENV, Env
from corekinect.utils.serde.convert import convert_str_to_type  # your shared converter


def test_position_msg_v6_from_csv_matches_pandas(csv_file_path: str | Path, env: Env = "VAL_1_0"):
    """Test position msg v6 from csv matches pandas."""
    log = Logger(log_name=test_position_msg_v6_from_csv_matches_pandas.__name__)
    assert csv_file_path.exists(), f"csv_file_path does not exist: {csv_file_path}"

    schema = SCHEMA_BY_ENV[env]

    # --------------------|  Load CSV with pandas  |--------------------
    df = pd.read_csv(csv_file_path)

    # --------------------|  Load CSV with message parser  |--------------------
    msgs = PositionMsgV6.from_csv_file(csv_file_path, env=env)

    assert len(msgs) == len(df), f"CSV row count = {len(df)} does not match message count = {len(msgs)}"

    type_hints = get_type_hints(PositionMsgV6, include_extras=True)

    # --------------------|  Row-by-row comparison  |--------------------
    for idx, msg in enumerate(msgs):
        row = df.iloc[idx]

        for f in fields(PositionMsgV6):
            if not f.init:
                continue  # skip non-init dc fields

            field_type = type_hints.get(f.name, f.type)

            # --------------------|  Resolve CSV column name |--------------------
            column_name = f.name
            if get_origin(field_type) is Annotated:
                metadata_items = get_args(field_type)[1:]
                for item in metadata_items:
                    if isinstance(item, db_translation):
                        mapped = item.by_schema.get(schema)
                        if mapped:
                            column_name = mapped
                        break

            # --------------------|  Column missing in CSV? |--------------------
            if column_name not in df.columns:
                log.warning(
                    f"CSV missing column '{column_name}' for field '{f.name}'. " f"Skipping comparison for this field."
                )
                continue  # skip this field entirely

            # --------------------|  Extract raw CSV value |--------------------
            raw = row[column_name]

            # Normalize NaN / NaT / None
            if raw is None or (isinstance(raw, float) and math.isnan(raw)):
                raw_str = None
            else:
                raw_str = str(raw)

            # --------------------|  Convert expected value |--------------------
            expected_value = convert_str_to_type(raw_str, field_type)

            # --------------------|  Get actual value |--------------------
            actual_value = getattr(msg, f.name)

            # --------------------|  Compare values |--------------------
            if isinstance(expected_value, float) or isinstance(actual_value, float):
                # both None → OK
                if expected_value is None and actual_value is None:
                    continue

                assert math.isclose(expected_value, actual_value, rel_tol=1e-9, abs_tol=1e-9), (
                    f"[Row {idx}] Float mismatch for field '{f.name}': "
                    f"expected={expected_value}, actual={actual_value}"
                )
            else:
                assert expected_value == actual_value, (
                    f"[Row {idx}] Mismatch for field '{f.name}': "
                    f"expected={expected_value!r}, actual={actual_value!r}"
                )


def ad_hoc_testing():
    """Ad hoc testing."""
    last_pos = PositionMsgV6.get_last(dut_id=0x70B3D584C01E1445, env="VAL_1_0")
    print(last_pos.temperature_fahrenheit)
    breakpoint


if __name__ == "__main__":
    test_position_msg_v6_from_csv_matches_pandas(
        Path("test_assets/uid_556_pos_csv_import.csv"),
        "DEV_0_9",
    )
