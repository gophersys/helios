import pytest

from ..src.progress import progress_bar


def test_progress_bar_zero():
    bar, percent = progress_bar(0, 100)
    assert bar.startswith("[")
    assert bar.endswith("] 0.0%\t\t")
    assert percent == 0.0


def test_progress_bar_half():
    bar, percent = progress_bar(50, 100, "Halfway")
    assert bar.count("=") == 30  # 60 * 50/100 = 30
    assert "Halfway" in bar
    assert percent == 50.0


def test_progress_bar_complete():
    bar, percent = progress_bar(100, 100, "Done")
    assert bar.count("=") == 60
    assert "Done" in bar
    assert percent == 100.0


def test_progress_bar_overflow():
    bar, percent = progress_bar(120, 100, "Overflow")
    assert bar.count("=") == 60  # Maximum filled length
    assert "Overflow" in bar
    assert percent == 100.0  # Capped at 100%


def test_progress_bar_negative():
    bar, percent = progress_bar(-10, 100, "Negative")
    assert bar.count("=") == 0
    assert "Negative" in bar
    assert percent == -10.0
