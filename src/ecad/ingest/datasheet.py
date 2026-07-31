"""Targeted datasheet extraction: section slicing + gated LLM candidates.

De-legacies ``src/pipeline/datasheet_parser.py``. Instead of handing a whole
PDF to the LLM (and silently falling back to hardcoded chips), this module

1. locates the pin / strapping / electrical (and peripherals) chapters
   deterministically with ``pdftotext -layout`` per page (``-f``/``-l``),
   using the running-page-header strategy and heading whitelist validated
   in ``data/datasheets/SECTIONS.md`` (Chinese editions are the primary
   pattern set, English the exception; both strapping-era chapter namings
   are matched; TOC/List-of-Tables repeats are rejected),
2. sends ONLY those pages to an injectable ``runner`` callable (default:
   Claude CLI ``claude --print``; three attempts, markdown-fence
   stripping), asking for JSON in the legacy datasheet_parser schema plus
   strapping notes,
3. gates the returned JSON through deterministic validation (pad
   uniqueness, non-empty pin table, parseable electrical types) before any
   typed object is built.

There are NO hardcoded chip fallbacks: a part that cannot be extracted
raises instead of degrading silently.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..model import ElectricalType, PinRole, PinSpec

Runner = Callable[[str], str]

PDFTOTEXT_TIMEOUT = 120
CLAUDE_TIMEOUT = 300
EXTRACT_ATTEMPTS = 3


class DatasheetError(Exception):
    """Base error for this module."""


class SectionNotFound(DatasheetError):
    """A mandatory chapter (pins/electrical) could not be located."""


class ExtractionFailed(DatasheetError):
    """The runner produced no parseable JSON within the attempt budget."""


class ValidationFailed(DatasheetError):
    """The candidate JSON failed the deterministic schema gate."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


# -------------------------------------------------------------------------
# Typed extraction result
# -------------------------------------------------------------------------

