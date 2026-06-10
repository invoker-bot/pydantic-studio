"""Session outcome — the result of an interactive editing session.

Renderer-agnostic: the Textual TUI returns it from ``run_app``; other
frontends can adopt the same contract. Callers branch on it instead of
guessing intent from exceptions or post-quit tree state:

.. code-block:: python

    outcome = run_app(tree)
    if outcome.submitted:
        instance = tree.to_instance()
        ...persist...
    else:
        ...abort without writing...
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = ["EditOutcome"]


@dataclass(frozen=True)
class EditOutcome:
    """How an editing session ended.

    ``submitted`` means the user explicitly committed (Ctrl+S or the
    confirm-exit Save action) and the tree validated at that moment.
    ``cancelled`` covers every other exit — quit on a clean tree,
    explicit discard, or closing the app.
    """

    status: Literal["submitted", "cancelled"]

    @property
    def submitted(self) -> bool:
        return self.status == "submitted"
