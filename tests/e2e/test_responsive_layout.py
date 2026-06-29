"""Responsive layout regressions for the React-backed web form."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_mobile_layout_has_no_horizontal_overflow(page: Page, fastapi_url: str) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_role("heading", name="_DemoSchema")).to_be_visible(timeout=5000)

    metrics = page.evaluate(
        """() => ({
            clientWidth: document.documentElement.clientWidth,
            scrollWidth: document.documentElement.scrollWidth,
            formBottom: document.querySelector("section")?.getBoundingClientRect().bottom,
            previewTop: document
                .querySelector('[data-testid="tree-preview"]')
                ?.closest("section")
                ?.getBoundingClientRect()
                .top,
        })"""
    )

    assert metrics["scrollWidth"] <= metrics["clientWidth"]
    assert metrics["previewTop"] >= metrics["formBottom"]
