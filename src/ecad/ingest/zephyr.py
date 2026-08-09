"""Zephyr devicetree + Espressif HAL parsers for factory cross-verification.

Ground truth per ``data/zephyr/VALIDATION.md`` (real formats quoted there):

- pinctrl headers (``<soc>-pinctrl.h``) use one shared ``ESP32_PINMUX(pin,
  sig_in, sig_out)`` macro for every SoC; defines are line-continued
  (``\\`` + newline) and use ``ESP_NOSIG`` as the no-signal sentinel.
- ``<soc>-gpio-sigmap.h`` companions are plain numeric ``#define ESP_*`` ids.
- ``<soc>_common.dtsi`` carries dual GPIO banks (``ngpios``) under a
  ``gpio`` wrapper node, plus every peripheral node label.
- HAL ``io_mux_reg.h`` maps ``IO_MUX_GPIO<N>_REG -> PERIPHS_IO_MUX_<PAD>_U``
  and lists ``FUNC_<PAD>_<FUNCTION> <index>`` with duplicate ``_0`` aliases
  (index-0 GPIO function repeated) that must be deduped.
- HAL ``soc_caps.h`` encodes input-only pins as ``BIT<n>`` terms cleared in
  ``SOC_GPIO_VALID_OUTPUT_GPIO_MASK`` (esp32: 34-39, esp32s2: 46; esp32s3
  has none — its GPIO46 is full I/O per soc_caps and the datasheet pin
  table, unlike the S2).

The pinned clones live in ``data/zephyr/`` and must match ``data/zephyr/PIN``
(``ensure()`` verifies this).  esp32h2 is absent from the LTS tree and uses
the newest-release fallback tree (``soc_source()`` / ``NeedsFallbackTree``).

Strapping pins are a per-SoC constant table sourced from the Espressif
datasheets/TRMs (chapter 启动配置项 / Boot Configurations, verified against
the PDFs cached in ``data/datasheets/``).

Pure stdlib, deterministic: same tree in, same SocInfo out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_PINCTRL_SUBDIR = Path("include/zephyr/dt-bindings/pinctrl")
_FALLBACK_DIRNAME = "zephyr-fallback"
_DEFAULT_FALLBACK_TAG = "v4.4.1"

# Strapping pins per SoC, from the vendor datasheet boot-configuration
# chapters (表 3-1 Strapping 管脚默认配置 / Boot Configurations):
STRAPPING: dict[str, tuple[int, ...]] = {
    "esp32": (0, 2, 5, 12, 15),      # GPIO0, GPIO2, GPIO5, MTDI, MTDO
    "esp32s2": (0, 45, 46),
    "esp32s3": (0, 3, 45, 46),
    "esp32c3": (2, 8, 9),
    "esp32c6": (4, 5, 8, 9, 15),     # MTMS=GPIO4, MTDI=GPIO5
    "esp32h2": (8, 9, 25),
}


class ZephyrTreeError(RuntimeError):
    """The data/zephyr trees are absent, drifted, or unparsable."""


class NeedsFallbackTree(ZephyrTreeError):
    """SoC needs the fallback (newest-release) Zephyr tree, which is absent."""


@dataclass(frozen=True)
class GpioInfo:
    iomux_functions: tuple[str, ...]  # ordered by IO MUX function index
    input_only: bool


@dataclass(frozen=True)
class PinmuxEntry:
    group: str            # e.g. "UART0_TX" (define name minus _GPIO<N>)
    gpio: int
    sig_in: str | None    # raw sigmap macro name; None == ESP_NOSIG
    sig_out: str | None


@dataclass(frozen=True)
class SocInfo:
    name: str
    gpio_count: int                   # sum of dtsi bank ngpios
    gpios: dict[int, GpioInfo]        # only GPIOs with a real IO MUX pad
    signals: dict[str, int]           # signal group -> its IO-MUX-native GPIO
    peripherals: tuple[str, ...]      # sorted dtsi node labels
    strapping: tuple[int, ...]


# --------------------------------------------------------------------------
# Parsers (pure text -> data; each unit-testable on fixture strings)
# --------------------------------------------------------------------------

_CONT = re.compile(r"\\\s*\n")
_PINMUX = re.compile(
    r"#define\s+([A-Za-z0-9_]+)_GPIO(\d+)\s+"
    r"ESP32_PINMUX\(\s*(\d+)\s*,\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*\)")
_SIGMAP = re.compile(r"#define\s+(ESP_[A-Za-z0-9_]+)\s+(\d+)\s*$", re.M)
_NGPIOS = re.compile(r"\bngpios\s*=\s*<\s*(\d+)\s*>")
_DTSI_LABEL = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*[A-Za-z0-9_,.+-]+(?:@[0-9a-fA-Fx]+)?\s*\{",
    re.M)
_IOMUX_REG = re.compile(
    r"#define\s+IO_MUX_GPIO(\d+)_REG\s+PERIPHS_IO_MUX_([A-Za-z0-9_]+)_U\b")
_FUNC = re.compile(r"#define\s+FUNC_([A-Za-z0-9_]+?)\s+(\d+)\s*$", re.M)
_OUT_MASK = re.compile(r"#define\s+SOC_GPIO_VALID_OUTPUT_GPIO_MASK\s+(.+)")
_BIT = re.compile(r"\bBIT(\d+)\b")


def parse_pinctrl(text: str) -> tuple[PinmuxEntry, ...]:
    """Parse ``ESP32_PINMUX`` defines (continuation lines joined first)."""
    joined = _CONT.sub(" ", text)
    entries = []
    for m in _PINMUX.finditer(joined):
        group, _, pin, sig_in, sig_out = m.groups()
        entries.append(PinmuxEntry(
            group=group,
            gpio=int(pin),  # trust the macro argument over the define suffix
            sig_in=None if sig_in == "ESP_NOSIG" else sig_in,
            sig_out=None if sig_out == "ESP_NOSIG" else sig_out,
        ))
    return tuple(entries)


def parse_sigmap(text: str) -> dict[str, int]:
    """``ESP_<SIGNAL>_IN/_OUT -> id``; skips the non-numeric ESP_NOSIG alias."""
    return {m.group(1): int(m.group(2)) for m in _SIGMAP.finditer(text)}


def parse_dtsi_ngpios(text: str) -> tuple[int, ...]:
    """Per-bank ``ngpios`` values in file order (dual banks on xtensa SoCs)."""
    return tuple(int(m.group(1)) for m in _NGPIOS.finditer(text))


def parse_dtsi_labels(text: str) -> tuple[str, ...]:
    """Sorted unique node labels (``label: node@addr {``)."""
    return tuple(sorted({m.group(1) for m in _DTSI_LABEL.finditer(text)}))


def parse_io_mux(text: str) -> dict[int, tuple[str, ...]]:
    """GPIO -> IO MUX function names ordered by function index.

    ``FUNC_<PAD>_<FUNCTION>`` needs the ``IO_MUX_GPIO<N>_REG`` pad map to
    split pad from function (both may contain underscores, e.g. pad
    ``XTAL_32K_P``, function ``CLK_OUT1``).  Duplicate ``<func>_0`` aliases
    of an existing function are dropped.
    """
    pad_to_gpio = {m.group(2): int(m.group(1)) for m in _IOMUX_REG.finditer(text)}
    pads = sorted(pad_to_gpio, key=len, reverse=True)  # longest-prefix match
    per_pad: dict[str, list[tuple[int, str]]] = {p: [] for p in pads}
    for m in _FUNC.finditer(text):
        full, idx = m.group(1), int(m.group(2))
        for pad in pads:
            if full.startswith(pad + "_"):
                per_pad[pad].append((idx, full[len(pad) + 1:]))
                break
    out: dict[int, tuple[str, ...]] = {}
    for pad, funcs in per_pad.items():
        names = {n for _, n in funcs}
        kept = sorted((i, n) for i, n in funcs
                      if not (n.endswith("_0") and n[:-2] in names))
        out[pad_to_gpio[pad]] = tuple(n for _, n in kept)
    return dict(sorted(out.items()))


def parse_input_only(soc_caps_text: str) -> tuple[int, ...]:
    """Input-only GPIOs = BITs cleared in SOC_GPIO_VALID_OUTPUT_GPIO_MASK."""
    m = _OUT_MASK.search(_CONT.sub(" ", soc_caps_text))
    if m is None:
        return ()
    return tuple(sorted(int(b) for b in _BIT.findall(m.group(1))))


def parse_pin_file(text: str) -> dict[str, dict[str, object]]:
    """Parse data/zephyr/PIN (small YAML subset: sections, scalars, lists)."""
    data: dict[str, dict[str, object]] = {}
    section: dict[str, object] | None = None
    list_key: str | None = None
    for raw in text.splitlines():
        line = re.sub(r"(^|\s)#.*$", "", raw).rstrip()
        if not line.strip():
            continue
        if not line[0].isspace():
            section = data.setdefault(line.strip().rstrip(":"), {})
            list_key = None
            continue
        if section is None:
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            if list_key is not None:
                lst = section.setdefault(list_key, [])
                assert isinstance(lst, list)
                lst.append(stripped[2:].strip())
            continue
        key, _, value = stripped.partition(":")
        key, value = key.strip(), value.strip()
        if value:
            section[key] = value
            list_key = None
        else:
            section[key] = []
            list_key = key
    return data


def _signal_base(raw: str) -> str:
    """``ESP_U0TXD_OUT`` -> ``U0TXD`` (HAL IO MUX function namespace)."""
    s = raw[4:] if raw.startswith("ESP_") else raw
    for suffix in ("_IN", "_OUT"):
        if s.endswith(suffix):
            return s[: -len(suffix)]
    return s


def _git_head(repo: Path) -> str | None:
    """Resolve a clone's HEAD commit sha without invoking git."""
    git_dir = repo / ".git"
    if git_dir.is_file():
        m = re.match(r"gitdir:\s*(.+)", git_dir.read_text().strip())
        if m is None:
            return None
        target = Path(m.group(1))
        git_dir = target if target.is_absolute() else (repo / target).resolve()
    head_file = git_dir / "HEAD"
    if not head_file.is_file():
        return None
    head = head_file.read_text().strip()
    if not head.startswith("ref:"):
        return head
    ref = head[4:].strip()
    loose = git_dir / ref
    if loose.is_file():
        return loose.read_text().strip()
    packed = git_dir / "packed-refs"
    if packed.is_file():
        for line in packed.read_text().splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == ref:
                return parts[0]
    return None


# --------------------------------------------------------------------------
# Tree handle
# --------------------------------------------------------------------------

def _clone_commands(url: str, dest: Path, *, tag: str | None, sha: str | None,
                    sparse: list[str] | tuple[str, ...]) -> str:
    branch = f" --branch {tag}" if tag else ""
    lines = [f"git clone --depth 1{branch} --filter=blob:none --sparse {url} {dest}"]
    if sha and not tag:
        lines += [f"git -C {dest} fetch --depth 1 origin {sha}",
                  f"git -C {dest} checkout --detach {sha}"]
    if sparse:
        lines.append(f"git -C {dest} sparse-checkout set " + " ".join(sparse))
    return "\n".join(lines)


class ZephyrTree:
    """Verified handle on the pinned data/zephyr clones."""

    def __init__(self, root: Path, pin: dict[str, dict[str, object]] | None = None):
        self.root = Path(root)
        self.pin = pin or {}
        self._cache: dict[str, SocInfo] = {}

    @property
    def lts_dir(self) -> Path:
        return self.root / "zephyr"

    @property
    def hal_dir(self) -> Path:
        return self.root / "hal_espressif"

    @property
    def fallback_dir(self) -> Path:
        return self.root / _FALLBACK_DIRNAME

    @property
    def fallback_tag(self) -> str:
        section = self.pin.get("fallback", {})
        tag = section.get("zephyr_tag") if isinstance(section, dict) else None
        return str(tag) if tag else _DEFAULT_FALLBACK_TAG

    def soc_source(self, name: str) -> str:
        """``"lts"`` if the SoC's pinctrl header is in the LTS tree, else
        ``"fallback"`` (the newest-release policy, currently for esp32h2)."""
        if (self.lts_dir / _PINCTRL_SUBDIR / f"{name}-pinctrl.h").is_file():
            return "lts"
        return "fallback"

    def _zephyr_side(self, name: str) -> Path:
        if self.soc_source(name) == "lts":
            return self.lts_dir
        if (self.fallback_dir / _PINCTRL_SUBDIR / f"{name}-pinctrl.h").is_file():
            return self.fallback_dir
        zsec = self.pin.get("zephyr", {})
        url = str(zsec.get("url", "https://github.com/zephyrproject-rtos/zephyr")) \
            if isinstance(zsec, dict) else "https://github.com/zephyrproject-rtos/zephyr"
        cmds = _clone_commands(
            url, self.fallback_dir, tag=self.fallback_tag, sha=None,
            sparse=("dts/xtensa/espressif", "dts/riscv/espressif",
                    "include/zephyr/dt-bindings/pinctrl"))
        raise NeedsFallbackTree(
            f"SoC {name!r} is not in the LTS tree ({self.lts_dir}); it needs the "
            f"{self.fallback_tag} fallback tree, which is absent. Clone it with:\n{cmds}")

    def _dtsi_path(self, zephyr_dir: Path, name: str) -> Path:
        for pattern in (f"dts/*/espressif/{name}/{name}_common.dtsi",
                        f"dts/*/espressif/{name}/{name}.dtsi"):
            hits = sorted(zephyr_dir.glob(pattern))
            if hits:
                return hits[0]
        raise ZephyrTreeError(
            f"no dtsi for {name!r} under {zephyr_dir}/dts/*/espressif/{name}/ "
            f"(is the sparse-checkout set missing dts/*/espressif?)")

    def soc(self, name: str) -> SocInfo:
        """Parse one SoC's Zephyr+HAL truth into a SocInfo (cached)."""
        if name in self._cache:
            return self._cache[name]
        hal_inc = self.hal_dir / "components" / "soc" / name / "include" / "soc"
        io_mux_path = hal_inc / "io_mux_reg.h"
        if not io_mux_path.is_file():
            raise ZephyrTreeError(
                f"unknown SoC {name!r}: no {io_mux_path} in the pinned HAL")
        zephyr_dir = self._zephyr_side(name)  # may raise NeedsFallbackTree
        pinctrl_path = zephyr_dir / _PINCTRL_SUBDIR / f"{name}-pinctrl.h"
        sigmap_path = zephyr_dir / _PINCTRL_SUBDIR / f"{name}-gpio-sigmap.h"
        if not sigmap_path.is_file():
            raise ZephyrTreeError(f"missing sigmap companion {sigmap_path}")
        dtsi_path = self._dtsi_path(zephyr_dir, name)

        iomux = parse_io_mux(io_mux_path.read_text())
        caps_path = hal_inc / "soc_caps.h"
        input_only = set(parse_input_only(caps_path.read_text())) \
            if caps_path.is_file() else set()
        gpios = {g: GpioInfo(iomux_functions=funcs, input_only=g in input_only)
                 for g, funcs in iomux.items()}

        dtsi_text = dtsi_path.read_text()
        ngpios = parse_dtsi_ngpios(dtsi_text)
        if not ngpios:
            raise ZephyrTreeError(f"no ngpios banks found in {dtsi_path}")

        sigmap = parse_sigmap(sigmap_path.read_text())
        signals: dict[str, int] = {}
        for entry in parse_pinctrl(pinctrl_path.read_text()):
            for raw in (entry.sig_in, entry.sig_out):
                if raw is None or raw not in sigmap:
                    continue
                info = gpios.get(entry.gpio)
                if info is None or _signal_base(raw) not in info.iomux_functions:
                    continue  # GPIO-matrix-routable, not this signal's home pad
                current = signals.get(entry.group)
                if current is None or entry.gpio < current:
                    signals[entry.group] = entry.gpio

        info = SocInfo(
            name=name,
            gpio_count=sum(ngpios),
            gpios=gpios,
            signals=dict(sorted(signals.items())),
            peripherals=parse_dtsi_labels(dtsi_text),
            strapping=STRAPPING.get(name, ()),
        )
        self._cache[name] = info
        return info


def ensure(repo_root: Path) -> ZephyrTree:
    """Verify data/zephyr clones match data/zephyr/PIN; return the handle.

    Raises ZephyrTreeError with exact fix commands when absent or drifted.
    """
    root = Path(repo_root) / "data" / "zephyr"
    pin_path = root / "PIN"
    if not pin_path.is_file():
        raise ZephyrTreeError(
            f"{pin_path} not found — the pinned-source manifest is required. "
            f"Restore it from the repo history or re-run the Stage-2 data prep "
            f"(see data/zephyr/VALIDATION.md).")
    pin = parse_pin_file(pin_path.read_text())

    problems: list[str] = []
    for section_name, dirname in (("zephyr", "zephyr"),
                                  ("hal_espressif", "hal_espressif")):
        section = pin.get(section_name)
        if not isinstance(section, dict) or "sha" not in section:
            raise ZephyrTreeError(f"{pin_path} has no {section_name}.sha entry")
        want = str(section["sha"])
        url = str(section.get("url", ""))
        tag = section.get("tag")
        sparse = section.get("sparse", [])
        assert isinstance(sparse, list)
        dest = root / dirname
        cmds = _clone_commands(url, dest, tag=str(tag) if tag else None,
                               sha=want, sparse=sparse)
        if not dest.is_dir():
            problems.append(f"{dest} is absent. Clone it with:\n{cmds}")
            continue
        head = _git_head(dest)
        if head != want:
            problems.append(
                f"{dest} is at {head or 'an unreadable HEAD'} but PIN pins {want}"
                f"{f' (tag {tag})' if tag else ''}. Fix:\nrm -rf {dest}\n{cmds}")
        elif sparse and not all((dest / s).exists() for s in sparse):
            problems.append(
                f"{dest} is missing sparse paths. Fix:\n"
                f"git -C {dest} sparse-checkout set " + " ".join(sparse))
    if problems:
        raise ZephyrTreeError(
            "data/zephyr does not match data/zephyr/PIN:\n\n" + "\n\n".join(problems))
    return ZephyrTree(root=root, pin=pin)
