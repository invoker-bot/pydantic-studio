"""LiteralNode + LiteralBuilder coverage."""

from __future__ import annotations

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import LiteralNode, SequenceNode
from tests.fixtures.schemas import WithLogLevel


def test_literal_string_field_builds_into_literal_node() -> None:
    tree = build_form_tree(WithLogLevel)
    level = tree.root.find("level")
    assert isinstance(level, LiteralNode)
    assert level.choices == ["debug", "info", "warn", "error"]
    assert level.default == "info"


def test_literal_int_field() -> None:
    tree = build_form_tree(WithLogLevel)
    sev = tree.root.find("severity")
    assert isinstance(sev, LiteralNode)
    assert sev.choices == [1, 2, 3]
    assert sev.default == 2


def test_literal_to_instance_round_trip() -> None:
    tree = build_form_tree(WithLogLevel, existing={"level": "warn"})
    instance = tree.to_instance()
    assert instance.level == "warn"


def test_literal_validate_rejects_unlisted_value() -> None:
    tree = build_form_tree(WithLogLevel)
    result = tree.set_value("level", "trace")
    assert result.ok is False
    assert any("not in choices" in e for e in result.errors)


def test_literal_validate_accepts_listed_value() -> None:
    tree = build_form_tree(WithLogLevel)
    result = tree.set_value("level", "error")
    assert result.ok is True


def test_literal_round_trips_through_snapshot() -> None:
    """Snapshot round-trip preserves Literal member identity (str stays str,
    int stays int) — guard against future serialization regressions."""
    from pydantic_studio.tree import snapshots as _snap

    tree = build_form_tree(
        WithLogLevel, existing={"level": "warn", "severity": 3}
    )
    snapshot = _snap.take(tree.root)
    restored_root = _snap.restore(snapshot)
    level = restored_root.find("level")
    sev = restored_root.find("severity")
    assert isinstance(level, LiteralNode)
    assert isinstance(sev, LiteralNode)
    assert level.value == "warn"
    assert isinstance(level.value, str)
    assert sev.value == 3
    assert isinstance(sev.value, int)


def test_literal_with_none_member() -> None:
    """``Literal[None, "off"]`` — None is a valid member, not a sentinel for
    "unset". validate_value must accept it on a required field."""
    from typing import Literal as _Literal

    from pydantic import BaseModel

    class S(BaseModel):
        flag: _Literal[None, "off"]

    tree = build_form_tree(S, existing={"flag": None})
    flag = tree.root.find("flag")
    assert isinstance(flag, LiteralNode)
    # required=True (no default), choices contains None — None must be valid.
    result = tree.set_value("flag", None)
    assert result.ok is True, result.errors


def test_add_item_to_list_of_literal_round_trips() -> None:
    """Regression (Sentry hft-python #13 — ``NoBuilderError: typing.Literal``):
    adding an item to a ``list[Literal[...]]`` must rebuild the *parametrized*
    Literal. The container only persists ``item_type_name`` as a string, and the
    old encoding collapsed ``Literal['a', 'b']`` to the bare ``typing.Literal``
    (choices dropped) → ``add_item`` raised NoBuilderError at registry lookup."""
    from typing import Literal as _Literal

    from pydantic import BaseModel

    class S(BaseModel):
        modes: list[_Literal["fast", "slow", "auto"]] = []

    tree = build_form_tree(S)
    result = tree.add_item("modes")
    assert result.ok is True, result.errors
    modes = tree.root.find("modes")
    assert isinstance(modes, SequenceNode)
    assert len(modes.items) == 1
    child = modes.items[0]
    assert isinstance(child, LiteralNode)
    assert child.choices == ["fast", "slow", "auto"]


def test_fq_resolve_round_trip_for_literal() -> None:
    """``_fq`` ∘ ``_resolve_type_name`` is identity for Literal types so a
    container's persisted ``item_type_name`` rebuilds the exact parametrized
    Literal (choices intact) after JSON serialization to the web client.
    Covers the JSON-encodable member kinds (str / int / bool / None) and
    members containing ``.`` (must not be split like a dotted module path)."""
    from typing import Literal as _Literal

    from pydantic_studio.tree.nodes import _resolve_type_name
    from pydantic_studio.types.utils import _fq

    for typ in (
        _Literal["a", "b", "c"],
        _Literal[1, 2, 3],
        _Literal[True, False],
        _Literal[None, "off"],
        _Literal["a.b", "c.d"],
    ):
        assert _resolve_type_name(_fq(typ)) == typ, _fq(typ)


def test_fq_does_not_structurally_encode_non_scalar_literal_members() -> None:
    """JSON can encode list/dict Literal members, but the result cannot safely
    rebuild a supported LiteralNode. Keep those exotic members on the bare
    typing.Literal path instead of emitting malformed structural metadata."""
    from typing import Literal as _Literal

    from pydantic_studio.types.utils import _fq

    assert _fq(_Literal[["nested"]]) == "typing.Literal"
    assert _fq(_Literal[{"x": "y"}]) == "typing.Literal"
