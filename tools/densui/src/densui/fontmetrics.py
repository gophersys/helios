"""Font metrics from the TTF itself — the only legal source of text size (A-1).

px = units / unitsPerEm * size. Advances are exact per string; cap height and
ascent/descent come from OS/2. A missing glyph raises — never a guessed width.
"""

from __future__ import annotations

from fontTools.ttLib import TTFont


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
