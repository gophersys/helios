"""Font metrics from the TTF itself — the only legal source of text size (A-1).

px = units / unitsPerEm * size. Advances are exact per string; cap height and
ascent/descent come from OS/2. A missing glyph raises — never a guessed width.

WHICH TTF is part of the same question, so it lives here too: resolve_path()
is the one ladder every build and every audit walks, and font_face_css() puts
those exact bytes in the page. A family name resolves to different files on
different hosts, or to nothing at all without erroring; bytes do not.
"""

from __future__ import annotations

import base64
import os
import pathlib

from fontTools.ttLib import TTFont

# Faces a host is known to carry, in the order the demo builds have always
# tried them: a Mac has Arial, the CI image ships fonts-dejavu-core. A declared
# [font].path is the panel's truth but names ONE host's filesystem —
# demos/telemetry declares the container's DejaVu and is built on a Mac daily.
PRESENT_FALLBACKS = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


class FontError(RuntimeError):
    pass


def resolve_path(declared: str | None = None) -> str:
    """The TTF this host solves, embeds and judges with — one ladder for all
    three. A page built from the environment's face while the audit resolved
    the declared one would be compared against a face nothing ever used, and
    ui.audit.check_font_identity would fail for a reason that is not a
    defect."""
    for cand in (os.environ.get("UI_FONT"), declared, *PRESENT_FALLBACKS):
        if cand and pathlib.Path(cand).exists():
            return cand
    raise FontError(
        f"no usable font: UI_FONT unset or absent, declared {declared!r} absent, "
        f"and none of {PRESENT_FALLBACKS} exists — set UI_FONT"
    )


def font_face_css(family: str, path: str | pathlib.Path, weight: str = "400") -> str:
    """`path`'s bytes as an @font-face rule, inlined as a data URI.

    The page then renders the face it was SOLVED with by construction, on every
    host, which is what turns check_font_identity into a statement about the
    panel instead of about what the machine happens to have installed."""
    b64 = base64.b64encode(pathlib.Path(path).read_bytes()).decode()
    return (
        f"@font-face {{ font-family: '{family}'; font-style: normal; "
        f"font-weight: {weight}; font-display: block; "
        f"src: url(data:font/ttf;base64,{b64}) format('truetype'); }}"
    )


class Face:
    def __init__(self, path: str, font_number: int = 0):
        self.font = TTFont(path, fontNumber=font_number)
        self.upm = self.font["head"].unitsPerEm
        os2 = self.font["OS/2"]
        self.cap_units = getattr(os2, "sCapHeight", None) or int(self.upm * 0.7)
        self.ascent_units = os2.sTypoAscender
        self.descent_units = os2.sTypoDescender
        self._cmap = self.font.getBestCmap()
        self._hmtx = self.font["hmtx"]

    def adv(self, text: str, px: float) -> float:
        total = 0
        for ch in text:
            glyph = self._cmap.get(ord(ch))
            if glyph is None:
                raise KeyError(f"{self!r}: no glyph for {ch!r}")
            total += self._hmtx[glyph][0]
        return total * px / self.upm

    def cap(self, px: float) -> float:
        return self.cap_units * px / self.upm

    def metrics(self, px: float = 16.0) -> dict:
        """Per-face table (typo-math appendix): everything the calculus uses,
        plus the cap-centring correction dy = (cap - A' + D')/2 in px — the
        amount box-centred text sits off true cap-centre in THIS face."""
        u = px / self.upm
        asc, desc, cap = self.ascent_units * u, self.descent_units * u, self.cap_units * u
        xh = getattr(self.font["OS/2"], "sxHeight", None)
        return {
            "upm": self.upm,
            "cap_em": round(self.cap_units / self.upm, 4),
            "xh_em": round(xh / self.upm, 4) if xh else None,
            "ascent_px": round(asc, 2),
            "descent_px": round(desc, 2),
            "cap_px": round(cap, 2),
            "centring_dy_px": round((cap - asc - desc) / 2, 2),
        }
