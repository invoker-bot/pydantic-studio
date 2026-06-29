"""Tests for subclass-aware builder dispatch — issue #3.

Specific builders historically used identity checks (``type_ is X``) which
rejected user subclasses of their target types — even though such
subclasses are the canonical Pydantic pattern for domain-specific value
types. This file exercises every affected builder with a representative
subclass.

Two patterns trigger the bug in practice:

1. **Pydantic-class subclasses** (``class HttpsUrl(AnyUrl): pass``,
   ``class TokenSecret(SecretStr): pass``) — Pydantic accepts these as
   field types directly because the parent class already publishes a
   ``__get_pydantic_core_schema__``. The subclass inherits validation,
   but pydantic-studio's identity-check matchers reject the subclass
   class object.

2. **stdlib subclasses with ``arbitrary_types_allowed=True``** (``class
   UserId(int): pass``, ``class HostAddress(IPv4Address): pass``) —
   Pydantic accepts these via an is-instance schema. The subclass
   dispatch in pydantic-studio still has to recognise the type so the
   right widget builds.

The subclasses live at module scope (not inside test functions) because
``UrlNode``'s ``target_type_name`` round-trip looks classes up from
``sys.modules`` — a function-local class is unreachable from
``_resolve_type_name``.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from ipaddress import IPv4Address, IPv4Network, IPv6Address
from pathlib import Path
from uuid import UUID

from pydantic import AnyUrl, BaseModel, ConfigDict, SecretStr

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import (
    BoolNode,
    BytesNode,
    DateNode,
    DatetimeNode,
    DecimalNode,
    FloatNode,
    IntNode,
    IpAddressNode,
    IpNetworkNode,
    PathNode,
    SecretNode,
    StringNode,
    UrlNode,
    UuidNode,
)

ARB = ConfigDict(arbitrary_types_allowed=True)


# ---------- subclass fixtures (module-level so target_type_name can find them) ----------


class UserId(int):
    """Domain identifier — subclass of int."""


class Score(float):
    """Domain numeric — subclass of float."""


class MoneyAmount(Decimal):
    """Currency value — subclass of Decimal."""


class MyBytes(bytes):
    """Subclass of bytes."""


class Slug(str):
    """Domain string — subclass of str."""


class HttpsUrl(AnyUrl):
    """Subclass of AnyUrl — Pydantic's recommended URL-narrowing pattern."""


class TokenSecret(SecretStr):
    """Subclass of SecretStr — domain credential type."""


class MyUUID(UUID):
    """Subclass of UUID — domain identifier."""


class HostAddress(IPv4Address):
    """Subclass of IPv4Address — host-only IP."""


class HostNetwork(IPv4Network):
    """Subclass of IPv4Network — restricted network range."""


class ProjectPath(type(Path())):
    """Subclass of Path — project-relative path."""


class EventTimestamp(datetime):
    """Subclass of datetime — domain event time."""


class CalendarDate(date):
    """Subclass of date — narrow to calendar-only semantics."""


# ---------- Pydantic-class subclasses (no arbitrary_types config needed) ----------


def test_url_subclass_dispatches_to_url_node():
    class M(BaseModel):
        endpoint: HttpsUrl

    tree = build_form_tree(M, existing={"endpoint": "https://example.com/"})
    endpoint_node = next(c for c in tree.root.fields if c.name == "endpoint")
    assert isinstance(endpoint_node, UrlNode)
    assert endpoint_node.target_type_name.endswith("HttpsUrl")


def test_secret_str_subclass_dispatches_to_secret_node():
    class M(BaseModel):
        token: TokenSecret

    tree = build_form_tree(M, existing={"token": TokenSecret("hunter2")})
    token_node = next(c for c in tree.root.fields if c.name == "token")
    assert isinstance(token_node, SecretNode)
    assert token_node.secret_kind == "str"


# ---------- stdlib subclasses (require arbitrary_types_allowed) ----------


