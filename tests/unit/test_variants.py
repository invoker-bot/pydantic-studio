from __future__ import annotations

import pytest
from pydantic import BaseModel

from pydantic_studio.io.yaml import save_yaml
from pydantic_studio.variants import (
    VariantRegistry,
    VariantSpec,
    build_variant_form_tree,
)


class EmailSettings(BaseModel):
    address: str = "ops@example.com"


class SlackSettings(BaseModel):
    channel: str = "#ops"


def test_variant_registry_keeps_order_and_labels() -> None:
    registry = VariantRegistry(
        [
            VariantSpec(id="email", model=EmailSettings, label="Email"),
            VariantSpec(id="slack", model=SlackSettings),
        ]
    )

    assert [spec.id for spec in registry] == ["email", "slack"]
    assert registry.get("email").label == "Email"
    assert registry.get("slack").label == "SlackSettings"


def test_variant_registry_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="duplicate variant id: email"):
        VariantRegistry(
            [
                VariantSpec(id="email", model=EmailSettings),
                VariantSpec(id="email", model=SlackSettings),
            ]
        )


def test_variant_registry_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="variant id must be non-empty"):
        VariantSpec(id=" ", model=EmailSettings)


def _registry() -> VariantRegistry:
    return VariantRegistry(
        [
            VariantSpec(id="email", model=EmailSettings, label="Email"),
            VariantSpec(id="slack", model=SlackSettings, label="Slack"),
        ]
    )


def test_build_variant_form_tree_attaches_metadata() -> None:
    tree = build_variant_form_tree(
        _registry(),
        selected_id="email",
        discriminator="class_name",
        persistence="inline_discriminator",
    )

    assert tree.schema_class is EmailSettings
    assert tree.variant is not None
    assert tree.variant.selected_id == "email"
    assert [option.id for option in tree.variant.options] == ["email", "slack"]
    assert tree.to_output_python()["class_name"] == "email"


def test_select_root_variant_rebuilds_schema_and_root() -> None:
    tree = build_variant_form_tree(_registry(), selected_id="email")

    result = tree.select_root_variant("slack")

    assert result.ok is True
    assert tree.schema_class is SlackSettings
    assert tree.variant is not None
    assert tree.variant.selected_id == "slack"
    assert tree.root.find("channel") is not None
    assert tree.root.find("address") is None


def test_select_root_variant_rejects_unknown_id_without_mutating() -> None:
    tree = build_variant_form_tree(_registry(), selected_id="email")

    result = tree.select_root_variant("pager")

    assert result.ok is False
    assert tree.schema_class is EmailSettings
    assert tree.variant is not None
    assert tree.variant.selected_id == "email"


def test_save_yaml_includes_inline_discriminator(tmp_path) -> None:
    tree = build_variant_form_tree(
        _registry(),
        selected_id="email",
        discriminator="class_name",
        persistence="inline_discriminator",
    )
    out = tmp_path / "settings.yaml"

    save_yaml(tree, out)

    text = out.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "class_name: email"
    assert "address: ops@example.com" in text
