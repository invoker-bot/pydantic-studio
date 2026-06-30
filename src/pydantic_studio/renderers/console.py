"""Sequential stdin/stdout renderer for pydantic-studio."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic_studio.exceptions import CancelledByUser
from pydantic_studio.io._json_strict import loads_strict_json
from pydantic_studio.outcome import EditOutcome
from pydantic_studio.renderers.textual_.widgets.cells.parse import parse_for_kind

InputFunc = Callable[[str], str]
PrintFunc = Callable[[str], None]

_TEXT_KINDS = {
    "string",
    "int",
    "float",
    "decimal",
    "datetime",
    "date",
    "time",
    "timedelta",
    "ip_address",
    "ip_network",
    "url",
    "email",
    "path",
    "uuid",
    "pattern",
    "bytes",
}


def run_console_app(
    tree: Any,
    save_path: str | Path | None = None,
    *,
    input_func: InputFunc = input,
    print_func: PrintFunc = print,
) -> EditOutcome:
    """Edit ``tree`` by asking one console prompt per field, then save."""

    try:
        print_func(f"Editing {tree.schema_name.split(':')[-1]}")
        _prompt_root_variant(tree, input_func, print_func)
        _edit_group(
            tree=tree,
            group=tree.root,
            base_path="",
            input_func=input_func,
            print_func=print_func,
        )
    except KeyboardInterrupt as exc:
        print_func("cancelled")
        raise CancelledByUser() from exc

    if save_path is None:
        print_func(repr(tree.to_instance()))
        return EditOutcome(status="submitted")

    from pydantic_studio.io.dispatch import save_config

    save_config(tree, save_path)
    print_func(f"saved to {Path(save_path)}")
    return EditOutcome(status="submitted")


def _prompt_root_variant(
    tree: Any,
    input_func: InputFunc,
    print_func: PrintFunc,
) -> None:
    variant = getattr(tree, "variant", None)
    if variant is None:
        return
    labels = [option.id for option in variant.options]
    current = variant.selected_id
    while True:
        raw = input_func(f"variant ({'/'.join(labels)}) [{current}]: ")
        if raw == "":
            return
        if raw not in labels:
            print_func(f"choose one of: {', '.join(labels)}")
            continue
        result = tree.select_root_variant(raw)
        if result.ok:
            return
        print_func("; ".join(result.errors) or "invalid variant")


def _edit_group(
    *,
    tree: Any,
    group: Any,
    base_path: str,
    input_func: InputFunc,
    print_func: PrintFunc,
) -> None:
    if base_path:
        print_func(f"[{base_path}]")
    for child in group.fields:
        path = _join_path(base_path, child.name)
        _edit_node(tree, child, path, input_func, print_func)


def _edit_node(
    tree: Any,
    node: Any,
    path: str,
    input_func: InputFunc,
    print_func: PrintFunc,
) -> None:
    kind = node.kind
    if kind == "group":
        _edit_group(
            tree=tree,
            group=node,
            base_path=path,
            input_func=input_func,
            print_func=print_func,
        )
        return
    if kind == "sequence":
        _edit_sequence(tree, node, path, input_func, print_func)
        return
    if kind == "mapping":
        _edit_mapping(tree, node, path, input_func, print_func)
        return
    if kind == "union":
        _edit_union(tree, node, path, input_func, print_func)
        return
    _prompt_leaf(tree, node, path, input_func, print_func)


def _prompt_leaf(
    tree: Any,
    node: Any,
    path: str,
    input_func: InputFunc,
    print_func: PrintFunc,
) -> None:
    while True:
        raw = input_func(_prompt_for(node, path))
        if raw == "":
            return
        ok, value_or_error = _parse_node_value(node, raw)
        if not ok:
            print_func(value_or_error)
            continue
        result = tree.set_value(path, value_or_error)
        if result.ok:
            return
        print_func("; ".join(result.errors) or "invalid value")


def _edit_sequence(
    tree: Any,
    node: Any,
    path: str,
    input_func: InputFunc,
    print_func: PrintFunc,
) -> None:
    if node.origin != "tuple_fixed":
        desired = _prompt_count(path, len(node.items), input_func, print_func)
        while len(node.items) > desired:
            tree.remove_item(path, len(node.items) - 1)
        while len(node.items) < desired:
            result = tree.add_item(path)
            if not result.ok:
                print_func("; ".join(result.errors) or "cannot add item")
                break

    for index, item in enumerate(list(node.items)):
        _edit_node(tree, item, f"{path}[{index}]", input_func, print_func)


def _edit_mapping(
    tree: Any,
    node: Any,
    path: str,
    input_func: InputFunc,
    print_func: PrintFunc,
) -> None:
    desired = _prompt_count(path, len(node.entries), input_func, print_func)
    while len(node.entries) > desired:
        tree.remove_entry(path, len(node.entries) - 1)
    while len(node.entries) < desired:
        key = _prompt_new_mapping_key(path, node, input_func, print_func)
        result = tree.add_entry(path, key)
        if not result.ok:
            print_func("; ".join(result.errors) or "cannot add entry")
            break

    for index, (key_node, value_node) in enumerate(list(node.entries)):
        new_key = input_func(f"{path}[{index}].key [{_format_value(key_node)}]: ")
        if new_key != "":
            ok, parsed_key = _parse_node_value(key_node, new_key)
            if ok:
                result = tree.rename_key(path, index, parsed_key)
                if not result.ok:
                    print_func("; ".join(result.errors) or "invalid key")
            else:
                print_func(parsed_key)
        _edit_node(tree, value_node, f"{path}[{index}]", input_func, print_func)


def _edit_union(
    tree: Any,
    node: Any,
    path: str,
    input_func: InputFunc,
    print_func: PrintFunc,
) -> None:
    labels = [name.rsplit(".", 1)[-1] for name in node.variant_type_names]
    current = 0 if node.selected_index is None else node.selected_index
    while True:
        raw = input_func(f"{path} variant ({'/'.join(labels)}) [{labels[current]}]: ")
        if raw == "":
            break
        try:
            index = int(raw) - 1
        except ValueError:
            if raw not in labels:
                print_func(f"choose one of: {', '.join(labels)}")
                continue
            index = labels.index(raw)
        result = tree.select_variant(path, index)
        if result.ok:
            break
        print_func("; ".join(result.errors) or "invalid variant")

    if node.selected is not None:
        _edit_node(tree, node.selected, path, input_func, print_func)


def _prompt_count(
    path: str,
    current: int,
    input_func: InputFunc,
    print_func: PrintFunc,
) -> int:
    while True:
        raw = input_func(f"{path} count [{current}]: ")
        if raw == "":
            return current
        try:
            value = int(raw)
        except ValueError:
            print_func(f"cannot parse {raw!r} as count")
            continue
        if value < 0:
            print_func("count must be >= 0")
            continue
        return value


def _prompt_new_mapping_key(
    path: str,
    node: Any,
    input_func: InputFunc,
    print_func: PrintFunc,
) -> Any:
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.builder import default_registry
    from pydantic_studio.tree.nodes import _resolve_type_name

    key_type = _resolve_type_name(node.key_type_name)
    key_builder = default_registry().find(key_type)
    key_node = key_builder.build(key_type, FieldInfo(annotation=key_type), None)
    while True:
        raw = input_func(f"{path} new key: ")
        ok, parsed = _parse_node_value(key_node, raw)
        if ok:
            return parsed
        print_func(parsed)


def _parse_node_value(node: Any, raw: str) -> tuple[bool, Any]:
    kind = node.kind
    if kind == "bool":
        lowered = raw.strip().lower()
        if lowered in {"y", "yes", "true", "1", "on"}:
            return True, True
        if lowered in {"n", "no", "false", "0", "off"}:
            return True, False
        return False, f"cannot parse {raw!r} as bool"
    if kind in {"enum", "literal"}:
        return _parse_choice(node, raw)
    if kind == "any":
        stripped = raw.strip()
        try:
            return True, loads_strict_json(stripped)
        except (json.JSONDecodeError, ValueError):
            return True, raw
    if kind == "secret":
        if getattr(node, "secret_kind", "str") == "bytes":
            return True, raw.encode()
        return True, raw
    if kind in _TEXT_KINDS:
        ok, parsed = parse_for_kind(kind, raw)
        if ok:
            return True, parsed
        return False, f"cannot parse {raw!r} as {kind}"
    return True, raw


def _parse_choice(node: Any, raw: str) -> tuple[bool, Any]:
    choices = _choice_values(node)
    if raw.isdigit():
        index = int(raw) - 1
        if 0 <= index < len(choices):
            return True, choices[index]
    for choice in choices:
        labels = {str(choice)}
        name = getattr(choice, "name", None)
        value = getattr(choice, "value", None)
        if name is not None:
            labels.add(str(name))
        if value is not None:
            labels.add(str(value))
        if raw in labels:
            return True, choice
    return False, f"choose one of: {'/'.join(str(c) for c in choices)}"


def _choice_values(node: Any) -> list[Any]:
    if node.kind == "enum":
        return [member for _, member in node.choices]
    return list(node.choices)


def _prompt_for(node: Any, path: str) -> str:
    suffix = ""
    if node.kind in {"enum", "literal"}:
        suffix = f" ({'/'.join(str(c) for c in _choice_values(node))})"
    return f"{path}{suffix} [{_format_value(node)}]: "


def _format_value(node: Any) -> str:
    value = getattr(node, "value", None)
    if value is None:
        return ""
    if node.kind == "bool":
        return "true" if value else "false"
    if node.kind == "bytes" and isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    if node.kind == "secret":
        return "<set>"
    enum_value = getattr(value, "value", None)
    if node.kind == "enum" and enum_value is not None:
        return str(enum_value)
    return str(value)


def _join_path(base: str, name: str) -> str:
    return name if base == "" else f"{base}.{name}"
