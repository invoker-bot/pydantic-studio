"""Parse-on-load: existing values for fields with transforming validators
must round-trip through the field's validator before entering the tree.

The motivating field report (HFT): ``Annotated[SecretStr,
PlainSerializer(encrypt), PlainValidator(decrypt)]``. ``load_yaml`` used
to copy the *ciphertext* into SecretNode.value; ``to_instance`` skipped
decryption (value already SecretStr) and ``model_dump`` re-encrypted —
every edit cycle wrapped secrets in another encryption layer.

The fixed contract: the tree holds the *runtime* representation for any
field whose metadata carries PlainValidator / BeforeValidator /
WrapValidator; saving re-applies the serializer exactly once.
"""

from __future__ import annotations

from typing import Annotated, Any

import pytest
from pydantic import (
    BaseModel,
    PlainSerializer,
    PlainValidator,
    SecretStr,
)

from pydantic_studio import build_form_tree, load_yaml, save_yaml
from pydantic_studio.tree.nodes import UnionNode


class _CodecError(RuntimeError):
    """Stands in for cryptography's InvalidToken (NOT a ValueError)."""


def _encode(plain: str) -> str:
    return f"ENC[{plain}]"


def _decode(token: str) -> str:
    if token.startswith("ENC[") and token.endswith("]"):
        return token[4:-1]
    raise _CodecError(f"not a token: {token!r}")


def _decrypt_secret(value: str | SecretStr) -> SecretStr:
    # Mirrors HFT's validator: runtime instances pass through untouched,
    # wire strings get decoded.
    if isinstance(value, SecretStr):
        return value
    return SecretStr(_decode(value))


_EncryptedSecret = Annotated[
    SecretStr,
    PlainSerializer(lambda s: _encode(s.get_secret_value()), return_type=str),
    PlainValidator(_decrypt_secret),
]


class _Vault(BaseModel):
    api_key: _EncryptedSecret
    leverage: int = 1


class _OptionalVault(BaseModel):
    api_key: _EncryptedSecret | None = None
    leverage: int = 1


class _Outer(BaseModel):
    vault: _Vault
    note: str = ""


class _VaultList(BaseModel):
    api_keys: list[_EncryptedSecret]
    leverage: int = 1


class _VaultMap(BaseModel):
    api_keys: dict[str, _EncryptedSecret]
    leverage: int = 1


class _OptionalVaultList(BaseModel):
    api_keys: list[_EncryptedSecret | None]
    leverage: int = 1


class _OptionalVaultMap(BaseModel):
    api_keys: dict[str, _EncryptedSecret | None]
    leverage: int = 1


class _OptionalVaultTuple(BaseModel):
    api_keys: tuple[_EncryptedSecret | None, ...]
    leverage: int = 1


class _CredentialRef(BaseModel):
    name: str


class _UnionVault(BaseModel):
    credential: _EncryptedSecret | _CredentialRef
    leverage: int = 1


class _UnionVaultList(BaseModel):
    credentials: list[_EncryptedSecret | _CredentialRef]
    leverage: int = 1


def _normalize(value: Any) -> str:
    return f"<{value}>" if not str(value).startswith("<") else str(value)


_NormalizedStr = Annotated[str, PlainValidator(_normalize)]


class _Normalizing(BaseModel):
    tag: _NormalizedStr = "<default>"


def test_existing_wire_value_is_parsed_into_runtime_form() -> None:
    tree = build_form_tree(_Vault, existing={"api_key": "ENC[real]"})
    assert tree._resolve_path("api_key").value == "real"


def test_single_serialization_after_load_edit_save_cycle() -> None:
    tree = build_form_tree(_Vault, existing={"api_key": "ENC[real]", "leverage": 3})
    tree.set_value("leverage", 5)  # the user only touches leverage
    dumped = tree.to_instance().model_dump(mode="json")
    assert dumped["api_key"] == "ENC[real]", (
        f"expected single encoding, got {dumped['api_key']!r} "
        "(double-encoding regression)"
    )


def test_nested_group_fields_are_parsed_too() -> None:
    tree = build_form_tree(
        _Outer, existing={"vault": {"api_key": "ENC[nested]", "leverage": 2}}
    )
    assert tree._resolve_path("vault.api_key").value == "nested"
    dumped = tree.to_instance().model_dump(mode="json")
    assert dumped["vault"]["api_key"] == "ENC[nested]"


def test_optional_transforming_value_is_parsed_too() -> None:
    tree = build_form_tree(
        _OptionalVault, existing={"api_key": "ENC[maybe]", "leverage": 2}
    )

    assert tree._resolve_path("api_key").value == "maybe"
    tree.set_value("leverage", 5)
    dumped = tree.to_instance().model_dump(mode="json")
    assert dumped["api_key"] == "ENC[maybe]"


def test_sequence_items_with_transforming_validators_are_parsed_too() -> None:
    tree = build_form_tree(
        _VaultList, existing={"api_keys": ["ENC[first]"], "leverage": 2}
    )

    assert tree._resolve_path("api_keys[0]").value == "first"
    tree.set_value("leverage", 5)
    dumped = tree.to_instance().model_dump(mode="json")
    assert dumped["api_keys"] == ["ENC[first]"]


