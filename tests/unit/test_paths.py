from __future__ import annotations

import pytest

from pydantic_studio.tree.paths import Path, PathSegment


def test_parse_simple_field():
    p = Path.parse("name")
    assert p.segments == ("name",)


def test_parse_nested_field():
    p = Path.parse("database.host")
    assert p.segments == ("database", "host")


def test_parse_with_index():
    p = Path.parse("replicas[2].host")
    assert p.segments == ("replicas", 2, "host")


def test_parse_multiple_indices():
    p = Path.parse("matrix[0][1]")
    assert p.segments == ("matrix", 0, 1)


def test_parse_root():
    p = Path.parse("")
    assert p.segments == ()


def test_parse_rejects_negative_index():
    with pytest.raises(ValueError, match="negative index"):
        Path.parse("foo[-1]")


def test_parse_rejects_unclosed_bracket():
    with pytest.raises(ValueError, match="unclosed"):
        Path.parse("foo[2")


def test_parse_rejects_non_integer_index():
    with pytest.raises(ValueError, match="non-integer"):
        Path.parse("foo[abc]")


def test_render_round_trip():
    raw = "database.replicas[2].host"
    assert Path.parse(raw).render() == raw


def test_append_field():
    p = Path(("foo",)).append("bar")
    assert p.render() == "foo.bar"


def test_append_index():
    p = Path(("foo",)).append(3)
    assert p.render() == "foo[3]"


def test_path_is_hashable():
    """Paths are used as dict keys (e.g., per-field error map)."""
    d: dict[Path, str] = {}
    d[Path(("a", "b"))] = "x"
    assert d[Path(("a", "b"))] == "x"


def test_path_segment_alias():
    """PathSegment is the canonical name for str | int."""
    s: PathSegment = "name"  # noqa: F841
    i: PathSegment = 0       # noqa: F841
