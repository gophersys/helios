"""densui.measure — reference forensics: measure a bitmap, never eyeball it.

The toolkit that replaced visual judgement in the founding session: exact
colour sampling, luminance run-length scans (find edges, plates, rings),
region statistics (darkest/lightest/dominant colours), and NEAREST-upscaled
zoom crops with labelled gridlines for anatomy reading. Requires the
[measure] extra (Pillow); importing without it fails loudly at call time.
"""
from __future__ import annotations

from collections import Counter


def _pil():
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:                      # pragma: no cover
        raise RuntimeError(
            "densui.measure needs Pillow — install densui[measure]") from exc
    return Image, ImageDraw


def load(path):
    image_mod, _ = _pil()
    return image_mod.open(path).convert("RGB")


def sample(img, x: int, y: int) -> str:
    r, g, b = img.load()[x, y][:3]
    return f"#{r:02x}{g:02x}{b:02x}"


def _lum(px, x, y) -> float:
    r, g, b = px[x, y][:3]
    return 0.299 * r + 0.587 * g + 0.114 * b


def dark_runs(img, *, y: int, threshold: float, x0: int = 0, x1: int | None = None,
              min_width: int = 2) -> list[tuple[int, int]]:
    """Horizontal runs of pixels darker than threshold on row y: [(start, end)]."""
    px = img.load()
    x1 = img.width if x1 is None else x1
    runs, start = [], None
    for x in range(x0, x1):
        dark = _lum(px, x, y) < threshold
        if dark and start is None:
            start = x
        if not dark and start is not None:
            if x - start >= min_width:
                runs.append((start, x - 1))
            start = None
    if start is not None and x1 - start >= min_width:
        runs.append((start, x1 - 1))
    return runs


def level_bands(img, *, x: int, y0: int = 0, y1: int | None = None,
                quantize: int = 16, min_height: int = 2) -> list[tuple[int, int, int]]:
    """Vertical run-length bands of quantised luminance on column x:
    [(start, end, level)] — the scan that found plates, gaps and title strips."""
    px = img.load()
    y1 = img.height if y1 is None else y1
    bands, last, start = [], None, y0
    for y in range(y0, y1):
        lvl = int(_lum(px, x, y)) // quantize
        if lvl != last:
            if last is not None and y - start >= min_height:
                bands.append((start, y - 1, last * quantize))
            last, start = lvl, y
    if last is not None and y1 - start >= min_height:
        bands.append((start, y1 - 1, last * quantize))
    return bands


def region_stats(img, box: tuple[int, int, int, int], top: int = 5) -> dict:
    """Darkest/lightest pixel (colour + position) and dominant colours in box."""
    px = img.load()
    x0, y0, x1, y1 = box
    darkest = (1e9, None, None)
    lightest = (-1.0, None, None)
    counts: Counter = Counter()
    for y in range(y0, y1):
        for x in range(x0, x1):
            lum = _lum(px, x, y)
            if lum < darkest[0]:
                darkest = (lum, sample(img, x, y), (x, y))
            if lum > lightest[0]:
                lightest = (lum, sample(img, x, y), (x, y))
            counts[sample(img, x, y)] += 1
    return {"darkest": darkest[1], "darkest_at": darkest[2],
            "lightest": lightest[1], "lightest_at": lightest[2],
            "top": counts.most_common(top)}


def zoom(img, box: tuple[int, int, int, int], out, *, scale: int = 8,
         grid_step: int | None = None, grid_divisor: float = 1.0) -> None:
    """NEAREST-upscale a crop for anatomy reading; optional red gridlines every
    grid_step source px, labelled in source units / grid_divisor (e.g. 2 for a
    @2x screenshot labelled in CSS px)."""
    image_mod, draw_mod = _pil()
    x0, y0, x1, y1 = box
    crop = img.crop(box).resize(((x1 - x0) * scale, (y1 - y0) * scale),
                                image_mod.NEAREST)
    if grid_step:
        d = draw_mod.Draw(crop)
        for gx in range(0, x1 - x0, grid_step):
            d.line([(gx * scale, 0), (gx * scale, crop.height)], fill=(255, 0, 0))
            d.text((gx * scale + 2, 2), str(int(gx / grid_divisor)), fill=(255, 0, 0))
        for gy in range(0, y1 - y0, grid_step):
            d.line([(0, gy * scale), (crop.width, gy * scale)], fill=(255, 0, 0))
            d.text((2, gy * scale + 2), str(int(gy / grid_divisor)), fill=(255, 0, 0))
    crop.save(out)
