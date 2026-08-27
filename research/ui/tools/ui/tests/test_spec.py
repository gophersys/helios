import pathlib
import re
import tomllib

import pytest

from ui.spec import SpecError, load_panel

DOC = pathlib.Path(__file__).resolve().parents[3] / "docs" / "spec.md"


def doc_example(font_path):
    m = re.search(r"```toml\n(.*?)```", DOC.read_text(), re.DOTALL)
    return tomllib.loads(m.group(1).replace("FONT", font_path))


def test_docs_example_validates(font_path):
    assert load_panel(doc_example(font_path))["panel"]["name"] == "example"


def test_typo_gets_a_suggestion(font_path):
    data = doc_example(font_path)
    u = data["solve"]["knob_rows"]["main"]["units"][0]
    u["widst"] = u.pop("widest")
    with pytest.raises(SpecError) as exc:
        load_panel(data)
    msg = str(exc.value)
    assert "units[0]: unknown key 'widst' (did you mean 'widest'?)" in msg
    assert "missing required key 'widest'" in msg


def test_all_errors_reported_at_once(font_path):
    data = doc_example(font_path)
    data["panle"] = data.pop("panel")  # top-level typo
    data["ratio"]["panel_w"] = 800  # bad ratio row
    with pytest.raises(SpecError) as exc:
        load_panel(data)
    errs = exc.value.errors
    assert any("panle" in e and "panel" in e for e in errs)
    assert any("ratio.panel_w" in e for e in errs)
    assert len(errs) >= 3  # incl. missing required panel


def test_missing_font_path_named(font_path):
    data = doc_example(font_path)
    data["font"]["path"] = "/nope/absent.ttf"
    with pytest.raises(SpecError, match="does not exist"):
        load_panel(data)
