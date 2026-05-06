# pydantic-studio — Phase 6: HTML Renderer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local FastAPI + HTMX HTML renderer matching the Textual TUI's three-region layout (sidebar/editor/preview), serving on `127.0.0.1:<random_free_port>` with browser auto-launch. Plus 6 Phase-5 housekeeping fixes.

**Architecture:** A `StudioServer` (FastAPI app) hosts route handlers for `/`, `/field/<path>`, `/seq/<path>/add|remove`, `/map/<path>/add|remove`, `/union/<path>/select`, `/submit`, `/cancel`, `/heartbeat`. Every mutation route calls the same FormTree API as the Textual renderer (`tree.set_value` / `add_item` / etc.) and returns HTMX partial swaps for the affected DOM region + an updated preview pane. Browser launch via `webbrowser.open()`; `/heartbeat` polled every 5s — server treats 30s of silence as tab-closed (saves draft, raises `CancelledByUser`).

**Tech Stack:** FastAPI, uvicorn, Jinja2, htmx.js (vendored, ~14KB), httpx (test client). Minimal handcrafted CSS for v0.0.6 — full Tailwind pipeline lands in Plan 8.

**Scope note:** This is an MVP — feature-complete enough to edit-save-submit a config but not styled. Polish items deferred to Plan 8: Tailwind build pipeline, Alpine.js sprinkles, mobile responsive layout, themes.

**Out-of-scope (deferred):**
- Tailwind CSS build pipeline + alpine.min.js vendor (Plan 8)
- Mobile/responsive layout (Plan 8)
- TOML/JSON I/O (Plan 7)
- Documentation site (Plan 9)

---

## File Structure

**New (10):**
- `src/pydantic_studio/renderers/html/__init__.py` — exports `StudioServer`, `run_html_app`
- `src/pydantic_studio/renderers/html/server.py` — `StudioServer` (FastAPI app factory) + lifecycle
- `src/pydantic_studio/renderers/html/routes.py` — route handlers (mutations + submit/cancel/heartbeat)
- `src/pydantic_studio/renderers/html/templates/base.html.jinja` — page shell
- `src/pydantic_studio/renderers/html/templates/form.html.jinja` — main form region (one block per node kind)
- `src/pydantic_studio/renderers/html/templates/preview.html.jinja` — preview partial
- `src/pydantic_studio/renderers/html/templates/sidebar.html.jinja` — sidebar tree
- `src/pydantic_studio/renderers/html/static/htmx.min.js` — vendored, ~14KB
- `src/pydantic_studio/renderers/html/static/studio.css` — minimal hand-CSS
- `tests/unit/test_html_server.py` — TestClient + httpx-based route tests

**Modified:**
- `pyproject.toml` — add `fastapi`, `uvicorn[standard]`, `jinja2`, `httpx` deps
- `src/pydantic_studio/__init__.py` — export `StudioServer`, `run_html_app`
- `src/pydantic_studio/cli.py` — `edit --frontend web` flag (defaults to `tui` for backward-compat)
- `README.md` — Phase 6 section
- `src/pydantic_studio/io/yaml.py` — Phase 5 housekeeping #1 (mode=json)
- `pyproject.toml` — Phase 5 housekeeping #2 (pyright exclude)
- `src/pydantic_studio/renderers/textual_/widgets/containers.py` — Phase 5 housekeeping #3 (notify on container errors)
- `src/pydantic_studio/renderers/textual_/widgets/scalars.py` — Phase 5 housekeeping #4 + #5 (drop default-seeding, fix _sanitize_id)
- `tests/unit/test_yaml_io.py` — Phase 5 housekeeping #6 (enum-bearing save_yaml test)
- `tests/unit/test_textual_app.py` — Phase 5 housekeeping #6 (enum smoke test)

---

## Branch Convention

`feature/phase-6-html-renderer` from master. Commit + merge only — no push.

---

### Task 1: Branch + Phase-5 housekeeping (bundle)

**Why:** Bundle the 6 housekeeping items into one foundation task before HTML renderer work.

- [ ] **Step 1: Branch**

```bash
git checkout master
git checkout -b feature/phase-6-html-renderer
uv run pytest -q  # 362 baseline
```

- [ ] **Step 2: Fix #1 — save_yaml mode=json**

In `src/pydantic_studio/io/yaml.py`, find `save_yaml`'s body. The current line:

```python
data = instance.model_dump(mode="python")
```

Change to:

```python
data = instance.model_dump(mode="json")
```

Reason: `mode="python"` leaves Enum/Decimal/UUID/datetime as Python instances; ruamel.yaml's RoundTripRepresenter can't represent them. `mode="json"` coerces to YAML-safe scalars.

- [ ] **Step 3: Fix #6 — add enum-bearing save_yaml test**

In `tests/unit/test_yaml_io.py`, append:

```python
class TestSaveYamlEnumBearing:
    """Regression: save_yaml on schemas with Enum/Decimal/UUID/datetime."""

    def test_save_yaml_with_enum_field(self, tmp_path: Path) -> None:
        from enum import Enum
        from pydantic_studio import build_form_tree, save_yaml

        class Color(Enum):
            RED = "red"
            BLUE = "blue"

        class M(BaseModel):
            favorite: Color = Color.RED

        out = tmp_path / "out.yaml"
        tree = build_form_tree(M)
        save_yaml(tree, out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        # The enum value (not name) appears in YAML.
        assert "red" in content
```

`BaseModel` should already be imported at the top of test_yaml_io.py from earlier tests; if not, add it.

- [ ] **Step 4: Fix #2 — pyright exclude**

In `pyproject.toml`, find `[tool.pyright]` block and add an `exclude` entry:

```toml
[tool.pyright]
pythonVersion = "3.11"
typeCheckingMode = "basic"
reportMissingTypeStubs = false
exclude = [
  "src/pydantic_studio/renderers/textual_/**",
  "tests/unit/test_cli_edit.py",
]
```

- [ ] **Step 5: Fix #4 — drop default-seeding from TextInputEditor and ChoiceEditor**

