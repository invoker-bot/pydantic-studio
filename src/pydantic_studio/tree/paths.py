"""JSONPath-style addressing for form-tree nodes.

Path syntax::

    ""                            → root
    "name"                        → top-level field 'name'
    "database.host"               → nested field
    "replicas[2]"                 → element 2 of a SequenceNode
    "database.replicas[2].host"   → mixed
    "matrix[0][1]"                → multiple indices

Indices are non-negative integers. Field names follow Python identifier rules
(letters, digits, underscores; no leading digit).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypeAlias

PathSegment: TypeAlias = str | int

_FIELD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# Reserved for callers that need to locate bracket spans (e.g., for
# highlighting in error messages); ``parse`` scans manually rather than
# using this regex.
_INDEX_RE = re.compile(r"\[([^\]]*)\]")


@dataclass(frozen=True, slots=True)
class Path:
    """An immutable address into a form tree.

    Use ``Path.parse(s)`` for human-readable strings, or ``Path((...))``
    directly for programmatic construction.
    """

    segments: tuple[PathSegment, ...] = ()

    @classmethod
    def parse(cls, raw: str) -> Path:
        if raw == "":
            return cls(())
        segments: list[PathSegment] = []
        i = 0
        n = len(raw)
        # Expect either a field name or an index segment to start.
        while i < n:
            if raw[i] == "[":
                end = raw.find("]", i)
                if end == -1:
                    msg = f"unclosed bracket in path {raw!r}"
                    raise ValueError(msg)
                inside = raw[i + 1 : end]
                try:
                    idx = int(inside)
                except ValueError as e:
                    msg = f"non-integer index {inside!r} in path {raw!r}"
                    raise ValueError(msg) from e
                if idx < 0:
                    msg = f"negative index {idx} in path {raw!r}"
                    raise ValueError(msg)
                segments.append(idx)
                i = end + 1
                # After ']', the next character (if any) must be '.' or '[' —
                # otherwise the input is malformed (e.g., "foo[2]bar").
                if i < n and raw[i] not in (".", "["):
                    msg = (
                        f"unexpected character {raw[i]!r} after ']' "
                        f"at position {i} in path {raw!r}"
                    )
                    raise ValueError(msg)
            elif raw[i] == ".":
                i += 1  # separator between two field-name segments
            else:
                m = _FIELD_RE.match(raw, i)
                if not m:
                    msg = f"unexpected character {raw[i]!r} at position {i} in path {raw!r}"
                    raise ValueError(msg)
                segments.append(m.group(0))
                i = m.end()
        return cls(tuple(segments))

    def render(self) -> str:
        out: list[str] = []
        for seg in self.segments:
            if isinstance(seg, int):
                out.append(f"[{seg}]")
            else:
                if out:
                    out.append(".")
                out.append(seg)
        return "".join(out)

    def append(self, segment: PathSegment) -> Path:
        return Path((*self.segments, segment))

    def __str__(self) -> str:
        return self.render()
