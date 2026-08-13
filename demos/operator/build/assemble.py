#!/usr/bin/env python3
"""Assemble operator.html from shell.html + modules + base64 brand fonts.

Fail-loud: any missing file, missing placeholder, duplicate placeholder,
'</script>' inside a JS module, failed node --check, or failed params
self-test aborts with a non-zero exit and a named cause.
"""
import base64
import pathlib
import subprocess
import sys

BUILD = pathlib.Path(__file__).resolve().parent
OUT = BUILD.parent / "operator.html"
FONTS = pathlib.Path.home() / "Library" / "Fonts"

MODULES = {
    "/* @PARAMS_JS@ */": BUILD / "params.js",
    "/* @ENGINE_JS@ */": BUILD / "engine.js",
    "/* @WIDGETS_JS@ */": BUILD / "widgets.js",
    "/* @DISPLAY_JS@ */": BUILD / "display.js",
    "/* @APP_JS@ */": BUILD / "app.js",
}
CSS = {"/* @WIDGETS_CSS@ */": BUILD / "widgets.css"}

ABLETON_FONTS = pathlib.Path("/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Fonts")
FONT_FACES = [
    ("Fraunces", FONTS / "Fraunces-VariableFont_SOFT,WONK,opsz,wght.ttf", "100 900"),
    ("Inter", FONTS / "Inter-VariableFont_opsz,wght.ttf", "100 900"),
    ("JetBrains Mono", FONTS / "JetBrainsMono-VariableFont_wght.ttf", "100 900"),
    # Mateo's licensed Live 12 install; private artifact, personal use
    ("Ableton Sans Small", ABLETON_FONTS / "AbletonSansSmall-Regular.ttf", "400"),
    ("Ableton Sans Small", ABLETON_FONTS / "AbletonSansSmall-Bold.ttf", "700"),
]


def die(msg: str) -> None:
    print(f"ASSEMBLE FAILED: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    shell = (BUILD / "shell.html").read_text()

    # 1. Gate: node --check every module, then run the params self-test.
    for ph, path in MODULES.items():
        if not path.exists():
            die(f"missing module {path.name}")
        r = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        if r.returncode != 0:
            die(f"node --check {path.name}: {r.stderr.strip()}")
    r = subprocess.run(["node", str(BUILD / "params.js")], capture_output=True, text=True)
    if r.returncode != 0 or "PASS" not in r.stdout:
        die(f"params self-test: rc={r.returncode} out={r.stdout.strip()!r} err={r.stderr.strip()!r}")
    print(f"params self-test: {r.stdout.strip()}")

    # 2. Inline CSS + JS modules.
    for table, kind in ((CSS, "css"), (MODULES, "js")):
        for ph, path in table.items():
            body = path.read_text()
            if not body.strip():
                die(f"{path.name} is empty")
            if kind == "js" and "</script>" in body:
                die(f"{path.name} contains literal </script>")
            if shell.count(ph) != 1:
                die(f"placeholder {ph} count != 1 in shell.html")
            shell = shell.replace(ph, body)

    # 3. Inline fonts.
    faces = []
    for family, path, weight in FONT_FACES:
        if not path.exists():
            die(f"missing font {path}")
        b64 = base64.b64encode(path.read_bytes()).decode()
        faces.append(
            f"@font-face {{ font-family: '{family}'; font-style: normal; "
            f"font-weight: {weight}; font-display: block; "
            f"src: url(data:font/ttf;base64,{b64}) format('truetype'); }}"
        )
    if shell.count("/* @FONTS_CSS@ */") != 1:
        die("font placeholder count != 1")
    shell = shell.replace("/* @FONTS_CSS@ */", "\n".join(faces))

    OUT.write_text(shell)
    mb = OUT.stat().st_size / 1e6
    if mb > 15.0:
        die(f"operator.html is {mb:.1f} MB — over the artifact budget")
    print(f"wrote {OUT} ({mb:.2f} MB)")

    # Solved positions — geometry is computed, never hand-written.
    r = subprocess.run(["uv", "run", "--with", "fonttools", "python3",
                        str(BUILD / "solve_layout.py")], capture_output=True, text=True)
    if r.returncode != 0:
        die(f"layout solver failed: {r.stderr.strip()}")
    out_text = OUT.read_text()
    if out_text.count("/* @SOLVED_POSITIONS@ */") != 1:
        die("solved-positions placeholder count != 1")
    OUT.write_text(out_text.replace("/* @SOLVED_POSITIONS@ */", r.stdout))

    # Gate 2 ratio audit — geometry drift fails the build.
    r = subprocess.run(["python3", str(BUILD / "ratio_audit.py")], text=True)
    if r.returncode != 0:
        die("ratio audit failed")

    # Overlap audit — any illegal glyph/box intersection fails the build.
    r = subprocess.run(["python3", str(BUILD / "overlap_audit.py")], text=True)
    if r.returncode != 0:
        die("overlap audit failed")

    # Content sweep — same proofs with every value at its widest string.
    r = subprocess.run(["python3", str(BUILD / "overlap_audit.py"), "--sweep"], text=True)
    if r.returncode != 0:
        die("content sweep failed")


if __name__ == "__main__":
    main()