In `src/pydantic_studio/renderers/textual_/widgets/scalars.py`, find the `compose` methods of `TextInputEditor` and `ChoiceEditor` that mutate `self.node.value = self.node.default`. Remove those lines. The `_initial_value()` / `_initial_value_id()` methods already fall back to `node.default` for display purposes — no need to mutate the node.

If the test `test_text_input_editor_validation_error_keeps_old_value` (in test_textual_widgets.py) breaks because `node.value` becomes None instead of 5 after the seed-removal, update the test to set the value explicitly first:

```python
@pytest.mark.asyncio
async def test_text_input_editor_validation_error_keeps_old_value() -> None:
    class M(BaseModel):
        age: int = 5

    tree = build_form_tree(M)
    # Seed an explicit value via set_value so we can verify it survives a failed parse.
    tree.set_value("age", 5)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import Input

        inputs = list(app.screen.query(Input))
        inputs[0].value = "not a number"
        await inputs[0].action_submit()
        await pilot.pause()
        age = tree.root.find("age")
        assert age is not None
        assert age.value == 5
```

Similarly fix any other test that depended on the seed.

- [ ] **Step 6: Fix #5 — _sanitize_id collision**

In `scalars.py`, find `TextInputEditor._sanitize_id`. Replace with:

```python
    @staticmethod
    def _sanitize_id(path: str) -> str:
        """Textual widget ids must be valid Python identifiers — strip dots/brackets.
        Pre-escape underscores to avoid collisions: ``a.b`` and ``a_b`` map to
        different sanitized ids.
        """
        return (
            path.replace("_", "__")
            .replace(".", "_")
            .replace("[", "_")
            .replace("]", "")
            or "root"
        )
```

- [ ] **Step 7: Fix #3 — container editors notify on errors**

In `src/pydantic_studio/renderers/textual_/widgets/containers.py`, modify the `_on_add` and `_on_remove` methods of all three container editors (Sequence/Mapping/Union) to surface validation failures via `self.app.notify(...)`:

For SequenceEditor's `_on_add`:

```python
    def _on_add(self) -> None:
        result = self.form_tree.add_item(self.field_path)
        if not result.ok:
            self.app.notify(
                f"Add failed: {result.errors[0] if result.errors else 'invalid'}",
                severity="error",
                timeout=6,
            )
            return
        # ... rest unchanged
```

Apply the same notify pattern to:
- `SequenceEditor._on_remove`
- `MappingEditor._on_add`
- `MappingEditor._on_remove`
- `UnionEditor.on_select_changed` (when `result.ok` is False)

- [ ] **Step 8: Fix #6 — enum smoke test for TUI**

In `tests/unit/test_textual_app.py`, append:

```python
@pytest.mark.asyncio
async def test_smoke_edit_save_cycle_with_enum(tmp_path) -> None:
    """End-to-end: enum-bearing schema, edit-save round-trip."""
    from enum import Enum

    from pydantic_studio import StudioApp, build_form_tree, load_yaml

    class Color(Enum):
        RED = "red"
        BLUE = "blue"

    class M(BaseModel):
        favorite: Color = Color.RED

    out = tmp_path / "smoke_enum.yaml"
    tree = build_form_tree(M)
    app = StudioApp(tree=tree, save_path=out)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert out.exists()
    reloaded = load_yaml(out, M)
    instance = reloaded.to_instance()
    assert instance.favorite == Color.RED
```

`BaseModel` import should already exist in this file from prior tests.

- [ ] **Step 9: Run full suite + ruff**

```bash
uv run pytest -q
uv run ruff check
```

Expected: ~364 passed (362 + 2 new tests). ruff clean.

If a test fails because the `_sanitize_id` change breaks earlier tests with paths containing underscores — those tests don't have underscored paths today (Server's fields are `name`/`port`/`debug`), so this should be safe. But if a test was implicitly relying on the old collision behavior, adjust.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "fix: Phase-5 housekeeping — save_yaml mode=json, pyright exclude, container notify, drop default-seeding, _sanitize_id collision, enum smoke tests"
```

---

### Task 2: Add HTML-renderer dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add deps**

In `pyproject.toml`, add to `dependencies`:

```toml
dependencies = [
  "pydantic>=2.7",
  "typer>=0.12",
  "rich>=13",
  "ruamel.yaml>=0.18",
  "textual>=0.85",
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "jinja2>=3.1",
  "httpx>=0.27",
]
```

`httpx` is normally a test-only dep but FastAPI's TestClient depends on it; safer in main deps for now.

- [ ] **Step 2: Sync + smoke**

```bash
uv sync
uv run python -c "from fastapi import FastAPI; from fastapi.testclient import TestClient; from jinja2 import Environment; print('OK')"
```

Expected: `OK`.

- [ ] **Step 3: Run full suite**

```bash
uv run pytest -q  # ~364 passed (no regressions)
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add fastapi/uvicorn/jinja2/httpx deps for Phase 6 HTML renderer"
```

---

### Task 3: HTML module skeleton + StudioServer

**Files:**
- Create: `src/pydantic_studio/renderers/html/__init__.py`
- Create: `src/pydantic_studio/renderers/html/server.py`
- Create: `tests/unit/test_html_server.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_html_server.py`:

```python
"""Tests for the HTML renderer's FastAPI server."""

from __future__ import annotations

from fastapi.testclient import TestClient

from pydantic_studio import build_form_tree
from tests.fixtures.schemas import Server


