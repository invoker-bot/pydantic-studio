"""E2E: UnionField - switch variants, assert preview + server tree.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect


def test_union_variant_buttons_expose_selected_state(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    variant_group = page.get_by_role("group", name="notifier variants")
    expect(variant_group).to_be_visible(timeout=5000)

    email_chip = variant_group.get_by_role("button", name="_EmailNotifier")
    slack_chip = variant_group.get_by_role("button", name="_SlackNotifier")
    expect(email_chip).to_have_attribute("aria-pressed", "true")
    expect(slack_chip).to_have_attribute("aria-pressed", "false")

    slack_chip.click()

    expect(email_chip).to_have_attribute("aria-pressed", "false")
    expect(slack_chip).to_have_attribute("aria-pressed", "true")


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


def test_readonly_union_descendant_disables_variant_switch(
    page: Page, readonly_notifier_address_url: str
) -> None:
    page.goto(f"{readonly_notifier_address_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    slack_chip = page.get_by_role("button", name="_SlackNotifier")
    expect(slack_chip).to_be_visible(timeout=5000)
    expect(slack_chip).to_be_disabled()
