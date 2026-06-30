"""Strict JSON parsing helpers shared by file and renderer entry points."""

from __future__ import annotations

import json
from typing import Any


def reject_non_finite_json_constant(value: str) -> None:
    msg = f"non-finite JSON constant {value!r} is not supported"
    raise ValueError(msg)


def object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            msg = f"duplicate JSON key {key!r} is not supported"
            raise ValueError(msg)
        obj[key] = value
    return obj


def loads_strict_json(text: str) -> Any:
    return json.loads(
        text,
        parse_constant=reject_non_finite_json_constant,
        object_pairs_hook=object_without_duplicate_keys,
    )


def dumps_strict_json(value: Any, *, ensure_ascii: bool = True) -> str:
    payload = json.dumps(value, ensure_ascii=ensure_ascii, allow_nan=False)
    loads_strict_json(payload)
    return payload


def load_strict_json(fp: Any) -> Any:
    return json.load(
        fp,
        parse_constant=reject_non_finite_json_constant,
        object_pairs_hook=object_without_duplicate_keys,
    )