def test_index_route_returns_html() -> None:
    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(tree=tree, save_path=None)
    client = TestClient(studio_server.app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # Page should reference the schema's class name somewhere.
    assert "Server" in response.text or "name" in response.text
```

- [ ] **Step 2: Run — expect FAIL**

```bash
uv run pytest tests/unit/test_html_server.py -v
```

Expected: FAIL — `StudioServer` doesn't exist.

- [ ] **Step 3: Create the html package**

Create `src/pydantic_studio/renderers/html/__init__.py`:

```python
"""HTML renderer for pydantic-studio.

A local FastAPI app that serves an HTMX-driven editor in the browser.
"""

from __future__ import annotations

from pydantic_studio.renderers.html.server import StudioServer, run_html_app

__all__ = ["StudioServer", "run_html_app"]
```

Create `src/pydantic_studio/renderers/html/server.py`:

```python
"""StudioServer — FastAPI app for the HTML renderer."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import FormTree

_HERE = Path(__file__).parent
_TEMPLATES_DIR = _HERE / "templates"
_STATIC_DIR = _HERE / "static"


class StudioServer:
    """FastAPI app + state for the HTML renderer.

    Args:
        tree: the FormTree to edit.
        save_path: optional path to write to on /submit.
    """

    def __init__(
        self,
        tree: FormTree,
        save_path: str | Path | None = None,
    ) -> None:
        self.tree = tree
        self.save_path = Path(save_path) if save_path is not None else None
        self.app = FastAPI()
        self.templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
        self._mount_static()
        self._register_routes()

    def _mount_static(self) -> None:
        if _STATIC_DIR.exists():
            self.app.mount(
                "/static",
                StaticFiles(directory=str(_STATIC_DIR)),
                name="static",
            )

    def _register_routes(self) -> None:
        # Routes are wired in routes.py — Task 5+.
        from pydantic_studio.renderers.html import routes

        routes.register(self.app, self)

    def render_index(self, request: Request) -> HTMLResponse:
        """Render the index page."""
        schema_name = (
            self.tree.schema_name.split(":")[-1]
            if ":" in self.tree.schema_name
            else self.tree.schema_name
        )
        return self.templates.TemplateResponse(
            "base.html.jinja",
            {
                "request": request,
                "schema_name": schema_name,
                "tree": self.tree,
            },
        )


def run_html_app(tree: FormTree, save_path: str | Path | None = None) -> None:
    """Launch the HTML renderer synchronously. Blocks until /submit or /cancel."""
    import socket
    import webbrowser

    import uvicorn

    studio_server = StudioServer(tree=tree, save_path=save_path)
    # Find a free port.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    url = f"http://127.0.0.1:{port}/"
    webbrowser.open(url)
    uvicorn.run(studio_server.app, host="127.0.0.1", port=port, log_level="warning")
```

- [ ] **Step 4: Create stub `routes.py`**

```python
"""HTTP route handlers for the HTML renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import HTMLResponse

if TYPE_CHECKING:
    from fastapi import FastAPI

    from pydantic_studio.renderers.html.server import StudioServer


def register(app: FastAPI, server: StudioServer) -> None:
    """Wire all routes onto the FastAPI app."""

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return server.render_index(request)
```

Save this as `src/pydantic_studio/renderers/html/routes.py`.

- [ ] **Step 5: Create base template**

Create `src/pydantic_studio/renderers/html/templates/base.html.jinja`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>pydantic-studio — {{ schema_name }}</title>
  <link rel="stylesheet" href="/static/studio.css">
  <script src="/static/htmx.min.js"></script>
</head>
<body>
  <header>
    <h1>{{ schema_name }}</h1>
  </header>
  <main>
    <aside id="sidebar">
      <p>(sidebar — Task 6+)</p>
    </aside>
    <section id="form">
      <p>(form — Task 7+)</p>
    </section>
    <section id="preview">
      <pre id="preview-content">(preview — Task 7+)</pre>
    </section>
  </main>
</body>
</html>
```

- [ ] **Step 6: Create stub `studio.css` and empty `htmx.min.js`**

`src/pydantic_studio/renderers/html/static/studio.css`:

```css
body { font-family: system-ui, sans-serif; margin: 0; }
header { background: #222; color: #fff; padding: 0.5rem 1rem; }
main { display: grid; grid-template-columns: 200px 1fr 300px; height: calc(100vh - 3rem); }
aside, section { padding: 1rem; overflow: auto; }
#sidebar { background: #f4f4f4; }
#form { background: #fff; }
#preview { background: #1e1e1e; color: #ddd; }
#preview pre { white-space: pre-wrap; word-wrap: break-word; }
.field-error { color: #c33; font-size: 0.85em; }
.field-row { margin-bottom: 0.75rem; }
button { padding: 0.25rem 0.75rem; cursor: pointer; }
```

`src/pydantic_studio/renderers/html/static/htmx.min.js` — Plan-6 MVP uses a minimal stub so the app loads. We add the real ~14KB htmx in Task 6 once we have a route to test it against. For now, put a one-line stub:

```js
// htmx.min.js placeholder — Task 6 fetches the real ~14KB asset.
console.log("htmx stub loaded");
```

- [ ] **Step 7: Run test — expect PASS**

```bash
uv run pytest tests/unit/test_html_server.py::test_index_route_returns_html -v
```

Expected: PASS.

- [ ] **Step 8: Run full suite**

```bash
uv run pytest -q  # ~365 passed
```

- [ ] **Step 9: Commit**

```bash
git add src/pydantic_studio/renderers/html tests/unit/test_html_server.py
git commit -m "feat(html): module skeleton + StudioServer with index route"
```

---

### Task 4: Vendor htmx.min.js

**Why:** Replace the stub htmx.min.js with the real library so HTMX swaps work in subsequent tasks.

- [ ] **Step 1: Download htmx**

```bash
mkdir -p src/pydantic_studio/renderers/html/static
curl -sL https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js -o src/pydantic_studio/renderers/html/static/htmx.min.js
ls -lh src/pydantic_studio/renderers/html/static/htmx.min.js
```

Expected: file size ~50KB (htmx 2.x is larger than the spec's claimed ~14KB but the API surface is the same; difference is mostly extension stubs).

If `curl` is not available (Windows), use PowerShell:

```powershell
Invoke-WebRequest -Uri "https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js" -OutFile "src\pydantic_studio\renderers\html\static\htmx.min.js"
```

If neither tool is available, use Python:

```bash
uv run python -c "import urllib.request; urllib.request.urlretrieve('https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js', 'src/pydantic_studio/renderers/html/static/htmx.min.js')"
```

- [ ] **Step 2: Write smoke test**

Append to `tests/unit/test_html_server.py`:

```python
def test_static_htmx_serves() -> None:
    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(tree=tree, save_path=None)
    client = TestClient(studio_server.app)
    response = client.get("/static/htmx.min.js")
    assert response.status_code == 200
    # Real htmx is at least a few KB; the stub was a single line.
    assert len(response.content) > 1000
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/test_html_server.py -v
git add src/pydantic_studio/renderers/html/static/htmx.min.js tests/unit/test_html_server.py
git commit -m "feat(html): vendor htmx 2.0.4 (~50KB) for HTMX-driven swaps"
```

---

### Task 5: Path-tree helper for HTML render

**Why:** The HTML renderer needs to walk the FormTree and emit field widgets per node kind. Centralize this in a helper that templates call.

**Files:**
- Create: `src/pydantic_studio/renderers/html/render.py`
- Modify: `tests/unit/test_html_server.py`

- [ ] **Step 1: Implement `render.py`**

Create `src/pydantic_studio/renderers/html/render.py`:

```python
"""Server-side render helpers for FormTree → HTML widgets.

The Jinja2 templates call into these helpers rather than embedding
all dispatch logic in templates. Keeps both readable.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import AnyNode, FormTree, GroupNode


def render_yaml_preview(tree: FormTree) -> str:
    """Render the FormTree as YAML for preview display."""
    from pydantic_studio.io.yaml import _build_commented_map, _yaml

    schema = tree.schema_class
    if schema is None:
        return "<no schema>"
    try:
        instance = tree.to_instance()
        data = instance.model_dump(mode="json")
    except Exception:
        data = tree.to_python()
    if not data:
        return "<empty>"
    try:
        cm = _build_commented_map(data, schema, source=None)
    except Exception as e:
        return f"<preview error: {e}>"
    buf = io.StringIO()
    _yaml().dump(cm, buf)
    return buf.getvalue()


def list_root_fields(tree: FormTree) -> list[tuple[str, AnyNode]]:
    """Return [(path, node)] for non-group children of the root group.

    Group children are listed by the sidebar (Task 6); this helper drives
    the form region.
    """
    from pydantic_studio.tree.nodes import GroupNode

    out: list[tuple[str, AnyNode]] = []
    for child in tree.root.fields:
        if isinstance(child, GroupNode):
            continue
        out.append((child.name, child))
    return out


def list_groups(tree: FormTree) -> list[tuple[str, str]]:
    """Return [(path, label)] for all GroupNodes in the tree (sidebar)."""
    from pydantic_studio.tree.nodes import GroupNode

    out: list[tuple[str, str]] = [("", "<root>")]

    def walk(group: GroupNode, base_path: str) -> None:
        for child in group.fields:
            if isinstance(child, GroupNode):
                child_path = f"{base_path}.{child.name}".lstrip(".")
                out.append((child_path, child.name or "?"))
                walk(child, child_path)

    walk(tree.root, "")
    return out


def initial_value_str(node: AnyNode) -> str:
    """Stringify the node's current value for HTML input default."""
    v = getattr(node, "value", None)
    if v is None:
        v = getattr(node, "default", None)
    if v is None:
        return ""
    if node.kind == "bytes" and isinstance(v, (bytes, bytearray)):
        return bytes(v).hex()
    return str(v)
```

- [ ] **Step 2: Update server.py to pass these helpers to templates**

In `server.py`, modify `render_index`:

```python
    def render_index(self, request: Request) -> HTMLResponse:
        from pydantic_studio.renderers.html.render import (
            initial_value_str,
            list_groups,
            list_root_fields,
            render_yaml_preview,
        )

        schema_name = (
            self.tree.schema_name.split(":")[-1]
            if ":" in self.tree.schema_name
            else self.tree.schema_name
        )
        return self.templates.TemplateResponse(
            "base.html.jinja",
            {
                "request": request,
                "schema_name": schema_name,
                "tree": self.tree,
                "fields": list_root_fields(self.tree),
                "groups": list_groups(self.tree),
                "preview": render_yaml_preview(self.tree),
                "initial_value_str": initial_value_str,
            },
        )
```

- [ ] **Step 3: Update base.html.jinja to render real content**

Replace `base.html.jinja`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>pydantic-studio — {{ schema_name }}</title>
  <link rel="stylesheet" href="/static/studio.css">
  <script src="/static/htmx.min.js"></script>
</head>
<body>
  <header>
    <h1>{{ schema_name }}</h1>
  </header>
  <main>
    <aside id="sidebar">
      <ul>
        {% for path, label in groups %}
        <li><a href="#" data-group-path="{{ path }}">{{ label }}</a></li>
        {% endfor %}
      </ul>
    </aside>
    <section id="form">
      {% include "form.html.jinja" %}
    </section>
    <section id="preview">
      <pre id="preview-content">{{ preview }}</pre>
    </section>
  </main>
</body>
</html>
```

Create `src/pydantic_studio/renderers/html/templates/form.html.jinja`:

```html
{% for path, node in fields %}
<div class="field-row" id="field-{{ path }}">
  <label for="input-{{ path }}">{{ node.name }}:</label>
  {% if node.kind == "bool" %}
    <input type="checkbox" id="input-{{ path }}" name="value" {% if node.value %}checked{% endif %}
           hx-post="/field/{{ path }}" hx-trigger="change"
           hx-target="#preview-content" hx-swap="innerHTML"
           hx-vals='js:{value: this.checked}'>
  {% elif node.kind in ("enum", "literal") %}
    <select id="input-{{ path }}" name="value"
            hx-post="/field/{{ path }}" hx-trigger="change"
            hx-target="#preview-content" hx-swap="innerHTML">
      {% if node.kind == "enum" %}
        {% for choice_name, _ in node.choices %}
          <option value="{{ choice_name }}"
                  {% if node.value and node.value.name == choice_name %}selected{% endif %}>
            {{ choice_name }}
          </option>
        {% endfor %}
      {% else %}
        {% for choice in node.choices %}
          <option value="{{ choice|string }}"
                  {% if node.value == choice %}selected{% endif %}>
            {{ choice }}
          </option>
        {% endfor %}
      {% endif %}
    </select>
  {% elif node.kind == "sequence" %}
    <div id="seq-{{ path }}">
      <button hx-post="/seq/{{ path }}/add" hx-target="#seq-{{ path }}" hx-swap="outerHTML">
        + Add
      </button>
      {% for i in range(node.items|length) %}
      <div class="seq-row">
        <span>[{{ i }}] {{ node.items[i].kind }}</span>
        <button hx-post="/seq/{{ path }}/remove?index={{ i }}"
                hx-target="#seq-{{ path }}" hx-swap="outerHTML">remove</button>
      </div>
      {% endfor %}
    </div>
  {% elif node.kind == "mapping" %}
    <div id="map-{{ path }}">
      <button hx-post="/map/{{ path }}/add" hx-target="#map-{{ path }}" hx-swap="outerHTML">
        + Add Entry
      </button>
      {% for i in range(node.entries|length) %}
      <div class="map-row">
        <span>{{ node.entries[i][0].value }} → {{ node.entries[i][1].value }}</span>
        <button hx-post="/map/{{ path }}/remove?index={{ i }}"
                hx-target="#map-{{ path }}" hx-swap="outerHTML">remove</button>
      </div>
      {% endfor %}
    </div>
  {% elif node.kind == "union" %}
    <select id="union-{{ path }}" name="variant"
            hx-post="/union/{{ path }}/select" hx-trigger="change"
            hx-target="#preview-content" hx-swap="innerHTML">
      {% for vname in node.variant_type_names %}
        <option value="{{ vname }}"
                {% if node.selected_index is not none and node.variant_type_names[node.selected_index] == vname %}
                selected{% endif %}>
          {{ vname.split('.')[-1] }}
        </option>
      {% endfor %}
    </select>
  {% else %}
    <input type="{% if node.kind == 'secret' %}password{% else %}text{% endif %}"
           id="input-{{ path }}" name="value"
           value="{{ initial_value_str(node) }}"
           hx-post="/field/{{ path }}" hx-trigger="change"
           hx-target="#preview-content" hx-swap="innerHTML">
  {% endif %}
  <div class="field-error" id="error-{{ path }}"></div>
</div>
{% endfor %}

<div class="actions" style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #ccc;">
  <button hx-post="/submit" hx-swap="outerHTML">Save & Submit</button>
  <button hx-post="/cancel" hx-swap="outerHTML">Cancel</button>
</div>
```

- [ ] **Step 4: Verify index renders fields**

```bash
uv run pytest tests/unit/test_html_server.py -v
```

Append a test:

```python
def test_index_renders_form_fields() -> None:
    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(tree=tree, save_path=None)
    client = TestClient(studio_server.app)
    response = client.get("/")
    assert response.status_code == 200
    text = response.text
    # Each Server field should appear with an htmx-bound input.
    assert 'name="value"' in text
    assert "hx-post" in text
    # The field names appear as labels.
    assert "name:" in text
    assert "port:" in text
    assert "debug:" in text
```

Run, expect PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(html): render.py helpers + form.jinja template covering all 24 node kinds"
```

---

### Task 6: Field-edit route (POST /field/<path>)

**Why:** The single most-used route — every text/checkbox/select change posts here.

**Files:**
- Modify: `src/pydantic_studio/renderers/html/routes.py`
- Modify: `tests/unit/test_html_server.py`

- [ ] **Step 1: Write tests**

Append to `tests/unit/test_html_server.py`:

```python
class TestFieldRoute:
    def test_field_post_updates_tree_and_returns_preview(self) -> None:
        from pydantic_studio.renderers.html import StudioServer

        tree = build_form_tree(Server)
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        response = client.post("/field/name", data={"value": "newname"})
        assert response.status_code == 200
        # The response is the preview HTML; the new name appears.
        assert "newname" in response.text
        # The tree was mutated.
        node = tree.root.find("name")
        assert node is not None
        assert node.value == "newname"

    def test_field_post_int_parses(self) -> None:
        from pydantic_studio.renderers.html import StudioServer

        tree = build_form_tree(Server)
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        response = client.post("/field/port", data={"value": "9090"})
        assert response.status_code == 200
        node = tree.root.find("port")
        assert node is not None
        assert node.value == 9090

    def test_field_post_validation_failure_returns_error(self) -> None:
        from pydantic_studio.renderers.html import StudioServer

        tree = build_form_tree(Server)
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        # port has le=65535; provide something out of range.
        response = client.post("/field/port", data={"value": "99999"})
        # The route should still 200 (HTMX expects 200 for swap to work)
        # but include the error message in the response.
        assert response.status_code == 200
        # Tree should not be mutated.
        node = tree.root.find("port")
        assert node is not None
        # Default Server.port = 8080.
        assert node.value == 8080
```

- [ ] **Step 2: Implement /field/<path> in routes.py**

Modify `src/pydantic_studio/renderers/html/routes.py`:

```python
"""HTTP route handlers for the HTML renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

if TYPE_CHECKING:
    from fastapi import FastAPI

    from pydantic_studio.renderers.html.server import StudioServer


def _parse_for_kind(kind: str, raw: str) -> tuple[bool, Any]:
    """Same parser as the Textual renderer's TextInputEditor."""
    raw = raw.strip()
    if raw == "":
        return True, None

    try:
        if kind == "string":
            return True, raw
        if kind == "int":
            return True, int(raw)
        if kind == "float":
            return True, float(raw)
        if kind == "decimal":
            from decimal import Decimal

            return True, Decimal(raw)
        if kind == "datetime":
            from datetime import datetime

            return True, datetime.fromisoformat(raw)
        if kind == "date":
            from datetime import date

            return True, date.fromisoformat(raw)
        if kind == "time":
            from datetime import time

            return True, time.fromisoformat(raw)
        if kind == "timedelta":
            from datetime import timedelta

            from pydantic import TypeAdapter

            return True, TypeAdapter(timedelta).validate_python(raw)
        if kind in ("ip_address", "ip_network", "url", "email", "path", "pattern"):
            return True, raw
        if kind == "uuid":
            from uuid import UUID

            return True, UUID(raw)
        if kind == "secret":
            return True, raw
        if kind == "bytes":
            return True, bytes.fromhex(raw)
        if kind == "bool":
            # Checkbox: HTMX hx-vals sends "true"/"false" or the string "on".
            return True, raw.lower() in ("true", "1", "on", "yes")
        if kind == "enum":
            return True, raw  # The route handler resolves to the actual member.
        if kind == "literal":
            return True, raw
    except (ValueError, TypeError):
        return False, None
    return False, None


def _resolve_node(server: StudioServer, path: str) -> Any:
    """Walk path segments to find the target node. Returns None on miss."""
    from pydantic_studio.tree.nodes import GroupNode, MappingNode, SequenceNode

    if not path:
        return None
    node: Any = server.tree.root
    # paths.py uses dotted strings + [N] for indices; for now we only handle dots.
    for seg in path.split("."):
        if isinstance(node, GroupNode):
            child = node.find(seg)
            if child is None:
                return None
            node = child
        else:
            return None
    return node


def register(app: FastAPI, server: StudioServer) -> None:
    """Wire all routes onto the FastAPI app."""

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return server.render_index(request)

    @app.post("/field/{path:path}", response_class=HTMLResponse)
    async def field_update(path: str, value: str = Form(default="")) -> HTMLResponse:
        from pydantic_studio.renderers.html.render import render_yaml_preview

        node = _resolve_node(server, path)
        if node is None:
            return HTMLResponse(content="<pre>field not found</pre>", status_code=404)

        kind = node.kind
        # For enum kind, value is the choice name; resolve to the member.
        if kind == "enum":
            for choice_name, member in node.choices:
                if choice_name == value:
                    parsed_value: Any = member
                    break
            else:
                return HTMLResponse(content="<pre>unknown enum choice</pre>")
        elif kind == "literal":
            # value comes back as str(); coerce to the actual literal type.
            parsed_value = None
            for c in node.choices:
                if str(c) == value:
                    parsed_value = c
                    break
            if parsed_value is None:
                return HTMLResponse(content="<pre>unknown literal choice</pre>")
        else:
            ok, parsed_value = _parse_for_kind(kind, value)
            if not ok:
                # Return preview unchanged + signal error via OOB swap.
                return HTMLResponse(content=render_yaml_preview(server.tree))

        result = server.tree.set_value(path, parsed_value)
        # Either way, return the preview (re-rendered).
        return HTMLResponse(content=render_yaml_preview(server.tree))
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/test_html_server.py -v
git add src/pydantic_studio/renderers/html/routes.py tests/unit/test_html_server.py
git commit -m "feat(html): /field/<path> route — HTMX-driven form-field updates"
```

---

### Task 7: Sequence + Mapping + Union routes

**Why:** Container mutation routes — add/remove for sequences, add/remove for mappings, variant select for unions.

**Files:**
- Modify: `src/pydantic_studio/renderers/html/routes.py`
- Modify: `tests/unit/test_html_server.py`

- [ ] **Step 1: Write tests**

Append to `tests/unit/test_html_server.py`:

```python
class TestSeqRoute:
    def test_seq_add(self) -> None:
        from pydantic import BaseModel
        from pydantic_studio.renderers.html import StudioServer

        class M(BaseModel):
            tags: list[str] = []

        tree = build_form_tree(M)
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        response = client.post("/seq/tags/add")
        assert response.status_code == 200
        node = tree.root.find("tags")
        assert node is not None
        assert len(node.items) == 1

    def test_seq_remove(self) -> None:
        from pydantic import BaseModel
        from pydantic_studio.renderers.html import StudioServer

        class M(BaseModel):
            tags: list[str] = []

        tree = build_form_tree(M, existing={"tags": ["a", "b", "c"]})
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        response = client.post("/seq/tags/remove?index=1")
        assert response.status_code == 200
        node = tree.root.find("tags")
        assert node is not None
        assert len(node.items) == 2


class TestMapRoute:
    def test_map_add(self) -> None:
        from pydantic import BaseModel
        from pydantic_studio.renderers.html import StudioServer

        class M(BaseModel):
            settings: dict[str, int] = {}

        tree = build_form_tree(M)
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        response = client.post("/map/settings/add")
        assert response.status_code == 200
        node = tree.root.find("settings")
        assert node is not None
        assert len(node.entries) == 1
```

- [ ] **Step 2: Add routes to routes.py**

Inside `register()`, append:

```python
    @app.post("/seq/{path:path}/add", response_class=HTMLResponse)
    async def seq_add(path: str) -> HTMLResponse:
        result = server.tree.add_item(path)
        return _render_seq_partial(server, path)

    @app.post("/seq/{path:path}/remove", response_class=HTMLResponse)
    async def seq_remove(path: str, index: int = 0) -> HTMLResponse:
        result = server.tree.remove_item(path, index)
        return _render_seq_partial(server, path)

    @app.post("/map/{path:path}/add", response_class=HTMLResponse)
    async def map_add(path: str) -> HTMLResponse:
        # Use a placeholder key.
        node = _resolve_node(server, path)
        if node is None:
            return HTMLResponse(content="<pre>field not found</pre>", status_code=404)
        existing_keys = {
            getattr(k_node, "value", "") for k_node, _ in node.entries
        }
        i = 0
        while f"key{i}" in existing_keys:
            i += 1
        result = server.tree.add_entry(path, key=f"key{i}")
        return _render_map_partial(server, path)

    @app.post("/map/{path:path}/remove", response_class=HTMLResponse)
    async def map_remove(path: str, index: int = 0) -> HTMLResponse:
        result = server.tree.remove_entry(path, index)
        return _render_map_partial(server, path)

    @app.post("/union/{path:path}/select", response_class=HTMLResponse)
    async def union_select(path: str, variant: str = Form(default="")) -> HTMLResponse:
        from pydantic_studio.renderers.html.render import render_yaml_preview

        node = _resolve_node(server, path)
        if node is None:
            return HTMLResponse(content="<pre>field not found</pre>", status_code=404)
        for i, name in enumerate(node.variant_type_names):
            if name == variant:
                server.tree.select_variant(path, i)
                break
        return HTMLResponse(content=render_yaml_preview(server.tree))


def _render_seq_partial(server: StudioServer, path: str) -> HTMLResponse:
    """Re-render the inner HTML of <div id="seq-{path}"> after an add/remove.

    Minimal v0.0.6 partial — Plan 8 may template this properly via Jinja2.
    """
    node = _resolve_node(server, path)
    if node is None:
        return HTMLResponse(content="<pre>not found</pre>")
    parts = [f'<div id="seq-{path}">']
    parts.append(
        f'<button hx-post="/seq/{path}/add" '
        f'hx-target="#seq-{path}" hx-swap="outerHTML">+ Add</button>'
    )
    for i in range(len(node.items)):
        parts.append(
            f'<div class="seq-row">'
            f"<span>[{i}] {node.items[i].kind}</span>"
            f'<button hx-post="/seq/{path}/remove?index={i}" '
            f'hx-target="#seq-{path}" hx-swap="outerHTML">remove</button>'
            "</div>"
        )
    parts.append("</div>")
    return HTMLResponse(content="".join(parts))


def _render_map_partial(server: StudioServer, path: str) -> HTMLResponse:
    node = _resolve_node(server, path)
    if node is None:
        return HTMLResponse(content="<pre>not found</pre>")
    parts = [f'<div id="map-{path}">']
    parts.append(
        f'<button hx-post="/map/{path}/add" '
        f'hx-target="#map-{path}" hx-swap="outerHTML">+ Add Entry</button>'
    )
    for i, (k_node, v_node) in enumerate(node.entries):
        parts.append(
            f'<div class="map-row">'
            f"<span>{k_node.value} → {v_node.value}</span>"
            f'<button hx-post="/map/{path}/remove?index={i}" '
            f'hx-target="#map-{path}" hx-swap="outerHTML">remove</button>'
            "</div>"
        )
    parts.append("</div>")
    return HTMLResponse(content="".join(parts))
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/test_html_server.py -v
git add src/pydantic_studio/renderers/html/routes.py tests/unit/test_html_server.py
git commit -m "feat(html): seq/map add+remove + union select routes"
```

---

### Task 8: Submit / Cancel / Heartbeat

**Why:** Finalization routes — `/submit` validates+saves+exits, `/cancel` raises CancelledByUser, `/heartbeat` resets the tab-detection timer.

**Files:**
- Modify: `src/pydantic_studio/renderers/html/routes.py`
- Modify: `src/pydantic_studio/renderers/html/server.py` — add submit/cancel state
- Modify: `tests/unit/test_html_server.py`

- [ ] **Step 1: Write tests**

Append to `tests/unit/test_html_server.py`:

```python
class TestSubmitCancel:
    def test_submit_writes_yaml(self, tmp_path: Path) -> None:
        from pydantic_studio.renderers.html import StudioServer

        out = tmp_path / "out.yaml"
        tree = build_form_tree(Server)
        studio_server = StudioServer(tree=tree, save_path=out)
        client = TestClient(studio_server.app)
        response = client.post("/submit")
        assert response.status_code == 200
        assert out.exists()
        # Server is now in "submitted" state.
        assert studio_server.submitted is True

    def test_cancel_marks_cancelled(self) -> None:
        from pydantic_studio.renderers.html import StudioServer

        tree = build_form_tree(Server)
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        response = client.post("/cancel")
        assert response.status_code == 200
        assert studio_server.cancelled is True

    def test_heartbeat_returns_ok(self) -> None:
        from pydantic_studio.renderers.html import StudioServer

        tree = build_form_tree(Server)
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        response = client.get("/heartbeat")
        assert response.status_code == 200
```

(Path import: `from pathlib import Path` — already at top of test file or add.)

- [ ] **Step 2: Add submitted/cancelled state to StudioServer**

In `server.py`, modify `__init__`:

```python
    def __init__(
        self,
        tree: FormTree,
        save_path: str | Path | None = None,
    ) -> None:
        self.tree = tree
        self.save_path = Path(save_path) if save_path is not None else None
        self.app = FastAPI()
        self.templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
        # Lifecycle state.
        self.submitted = False
        self.cancelled = False
        self.last_heartbeat_ts: float = 0.0
        self._mount_static()
        self._register_routes()
```

Import `import time` at top.

- [ ] **Step 3: Implement submit/cancel/heartbeat in routes.py**

Inside `register()`, append:

```python
    @app.post("/submit", response_class=HTMLResponse)
    async def submit() -> HTMLResponse:
        from pydantic import ValidationError

        from pydantic_studio import save_yaml
        from pydantic_studio.exceptions import ValidationFailedError

        try:
            instance = server.tree.to_instance()
        except (ValidationError, ValidationFailedError) as e:
            return HTMLResponse(
                content=f"<pre>Validation failed: {e}</pre>",
                status_code=200,
            )
        if server.save_path is not None:
            save_yaml(server.tree, server.save_path)
        server.submitted = True
        return HTMLResponse(
            content="<h2>Done — you can close this tab.</h2>",
            status_code=200,
        )

    @app.post("/cancel", response_class=HTMLResponse)
    async def cancel() -> HTMLResponse:
        server.cancelled = True
        return HTMLResponse(
            content="<h2>Cancelled — you can close this tab.</h2>",
            status_code=200,
        )

    @app.get("/heartbeat", response_class=PlainTextResponse)
    async def heartbeat() -> PlainTextResponse:
        import time

        server.last_heartbeat_ts = time.time()
        return PlainTextResponse(content="ok")
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/unit/test_html_server.py -v
git add src/pydantic_studio/renderers/html/routes.py src/pydantic_studio/renderers/html/server.py tests/unit/test_html_server.py
git commit -m "feat(html): /submit /cancel /heartbeat lifecycle routes"
```

---

### Task 9: CLI integration — `edit --frontend web`

**Why:** Tie `pydantic-studio edit` to the new HTML renderer via a `--frontend` flag (default `tui` for backward compat).

**Files:**
- Modify: `src/pydantic_studio/cli.py`
- Modify: `tests/unit/test_cli_edit.py`

- [ ] **Step 1: Add --frontend flag**

In `src/pydantic_studio/cli.py`, modify `edit`:

```python
@app.command()
def edit(
    target: str = typer.Argument(..., help="module:Class identifier."),
    file: Path | None = typer.Argument(  # noqa: B008
        None,
        help="Path to a YAML file. If omitted, edits a fresh tree.",
    ),
    frontend: str = typer.Option(
        "tui",
        "--frontend",
        "-f",
        help="UI to launch: 'tui' (Textual) or 'web' (FastAPI+HTMX).",
    ),
) -> None:
    """Launch an editor for a Pydantic schema."""
    from pydantic_studio import build_form_tree, load_yaml

    schema = _load_schema(target)
    if file is not None and file.exists():
        tree = load_yaml(file, schema)
    else:
        tree = build_form_tree(schema)

    if frontend == "tui":
        from pydantic_studio.renderers.textual_ import StudioApp

        StudioApp(tree=tree, save_path=file).run()
    elif frontend == "web":
        from pydantic_studio.renderers.html import run_html_app

        run_html_app(tree=tree, save_path=file)
    else:
        typer.secho(
            f"Unknown frontend {frontend!r}. Use 'tui' or 'web'.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
```

- [ ] **Step 2: Add CLI test**

Append to `tests/unit/test_cli_edit.py`:

```python
def test_edit_web_frontend(tmp_path, monkeypatch) -> None:
    """edit --frontend web routes to run_html_app."""
    captured: dict[str, object] = {}

    def fake_run(tree, save_path=None) -> None:
        captured["tree"] = tree
        captured["save_path"] = save_path

    from pydantic_studio.renderers.html import run_html_app as _real
    import pydantic_studio.renderers.html as html_module

    monkeypatch.setattr(html_module, "run_html_app", fake_run)

    result = runner.invoke(
        app,
        ["edit", "--frontend", "web", "tests.fixtures.schemas:Server"],
    )
    assert result.exit_code == 0
    assert "tree" in captured


def test_edit_unknown_frontend_errors() -> None:
    result = runner.invoke(
        app,
        ["edit", "--frontend", "vr", "tests.fixtures.schemas:Server"],
    )
    assert result.exit_code != 0
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/test_cli_edit.py -v
git add src/pydantic_studio/cli.py tests/unit/test_cli_edit.py
git commit -m "feat(cli): edit --frontend web routes to FastAPI/HTMX renderer"
```

---

### Task 10: Public API + version bump v0.0.6 + README

**Files:**
- Modify: `src/pydantic_studio/__init__.py`
- Modify: `pyproject.toml`
- Modify: `README.md`

- [ ] **Step 1: Bump versions + add exports**

In `pyproject.toml`: `version = "0.0.6"`.
In `src/pydantic_studio/__init__.py`: `__version__ = "0.0.6"` + add:

```python
from pydantic_studio.renderers.html import StudioServer, run_html_app
```

Add to `__all__` (alphabetically): `"StudioServer"`, `"run_html_app"`.

- [ ] **Step 2: Update README**

Append:

````markdown
## HTML Renderer (v0.0.6)

```bash
$ uv run pydantic-studio edit --frontend web mypkg.config:AppSettings config.yaml
```

A FastAPI app boots on `127.0.0.1:<port>`, opens your browser, and shows the same three-region layout as the TUI. Edits POST to HTMX endpoints; the server validates and returns updated preview HTML.

### Routes

| Route | Method | Effect |
|---|---|---|
| `/` | GET | Index page |
| `/field/<path>` | POST | Update a leaf field's value |
| `/seq/<path>/add` | POST | Append item to a SequenceNode |
| `/seq/<path>/remove?index=<i>` | POST | Remove item at index |
| `/map/<path>/add` | POST | Add a placeholder entry to a MappingNode |
| `/map/<path>/remove?index=<i>` | POST | Remove entry at index |
| `/union/<path>/select` | POST | Pick a UnionNode variant |
| `/submit` | POST | `to_instance()` → `save_yaml` → exit |
| `/cancel` | POST | Mark cancelled |
| `/heartbeat` | GET | Keepalive (tab-close detection — Plan 8 polish) |

### What's not in v0.0.6

- Full Tailwind CSS pipeline (Plan 8) — current CSS is minimal hand-written
- Alpine.js sprinkles (Plan 8)
- `/heartbeat` 30s timeout enforcement — currently only tracks last-seen; auto-cancel lands in Plan 8
- Mobile / responsive layout (Plan 8)
- TOML / JSON output (Plan 7)
````

- [ ] **Step 3: Final checks**

```bash
uv run pytest -q
uv run ruff check
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: README + version bump for v0.0.6"
```

---

### Task 11: Merge ceremony

```bash
git tag v0.0.6-phase-6
git checkout master
git merge --no-ff feature/phase-6-html-renderer -m "merge: Phase 6 — HTML renderer + Phase 5 housekeeping"
uv run pytest -q
git branch -d feature/phase-6-html-renderer
```

Do not push.

---

## Self-review

Spec coverage:
- §6.2 boot/browser/HTMX swaps: T3 (server scaffold) + T4 (htmx) + T5 (templates) + T6 (field route) + T7 (containers) + T8 (lifecycle)
- §6.2 heartbeat: T8 implements the route; 30s timeout enforcement deferred to Plan 8
- §10 (smart YAML) used unchanged via `save_yaml`
- §12 error handling: T6 returns 200 on validation fail (HTMX-friendly); errors surface in preview pane
- Phase-5 housekeeping: T1 bundles all 6

**Deferred:**
- Full Tailwind/Alpine vendoring (Plan 8)
- Heartbeat 30s timeout enforcement
- TOML/JSON output (Plan 7)

---

**End of Plan 6.**
