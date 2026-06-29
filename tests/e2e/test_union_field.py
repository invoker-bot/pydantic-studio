"""E2E: UnionField - switch variants, assert preview + server tree.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect


def test_switch_union_variant(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    # The notifier field has a default of EmailNotifier so the email
    # chip is initially selected. Click the Slack chip to switch.
    slack_chip = page.get_by_role("button", name="_SlackNotifier")
    expect(slack_chip).to_be_visible(timeout=5000)
    slack_chip.click()

    # Server tree should now show the Slack variant selected.
    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    notifier_field = next(
        f for f in body["root"]["fields"] if f["name"] == "notifier"
    )
    assert notifier_field["selected_index"] is not None
    selected = notifier_field["selected"]
    assert selected is not None
    # The selected GroupNode's schema_class short name should be SlackNotifier
    assert "Slack" in selected["schema_class"]

    group_toggle = page.get_by_role("button", name=re.compile(r"^group\s+_SlackNotifier\b"))
    expect(group_toggle).to_be_visible(timeout=5000)
    group_toggle.click()

    channel_input = page.get_by_label("channel", exact=True)
    expect(channel_input).to_be_visible(timeout=5000)
    channel_input.fill("#alerts")
    channel_input.blur()

    preview = page.get_by_test_id("tree-preview")
    expect(preview).to_contain_text("notifier:", timeout=5000)
    expect(preview).to_contain_text("kind: slack", timeout=5000)
    expect(preview).to_contain_text("channel: '#alerts'", timeout=5000)

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    notifier_field = next(
        f for f in body["root"]["fields"] if f["name"] == "notifier"
    )
    channel = next(
        f for f in notifier_field["selected"]["fields"] if f["name"] == "channel"
    )
    assert channel["value"] == "#alerts"
