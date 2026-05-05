"""Type-dispatch layer.

Each module in this package owns one type family. ``registry.py`` defines
the ``NodeBuilder`` Protocol and the ``Registry`` class; the per-family
modules (``primitives``, ``models``, ``choices``, ``sequences``,
``mapping``, ``unions``) implement concrete builders.
"""

from __future__ import annotations

# Each module exports its own classes; ``types/__init__.py`` is intentionally
# a namespace package — import directly from the per-family submodule.
__all__: list[str] = []
