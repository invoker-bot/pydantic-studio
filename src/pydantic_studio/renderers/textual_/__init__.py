"""Textual renderer for pydantic-studio.

Public exports:
- ``StudioApp`` — the App class, instantiate with a FormTree to launch
- ``run_app`` — convenience function that builds an app and runs it
  synchronously, returning the saved BaseModel instance (or None if the
  user quit without saving).
"""

from __future__ import annotations

from pydantic_studio.renderers.textual_.app import StudioApp, run_app

__all__ = ["StudioApp", "run_app"]
