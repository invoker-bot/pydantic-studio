"""Accessibility regressions for the React-backed web form."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_labels_reference_labelable_controls(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_role("heading", name="_DemoSchema")).to_be_visible(timeout=5000)

    broken = page.evaluate(
        """() => {
            const labelableTags = new Set([
                "BUTTON",
                "INPUT",
                "METER",
                "OUTPUT",
                "PROGRESS",
                "SELECT",
                "TEXTAREA",
            ]);
            return Array.from(document.querySelectorAll("label[for]"))
                .map((label) => {
                    const targetId = label.getAttribute("for");
                    const target = targetId ? document.getElementById(targetId) : null;
                    return {
                        label: label.textContent?.trim() ?? "",
                        targetId,
                        tagName: target?.tagName ?? null,
                    };
                })
                .filter((entry) => !entry.tagName || !labelableTags.has(entry.tagName));
        }"""
    )

    assert broken == []


def test_field_validation_errors_are_announced_as_alerts(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_role("heading", name="_DemoSchema")).to_be_visible(timeout=5000)

    workers = page.get_by_label("workers", exact=True)
    workers.fill("0")
    workers.blur()

    alert = page.get_by_role("alert")
    expect(alert).to_contain_text("must be >= 1", timeout=5000)
    expect(workers).to_have_attribute("aria-invalid", "true")

    describedby = workers.get_attribute("aria-describedby")
    assert describedby is not None
    describedby_target = page.locator(f'[id="{describedby}"]')
    expect(describedby_target).to_have_attribute("role", "alert")
    expect(describedby_target).to_contain_text("must be >= 1")

    workers.fill("2")

    expect(page.get_by_role("alert")).to_have_count(0)
    expect(workers).not_to_have_attribute("aria-invalid", "true")
    assert workers.get_attribute("aria-describedby") is None
