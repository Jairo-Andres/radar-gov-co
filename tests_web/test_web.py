import json
from pathlib import Path

from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parent.parent
AXE = (ROOT / "node_modules" / "axe-core" / "axe.min.js").read_text(encoding="utf-8")
AXE_OPTIONS = {"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}}


def latest_summary():
    latest = json.loads((ROOT / "data" / "latest.json").read_text(encoding="utf-8"))
    return json.loads((ROOT / "data" / latest["summary"]).read_text(encoding="utf-8"))


def run_axe(page):
    page.evaluate(AXE)
    return page.evaluate("async (o) => (await axe.run(document, o)).violations.map(v => v.id + ': ' + v.nodes.length)", AXE_OPTIONS)


def test_ranking_matches_latest_summary(page, base_url):
    summary = latest_summary()
    page.goto(base_url)
    rows = page.locator("#ranking-body tr")
    expect(rows).to_have_count(len(summary["sites"]))
    first = summary["sites"][0]
    expect(rows.first).to_contain_text(first["name"])
    expect(rows.first).to_contain_text(str(first["overall"]))
    scored = [s for s in summary["sites"] if s["overall"] is not None]
    expect(page.locator(".blip")).to_have_count(len(scored))


def test_filter_by_entity_type(page, base_url):
    summary = latest_summary()
    page.goto(base_url)
    page.get_by_role("button", name="Alcaldías").click()
    alcaldias = [s for s in summary["sites"] if s["category"] == "Alcaldía"]
    expect(page.locator("#ranking-body tr")).to_have_count(len(alcaldias))


def test_site_sheet_opens_and_closes_with_keyboard(page, base_url):
    summary = latest_summary()
    first = summary["sites"][0]
    page.goto(base_url)
    page.get_by_role("button", name=first["name"], exact=True).click()
    dialog = page.locator("#sheet")
    expect(dialog).to_be_visible()
    expect(dialog.locator("#sheet-title")).to_have_text(first["name"])
    expect(dialog).to_contain_text("reglas WCAG incumplidas")
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()


def test_deep_link_opens_sheet(page, base_url):
    site = latest_summary()["sites"][-1]
    page.goto(f"{base_url}#{site['id']}")
    expect(page.locator("#sheet-title")).to_have_text(site["name"])


def test_page_has_no_wcag_violations(page, base_url):
    page.goto(base_url)
    expect(page.locator("#ranking-body tr").first).to_be_visible()
    assert run_axe(page) == []


def test_sheet_has_no_wcag_violations(page, base_url):
    page.goto(base_url)
    page.locator(".site-btn").first.click()
    expect(page.locator(".components li").first).to_be_visible()
    assert run_axe(page) == []


def test_mobile_has_no_horizontal_overflow(browser, base_url):
    context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page = context.new_page()
    page.goto(base_url)
    expect(page.locator("#ranking-body tr").first).to_be_visible()
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    context.close()
    assert overflow <= 0
