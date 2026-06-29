"""E2E for the SPA's Save / Cancel action bar.

Phases 1-5 shipped all field components but never wired a top-level
action bar to call ``POST /api/submit`` / ``POST /api/cancel``. Without
these, the SPA is a read-only editor: edits propagate to the FormTree
but the user has no way to commit them. These tests pin the action bar
shape and the success-state UX so the gap can't silently reopen.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_save_and_cancel_buttons_visible(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)
    expect(page.get_by_role("button", name="Save")).to_be_visible()
    expect(page.get_by_role("button", name="Cancel")).to_be_visible()


def test_save_click_marks_submitted_and_shows_success(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    page.get_by_role("button", name="Save").click()

    expect(page.get_by_text("Saved", exact=False)).to_be_visible(timeout=5000)
    expect(page.get_by_role("button", name="Save")).to_have_count(0)


def test_cancel_click_shows_cancelled_state(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    page.get_by_role("button", name="Cancel").click()

    expect(page.get_by_text("Cancelled", exact=False)).to_be_visible(timeout=5000)
    expect(page.get_by_role("button", name="Save")).to_have_count(0)
