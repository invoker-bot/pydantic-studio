# Embedding

pydantic-studio can run as a standalone editor or as an embedded editor inside
a larger Python application.

## ASGI Web Embedding

The Web renderer exposes a mountable ASGI application. FastAPI and Starlette are
both supported hosts because both expose Starlette's `mount(...)` API, but the
public contract is ASGI rather than FastAPI-specific.

```python
from starlette.applications import Starlette

from pydantic_studio import build_form_tree, mount_html_app
from myapp.config import Settings

host = Starlette()
tree = build_form_tree(Settings)
server = mount_html_app(host, "/studio", tree=tree)
```

Open `/studio/` in the host app. The browser uses `/studio/api/*` and
`/studio/static/*`; the editor does not assume it owns the site root.

FastAPI hosts use the same helper:

```python
from fastapi import FastAPI

from pydantic_studio import build_form_tree, mount_html_app
from myapp.config import Settings

app = FastAPI()
server = mount_html_app(app, "/studio", tree=build_form_tree(Settings))
```

The returned `StudioServer` exposes `server.session`. Persist only after an
explicit submit:

```python
if server.session.submitted:
    settings = server.session.tree.to_instance()
```

## Textual Embedding

Textual applications can push `StudioScreen` with an `EditSession`:

```python
from textual.app import App

from pydantic_studio import EditSession, StudioScreen, build_form_tree
from myapp.config import Settings


class HostApp(App):
    def __init__(self) -> None:
        super().__init__()
        self.session = EditSession(tree=build_form_tree(Settings))

    def on_mount(self) -> None:
        self.push_screen(StudioScreen(self.session))

    def on_studio_session_ended(self, event) -> None:
        if event.outcome.submitted:
            settings = self.session.tree.to_instance()
```

`StudioApp` and `run_app(...)` remain the standalone launchers.
