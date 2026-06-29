"""E2E for Phase 5 special fields: uuid (regenerate button), secret
(show toggle), pattern (flag chips render).
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_uuid_regenerate_button_updates_value(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    request_id = page.get_by_label("request_id", exact=True)
    expect(request_id).to_be_visible(timeout=5000)
    expect(request_id).to_have_value(
        "00000000-0000-0000-0000-000000000000", timeout=5000
    )

    # Click regenerate. crypto.randomUUID returns a fresh v4 UUID.
    regen = page.get_by_role("button", name="regenerate request_id")
    expect(regen).to_be_visible()
    regen.click()

    # The input now holds a different UUID. Wait for the round-trip
    # to update node.value (re-render via useQuery).
    expect(request_id).not_to_have_value(
        "00000000-0000-0000-0000-000000000000", timeout=5000
    )

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "request_id")
    assert field["kind"] == "uuid"
    new_value = field["value"]
    # Sanity: it's a valid UUID-shaped string.
    assert len(new_value) == 36
    assert new_value.count("-") == 4
    # And it's NOT the all-zeros placeholder.
    assert new_value != "00000000-0000-0000-0000-000000000000"


def test_secret_show_toggle_reveals_input_type(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    api_key = page.get_by_label("api_key", exact=True)
    expect(api_key).to_be_visible(timeout=5000)
    expect(api_key).to_have_attribute("type", "password")

    # Click the show toggle. After click, input type flips to "text".
    # `exact=True` matters: the schema also has an `api_key_bytes` field,
    # so "show api_key" otherwise matches both buttons.
    show_btn = page.get_by_role("button", name="show api_key", exact=True)
    expect(show_btn).to_be_visible()
    show_btn.click()
    expect(api_key).to_have_attribute("type", "text", timeout=2000)

    # The button text should now read "hide".
    hide_btn = page.get_by_role("button", name="hide api_key", exact=True)
    expect(hide_btn).to_be_visible(timeout=2000)


def test_secret_edit_round_trips_value(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    api_key = page.get_by_label("api_key", exact=True)
    expect(api_key).to_be_visible(timeout=5000)
    api_key.fill("hunter2")
    api_key.blur()

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "api_key")
    assert field["kind"] == "secret"
    assert field["secret_kind"] == "str"
    # SecretStr round-trips as the plaintext on the wire (per
    # SecretNode's bytes-as-str storage; the actual Pydantic SecretStr
    # masking happens only at model_dump_secrets / __str__).
    assert field["value"] == "hunter2"


def test_pattern_field_renders_flag_chips(
    page: Page, fastapi_url: str
) -> None:
    """The default pattern_field has re.IGNORECASE set; the component
    derives an 'i' chip from the flags bitmask (= 2). This test asserts
    the chip is rendered and read-only (no toggle button)."""
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    pattern_input = page.get_by_label("pattern_field", exact=True)
    expect(pattern_input).to_be_visible(timeout=5000)

    # The 'i' chip lives inside the FieldHeader for pattern_field. Two
    # selectors that work:
    #   - by tooltip text (title attribute = IGNORECASE)
    #   - by text content "i" near the pattern_field label
    # Use the tooltip selector to avoid matching unrelated 'i' glyphs.
    ignorecase_chip = page.locator('span[title="IGNORECASE"]')
    expect(ignorecase_chip).to_be_visible(timeout=5000)

    # Server tree still shows the original flags value (re.IGNORECASE = 2,
    # potentially OR'd with re.UNICODE which PatternNode strips). Phase 5
    # does NOT let users toggle flags - assert no toggle Button exists.
    toggle_buttons = page.get_by_role("button", name="toggle IGNORECASE")
    assert toggle_buttons.count() == 0
