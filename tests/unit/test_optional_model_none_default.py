"""Optional[BaseModel] fields defaulting to None must round-trip None.

Regression for the section-expansion bug: an untouched ``Optional[Model] =
None`` field used to materialize as a fully-defaulted model instance on
``to_instance()`` (the demoted GroupNode pre-fills every child with its
schema default, so the all-None optional-group rule never fired). Editing
any child must still activate the group, and ``None``-only annotations
must build instead of raising ``NoBuilderError``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree


class Section(BaseModel):
    a: int = 1
    b: str = "x"


class Host(BaseModel):
    x: int = 1
    simulate: Section | None = None


def test_untouched_optional_model_resolves_to_none() -> None:
    tree = build_form_tree(Host)
    inst = tree.to_instance()
    assert inst.simulate is None


def test_editing_child_field_activates_group() -> None:
    tree = build_form_tree(Host)
    result = tree.set_value("simulate.a", 5)
    assert result.ok, result.errors
    inst = tree.to_instance()
    assert inst.simulate == Section(a=5)


def test_existing_section_data_is_kept() -> None:
    tree = build_form_tree(Host, existing={"simulate": {"a": 3}})
    inst = tree.to_instance()
    assert inst.simulate == Section(a=3)


def test_default_factory_optional_model_keeps_prefill() -> None:
    class HostFactory(BaseModel):
        simulate: Section | None = Field(default_factory=Section)

    inst = build_form_tree(HostFactory).to_instance()
    assert inst.simulate == Section()


def test_missing_required_skips_unactivated_group() -> None:
    class RequiredSection(BaseModel):
        must: int

    class HostRequired(BaseModel):
        sec: RequiredSection | None = None

    tree = build_form_tree(HostRequired)
    assert tree.missing_required_paths() == []
    assert tree.to_instance().sec is None


def test_none_only_annotation_builds_and_resolves_none() -> None:
    class HostMarker(BaseModel):
        marker: None = None

    tree = build_form_tree(HostMarker)
    assert tree.to_instance().marker is None
