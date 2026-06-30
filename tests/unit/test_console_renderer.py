from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from pydantic_studio import build_form_tree, load_yaml
from pydantic_studio.renderers.console import run_console_app
from pydantic_studio.variants import VariantRegistry, VariantSpec, build_variant_form_tree


class PromptSchema(BaseModel):
    name: str = "prod"
    port: int = 8080
    debug: bool = False
    level: Literal["debug", "info"] = "info"


class PromptAnySchema(BaseModel):
    payload: Any = None


class ConsoleEmail(BaseModel):
    address: str = "ops@example.com"


class ConsoleSlack(BaseModel):
    channel: str = "#ops"


def _input_from(values: list[str]):
    prompts: list[str] = []
    iterator = iter(values)

    def input_func(prompt: str) -> str:
        prompts.append(prompt)
        return next(iterator)

    return input_func, prompts


def test_console_prompts_each_leaf_and_saves_yaml(tmp_path) -> None:
    tree = build_form_tree(PromptSchema)
    out = tmp_path / "config.yaml"
    input_func, prompts = _input_from(["staging", "9090", "y", "debug"])
    lines: list[str] = []

    run_console_app(tree, out, input_func=input_func, print_func=lines.append)

    reloaded = load_yaml(out, PromptSchema).to_instance()
    assert reloaded == PromptSchema(
        name="staging",
        port=9090,
        debug=True,
        level="debug",
    )
    assert prompts == [
        "name [prod]: ",
        "port [8080]: ",
        "debug [false]: ",
        "level (debug/info) [info]: ",
    ]
    assert lines[-1] == f"saved to {out}"


def test_console_blank_answers_keep_defaults(tmp_path) -> None:
    tree = build_form_tree(PromptSchema)
    out = tmp_path / "config.yaml"
    input_func, _ = _input_from(["", "", "", ""])

    run_console_app(tree, out, input_func=input_func, print_func=lambda _: None)

    assert load_yaml(out, PromptSchema).to_instance() == PromptSchema()


def test_console_reprompts_after_parse_error(tmp_path) -> None:
    tree = build_form_tree(PromptSchema)
    out = tmp_path / "config.yaml"
    input_func, _ = _input_from(["prod", "abc", "9091", "", ""])
    lines: list[str] = []

    run_console_app(tree, out, input_func=input_func, print_func=lines.append)

    assert load_yaml(out, PromptSchema).to_instance().port == 9091
    assert "cannot parse 'abc' as int" in lines


def test_console_any_preserves_non_standard_json_as_plain_text() -> None:
    from pydantic_studio.renderers.console import _parse_node_value

    tree = build_form_tree(PromptAnySchema)
    node = tree.root.find("payload")
    assert node is not None

    for raw in ("NaN", "Infinity", "-Infinity", '{"a": 1, "a": 2}'):
        ok, parsed = _parse_node_value(node, raw)
        assert ok is True
        assert parsed == raw


def test_console_prompts_for_root_variant_before_fields(tmp_path) -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=ConsoleEmail, label="Email"),
                VariantSpec(id="slack", model=ConsoleSlack, label="Slack"),
            ]
        ),
        selected_id="email",
        discriminator="class_name",
        persistence="inline_discriminator",
    )
    out = tmp_path / "config.yaml"
    input_func, prompts = _input_from(["slack", "#alerts"])

    run_console_app(tree, out, input_func=input_func, print_func=lambda _: None)

    assert prompts[0] == "variant (email/slack) [email]: "
    assert prompts[1] == "channel [#ops]: "
    assert "class_name: slack" in out.read_text(encoding="utf-8")