def test_int_subclass_dispatches_to_int_node():
    class M(BaseModel):
        model_config = ARB
        uid: UserId

    tree = build_form_tree(M, existing={"uid": UserId(42)})
    uid_node = next(c for c in tree.root.fields if c.name == "uid")
    assert isinstance(uid_node, IntNode)
    assert uid_node.value == 42


def test_float_subclass_dispatches_to_float_node():
    class M(BaseModel):
        model_config = ARB
        score: Score

    tree = build_form_tree(M, existing={"score": Score(0.95)})
    score_node = next(c for c in tree.root.fields if c.name == "score")
    assert isinstance(score_node, FloatNode)


def test_str_subclass_dispatches_to_string_node():
    class M(BaseModel):
        model_config = ARB
        slug: Slug

    tree = build_form_tree(M, existing={"slug": Slug("hello-world")})
    slug_node = next(c for c in tree.root.fields if c.name == "slug")
    assert isinstance(slug_node, StringNode)
    assert slug_node.value == "hello-world"


def test_decimal_subclass_dispatches_to_decimal_node():
    class M(BaseModel):
        model_config = ARB
        price: MoneyAmount

    tree = build_form_tree(M, existing={"price": MoneyAmount("19.99")})
    price_node = next(c for c in tree.root.fields if c.name == "price")
    assert isinstance(price_node, DecimalNode)


def test_bytes_subclass_dispatches_to_bytes_node():
    class M(BaseModel):
        model_config = ARB
        blob: MyBytes

    tree = build_form_tree(M, existing={"blob": MyBytes(b"abc")})
    blob_node = next(c for c in tree.root.fields if c.name == "blob")
    assert isinstance(blob_node, BytesNode)


def test_uuid_subclass_dispatches_to_uuid_node():
    class M(BaseModel):
        model_config = ARB
        rid: MyUUID

    tree = build_form_tree(
        M, existing={"rid": MyUUID("12345678-1234-5678-1234-567812345678")}
    )
    rid_node = next(c for c in tree.root.fields if c.name == "rid")
    assert isinstance(rid_node, UuidNode)


def test_ipv4_subclass_dispatches_to_ip_address_node_version_4():
    class M(BaseModel):
        model_config = ARB
        host: HostAddress

    tree = build_form_tree(M, existing={"host": HostAddress("10.0.0.1")})
    host_node = next(c for c in tree.root.fields if c.name == "host")
    assert isinstance(host_node, IpAddressNode)
    assert host_node.version == 4


def test_ipv4_network_subclass_dispatches_to_ip_network_node_version_4():
    class M(BaseModel):
        model_config = ARB
        net: HostNetwork

    tree = build_form_tree(M, existing={"net": HostNetwork("10.0.0.0/24")})
    net_node = next(c for c in tree.root.fields if c.name == "net")
    assert isinstance(net_node, IpNetworkNode)
    assert net_node.version == 4


def test_path_subclass_dispatches_to_path_node():
    class M(BaseModel):
        model_config = ARB
        location: ProjectPath

    tree = build_form_tree(M, existing={"location": ProjectPath("/etc/x")})
    loc_node = next(c for c in tree.root.fields if c.name == "location")
    assert isinstance(loc_node, PathNode)


# ---------- temporal hierarchy: datetime IS-A date in stdlib ----------


def test_datetime_subclass_dispatches_to_datetime_node():
    class M(BaseModel):
        model_config = ARB
        when: EventTimestamp

    tree = build_form_tree(
        M, existing={"when": EventTimestamp(2026, 5, 7, 12, 0)}
    )
    when_node = next(c for c in tree.root.fields if c.name == "when")
    assert isinstance(when_node, DatetimeNode)


def test_date_subclass_dispatches_to_date_node():
    class M(BaseModel):
        model_config = ARB
        on: CalendarDate

    tree = build_form_tree(M, existing={"on": CalendarDate(2026, 5, 7)})
    on_node = next(c for c in tree.root.fields if c.name == "on")
    assert isinstance(on_node, DateNode)


