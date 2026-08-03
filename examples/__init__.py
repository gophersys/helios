"""Reference designs built from the typed model + the circuit-block layer.

Each example is a package exposing ``build() -> dict[str, Design]`` (one
:class:`~src.ecad.design.Design` per schematic sheet) and a ``PROVENANCE``
list citing the source of every design decision it makes.
"""
