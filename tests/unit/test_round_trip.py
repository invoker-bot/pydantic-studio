from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, Field

from pydantic_studio.exceptions import ValidationFailedError
from pydantic_studio.tree.builder import build_form_tree
from tests.fixtures.schemas import Person, Simple

if TYPE_CHECKING:
    from pathlib import Path


def test_to_instance_simple_full_population():
    tree = build_form_tree(Simple)
    tree.set_value("name", "alice")
    tree.set_value("age", 30)
    tree.set_value("height", 1.75)
    tree.set_value("enabled", False)
    tree.set_value("balance", Decimal("12.50"))
    inst = tree.to_instance()
    assert isinstance(inst, Simple)
    assert inst.name == "alice"
    assert inst.age == 30
    assert inst.height == 1.75
    assert inst.enabled is False
    assert inst.balance == Decimal("12.50")


def test_to_instance_uses_defaults_for_omitted_fields():
    tree = build_form_tree(Simple)
    tree.set_value("name", "alice")
    inst = tree.to_instance()
    assert inst.name == "alice"
    assert inst.age == 0  # schema default
    assert inst.enabled is True


def test_to_instance_raises_on_required_missing():
    tree = build_form_tree(Simple)  # 'name' has no default → required
    with pytest.raises(ValidationFailedError) as exc_info:
        tree.to_instance()
    assert any("name" in e for e in exc_info.value.errors)


def test_to_instance_round_trip_with_nested_model():
    tree = build_form_tree(Person)
    tree.set_value("name", "alice")
    tree.set_value("address.street", "1 Main St")
    tree.set_value("address.city", "Springfield")
    inst = tree.to_instance()
    assert isinstance(inst, Person)
    assert inst.address.street == "1 Main St"


def test_to_instance_load_then_edit_then_save_round_trip():
    """The flagship round-trip: load existing dict → edit → emit identical dict modulo edits."""
    initial = {
        "name": "alice",
        "age": 30,
        "height": 1.7,
        "enabled": True,
        "balance": Decimal("0.00"),
    }
    tree = build_form_tree(Simple, existing=initial)
    tree.set_value("age", 31)
    inst = tree.to_instance()
    assert inst.model_dump() == {**initial, "age": 31}


def test_to_instance_preserves_alias_field_edits():
    class AliasConfig(BaseModel):
        api_key: str = Field(default="secret", alias="api-key")

    tree = build_form_tree(AliasConfig)
    result = tree.set_value("api_key", "rotated")

    assert result.ok is True
    assert tree.to_instance().api_key == "rotated"


def test_saved_serialization_aliases_reload_across_formats(tmp_path: Path) -> None:
    from pydantic_studio import load_config, save_config

    class AliasConfig(BaseModel):
        api_key: str = Field(
            default="secret",
            alias="api-key",
            serialization_alias="apiKey",
        )

    tree = build_form_tree(AliasConfig)
    result = tree.set_value("api_key", "rotated")
    assert result.ok is True

    for suffix in ("yaml", "toml", "json"):
        path = tmp_path / f"config.{suffix}"
        save_config(tree, path)

        assert "apiKey" in path.read_text(encoding="utf-8")
        assert load_config(path, AliasConfig).to_instance().api_key == "rotated"