def test_bare_datetime_does_not_match_date_builder():
    """``datetime`` is a subclass of ``date`` — DateBuilder must exclude
    datetime so a plain ``datetime`` field still gets DatetimeNode and
    not the (subclass-widened) DateBuilder."""

    class M(BaseModel):
        ts: datetime

    tree = build_form_tree(M, existing={"ts": datetime(2026, 5, 7, 12, 0)})
    ts_node = next(c for c in tree.root.fields if c.name == "ts")
    assert isinstance(ts_node, DatetimeNode)


# ---------- bool/int boundary preserved after widening ----------


def test_bool_remains_bool_node_when_int_widened():
    """``bool`` is a subclass of ``int`` in Python — IntBuilder must
    exclude it so bare ``bool`` fields keep landing in BoolBuilder."""

    class M(BaseModel):
        flag: bool = True

    tree = build_form_tree(M)
    flag_node = next(c for c in tree.root.fields if c.name == "flag")
    assert isinstance(flag_node, BoolNode)


# ---------- IPv6 sibling preserved (matches second OR branch) ----------


def test_ipv6_address_still_matches_ip_address_builder():
    """Sibling type — IPv6Address is *not* a subclass of IPv4Address but
    both should still match IpAddressBuilder. Verify the post-widening
    matcher handles both branches of the OR."""

    class M(BaseModel):
        host6: IPv6Address

    tree = build_form_tree(M, existing={"host6": IPv6Address("::1")})
    host6_node = next(c for c in tree.root.fields if c.name == "host6")
    assert isinstance(host6_node, IpAddressNode)
    assert host6_node.version == 6


# ---------- Optional masking regression ----------


def test_optional_subclass_with_populated_data_round_trips():
    """The ``Optional[Subclass]`` masking pattern: when None is the
    declared default, build_form_tree(M) succeeds because UnionBuilder
    walks the None branch. The subclass-builder bug only surfaced
    when *populated* existing data forced UnionBuilder._preselect to
    reach for the inner type's builder. Regression test for that
    hard-to-spot crash-on-load scenario."""

    class M(BaseModel):
        endpoint: HttpsUrl | None = None

    # populated existing forces UnionBuilder to dispatch into the
    # url-subclass branch — pre-fix this raised NoBuilderError.
    tree = build_form_tree(M, existing={"endpoint": "https://example.com/"})
    endpoint_node = next(c for c in tree.root.fields if c.name == "endpoint")
    # Optional[T] with a single non-None variant collapses to the
    # inner builder's node with required=False.
    assert isinstance(endpoint_node, UrlNode)
    assert endpoint_node.required is False


def test_subclass_with_none_default_still_builds():
    """Sanity counterpart: even without populated data, the form must
    open — so this is the day-1 path, not a regression target."""

    class M(BaseModel):
        token: TokenSecret | None = None

    tree = build_form_tree(M)
    token_node = next(c for c in tree.root.fields if c.name == "token")
    assert isinstance(token_node, SecretNode)
    assert token_node.required is False


# ---------- existing baseline preserved (no regression) ----------


def test_bare_int_field_still_dispatches_to_int_node():
    """Every type that matched ``type_ is X`` today still matches
    ``issubclass(type_, X)``. Reflexivity sanity check."""

    class M(BaseModel):
        n: int

    tree = build_form_tree(M, existing={"n": 5})
    n_node = next(c for c in tree.root.fields if c.name == "n")
    assert isinstance(n_node, IntNode)


def test_bare_pattern_unaffected_by_changes():
    """PatternBuilder was intentionally left alone — re.Pattern's
    subclass story is non-standard. Verify the existing path still
    works after the broader sweep."""

    class M(BaseModel):
        rx: re.Pattern[str] = re.compile(r"\w+")

    tree = build_form_tree(M)
    rx_node = next(c for c in tree.root.fields if c.name == "rx")
    assert rx_node.kind == "pattern"
