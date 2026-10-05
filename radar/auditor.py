"""Auditoría de un sitio: hasta 3 páginas, escritorio y móvil, axe-core y Lighthouse.

Tráfico total por sitio: robots.txt, la página de inicio (escritorio y móvil con
Playwright, más 3 cargas de Lighthouse por vista) y hasta 2 páginas internas, con
una pausa de al menos 3 segundos antes de cada carga y siempre de forma secuencial.
Nunca se llenan formularios ni se inicia sesión.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from playwright.sync_api import Browser, Page

from . import parsers, scoring
from .browser import fetch_robots_with_browser, new_context, short_error
from .config import LIGHTHOUSE_RUNS, MAX_PAGES_PER_SITE, Settings, Site
from .links import is_first_party, is_ignored_failure, pick_internal_pages, unique_failed
from .lighthouse import run_lighthouse

AXE_SOURCE = (Path(__file__).resolve().parent.parent / "node_modules" / "axe-core" / "axe.min.js")
AXE_OPTIONS = {"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}, "resultTypes": ["violations"]}
SETTLE_MS = 2_000

_SECURITY_ERROR_TOKENS = ("ERR_CERT", "ERR_SSL", "SSL", "CERT_")


class SecurityLog:
    """Hallazgos de seguridad encontrados por casualidad. Solo se guardan en private/."""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, site: Site, source: str, detail) -> None:
        self.items.append({"site": site.id, "url": site.url, "source": source, "detail": detail})


def public_error(error: Exception, site: Site, where: str, security: SecurityLog) -> str:
    """Mensaje publicable. Los errores de TLS/certificados se guardan en privado."""
    text = short_error(error)
    if any(token in text for token in _SECURITY_ERROR_TOKENS):
        security.add(site, where, text)
        return f"{where}: no se pudo cargar la página"
    if "Timeout" in text:
        return f"{where}: la página no terminó de cargar a tiempo"
    if "ERR_NAME_NOT_RESOLVED" in text or "ERR_CONNECTION" in text:
        return f"{where}: no se pudo conectar con el sitio"
    return f"{where}: {text}"


def _visit(page: Page, url: str, home_url: str, pause: float, axe_source: str) -> dict:
    """Carga una página como un visitante normal y corre axe-core.
    Registra los recursos que fallan al cargarla (respuesta >= 400 o error de red)."""
    broken: list[dict] = []

    def on_response(response):
        if response.status >= 400 and response.request.resource_type != "document":
            broken.append({"url": response.url, "status": response.status, "type": response.request.resource_type})

    def on_failed(request):
        failure = request.failure
        if not is_ignored_failure(failure) and request.resource_type != "document":
            broken.append({"url": request.url, "status": None, "type": request.resource_type, "error": (failure or "")[:80]})

    page.on("response", on_response)
    page.on("requestfailed", on_failed)
    time.sleep(pause)
    started = time.monotonic()
    try:
        response = page.goto(url, wait_until="load")
        load_ms = round((time.monotonic() - started) * 1000)
        page.wait_for_timeout(SETTLE_MS)
        status = response.status if response else None
        record = {"url": url, "final_url": page.url, "status": status, "load_ms": load_ms}
        if status and status >= 400:
            broken.append({"url": url, "status": status, "type": "document"})
        raw = page.evaluate(
            "async ([source, options]) => { if (!window.axe) { (0, eval)(source); } return await axe.run(document, options); }",
            [axe_source, AXE_OPTIONS],
        )
        findings = parsers.parse_axe(raw)
        record["axe"] = {"score": scoring.axe_score(findings), "violations": findings}
    finally:
        page.remove_listener("response", on_response)
        page.remove_listener("requestfailed", on_failed)
    unique = _dedupe(broken)
    record["failed_resources"] = [dict(item, first_party=True) for item in unique if is_first_party(item["url"], home_url)]
    record["third_party_failures"] = sum(1 for item in unique if not is_first_party(item["url"], home_url))
    return record


def _dedupe(items: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for item in items:
        seen.setdefault(item["url"], item)
    return list(seen.values())


def _mobile_checks(page: Page) -> dict:
    return page.evaluate(
        """() => {
            const meta = document.querySelector('meta[name="viewport"]');
            const content = meta ? (meta.getAttribute('content') || '') : '';
            const root = document.documentElement;
            return {
                viewport_meta: /width\\s*=\\s*device-width/i.test(content),
                // Sin meta viewport el móvil renderiza a 980 px: también cuenta como desborde.
                horizontal_overflow: root.scrollWidth > window.screen.width,
                scroll_width: root.scrollWidth,
                viewport_width: window.innerWidth,
                screen_width: window.screen.width,
            };
        }"""
    )


def audit_site(
    browser: Browser,
    site: Site,
    settings: Settings,
    screenshots_dir: Path,
    security: SecurityLog,
    chrome_path: str | None = None,
    log: Callable[[str], None] = print,
    lighthouse_runner: Callable[..., dict] = run_lighthouse,
) -> dict:
    axe_source = AXE_SOURCE.read_text(encoding="utf-8")
    record: dict = {
        "id": site.id,
        "name": site.name,
        "category": site.category,
        "url": site.url,
        "audited_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "ok",
        "pages": [],
        "mobile": None,
        "lighthouse": {"mobile": None, "desktop": None},
        "errors": [],
    }

    desktop = new_context(browser)
    page = desktop.new_page()
    robots, robots_state = fetch_robots_with_browser(page, site.url)
    record["robots"] = robots_state
    if not robots.allowed(site.url):
        desktop.close()
        record["status"] = "omitido_robots"
        record["errors"].append("robots.txt no permite visitar la página de inicio")
        log(f"  {site.id}: omitido por robots.txt")
        return record
    pause = max(settings.pause_seconds, robots.crawl_delay() or 0)

    # 1) Inicio en escritorio + elección de páginas internas.
    hrefs: list[str] = []
    try:
        log(f"  {site.id}: inicio (escritorio)")
        home = _visit(page, site.url, site.url, pause, axe_source)
        home["viewport"] = "desktop"
        page.screenshot(path=str(screenshots_dir / f"{site.id}-desktop.jpg"), type="jpeg", quality=60)
        home["screenshot"] = f"screenshots/{site.id}-desktop.jpg"
        record["pages"].append(home)
        hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    except Exception as error:
        record["errors"].append(public_error(error, site, "inicio (escritorio)", security))

    max_pages = min(settings.max_pages, MAX_PAGES_PER_SITE)
    internal = [u for u in site.pages if robots.allowed(u)][: max_pages - 1]
    if not internal and hrefs:
        aliases = tuple(p["final_url"] for p in record["pages"][:1])
        internal = pick_internal_pages(site.url, hrefs, robots.allowed, max_pages - 1, aliases)

    # 2) Páginas internas en escritorio.
    for url in internal:
        try:
            log(f"  {site.id}: {url}")
            visited = _visit(page, url, site.url, pause, axe_source)
            visited["viewport"] = "desktop"
            record["pages"].append(visited)
        except Exception as error:
            record["errors"].append(public_error(error, site, "página interna", security))
    desktop.close()

    # 3) Inicio en móvil.
    mobile = new_context(browser, mobile=True)
    mobile_page = mobile.new_page()
    try:
        log(f"  {site.id}: inicio (móvil)")
        home_mobile = _visit(mobile_page, site.url, site.url, pause, axe_source)
        home_mobile["viewport"] = "mobile"
        record["mobile"] = _mobile_checks(mobile_page)
        mobile_page.screenshot(path=str(screenshots_dir / f"{site.id}-mobile.jpg"), type="jpeg", quality=60)
        home_mobile["screenshot"] = f"screenshots/{site.id}-mobile.jpg"
        record["pages"].append(home_mobile)
    except Exception as error:
        record["errors"].append(public_error(error, site, "inicio (móvil)", security))
    mobile.close()

    # 4) Lighthouse sobre el inicio: 3 corridas por vista, mediana.
    for form in ("mobile", "desktop"):
        runs: list[dict] = []
        failures = 0
        for attempt in range(1, LIGHTHOUSE_RUNS + 1):
            time.sleep(pause)
            try:
                log(f"  {site.id}: Lighthouse ({form}) {attempt}/{LIGHTHOUSE_RUNS}")
                lhr = lighthouse_runner(site.url, form, chrome_path)
                summary, findings = parsers.parse_lighthouse(lhr)
                for item in findings:
                    security.add(site, f"lighthouse-{form}", item)
                if summary.get("runtime_error"):
                    # Lighthouse no pudo cargar la página: no se publica el código exacto
                    # (algunos, como CHROME_INTERSTITIAL_ERROR, pueden deberse a certificados).
                    security.add(site, f"lighthouse-{form}", {"runtime_error": summary["runtime_error"]})
                    failures += 1
                else:
                    runs.append(summary)
            except Exception as error:
                public_error(error, site, f"Lighthouse ({form})", security)
                failures += 1
        record["lighthouse"][form] = parsers.median_lighthouse(runs)
        if failures:
            record["errors"].append(
                f"Lighthouse ({form}): {failures} de {LIGHTHOUSE_RUNS} corridas no pudieron analizar la página"
            )

    finish_record(record)
    return record


def finish_record(record: dict) -> dict:
    """Calcula puntuaciones a partir de lo recogido (separado para poder probarlo)."""
    pages = record.get("pages", [])
    axe_scores = [p["axe"]["score"] for p in pages if p.get("axe")]
    failed = [b for b in unique_failed(pages) if b.get("first_party")]
    mobile = record.get("mobile") or {}
    px = scoring.overflow_px(mobile.get("scroll_width"), mobile.get("screen_width"))
    if record.get("mobile") is not None:
        record["mobile"]["overflow_px"] = px
    components = scoring.component_scores(
        axe_scores=axe_scores,
        lighthouse=record.get("lighthouse", {}),
        failed_count=len(failed) if pages else None,
        mobile_overflow_px=px,
    )
    overall = scoring.overall_score(components)
    record["wcag"] = parsers.wcag_summary(pages)
    record["failed_resources_first_party"] = len(failed)
    record["third_party_failures"] = sum(p.get("third_party_failures", 0) for p in pages)
    record["scores"] = {**components, "overall": overall}
    record["light"] = scoring.light(overall)
    if not pages:
        record["status"] = "sin_respuesta"
    elif record.get("errors"):
        record["status"] = "parcial"
    return record
