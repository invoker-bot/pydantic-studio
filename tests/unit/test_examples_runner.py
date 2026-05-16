from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from pydantic import BaseModel


def _load_runner():
    path = Path(__file__).parents[2] / "examples" / "_runner.py"
    spec = importlib.util.spec_from_file_location("examples_runner_for_tests", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DemoSchema(BaseModel):
    name: str = "demo"


def test_examples_runner_defaults_to_console(monkeypatch) -> None:
    runner = _load_runner()
    calls: list[str] = []

    monkeypatch.setattr(sys, "argv", ["example.py"])
    monkeypatch.setattr(runner, "_console", lambda schema, existing: calls.append("console"))

    runner.run_demo(DemoSchema)

    assert calls == ["console"]


def test_examples_runner_accepts_explicit_console(monkeypatch) -> None:
    runner = _load_runner()
    calls: list[str] = []

    monkeypatch.setattr(sys, "argv", ["example.py", "console"])
    monkeypatch.setattr(runner, "_console", lambda schema, existing: calls.append("console"))

    runner.run_demo(DemoSchema)

    assert calls == ["console"]
