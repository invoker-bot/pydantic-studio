"""Textual screens for pydantic-studio.

After the M1 cutover, the primary screen is ``ConfigScreen`` — the
single-panel Claude Code /config-style editor. ``ChooserScreen``
handles ChoiceCell large-choice fields. ``ErrorsScreen`` lists
validation failures when a Ctrl+S save is rejected. The legacy
three-pane ``EditorScreen`` (sidebar + editor pane + preview) was
retired along with its supporting widgets in `widgets/scalars.py`,
`containers.py`, `editor.py`, `sidebar.py`, `preview.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding, BindingType
from textual.screen import Screen

from pydantic_studio.renderers.textual_.widgets.breadcrumb import Breadcrumb
from pydantic_studio.renderers.textual_.widgets.field_list import (
    CursorMoved,
    FieldListView,
)
from pydantic_studio.renderers.textual_.widgets.footer_hints import FooterHints
from pydantic_studio.renderers.textual_.widgets.help_bar import HelpBar

if TYPE_CHECKING:
    from typing import Any

    from textual.app import ComposeResult

    from pydantic_studio.renderers.textual_.widgets.cells import (
        EditModeEntered,
        EditModeExited,
    )
    from pydantic_studio.tree.nodes import AnyNode, FormTree, GroupNode


class ConfigScreen(Screen):
    """TUI v2 single-panel screen: Breadcrumb + FieldListView + HelpBar
    + FooterHints.

    M1 ships the chrome; M2 lights up editing via per-kind cells. The
    screen listens for ``EditModeEntered`` / ``EditModeExited`` messages
    posted by cells and flips the footer between "idle" and "editing".
    The same screen is reused for drilled-in groups, sequences,
    mappings, and union selections; footer hints adapt to the active
    container.

    `/` mounts a filter Input above the list (group screens only). The
    Input lives on the *screen*, not inside FieldListView — the list
    recomposes on every filter keystroke, and an Input inside it would
    be rebuilt (and lose focus) per character.
    """

    CSS_PATH = "theme.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        # Ctrl+F: the universal find chord. (A bare `/` would type into
        # the form-mode persistent Inputs.) priority so it also works
        # while an Input has focus.
        Binding("ctrl+f", "show_filter", "filter", show=False, priority=True),
        Binding("escape", "dismiss_filter", "clear filter", show=False),
    ]

    _FILTER_INPUT_ID = "field-filter"

    def __init__(
        self,
        group: GroupNode,
        form_tree: FormTree,
        breadcrumb_parts: list[str],
        base_path: str = "",
    ) -> None:
        super().__init__()
        self._group = group
        self._form_tree = form_tree
        self._breadcrumb_parts = breadcrumb_parts
        self._base_path = base_path
        self._footer_mode = self._mode_for_container(group)

    def compose(self) -> ComposeResult:
        from pydantic_studio.renderers.textual_.widgets.action_bar import ActionBar

        yield Breadcrumb(parts=self._breadcrumb_parts)
        yield FieldListView(
            group=self._group,
            form_tree=self._form_tree,
            base_path=self._base_path,
        )
        yield HelpBar()
        yield ActionBar()
        yield FooterHints(mode=self._footer_mode)

    def _mode_for_container(self, group: AnyNode) -> str:
        if group.kind == "sequence":
            return "sequence"
        if group.kind == "mapping":
            return "mapping"
        if group.kind == "union":
            return "union"
        return "idle"

    def action_show_filter(self) -> None:
        """`/` — mount (or refocus) the filter input. Group screens only:
        sequence/mapping rows are positional, and filtering would desync
        the cursor index from the container index used by A/D/move."""
        from textual.widgets import Input

        if self._group.kind != "group":
            return
        existing = self._filter_input()
        if existing is not None:
            existing.focus()
            return
        field_list = self.query_one(FieldListView)
        inp = Input(placeholder="filter fields…", id=self._FILTER_INPUT_ID)
        self.mount(inp, before=field_list)
        inp.focus()

    def action_dismiss_filter(self) -> None:
        """Esc while the filter input is focused (the input itself has no
        escape binding, so the event resolves at screen level)."""
        self.clear_filter()

    def _filter_input(self):
        from textual.widgets import Input

        try:
            return self.query_one(f"#{self._FILTER_INPUT_ID}", Input)
        except Exception:
            return None

    def clear_filter(self) -> bool:
        """Remove the filter input and restore all rows.

        Returns True when there was a filter to clear — callers use the
        result to implement layered Esc (edit > filter > screen > session).
        """
        inp = self._filter_input()
        if inp is None:
            return False
        inp.remove()
        view = self.query_one(FieldListView)
        view.set_filter("")
        view.focus()
        return True

    def on_input_changed(self, event) -> None:
        if getattr(event.input, "id", None) != self._FILTER_INPUT_ID:
            return  # cell Inputs bubble up here too — not ours
        self.query_one(FieldListView).set_filter(event.value)

    def on_input_submitted(self, event) -> None:
        if getattr(event.input, "id", None) != self._FILTER_INPUT_ID:
            return
        # Keep the filter (and the input as its visible indicator);
        # hand focus back to the narrowed list.
        self.query_one(FieldListView).focus()

    def _refresh_help_bar(self, node: Any, path: str) -> None:
        try:
            bar = self.query_one(HelpBar)
        except Exception:
            return
        readonly = path in getattr(self.app, "readonly_paths", frozenset())
        missing = len(self._form_tree.missing_required_paths())
        bar.show_node(node, missing_count=missing, readonly=readonly)

    def on_cursor_moved(self, event: CursorMoved) -> None:
        self._refresh_help_bar(event.node, event.path)

    def on_cell_value_changed(self, event) -> None:
        """A form-mode commit/revert happened — refresh the HelpBar
        (missing-required counter) for the still-focused row."""
        try:
            view = self.query_one(FieldListView)
            specs = view._row_specs()
            if 0 <= view.cursor < len(specs):
                spec = specs[view.cursor]
                self._refresh_help_bar(spec.node, spec.path)
        except Exception:
            return

    def on_edit_mode_entered(self, event: EditModeEntered) -> None:
        try:
            footer = self.query_one(FooterHints)
            footer.set_mode("editing")
        except Exception:
            return

    def on_edit_mode_exited(self, event: EditModeExited) -> None:
        try:
            footer = self.query_one(FooterHints)
            footer.set_mode(self._footer_mode)
        except Exception:
            return
        # A commit may have filled (or blanked) values — refresh the
        # missing-required counter for the still-focused row.
        try:
            view = self.query_one(FieldListView)
            specs = view._row_specs()
            if 0 <= view.cursor < len(specs):
                spec = specs[view.cursor]
                self._refresh_help_bar(spec.node, spec.path)
        except Exception:
            return


class ChooserScreen(Screen):
    """Push-screen presenter for ChoiceCell large-choice fields.

    Lists all options; up/down to navigate, Enter to commit + pop.
    """

    CSS_PATH = "theme.tcss"

    def __init__(
        self,
        node: AnyNode,
        path: str,
        form_tree: FormTree,
    ) -> None:
        super().__init__()
        self._node = node
        self._path = path
        self._form_tree = form_tree

    @property
    def options(self) -> list[tuple[str, Any]]:
        if self._node.kind == "enum":
            from pydantic_studio.renderers.textual_.widgets.cells.labels import enum_label

            return [(enum_label(member), member) for _, member in self._node.choices]
        return [(str(c), c) for c in self._node.choices]

    def select(self, idx: int) -> None:
        if not (0 <= idx < len(self.options)):
            return
        _, value = self.options[idx]
        self._form_tree.set_value(self._path, value)
        self.app.pop_screen()

    def compose(self) -> ComposeResult:
        from textual.widgets import Label, ListItem, ListView

        with ListView(id="chooser-list"):
            for label, _ in self.options:
                yield ListItem(Label(label))


class RenameKeyScreen(Screen):
    """Prompt for renaming a mapping key."""

    CSS_PATH = "theme.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "back", show=False),
    ]

    def __init__(
        self,
        form_tree: FormTree,
        mapping_path: str,
        index: int,
        initial: str,
        field_list: FieldListView,
    ) -> None:
        super().__init__()
        self._form_tree = form_tree
        self._mapping_path = mapping_path
        self._index = index
        self._initial = initial
        self._field_list = field_list
        self._error: str | None = None

    def compose(self) -> ComposeResult:
        from textual.widgets import Input, Static

        yield Static("Rename key", classes="rename-key--title", markup=False)
        yield Input(value=self._initial, classes="rename-key--input")
        yield Static(self.error_text, classes="rename-key--error", markup=False)

    @property
    def error_text(self) -> str:
        return "" if self._error is None else f"[!] {self._error}"

    def on_mount(self) -> None:
        from textual.widgets import Input

        self.query_one(Input).focus()

    def on_input_submitted(self, event) -> None:
        result = self._field_list.rename_key_at(self._index, event.value)
        if not result.ok:
            self._error = "; ".join(result.errors) or "invalid"
            try:
                from textual.widgets import Static

                self.query_one(".rename-key--error", Static).update(self.error_text)
            except Exception:
                pass
            return
        self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.pop_screen()


class ConfirmExitScreen(Screen):
    """Unsaved-changes guard, pushed by ``StudioApp.action_quit`` when
    the tree is dirty. Three exits:

    - ``s`` — save & exit (same path as Ctrl+S; validation failures
      bounce back to the editor with the errors screen)
    - ``d`` — discard & exit (session ends ``cancelled``)
    - ``Esc`` — keep editing
    """

    CSS_PATH = "theme.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("s", "save_and_exit", "save & exit", show=False),
        Binding("d", "discard", "discard", show=False),
        Binding("escape", "keep_editing", "keep editing", show=False),
    ]

    def compose(self) -> ComposeResult:
        from textual.widgets import Static

        yield Static(
            "You have unsaved changes.", classes="confirm-exit--title", markup=False
        )
        yield Static(
            "S save & exit | D discard | Esc keep editing",
            classes="confirm-exit--hints",
            markup=False,
        )

    def action_save_and_exit(self) -> None:
        self.app._submit()  # type: ignore[attr-defined]

    def action_discard(self) -> None:
        self.app._finish("cancelled")  # type: ignore[attr-defined]

    def action_keep_editing(self) -> None:
        self.app.pop_screen()


class ErrorsScreen(Screen):
    """Modal listing validation errors after a failed save.

    Pushed by :meth:`StudioApp.action_save` when ``save_yaml`` raises
    :exc:`ValidationFailedError`. The body shows one line per error;
    Esc dismisses, returns control to the underlying ConfigScreen, and
    jumps the cursor to the first offending field so the fix is one
    keystroke away instead of a memory exercise.
    """

    CSS_PATH = "theme.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "back", show=False),
        Binding("enter", "dismiss", "back", show=False),
    ]

    def __init__(self, errors: list[str], paths: list[str] | None = None) -> None:
        super().__init__()
        self._errors = list(errors)
        self._paths = list(paths) if paths is not None else []

    @property
    def error_text(self) -> str:
        """Concatenated error lines — used by tests to assert content."""
        return "\n".join(self._errors)

    def compose(self) -> ComposeResult:
        from textual.containers import VerticalScroll
        from textual.widgets import Static

        header = "Validation failed — fix these before saving:"
        yield Static(header, classes="errors-screen--header")
        with VerticalScroll(id="errors-list"):
            for err in self._errors:
                yield Static(f"  - {err}", classes="errors-screen--item")
        yield Static(
            "Esc / Enter: back to editor",
            classes="errors-screen--footer",
        )

    def action_dismiss(self) -> None:  # type: ignore[override]
        """Pop back to the editor and focus the first offending field."""
        self.app.pop_screen()
        if not self._paths:
            return
        try:
            view = self.app.screen.query_one(FieldListView)
        except Exception:
            return
        view.focus_path(self._paths[0])
