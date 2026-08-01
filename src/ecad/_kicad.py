"""Access point for the vendored kiutils in tools/.

Isolated in its own module and imported lazily (inside the .kicad_sym
emitter, not at package import) so that `import src.ecad` never mutates
sys.path. Callers that only build a Design or query symbol geometry pay
neither the path insertion nor the kiutils import.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TOOLS = str(Path(__file__).resolve().parent.parent.parent / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from kiutils.items.common import Effects, Fill, Font, Position, Property, Stroke
from kiutils.items.syitems import SyRect
from kiutils.symbol import Symbol, SymbolLib, SymbolPin

__all__ = [
    "Effects", "Fill", "Font", "Position", "Property", "Stroke",
    "SyRect", "Symbol", "SymbolLib", "SymbolPin",
]
