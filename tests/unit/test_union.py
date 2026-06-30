"""UnionNode + UnionBuilder coverage. select_variant lives in T15."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import BoolNode, IntNode, StringNode, UnionNode
from tests.fixtures.schemas import WithOptional, WithUnion


class _DUEmail(BaseModel):
    """Discriminated-union variant: email channel."""

    kind: Literal["email"] = "email"
    address: str


class _DUSlack(BaseModel):
    """Discriminated-union variant: slack channel."""

    kind: Literal["slack"] = "slack"
    channel: str


_DUNotifier = Annotated[_DUEmail | _DUSlack, Field(discriminator="kind")]


class _DUJob(BaseModel):
    """Holder model for the seeded discriminated-union regression test."""

    notifiers: list[_DUNotifier] = Field(default_factory=list)


def test_optional_demotes_to_inner_type_node() -> None:
    """``str | None`` becomes a StringNode with required=False, NOT a UnionNode."""
    tree = build_form_tree(WithOptional)
    nick = tree.root.find("nickname")
    assert isinstance(nick, StringNode)
    assert nick.required is False
    age = tree.root.find("age")
    assert isinstance(age, IntNode)
    assert age.required is False


def test_true_union_becomes_union_node() -> None:
    tree = build_form_tree(WithUnion)
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.variant_type_names == ["builtins.int", "builtins.str"]


def test_union_pre_populated_from_existing_int() -> None:
    tree = build_form_tree(WithUnion, existing={"value": 42})
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected_index == 0
    assert isinstance(val.selected, IntNode)
    assert val.selected.value == 42


def test_union_pre_populated_from_existing_str() -> None:
    tree = build_form_tree(WithUnion, existing={"value": "hi"})
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected_index == 1
    assert isinstance(val.selected, StringNode)
    assert val.selected.value == "hi"


def test_union_to_python_returns_inner_value() -> None:
    tree = build_form_tree(WithUnion, existing={"value": 7})
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.to_python() == 7


def test_union_to_instance_round_trip() -> None:
    tree = build_form_tree(WithUnion, existing={"value": "hello"})
    instance = tree.to_instance()
    assert instance.value == "hello"


def test_select_variant_switches_to_str() -> None:
    tree = build_form_tree(WithUnion, existing={"value": 42})
    result = tree.select_variant("value", 1)  # switch to str
    assert result.ok is True
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected_index == 1
    assert isinstance(val.selected, StringNode)
    assert val.selected.value is None  # fresh; previous int 42 is discarded


def test_select_variant_undo_restores() -> None:
    tree = build_form_tree(WithUnion, existing={"value": 42})
    tree.select_variant("value", 1)
    assert tree.undo() is True
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected_index == 0
    assert isinstance(val.selected, IntNode)
    assert val.selected.value == 42


def test_select_variant_out_of_range_returns_error() -> None:
    tree = build_form_tree(WithUnion)
    result = tree.select_variant("value", 99)
    assert result.ok is False
    assert any("out of range" in e for e in result.errors)


def test_select_variant_with_seed_value() -> None:
    """Optional second arg lets caller seed the new variant's value."""
    tree = build_form_tree(WithUnion)
    result = tree.select_variant("value", 1, seed="seeded")
    assert result.ok is True
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected.value == "seeded"


def test_select_variant_rejects_invalid_seed_without_mutating() -> None:
    tree = build_form_tree(WithUnion, existing={"value": "keep-me"})

    result = tree.select_variant("value", 0, seed="not-an-int")

    assert result.ok is False
    assert any("expected int" in error for error in result.errors)
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected_index == 1
    assert isinstance(val.selected, StringNode)
    assert val.selected.value == "keep-me"
    assert tree.snapshots == []


def test_discriminated_union_in_list_preserves_inner_field_values() -> None:
    """Regression: ``UnionBuilder._preselect`` validates a dict seed into
    a BaseModel instance and passes that instance to the inner builder.
    Previously ``GroupBuilder.build`` only accepted dict-shaped ``existing``,
    so the validated instance got dropped and every inner field was None —
    ``to_instance()`` then failed with ``union_tag_not_found``.
    """
    tree = build_form_tree(
        _DUJob,
        existing={
            "notifiers": [
                {"kind": "email", "address": "ops@example.com"},
                {"kind": "slack", "channel": "#ops"},
            ],
        },
    )
    instance = tree.to_instance()
    assert len(instance.notifiers) == 2
    assert isinstance(instance.notifiers[0], _DUEmail)
    assert instance.notifiers[0].address == "ops@example.com"
    assert isinstance(instance.notifiers[1], _DUSlack)
    assert instance.notifiers[1].channel == "#ops"


def test_select_variant_with_annotated_variant() -> None:
    """Regression (Sentry hft-python #15 — ``NoBuilderError: typing.Annotated``):
    selecting a union variant that is itself ``Annotated[T, ...]`` must build
    T's node, not crash. ``variant_type_names`` stored each variant via ``_fq``,
    which collapsed ``Annotated[bool, Strict()]`` (``pydantic.StrictBool``) to the
    bare ``typing.Annotated`` — the inner type lost — so ``select_variant``
    raised NoBuilderError at registry lookup. Mirrors ``hft``'s
    ``condition: Optional[Union[StrictBool, str]]`` executor field that crashed
    ``hft config gen executor --web``.
    """
    from pydantic import StrictBool

    class M(BaseModel):
        condition: StrictBool | str | None = None

    tree = build_form_tree(M)
    union = tree.root.find("condition")
    assert isinstance(union, UnionNode)
    # The StrictBool variant must not collapse to the builder-less special form.
    assert "typing.Annotated" not in union.variant_type_names
    result = tree.select_variant("condition", 0)  # the StrictBool (bool) variant
    assert result.ok is True, result.errors
    union = tree.root.find("condition")
    assert isinstance(union, UnionNode)
    assert union.selected_index == 0
    assert isinstance(union.selected, BoolNode)
