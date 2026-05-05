"""Type-dispatch layer.

Each module in this package owns one type family. ``registry.py`` defines
the ``NodeBuilder`` Protocol and the ``Registry`` class; the per-family
modules (``primitives``, ``models``, ``choices``, ``sequences``,
``mapping``, ``unions``) implement concrete builders.
"""

from __future__ import annotations