@dataclass(frozen=True)
class PageRange:
    """Inclusive 1-based PDF page range (pdftotext page indices)."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 1 or self.end < self.start:
            raise ValueError(f"invalid PageRange({self.start}, {self.end})")

    def pages(self) -> range:
        return range(self.start, self.end + 1)

    @property
    def count(self) -> int:
        return self.end - self.start + 1


@dataclass(frozen=True)
class CapSpec:
    value: str
    purpose: str = ""


@dataclass(frozen=True)
class PowerSpec:
    voltage_min: float = 0.0
    voltage_typ: float = 0.0
    voltage_max: float = 0.0
    power_pins: tuple[str, ...] = ()
    decoupling_caps: tuple[CapSpec, ...] = ()


@dataclass(frozen=True)
class ExtractedPin:
    """One extracted pad: the typed PinSpec plus datasheet-only fields."""

    spec: PinSpec
    group: str
    raw_type: str


@dataclass(frozen=True)
class Provenance:
    pdf_name: str
    pdf_sha256: str
    pages_used: tuple[int, ...]
    page_count: int

    @property
    def ratio(self) -> float:
        """Fraction of the PDF that was sent to the LLM."""
        return len(self.pages_used) / self.page_count if self.page_count else 0.0


@dataclass(frozen=True)
class ExtractedPart:
    chip_name: str
    manufacturer: str
    description: str
    package: str
    pins: tuple[ExtractedPin, ...]
    power: PowerSpec
    strapping_pins: tuple[str, ...]
    strapping_notes: tuple[str, ...]
    provenance: Provenance

    def pin_specs(self) -> tuple[PinSpec, ...]:
        return tuple(p.spec for p in self.pins)


# -------------------------------------------------------------------------
# pdftotext access (deterministic, cached per page)
# -------------------------------------------------------------------------

@lru_cache(maxsize=8192)
def _page_text(pdf: str, page: int) -> str | None:
    """Extract one page with ``pdftotext -layout -f N -l N``; None if out of range."""
    proc = subprocess.run(
        ["pdftotext", "-layout", "-f", str(page), "-l", str(page), pdf, "-"],
        capture_output=True, text=True, timeout=PDFTOTEXT_TIMEOUT,
    )
    return proc.stdout if proc.returncode == 0 else None


def _page_count(pdf: str) -> int:
    n = 1
    while _page_text(pdf, n) is not None:
        n += 1
    return n - 1


# -------------------------------------------------------------------------
# Section finder (SECTIONS.md running-page-header strategy)
# -------------------------------------------------------------------------

# TOC/List-of-Tables repeats: trailing right-aligned page number or dot leader.
_TOC_LINE = re.compile(r"\s{2,}\d{1,3}\s*$|\.{3,}")

# Whitelisted full-line-anchored headings (zh primary, en alternations).
_TOP_TITLES = {
    "pins": r"管脚定义|管脚|Pins",
    "strapping": r"启动配置项|Boot\s+Configurations",
    "electrical": r"电气特性|Electrical\s+Characteristics",
    "peripherals": r"外设接口和传感器|外设",
}
_TOP = {k: re.compile(rf"^\s{{0,10}}(\d+)\s+({v})\s*$") for k, v in _TOP_TITLES.items()}
_SUB_STRAPPING = re.compile(r"^\s{0,10}(\d+\.\d+)\s+(Strapping\s*(?:管脚|Pins))\s*$")
_SUB_PERIPH_MODERN = re.compile(r"^\s{0,10}(\d+\.\d+)\s+(外设|Peripherals)\s*$")
_SUB_PERIPH_LEGACY = re.compile(r"^\s{0,10}(\d+\.\d+)\s+(模拟外设|数字外设)\s*$")
_WIRELESS_BOUNDARY = re.compile(
    r"^\s{0,10}(\d+(?:\.\d+)?)\s+(无线通信|Wireless\s+Communication)\s*$")
# RF subsections embedded in legacy/slim electrical chapters (trim point).
_RF_SUBHEADING = re.compile(
    r"^\s{0,10}\d+\.\d+(?:\.\d+)*\s+(?:Wi-?Fi\s*射频|低功耗蓝牙射频|蓝牙射频|射频)")


def _find_heading(pdf: str, pattern: re.Pattern[str], start: int = 1,
                  end: int | None = None) -> tuple[int, str, str] | None:
    """First page whose body has a whitelisted heading; (page, number, title)."""
    page = start
    while end is None or page <= end:
        text = _page_text(pdf, page)
        if text is None:
            return None
        for line in text.splitlines():
            if _TOC_LINE.search(line):
                continue
            m = pattern.match(line)
            if m:
                return page, m.group(1), " ".join(m.group(2).split())
        page += 1
    return None


def _header_matches(pdf: str, page: int, number: str, title: str) -> bool:
    """True if the running header (first non-blank line) repeats ``N Title``."""
    text = _page_text(pdf, page)
    if text is None:
        return False
    for line in text.splitlines():
        if line.strip():
            return " ".join(line.split()) == f"{number} {title}"
    return False


def _page_continues(text: str, number: str) -> bool:
    """Chapter-continuation fallback for pages without the running header.

    Legacy esp32.pdf prints rotated pin-table pages with a logo line instead
    of the chapter header. A page still belongs to chapter N unless the next
    chapter's own top-level heading (``N+1 <Title>``, title not starting
    with a digit — pin rows and footnotes mimic numbered headings) shows up.
    """
    nxt = re.compile(rf"^\s*{int(number) + 1}\s+[^\d\s.].*$")
    for line in text.splitlines():
        if _TOC_LINE.search(line):
            continue
        if nxt.match(line):
            return False
    return True


def _chapter_range(pdf: str, start: int, number: str, title: str) -> PageRange:
    """Extend from the heading page while pages keep belonging to the chapter.

    Primary signal: the running header repeats ``N Title`` atop every page.
    Fallback (SECTIONS.md): stop at the page carrying the next top-level
    chapter heading.
    """
    end = start
    while True:
        text = _page_text(pdf, end + 1)
        if text is None:
            break
        if _header_matches(pdf, end + 1, number, title) or \
                _page_continues(text, number):
            end += 1
            continue
        break
    return PageRange(start, end)


def find_sections(pdf: Path) -> dict[str, PageRange]:
    """Locate target chapters. Keys: pins, strapping, electrical, peripherals.

    ``pins`` and ``electrical`` are mandatory (SectionNotFound otherwise);
    ``strapping`` falls back from the modern top-level chapter to the legacy
    ``N.M Strapping ...`` subsection inside the pins chapter; ``peripherals``
    is omitted for slim-module datasheets that defer to the chip datasheet.
    """
    pdf = Path(pdf)
    if not pdf.is_file():
        raise FileNotFoundError(f"no such PDF: {pdf}")
    doc = str(pdf)
    sections: dict[str, PageRange] = {}

    hit = _find_heading(doc, _TOP["pins"])
    if hit is None:
        raise SectionNotFound(f"{pdf.name}: no pins chapter found")
    pins = _chapter_range(doc, *hit)
    sections["pins"] = pins

    hit = _find_heading(doc, _TOP["electrical"], start=pins.end)
    if hit is None:
        raise SectionNotFound(f"{pdf.name}: no electrical chapter found")
    electrical = _chapter_range(doc, *hit)

    # Strapping: modern top-level chapter, else legacy subsection of pins.
    hit = _find_heading(doc, _TOP["strapping"], start=pins.end,
                        end=electrical.start - 1)
    if hit is not None:
        sections["strapping"] = _chapter_range(doc, *hit)
    else:
        sub = _find_heading(doc, _SUB_STRAPPING, start=pins.start, end=pins.end)
        if sub is not None:
            sections["strapping"] = PageRange(sub[0], pins.end)

    sections["electrical"] = electrical

    periph = _find_peripherals(doc, pins, electrical)
    if periph is not None:
        sections["peripherals"] = periph
    return sections


def _find_peripherals(doc: str, pins: PageRange,
                      electrical: PageRange) -> PageRange | None:
    """Peripherals live between pins and electrical, in one of three shapes."""
    lo, hi = pins.end, electrical.start - 1
    if hi < lo:
        return None
    top = _find_heading(doc, _TOP["peripherals"], start=lo, end=hi)
    if top is not None:
        return _chapter_range(doc, *top)
    modern = _find_heading(doc, _SUB_PERIPH_MODERN, start=lo, end=hi)
    legacy = _find_heading(doc, _SUB_PERIPH_LEGACY, start=lo, end=hi)
    if modern is not None and (legacy is None or modern[0] <= legacy[0]):
        wireless = _find_heading(doc, _WIRELESS_BOUNDARY, start=modern[0], end=hi)
        return PageRange(modern[0], wireless[0] if wireless else hi)
    if legacy is not None:
        # Scattered legacy subsections run up to the electrical chapter.
        return PageRange(legacy[0], hi)
    return None


# -------------------------------------------------------------------------
# Slicing
# -------------------------------------------------------------------------

def _slice(pdf: Path, sections: dict[str, PageRange]) -> tuple[str, tuple[int, ...]]:
    """Render the pin/strapping/electrical pages; RF-trim the electrical tail."""
    for key in ("pins", "electrical"):
        if key not in sections:
            raise SectionNotFound(f"slice_text needs a {key!r} section")
    doc = str(Path(pdf))
    electrical = sections["electrical"]
    keep = [sections[k] for k in ("pins", "strapping") if k in sections]
    non_elec = {p for r in keep for p in r.pages()}
    pages = sorted(non_elec | set(electrical.pages()))

    # Locate the first RF subheading inside the electrical chapter.
    trim: tuple[int, int] | None = None
    for page in electrical.pages():
        lines = (_page_text(doc, page) or "").splitlines()
        for i, line in enumerate(lines):
            if _RF_SUBHEADING.match(line) and not _TOC_LINE.search(line):
                trim = (page, i)
                break
        if trim:
            break

    chunks: list[str] = []
    used: list[int] = []
    for page in pages:
        text = _page_text(doc, page) or ""
        if trim is not None and page not in non_elec:
            if page > trim[0]:
                continue  # electrical-only page after the RF cut
            if page == trim[0]:
                lines = text.splitlines()[:trim[1]]
                if sum(1 for ln in lines if ln.strip()) < 2:
                    continue  # only the running header precedes the RF heading
                text = "\n".join(lines)
        chunks.append(f"===== [{Path(pdf).name} p.{page}] =====\n"
                      f"{text.rstrip(chr(12) + chr(10))}\n")
        used.append(page)
    return "\n".join(chunks), tuple(used)


def slice_text(pdf: Path, sections: dict[str, PageRange]) -> str:
    """Text of only the pin/strapping/electrical pages (RF tail trimmed)."""
    return _slice(pdf, sections)[0]


# -------------------------------------------------------------------------
# Extraction prompt + runner
# -------------------------------------------------------------------------

_SCHEMA_PROMPT = """\
The text below was sliced from the pin-definition, strapping/boot-configuration
and electrical-characteristics chapters of a component datasheet (pdftotext
-layout output; the original may be Chinese). Using ONLY this text, extract:
1. "chip_name": the chip/module name
2. "manufacturer": manufacturer name
3. "description": one-line description
4. "package": package type (e.g. "SMD-41")
5. "pins": array of objects with keys:
   - "number": pin number (string)
   - "name": primary pin name (bold name / name before any slash)
   - "type": one of "P" (power), "I" (input), "O" (output), "IO" or "I/O"
     (bidirectional), "I/O/T" (bidirectional with tristate)
   - "functions": array of alternate function name strings
   - "group": one of Power, Control, GPIO, UART, SPI, I2C, USB, JTAG, ADC,
     Touch, Camera, SDIO, PWM, Clock, Other
