"""densui.compare — reference-vs-built A/B composites.

The ratio audit catches geometry drift; only a side-by-side composite catches
wrong component anatomy, structure and typeface. Each region becomes one
image: reference on top, build below, NEAREST-upscaled, split by a divider.
Requires the [measure] extra (Pillow).
"""

from __future__ import annotations

import pathlib

from densui.measure import _pil, sample

DIVIDER = (200, 40, 40)


def find_color_row(img, x: int, color: str, tol: int = 4) -> int | None:
    """First y where pixel (x, y) matches color within tol per channel — the
    locator trick for finding a device's top edge in a page screenshot."""
    want = tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))
    px = img.load()
    for y in range(img.height):
        got = px[x, y][:3]
        if all(abs(g - w) <= tol for g, w in zip(got, want)):
            return y
    return None


def side_by_side(
    ref,
    built,
    regions: dict[str, tuple[int, int, int, int]],
    out_dir: str | pathlib.Path,
    *,
    scale: int = 2,
    divider: int = 8,
) -> dict[str, pathlib.Path]:
    """For each named region (same box in both images): stack ref above built,
    upscale NEAREST, save cmp_<name>.png. Returns {name: path}."""
    image_mod, _ = _pil()
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, pathlib.Path] = {}
    for name, (x0, y0, x1, y1) in regions.items():
        w, h = x1 - x0, y1 - y0
        a = ref.crop((x0, y0, x1, y1)).resize((w * scale, h * scale), image_mod.NEAREST)
        b = built.crop((x0, y0, x1, y1)).resize((w * scale, h * scale), image_mod.NEAREST)
        canvas = image_mod.new("RGB", (w * scale, h * scale * 2 + divider), DIVIDER)
        canvas.paste(a, (0, 0))
        canvas.paste(b, (0, h * scale + divider))
        path = out_dir / f"cmp_{name}.png"
        canvas.save(path)
        written[name] = path
    return written


__all__ = ["DIVIDER", "find_color_row", "sample", "side_by_side"]
