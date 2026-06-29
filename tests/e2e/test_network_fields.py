"""E2E for Phase 5 network + web fields: url, email, ip_address.

Each test fills the input, blurs to commit, then asserts the server
tree reflects the new value. ip_network reuses ip_address's code path
(same component shape, different placeholder) so isn't covered here.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_edit_url_field_updates_tree(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    homepage = page.get_by_label("homepage", exact=True)
    expect(homepage).to_be_visible(timeout=5000)
    homepage.fill("https://pydantic.dev")
    homepage.blur()

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "homepage")
    assert field["kind"] == "url"
    # HttpUrl normalizes (may add trailing slash); assert the prefix.
    assert field["value"].startswith("https://pydantic.dev")
    # The component shows a short type chip; verify the target_type_name
    # carries through the API so the chip renders.
    assert field["target_type_name"].endswith(("HttpUrl", "Url"))


def test_edit_email_field_updates_tree(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    contact = page.get_by_label("contact", exact=True)
    expect(contact).to_be_visible(timeout=5000)
    contact.fill("support@pydantic.dev")
    contact.blur()

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "contact")
    # conftest.py now annotates contact as EmailStr (email-validator is
    # pinned in the dev dependency group), so the registry maps it to
    # an EmailNode (kind == "email").
    assert field["kind"] == "email"
    assert field["value"] == "support@pydantic.dev"


def test_edit_ip_address_field_updates_tree(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    bind_ip = page.get_by_label("bind_ip", exact=True)
    expect(bind_ip).to_be_visible(timeout=5000)
    bind_ip.fill("10.42.0.1")
    bind_ip.blur()

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "bind_ip")
    assert field["kind"] == "ip_address"
    assert field["version"] == 4
    assert field["value"] == "10.42.0.1"