6. "power": object with keys:
   - "voltage_min": number (volts)
   - "voltage_typ": number (volts)
   - "voltage_max": number (volts)
   - "power_pins": array of pin name strings
   - "decoupling_caps": array of {"value": "...", "purpose": "..."}
7. "strapping": object with keys:
   - "pins": array of strapping pin name strings
   - "notes": array of strings (default levels, boot-mode implications,
     timing requirements)
Every pin of the pin-definition table must appear exactly once in "pins".
Output ONLY valid JSON, no markdown fences or commentary.
"""


def build_prompt(pdf_name: str, sliced_text: str) -> str:
    """Deterministic extraction prompt over the sliced pages only."""
    return (f"Datasheet: {pdf_name}\n\n{_SCHEMA_PROMPT}\n"
            f"--- BEGIN DATASHEET TEXT ---\n{sliced_text}\n"
            f"--- END DATASHEET TEXT ---\n")


def _claude_runner(prompt: str) -> str:
    """Default runner: shell out to ``claude --print`` (like the legacy path)."""
    cli = shutil.which("claude")
    if cli is None:
        raise ExtractionFailed("claude CLI not found on PATH")
    try:
        proc = subprocess.run([cli, "--print"], input=prompt,
                              capture_output=True, text=True,
                              timeout=CLAUDE_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise ExtractionFailed(f"claude CLI timed out after {CLAUDE_TIMEOUT}s") from exc
    if proc.returncode != 0:
        raise ExtractionFailed(f"claude CLI exited {proc.returncode}: "
                               f"{proc.stderr.strip()[:200]}")
    return proc.stdout


def _strip_fences(text: str) -> str:
    """Drop markdown code-fence lines (legacy-compatible)."""
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(ln for ln in text.split("\n") if not ln.startswith("```"))
    return text.strip()


# -------------------------------------------------------------------------
# Validation gate
# -------------------------------------------------------------------------

_PIN_TYPE_MAP = {
    "P": "power_in", "I": "input", "O": "output",
    "IO": "bidirectional", "I/O": "bidirectional", "I/O/T": "bidirectional",
}


def _parse_pin_type(raw: str) -> ElectricalType | None:
    """Datasheet abbreviation or KiCad name -> ElectricalType; None if bogus."""
    key = raw.strip().upper()
    if key in _PIN_TYPE_MAP:
        return ElectricalType(_PIN_TYPE_MAP[key])
    parsed = ElectricalType.parse(raw)
    if parsed is ElectricalType.UNSPECIFIED and key != "UNSPECIFIED":
        return None
    return parsed


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_extraction(data: object) -> list[str]:
    """Schema-ish checks on the candidate JSON; empty list means valid."""
    if not isinstance(data, dict):
        return ["candidate is not a JSON object"]
    problems: list[str] = []
    if not str(data.get("chip_name") or "").strip():
        problems.append("chip_name missing or empty")

    pins = data.get("pins")
    if not isinstance(pins, list) or not pins:
        problems.append("pins missing or empty")
        pins = []
    seen: set[str] = set()
    for i, entry in enumerate(pins):
        if not isinstance(entry, dict):
            problems.append(f"pins[{i}] is not an object")
            continue
        pad = str(entry.get("number", "")).strip()
        if not pad:
            problems.append(f"pins[{i}] has no number")
        elif pad in seen:
            problems.append(f"duplicate pad number {pad!r}")
        else:
            seen.add(pad)
        if not str(entry.get("name") or "").strip():
            problems.append(f"pins[{i}] (pad {pad!r}) has no name")
        raw_type = str(entry.get("type") or "")
        if _parse_pin_type(raw_type) is None:
            problems.append(f"pins[{i}] (pad {pad!r}) has unparseable type {raw_type!r}")
        functions = entry.get("functions", [])
        if not (isinstance(functions, list)
                and all(isinstance(f, str) for f in functions)):
            problems.append(f"pins[{i}] (pad {pad!r}) functions is not a string array")

    power = data.get("power", {})
    if not isinstance(power, dict):
        problems.append("power is not an object")
    else:
        volts = [power.get(k, 0) for k in ("voltage_min", "voltage_typ",
                                           "voltage_max")]
        if not all(_is_number(v) for v in volts):
            problems.append("power voltages are not numbers")
        elif all(v > 0 for v in volts) and not (volts[0] <= volts[1] <= volts[2]):
            problems.append("power voltages not ordered min <= typ <= max")
        pp = power.get("power_pins", [])
        if not (isinstance(pp, list) and all(isinstance(p, str) for p in pp)):
            problems.append("power.power_pins is not a string array")

    strapping = data.get("strapping", {})
    if not isinstance(strapping, dict):
        problems.append("strapping is not an object")
    else:
        for key in ("pins", "notes"):
            val = strapping.get(key, [])
            if not (isinstance(val, list) and all(isinstance(s, str) for s in val)):
                problems.append(f"strapping.{key} is not a string array")
    return problems


# -------------------------------------------------------------------------
# Typed part construction
# -------------------------------------------------------------------------

_GROUP_ROLES = {
    "POWER": PinRole.POWER, "CONTROL": PinRole.CONTROL,
    "UART": PinRole.COMM, "SPI": PinRole.COMM, "I2C": PinRole.COMM,
    "USB": PinRole.COMM, "SDIO": PinRole.COMM, "JTAG": PinRole.COMM,
    "ADC": PinRole.ANALOG, "TOUCH": PinRole.ANALOG,
    "GPIO": PinRole.GPIO, "PWM": PinRole.GPIO, "CLOCK": PinRole.GPIO,
}
_GPIO_NAME = re.compile(r"^(?:GPIO|IO)(\d+)$")


def _role_for(name: str, group: str, etype: ElectricalType) -> PinRole:
    upper = name.strip().upper()
    if etype is ElectricalType.NO_CONNECT or upper == "NC":
        return PinRole.NC
    if upper.startswith("GND") or upper in ("VSS", "EPAD"):
        return PinRole.GROUND
    if etype in (ElectricalType.POWER_IN, ElectricalType.POWER_OUT):
        return PinRole.POWER
    return _GROUP_ROLES.get(group.strip().upper(), PinRole.SIGNAL)


def _build_pin(entry: dict) -> ExtractedPin:
    name = str(entry["name"]).strip()
    raw_type = str(entry.get("type") or "")
    etype = _parse_pin_type(raw_type)
    assert etype is not None  # guaranteed by validate_extraction
    group = str(entry.get("group") or "")
    gpio_match = _GPIO_NAME.match(name.upper())
    spec = PinSpec(
        pad=str(entry["number"]).strip(), name=name, etype=etype,
        role=_role_for(name, group, etype),
        gpio=int(gpio_match.group(1)) if gpio_match else None,
        functions=tuple(str(f) for f in entry.get("functions", [])),
    )
    return ExtractedPin(spec=spec, group=group, raw_type=raw_type)


def extract(pdf: Path, *, runner: Runner | None = None) -> ExtractedPart:
    """Slice the PDF, run the LLM over only those pages, gate, and type.

    ``runner`` maps prompt -> raw response text (injectable for tests);
    the default shells out to ``claude --print``. Raises SectionNotFound /
    ExtractionFailed / ValidationFailed — never falls back to canned data.
    """
    pdf = Path(pdf)
    sections = find_sections(pdf)
    sliced, pages_used = _slice(pdf, sections)
    prompt = build_prompt(pdf.name, sliced)
    run = runner or _claude_runner

    data: dict | None = None
    errors: list[str] = []
    for _ in range(EXTRACT_ATTEMPTS):
        try:
            raw = run(prompt)
        except ExtractionFailed as exc:
            errors.append(str(exc))
            continue
        try:
            data = json.loads(_strip_fences(raw))
            break
        except json.JSONDecodeError as exc:
            errors.append(f"JSON decode failed: {exc}")
    if data is None:
        raise ExtractionFailed(
            f"{pdf.name}: no parseable JSON after {EXTRACT_ATTEMPTS} attempts "
            f"({'; '.join(errors[-3:])})")

    problems = validate_extraction(data)
    if problems:
        raise ValidationFailed(problems)

    power = data.get("power", {})
    strapping = data.get("strapping", {})
    return ExtractedPart(
        chip_name=str(data.get("chip_name", "")).strip(),
        manufacturer=str(data.get("manufacturer", "")).strip(),
        description=str(data.get("description", "")).strip(),
        package=str(data.get("package", "")).strip(),
        pins=tuple(_build_pin(p) for p in data["pins"]),
        power=PowerSpec(
            voltage_min=float(power.get("voltage_min", 0) or 0),
            voltage_typ=float(power.get("voltage_typ", 0) or 0),
            voltage_max=float(power.get("voltage_max", 0) or 0),
            power_pins=tuple(power.get("power_pins", [])),
            decoupling_caps=tuple(
                CapSpec(value=str(c.get("value", "")),
                        purpose=str(c.get("purpose", "")))
                for c in power.get("decoupling_caps", [])
                if isinstance(c, dict)),
        ),
        strapping_pins=tuple(strapping.get("pins", [])),
        strapping_notes=tuple(strapping.get("notes", [])),
        provenance=Provenance(
            pdf_name=pdf.name,
            pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
            pages_used=pages_used,
            page_count=_page_count(str(pdf)),
        ),
    )
