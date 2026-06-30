"""Generic selectable Pydantic model variants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from pydantic_studio.tree.nodes import FormTree


VariantPersistence = Literal["metadata", "inline_discriminator", "model_field"]


def _model_type_name(model: type[BaseModel]) -> str:
    return f"{model.__module__}.{model.__qualname__}"


@dataclass(frozen=True)
class VariantSpec:
    """One selectable Pydantic model variant."""

    id: str
    model: type[BaseModel]
    label: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        normalized = self.id.strip()
        if not normalized:
            msg = "variant id must be non-empty"
            raise ValueError(msg)
        if not isinstance(self.model, type) or not issubclass(self.model, BaseModel):
            msg = f"variant {normalized!r} model must be a Pydantic BaseModel subclass"
            raise TypeError(msg)
        object.__setattr__(self, "id", normalized)
        if self.label is None:
            object.__setattr__(self, "label", self.model.__name__)

    @property
    def display_label(self) -> str:
        return self.label or self.model.__name__

    @property
    def model_type_name(self) -> str:
        return _model_type_name(self.model)


class VariantRegistry:
    """Ordered lookup for selectable Pydantic model variants."""

    def __init__(self, variants: Iterable[VariantSpec]) -> None:
        self._variants = list(variants)
        if not self._variants:
            msg = "at least one variant is required"
            raise ValueError(msg)
        self._by_id: dict[str, VariantSpec] = {}
        for spec in self._variants:
            if spec.id in self._by_id:
                msg = f"duplicate variant id: {spec.id}"
                raise ValueError(msg)
            self._by_id[spec.id] = spec

    def __iter__(self) -> Iterator[VariantSpec]:
        return iter(self._variants)

    def __len__(self) -> int:
        return len(self._variants)

    def get(self, id_: str) -> VariantSpec:
        try:
            return self._by_id[id_]
        except KeyError as exc:
            known = ", ".join(self._by_id)
            msg = f"unknown variant id {id_!r}; known variants: {known}"
            raise ValueError(msg) from exc

    @property
    def default_id(self) -> str:
        return self._variants[0].id


def build_variant_form_tree(
    variants: VariantRegistry,
    *,
    selected_id: str | None = None,
    existing: dict[str, object] | None = None,
    discriminator: str | None = None,
    persistence: VariantPersistence = "metadata",
) -> FormTree:
    """Build a FormTree for a selectable set of root model variants."""

    allowed = {"metadata", "inline_discriminator", "model_field"}
    if persistence not in allowed:
        msg = f"unknown variant persistence {persistence!r}; use one of {sorted(allowed)}"
        raise ValueError(msg)
    if persistence == "inline_discriminator" and not discriminator:
        msg = "inline_discriminator persistence requires a discriminator"
        raise ValueError(msg)

    from pydantic_studio.tree.builder import build_form_tree

    selected = selected_id
    if (
        selected is None
        and persistence == "inline_discriminator"
        and discriminator is not None
        and existing
    ):
        raw_selected = existing.get(discriminator)
        if raw_selected is not None:
            if not isinstance(raw_selected, str):
                msg = (
                    f"inline discriminator {discriminator!r} must be a string, "
                    f"got {type(raw_selected).__name__}"
                )
                raise ValueError(msg)
            selected = raw_selected
    selected = selected or variants.default_id
    spec = variants.get(selected)
    tree = build_form_tree(spec.model, existing=existing)
    tree.attach_variant_registry(
        variants,
        selected_id=selected,
        discriminator=discriminator,
        persistence=persistence,
    )
    return tree
