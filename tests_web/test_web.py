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
    context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, locale="es-CO")
    page = context.new_page()
    page.goto(base_url)
    expect(page.locator("#ranking-body tr").first).to_be_visible()
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    context.close()
    assert overflow <= 0


def test_findings_section_matches_summary(page, base_url):
    findings = latest_summary()["findings"]
    page.goto(base_url)
    expect(page.locator("#findings-title")).to_contain_text(str(findings["sites_measured"]))
    expect(page.locator("#top-rules li")).to_have_count(len(findings["top_rules"]))
    expect(page.locator("#by-category li")).to_have_count(len(findings["by_category"]))


def test_language_toggle_switches_to_english_and_back(page, base_url):
    page.goto(base_url)
    expect(page.locator("#ranking-body tr").first).to_be_visible()
    page.get_by_role("button", name="Read in English").click()
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.locator("#ranking-title")).to_have_text("Leaderboard")
    expect(page.locator("#findings-title")).to_contain_text("WCAG 2.1 AA")
    assert "lang=en" in page.url
    assert run_axe(page) == []
    page.get_by_role("button", name="Ver en español").click()
    expect(page.locator("html")).to_have_attribute("lang", "es")
    expect(page.locator("#ranking-title")).to_have_text("Tabla de posiciones")


def test_english_link_opens_in_english(page, base_url):
    page.goto(f"{base_url}?lang=en")
    expect(page.locator("#ranking-title")).to_have_text("Leaderboard")
    page.locator(".site-btn").first.click()
    expect(page.locator("#sheet")).to_contain_text("Score components")


def test_share_metadata_is_present(page, base_url):
    page.goto(base_url)
    image = page.locator('meta[property="og:image"]').get_attribute("content")
    assert image.endswith("/og-image.png")
    assert page.locator('meta[name="twitter:card"]').get_attribute("content") == "summary_large_image"
    assert (ROOT / "web" / "og-image.png").exists()


def test_english_browser_gets_english_by_default(browser, base_url):
    context = browser.new_context(locale="en-US")
    page = context.new_page()
    page.goto(base_url)
    expect(page.locator("html")).to_have_attribute("lang", "en")
    context.close()


def test_overflow_evidence_is_shown_when_available(page, base_url):
    latest = json.loads((ROOT / "data" / "latest.json").read_text(encoding="utf-8"))
    run_dir = ROOT / "data" / latest["summary"].rsplit("/", 1)[0]
    with_evidence = [
        p.stem for p in (run_dir / "sites").glob("*.json")
        if json.loads(p.read_text(encoding="utf-8")).get("mobile", {}) and
        (json.loads(p.read_text(encoding="utf-8"))["mobile"] or {}).get("evidence", {}).get("screenshot")
    ]
    if not with_evidence:
        return
    page.goto(f"{base_url}#{with_evidence[0]}")
    evidence = page.locator(".evidence img")
    expect(evidence).to_be_visible()
    assert page.evaluate("(img) => img.complete && img.naturalWidth > 0", evidence.element_handle())


def test_radar_3d_and_flat_views(page, base_url):
    page.goto(base_url)
    expect(page.locator("#radar-3d")).to_be_visible()
    expect(page.locator("#radar-canvas")).to_have_attribute("role", "img")
    page.get_by_role("button", name="Vista plana").click()
    expect(page.locator("#radar-svg")).to_be_visible()
    expect(page.locator("#radar-3d")).to_be_hidden()
    # En la vista plana cada portal es una marca enfocable con teclado.
    page.locator(".blip").first.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#sheet")).to_be_visible()


def test_reduced_motion_starts_flat_and_without_counters(browser, base_url):
    context = browser.new_context(locale="es-CO", reduced_motion="reduce")
    page = context.new_page()
    page.goto(base_url)
    expect(page.locator("#view-flat")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#kpi-avg")).to_have_text(str(latest_summary()["average_overall"]))
    context.close()


def test_counters_expose_final_value_to_screen_readers(page, base_url):
    summary = latest_summary()
    page.goto(base_url)
    expect(page.locator("#kpi-avg .sr-only")).to_have_text(str(summary["average_overall"]))
