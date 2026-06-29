"""Server-side render helpers for FormTree → HTML widgets."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import AnyNode, FormTree, GroupNode


def render_yaml_preview(tree: FormTree) -> str:
    """Render the FormTree as YAML for preview display.

    Tries ``to_instance().model_dump(mode="json")`` first (the validated
    canonical form). Falls back to ``tree.to_python()`` if validation
    hasn't passed yet OR if ``model_dump`` itself raises (pydantic v2
    raises on non-UTF8 ``bytes`` fields in JSON mode — a quirk we have
    to swallow so the preview keeps working). Either source is then
    coerced through ``_coerce_to_yaml_safe`` so ruamel.yaml — which can't
    natively represent Enum/Decimal/UUID/time/timedelta — gets a safe
    payload. Any remaining failure returns ``<preview error: …>``
    instead of propagating; the preview must always return a string.
    """
    from pydantic_studio.io.yaml import _build_commented_map, _yaml

    schema = tree.schema_class
    if schema is None:
        return "<no schema>"
    try:
        data = tree.to_output_python()
    except Exception:
        data = tree.to_python()
    if not data:
        return "<empty>"
    try:
        safe = _coerce_to_yaml_safe(data)
        cm = _build_commented_map(safe, schema, source=None)
        buf = io.StringIO()
        _yaml().dump(cm, buf)
        return buf.getvalue()
    except Exception as e:
        return f"<preview error: {e}>"


def _coerce_to_yaml_safe(obj: Any) -> Any:
    """Recursively convert Python objects to YAML-representable forms.

    ruamel.yaml natively handles str/int/float/bool/None/list/dict/
    date/datetime/bytes. Everything else (Enum incl. StrEnum/IntEnum,
    Decimal, UUID, time, timedelta, Path, HttpUrl, IPvXAddress, etc.)
    raises ``RepresenterError`` — pre-flatten with ``str()`` here so the
    preview survives. The legacy renderer skipped this step and crashed
    silently whenever any of those types reached the dumper via the
    ``tree.to_python()`` fallback path.

    SecretStr / SecretBytes are masked rather than revealed so users
    don't accidentally screenshot a preview with plaintext secrets.
    """
    from datetime import date, datetime
    from enum import Enum

    if isinstance(obj, dict):
        return {k: _coerce_to_yaml_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_coerce_to_yaml_safe(v) for v in obj]
    if hasattr(obj, "get_secret_value"):
        return "**********"
    if isinstance(obj, Enum):
        # StrEnum.value / IntEnum.value are plain str/int (not the enum
        # itself), so this unwraps cleanly. Otherwise fall to str(member).
        return obj.value if isinstance(obj.value, (str, int, float, bool)) else str(obj)
    if obj is None or isinstance(
        obj, (str, int, float, bool, bytes, bytearray, date, datetime)
    ):
        return obj
    return str(obj)


def list_root_fields(tree: FormTree) -> list[tuple[str, AnyNode]]:
    """Return [(path, node)] for non-group children of the root group."""
    from pydantic_studio.tree.nodes import GroupNode

    out: list[tuple[str, AnyNode]] = []
    for child in tree.root.fields:
        if isinstance(child, GroupNode):
            continue
        out.append((child.name, child))
    return out


def list_groups(tree: FormTree) -> list[tuple[str, str]]:
    """Return [(path, label)] for all GroupNodes (sidebar nav)."""
    from pydantic_studio.tree.nodes import GroupNode

    out: list[tuple[str, str]] = [("", "<root>")]

    def walk(group: GroupNode, base_path: str) -> None:
        for child in group.fields:
            if isinstance(child, GroupNode):
                child_path = f"{base_path}.{child.name}".lstrip(".")
                out.append((child_path, child.name or "?"))
                walk(child, child_path)

    walk(tree.root, "")
    return out


def initial_value_str(node: AnyNode) -> str:
    """Stringify the node's current value for HTML input default.

    Falls back to ``node.default`` when value is None.
    """
    v = getattr(node, "value", None)
    if v is None:
        v = getattr(node, "default", None)
    if v is None:
        return ""
    if node.kind == "bytes" and isinstance(v, (bytes, bytearray)):
        return bytes(v).hex()
    return str(v)