def test_mapping_values_with_transforming_validators_are_parsed_too() -> None:
    tree = build_form_tree(
        _VaultMap, existing={"api_keys": {"primary": "ENC[first]"}, "leverage": 2}
    )
    api_keys = tree._resolve_path("api_keys")

    assert api_keys.entries[0][1].value == "first"
    tree.set_value("leverage", 5)
    dumped = tree.to_instance().model_dump(mode="json")
    assert dumped["api_keys"] == {"primary": "ENC[first]"}


def test_optional_sequence_items_with_transforming_validators_are_parsed_too() -> None:
    tree = build_form_tree(
        _OptionalVaultList,
        existing={"api_keys": ["ENC[first]", None], "leverage": 2},
    )

    assert tree._resolve_path("api_keys[0]").value == "first"
    assert tree._resolve_path("api_keys[1]").value is None
    tree.set_value("leverage", 5)
    dumped = tree.to_instance().model_dump(mode="json")
    assert dumped["api_keys"] == ["ENC[first]", None]


def test_optional_mapping_values_with_transforming_validators_are_parsed_too() -> None:
    tree = build_form_tree(
        _OptionalVaultMap,
        existing={"api_keys": {"primary": "ENC[first]", "empty": None}, "leverage": 2},
    )
    api_keys = tree._resolve_path("api_keys")

    assert api_keys.entries[0][1].value == "first"
    assert api_keys.entries[1][1].value is None
    tree.set_value("leverage", 5)
    dumped = tree.to_instance().model_dump(mode="json")
    assert dumped["api_keys"] == {"primary": "ENC[first]", "empty": None}


def test_optional_tuple_items_with_transforming_validators_are_parsed_too() -> None:
    tree = build_form_tree(
        _OptionalVaultTuple,
        existing={"api_keys": ("ENC[first]", None), "leverage": 2},
    )

    assert tree._resolve_path("api_keys[0]").value == "first"
    assert tree._resolve_path("api_keys[1]").value is None
    tree.set_value("leverage", 5)
    dumped = tree.to_instance().model_dump(mode="json")
    assert dumped["api_keys"] == ["ENC[first]", None]


def test_true_union_transforming_variant_is_preselected_from_wire_value() -> None:
    tree = build_form_tree(
        _UnionVault,
        existing={"credential": "ENC[union]", "leverage": 2},
    )
    credential = tree._resolve_path("credential")

    assert isinstance(credential, UnionNode)
    assert credential.selected_index == 0
    assert credential.selected is not None
    assert credential.selected.value == "union"
    tree.set_value("leverage", 5)
    dumped = tree.to_instance().model_dump(mode="json")
    assert dumped["credential"] == "ENC[union]"


def test_sequence_true_union_transforming_variant_is_preselected() -> None:
    tree = build_form_tree(
        _UnionVaultList,
        existing={"credentials": ["ENC[first]"], "leverage": 2},
    )
    credential = tree._resolve_path("credentials[0]")

    assert isinstance(credential, UnionNode)
    assert credential.selected_index == 0
    assert credential.selected is not None
    assert credential.selected.value == "first"
    tree.set_value("leverage", 5)
    dumped = tree.to_instance().model_dump(mode="json")
    assert dumped["credentials"] == ["ENC[first]"]


def test_plain_validator_transform_applies_to_non_secret_types() -> None:
    tree = build_form_tree(_Normalizing, existing={"tag": "raw"})
    assert tree._resolve_path("tag").value == "<raw>"


def test_validation_error_falls_back_to_raw_value() -> None:
    def _strict(value: Any) -> str:
        if value == "bad":
            raise ValueError("nope")
        return str(value)

    class _Strict(BaseModel):
        tag: Annotated[str, PlainValidator(_strict)] = "ok"

    tree = build_form_tree(_Strict, existing={"tag": "bad"})
    # The user is repairing a broken file — show what's on disk as-is.
    assert tree._resolve_path("tag").value == "bad"


def test_non_validation_errors_propagate() -> None:
    with pytest.raises(_CodecError):
        build_form_tree(_Vault, existing={"api_key": "garbage-not-a-token"})


def test_fields_without_transforms_keep_raw_path() -> None:
    class _Plain(BaseModel):
        count: int = 1

    tree = build_form_tree(_Plain, existing={"count": 7})
    assert tree._resolve_path("count").value == 7


def test_model_instance_existing_uses_runtime_value_for_transform_fields() -> None:
    """The BaseModel-instance branch (union preselect path) must not
    re-serialize transform fields via model_dump — that re-encrypts."""
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.builder import default_registry

    instance = _Vault(api_key="ENC[live]", leverage=2)
    assert instance.api_key.get_secret_value() == "live"

    reg = default_registry()
    builder = reg.find(_Vault)
    node = builder.build(_Vault, FieldInfo(annotation=_Vault), instance)
    api_key_node = next(c for c in node.fields if c.name == "api_key")
    assert api_key_node.value == "live", (
        f"expected runtime plaintext, got {api_key_node.value!r} "
        "(model_dump re-serialization regression)"
    )


def test_yaml_end_to_end_no_double_encoding(tmp_path) -> None:
    """The literal downstream scenario: gen → edit (touch one field) →
    saved secret still decodes to the original plaintext in one step."""
    path = tmp_path / "vault.yaml"
    tree = build_form_tree(_Vault)
    tree.set_value("api_key", "real")
    save_yaml(tree, path)

    tree2 = load_yaml(path, _Vault)
    tree2.set_value("leverage", 9)
    save_yaml(tree2, path)

    tree3 = load_yaml(path, _Vault)
    assert tree3._resolve_path("api_key").value == "real"
    assert tree3._resolve_path("leverage").value == 9
