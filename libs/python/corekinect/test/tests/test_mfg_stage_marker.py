"""Tests for the ``@pytest.mark.mfg_stage`` compound marker.

Manufacturing tests today carry three decorators each:

    @pytest.mark.electrical
    @pytest.mark.sequential
    @pytest.mark.timeout(30)
    def test_01_uvlo(slot, config, report): ...

The compound marker collapses that to one:

    @pytest.mark.mfg_stage("electrical", timeout=30)
    def test_01_uvlo(slot, config, report): ...

Behaviour: at collection time the framework expands ``mfg_stage`` into
the three existing markers so the rest of the pipeline (slot_parallel
group keys, sequential plugin, soft per-test timer) sees what it
already expects. The expansion is hookimpl-based, idempotent, and
keeps the test functions free of decorator stack dressing.
"""

from __future__ import annotations

import textwrap

import pytest

pytest_plugins = ["pytester"]


def _conftest_loading_framework() -> str:
    return textwrap.dedent(
        """
        pytest_plugins = ["corekinect.test.pytest_integration"]
        """
    ).lstrip()


def test_mfg_stage_expands_into_three_markers(pytester: pytest.Pytester) -> None:
    """A test marked ``mfg_stage("electrical", timeout=30)`` should end
    up carrying the three existing markers after collection."""
    pytester.makeconftest(_conftest_loading_framework())
    pytester.makepyfile(test_compound=textwrap.dedent('''
        import json
        import pytest


        @pytest.mark.mfg_stage("electrical", timeout=30)
        def test_one():
            pass


        def test_collected_markers(request):
            # Look up test_one's marker set via collect-only inspection.
            item = next(
                i for i in request.session.items
                if i.name == "test_one"
            )
            names = sorted({m.name for m in item.iter_markers()})
            with open("/tmp/_marker_observation.json", "w") as fh:
                json.dump(names, fh)
    '''))

    result = pytester.runpytest("-q", "-p", "no:cacheprovider", "-p", "no:randomly")
    # Both tests pass: test_one (has decorators) and test_collected_markers
    # (the inspector). No timeout actually fires because plain test_one
    # body returns immediately.
    result.assert_outcomes(passed=2)

    import json
    with open("/tmp/_marker_observation.json") as fh:
        observed = set(json.load(fh))
    assert "electrical" in observed, f"expected 'electrical' in {observed}"
    assert "sequential" in observed, f"expected 'sequential' in {observed}"
    assert "timeout" in observed, f"expected 'timeout' in {observed}"
    # The mfg_stage marker itself remains so corectl validators can
    # still inspect it.
    assert "mfg_stage" in observed


def test_mfg_stage_carries_correct_timeout_value(pytester: pytest.Pytester) -> None:
    """The expanded ``timeout`` marker must use the ``timeout=`` kwarg
    from ``mfg_stage``, not a default.
    """
    pytester.makeconftest(_conftest_loading_framework())
    pytester.makepyfile(test_timeout_value=textwrap.dedent('''
        import json
        import pytest


        @pytest.mark.mfg_stage("post", timeout=265)
        def test_one():
            pass


        def test_inspect(request):
            item = next(i for i in request.session.items if i.name == "test_one")
            timeout_mark = item.get_closest_marker("timeout")
            with open("/tmp/_timeout_observation.json", "w") as fh:
                json.dump({
                    "args": list(timeout_mark.args),
                    "kwargs": dict(timeout_mark.kwargs),
                }, fh)
    '''))

    result = pytester.runpytest("-q", "-p", "no:cacheprovider", "-p", "no:randomly")
    result.assert_outcomes(passed=2)

    import json
    with open("/tmp/_timeout_observation.json") as fh:
        observed = json.load(fh)
    # pytest-timeout accepts ``timeout`` either positional or by kwarg;
    # we set it positionally to match how authors write
    # ``@pytest.mark.timeout(30)``.
    timeout_value = (
        observed["args"][0] if observed["args"] else observed["kwargs"].get("timeout")
    )
    assert timeout_value == 265


def test_mfg_stage_stage_arg_becomes_stage_marker(pytester: pytest.Pytester) -> None:
    """``mfg_stage("fw_flash", ...)`` adds ``@pytest.mark.fw_flash``.

    The stage arg is typically one of ``electrical / fw_flash / post``
    but the helper doesn't enforce a fixed list — any product can
    define its own stages.
    """
    pytester.makeconftest(_conftest_loading_framework())
    pytester.makepyfile(test_stage_arg=textwrap.dedent('''
        import json
        import pytest


        @pytest.mark.mfg_stage("fw_flash", timeout=40)
        def test_one():
            pass


        def test_inspect(request):
            item = next(i for i in request.session.items if i.name == "test_one")
            names = sorted({m.name for m in item.iter_markers()})
            with open("/tmp/_stage_observation.json", "w") as fh:
                json.dump(names, fh)
    '''))

    result = pytester.runpytest("-q", "-p", "no:cacheprovider", "-p", "no:randomly")
    result.assert_outcomes(passed=2)

    import json
    with open("/tmp/_stage_observation.json") as fh:
        observed = set(json.load(fh))
    assert "fw_flash" in observed


def test_mfg_stage_is_idempotent_under_repeated_collection(
    pytester: pytest.Pytester,
) -> None:
    """A second collection pass must not double-add the markers.

    Pytester runs the inner pytest fresh each time so this exercise
    is mostly defensive — but the expansion has historically been a
    source of "marker N times" bugs in plugin code.
    """
    pytester.makeconftest(_conftest_loading_framework())
    pytester.makepyfile(test_idempotent=textwrap.dedent('''
        import json
        import pytest


        @pytest.mark.mfg_stage("post", timeout=30)
        def test_one():
            pass


        def test_inspect(request):
            item = next(i for i in request.session.items if i.name == "test_one")
            counts = {}
            for m in item.iter_markers():
                counts[m.name] = counts.get(m.name, 0) + 1
            with open("/tmp/_idempotent_observation.json", "w") as fh:
                json.dump(counts, fh)
    '''))

    result = pytester.runpytest("-q", "-p", "no:cacheprovider", "-p", "no:randomly")
    result.assert_outcomes(passed=2)

    import json
    with open("/tmp/_idempotent_observation.json") as fh:
        counts = json.load(fh)
    assert counts.get("post", 0) == 1, f"'post' marker added more than once: {counts}"
    assert counts.get("sequential", 0) == 1
    assert counts.get("timeout", 0) == 1
