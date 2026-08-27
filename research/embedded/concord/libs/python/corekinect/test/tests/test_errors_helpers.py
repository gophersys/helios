"""Tests for :mod:`corekinect.test.errors` message helpers.

The helpers keep skip/fail messages consistent across the framework:
every call site says "VAR_NAME not set — cannot PURPOSE" the same
way, so logs and operator tooling can pattern-match on structure.
"""

from __future__ import annotations

import pytest

from corekinect.test.errors import (
    bad_testbed_class,
    missing_env_var,
)


class TestMissingEnvVar:
    """``missing_env_var`` formats the standard skip/fail prefix."""

    def test_basic_form_names_var_and_purpose(self) -> None:
        msg = missing_env_var("MTIB_ADDRESS", "connect to hardware")
        assert msg == "MTIB_ADDRESS not set — cannot connect to hardware."

    def test_alternatives_are_listed_after_the_sentence(self) -> None:
        msg = missing_env_var(
            "MTIB_HOSTS",
            "enumerate slots",
            alternatives=("MTIB_HOST", "FIXTURE_CONFIG_PATH"),
        )
        assert msg == (
            "MTIB_HOSTS not set — cannot enumerate slots. "
            "Alternatives: MTIB_HOST, FIXTURE_CONFIG_PATH."
        )

    def test_empty_alternatives_are_silent(self) -> None:
        msg = missing_env_var("DEVICE_ID", "create context", alternatives=("",))
        assert msg == "DEVICE_ID not set — cannot create context."
        assert "Alternatives" not in msg

    def test_hint_appended_last_when_present(self) -> None:
        msg = missing_env_var(
            "DEVICE_ID",
            "create context",
            hint="run `corectl auth login`",
        )
        assert msg.endswith("Hint: run `corectl auth login`.")
        # Hint comes after purpose, not before.
        assert msg.index("not set") < msg.index("Hint")

    def test_alternatives_and_hint_coexist_in_order(self) -> None:
        msg = missing_env_var(
            "MTIB_HOSTS",
            "enumerate slots",
            alternatives=("MTIB_HOST",),
            hint="check your K8s runner deployment env",
        )
        assert msg == (
            "MTIB_HOSTS not set — cannot enumerate slots. "
            "Alternatives: MTIB_HOST. "
            "Hint: check your K8s runner deployment env."
        )

    def test_returns_a_plain_string_not_an_exception(self) -> None:
        # The helper formats messages; callers decide raise vs skip.
        assert isinstance(missing_env_var("X", "y"), str)


class TestBadTestBedClass:
    """``bad_testbed_class`` surfaces both module reference and root cause."""

    def test_names_path_and_wrapped_exception_type(self) -> None:
        cause = ImportError("No module named 'missing'")
        msg = bad_testbed_class("app.fake:TestBed", cause)
        assert "app.fake:TestBed" in msg
        assert "ImportError" in msg
        assert "No module named 'missing'" in msg

    def test_works_for_non_import_errors_too(self) -> None:
        # A circular import surfaces as AttributeError inside _import_testbed_class;
        # the helper shouldn't assume the cause type.
        cause = AttributeError("module has no attribute 'TestBed'")
        msg = bad_testbed_class("app.fake:TestBed", cause)
        assert "AttributeError" in msg
        assert "module has no attribute" in msg

    def test_does_not_swallow_path_when_cause_is_empty(self) -> None:
        class _Bare(Exception):
            pass

        msg = bad_testbed_class("pkg:Thing", _Bare())
        assert "pkg:Thing" in msg
        assert "_Bare" in msg
