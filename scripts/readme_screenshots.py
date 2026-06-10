"""Regenerate the README screenshots in docs/assets/readme/.

Drives both frontends against ``examples/02_server_config.py``'s
ServerConfig (so every shot is reproducible with the shipped example):

- TUI: Textual's pilot harness + ``export_screenshot()`` SVGs
- Web: a throwaway StudioServer + headless Chromium PNGs

Run from the repo root::

    uv run python scripts/readme_screenshots.py
"""

from __future__ import annotations

import asyncio
import socket
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "docs" / "assets" / "readme"
sys.path.insert(0, str(REPO / "examples"))

from importlib import import_module  # noqa: E402

ServerConfig = import_module("02_server_config").ServerConfig

from pydantic_studio import build_form_tree  # noqa: E402
from pydantic_studio.renderers.textual_.app import StudioApp  # noqa: E402

TUI_SIZE = (96, 16)


async def _tui_form_shot() -> str:
    """Hero: form mode mid-flight — typed name, cursor on a required
    field, HelpBar guidance + required counter, ActionBar buttons."""
    tree = build_form_tree(ServerConfig)
    app = StudioApp(tree=tree, save_path="server.yaml")
    async with app.run_test(size=TUI_SIZE) as pilot:
        await pilot.pause()
        for ch in "api-gateway":
            await pilot.press(ch)
        await pilot.press("enter")  # commit + advance to api_url (required)
        await pilot.pause()
        return app.export_screenshot(title="pydantic-studio — examples/02_server_config.py tui")


async def _tui_sequence_shot() -> str:
    """Container screen: breadcrumb, [ + add item ] row, per-row ✕."""
    tree = build_form_tree(ServerConfig)
    tree.set_value("name", "api-gateway")
    tree.set_value("database.primary.host", "db-1.internal")
    tree.add_item("database.read_replicas")
    tree.set_value("database.read_replicas.0.host", "db-ro-1.internal")
    tree.add_item("database.read_replicas")
    tree.set_value("database.read_replicas.1.host", "db-ro-2.internal")
    app = StudioApp(tree=tree, save_path="server.yaml")
    async with app.run_test(size=TUI_SIZE) as pilot:
        await pilot.pause()
        from pydantic_studio.renderers.textual_.widgets.field_list import (
            FieldListView,
        )

        # Drill: root -> database -> read_replicas (breadcrumb grows).
        app.screen.query_one(FieldListView).focus_path("database")
        await pilot.press("enter")
        await pilot.pause()
        app.screen.query_one(FieldListView).focus_path("database.read_replicas")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        return app.export_screenshot(title="pydantic-studio — sequence editing")


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _web_shots() -> None:
    import uvicorn
    from playwright.sync_api import sync_playwright

    from pydantic_studio.renderers.html.server import StudioServer

    tree = build_form_tree(ServerConfig)
    tree.set_value("name", "api-gateway")
    server = StudioServer(
        tree=tree, save_path="server.yaml", heartbeat_timeout_seconds=3600
    )
    port = _free_port()
    config = uvicorn.Config(
        server.app, host="127.0.0.1", port=port, log_level="error"
    )
    uv_server = uvicorn.Server(config)
    thread = threading.Thread(target=uv_server.run, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}/"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 860})
        page.goto(url)
        page.wait_for_selector("text=ServerConfig")
        page.screenshot(
            path=str(ASSETS / "web-form.png"),
            clip={"x": 0, "y": 0, "width": 1440, "height": 560},
        )

        # Submit with required fields missing -> anchored errors.
        page.get_by_role("button", name="Save").click()
        page.wait_for_selector("[data-testid=submit-errors]")
        page.wait_for_timeout(900)  # let the smooth-scroll settle
        page.screenshot(path=str(ASSETS / "web-errors.png"))
        browser.close()

    uv_server.should_exit = True
    thread.join(timeout=5)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    svg = asyncio.run(_tui_form_shot())
    (ASSETS / "tui-form.svg").write_text(svg, encoding="utf-8")
    svg = asyncio.run(_tui_sequence_shot())
    (ASSETS / "tui-sequence.svg").write_text(svg, encoding="utf-8")
    _web_shots()
    for name in ("tui-form.svg", "tui-sequence.svg", "web-form.png", "web-errors.png"):
        size = (ASSETS / name).stat().st_size
        print(f"  {name}: {size / 1024:.0f} KiB")


if __name__ == "__main__":
    main()
