"""E2E for Phase 5 temporal fields: date, datetime, time, timedelta.

Drives each input through the browser, fetches /api/tree, and asserts
the wire format the components emit lines up with what the dispatcher's
coercion expects (verified by checking the server tree reflects the
expected ISO-formatted value after the mutation).
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_edit_date_field_updates_tree(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    starts_on = page.get_by_label("starts_on", exact=True)
    expect(starts_on).to_be_visible(timeout=5000)
    starts_on.fill("2026-06-15")
    starts_on.blur()

    # Server tree should now show the new date as an ISO string.
    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "starts_on")
    assert field["kind"] == "date"
    assert field["value"] == "2026-06-15"


def test_edit_datetime_field_updates_tree(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    last_run = page.get_by_label("last_run", exact=True)
    expect(last_run).to_be_visible(timeout=5000)
    # type=datetime-local wants 'YYYY-MM-DDTHH:MM' (no tz, no seconds).
    last_run.fill("2026-03-04T09:15")
    last_run.blur()

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "last_run")
    assert field["kind"] == "datetime"
    # Pydantic emits ISO with seconds (00) and may add tz info; assert
    # the prefix matches what we typed.
    assert field["value"].startswith("2026-03-04T09:15")


def test_edit_time_field_updates_tree(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    cron_at = page.get_by_label("cron_at", exact=True)
    expect(cron_at).to_be_visible(timeout=5000)
    cron_at.fill("18:00:00")
    cron_at.blur()

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "cron_at")
    assert field["kind"] == "time"
    assert field["value"].startswith("18:00")


def test_edit_timedelta_field_updates_tree(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    ttl_input = page.get_by_label("ttl", exact=True)
    expect(ttl_input).to_be_visible(timeout=5000)
    ttl_input.fill("PT2H30M")
    ttl_input.blur()

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "ttl")
    assert field["kind"] == "timedelta"
    # Pydantic JSON-dumps timedelta as the ISO-8601 duration form. The
    # round-trip preserves the value (2.5h = 9000s = PT2H30M). We assert
    # the seconds-equivalent rather than the literal string because
    # Pydantic emits "PT9000S" or "PT2H30M" depending on version. Both
    # encode 2.5 hours.
    assert field["value"] in ("PT2H30M", "PT9000S", "PT2H30M0S")
