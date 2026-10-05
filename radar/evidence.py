"""Evidencia del desborde en móvil y re-verificación de anomalías.

- capture_overflow_evidence: qué elementos se salen de la pantalla de 390 px y una
  captura con una línea en el borde de la pantalla. La usa el auditor cada semana.
- recheck_sites: vuelve a cargar solo la página de inicio en móvil (una visita por
  sitio, con pausa) para confirmar una anomalía. No cambia las notas: guarda la
  verificación junto a la medición original.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from .browser import fetch_robots_with_browser, new_context, short_error
from .config import Settings, Site
from .links import failure_kind, is_first_party, is_ignored_failure

_OFFENDERS_JS = """
() => {
  const limit = window.screen.width;
  const describe = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    else if (el.classList.length) s += '.' + [...el.classList].slice(0, 2).join('.');
    return s.slice(0, 120);
  };
  // Un elemento dentro de un contenedor que recorta (overflow hidden/clip/auto) no
  // ensancha la página aunque su caja pase del borde (por ejemplo, un carrusel).
  const clipped = (el) => {
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      const ox = getComputedStyle(a).overflowX;
      if (ox !== 'visible' && a.getBoundingClientRect().right + window.scrollX <= limit + 1) return true;
    }
    return false;
  };
  const wide = [];
  for (const el of document.body ? document.body.querySelectorAll('*') : []) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && r.right + window.scrollX > limit + 1 && !clipped(el)) wide.push([el, r]);
  }
  // Se queda con los más profundos: elementos que desbordan sin un hijo que también desborde.
  const set = new Set(wide.map(([el]) => el));
  const leaves = wide.filter(([el]) => ![...el.children].some((c) => set.has(c)));
  return leaves
    .sort((a, b) => b[1].right - a[1].right)
    .slice(0, 5)
    .map(([el, r]) => ({ selector: describe(el), right_px: Math.round(r.right + window.scrollX), width_px: Math.round(r.width) }));
}
"""

_MARK_JS = """
(limit) => {
  const mark = document.createElement('div');
  mark.id = '__radar_limit';
  const height = Math.min(document.documentElement.scrollHeight, 1400);
  mark.style.cssText = `position:absolute;left:${limit}px;top:0;width:0;height:${height}px;border-left:3px dashed #ff2d55;z-index:2147483647;pointer-events:none`;
  const label = document.createElement('div');
  label.textContent = `${limit} px (borde de la pantalla)`;
  label.style.cssText = 'position:absolute;top:8px;left:6px;background:#ff2d55;color:#fff;font:bold 12px/1.2 sans-serif;padding:3px 6px;white-space:nowrap';
  mark.appendChild(label);
  document.body.appendChild(mark);
  return height;
}
"""


def capture_overflow_evidence(page: Page, screenshot_path: Path) -> dict:
    """Debe llamarse con la página ya cargada en el contexto móvil."""
    sizes = page.evaluate(
        "() => ({ scroll: document.documentElement.scrollWidth, screen: window.screen.width,"
        " scale: window.visualViewport ? window.visualViewport.scale : 1 })"
    )
    overflow = max(0, sizes["scroll"] - sizes["screen"])
    evidence = {"overflow_px": overflow, "scroll_width": sizes["scroll"], "screen_width": sizes["screen"],
                "zoom": round(sizes["scale"], 2), "offenders": []}
    if overflow <= 0:
        return evidence
    if sizes["scale"] < 0.99:
        # El navegador redujo toda la página para que quepa (típico sin meta viewport):
        # la evidencia es la vista tal como la ve el usuario, a escala reducida.
        evidence["zoomed_out"] = True
        page.screenshot(path=str(screenshot_path), type="jpeg", quality=70)
        evidence["screenshot"] = f"screenshots/{screenshot_path.name}"
        return evidence
    evidence["offenders"] = page.evaluate(_OFFENDERS_JS)
    height = page.evaluate(_MARK_JS, sizes["screen"])
    try:
        page.screenshot(
            path=str(screenshot_path), type="jpeg", quality=70, full_page=True,
            clip={"x": 0, "y": 0, "width": sizes["scroll"], "height": height},
        )
        evidence["screenshot"] = f"screenshots/{screenshot_path.name}"
    finally:
        page.evaluate("() => document.getElementById('__radar_limit')?.remove()")
    return evidence


def recheck_sites(settings: Settings, sites: list[Site], day_dir: Path) -> list[dict]:
    """Vuelve a visitar la página de inicio en móvil y guarda la verificación en la ficha."""
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for index, site in enumerate(sites):
            record_path = day_dir / "sites" / f"{site.id}.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            context = new_context(browser, mobile=True)
            page = context.new_page()
            robots, _ = fetch_robots_with_browser(page, site.url)
            check: dict = {"checked_at": datetime.now().astimezone().isoformat(timespec="seconds"), "page": site.url}
            if not robots.allowed(site.url):
                check["error"] = "robots.txt no permite la visita o no se pudo leer"
            else:
                failures: list[dict] = []
                page.on("response", lambda r: r.status >= 400 and r.request.resource_type != "document"
                        and failures.append({"url": r.url, "status": r.status, "type": r.request.resource_type}))
                page.on("requestfailed", lambda r: not is_ignored_failure(r.failure) and r.resource_type != "document"
                        and failures.append({"url": r.url, "status": None, "type": r.resource_type, "error": (r.failure or "")[:80]}))
                time.sleep(settings.pause_seconds)
                try:
                    # Basta con el DOM: algunos portales dejan peticiones abiertas y nunca disparan "load".
                    page.goto(site.url, wait_until="domcontentloaded")
                    try:
                        page.wait_for_load_state("load", timeout=15_000)
                    except Exception:
                        check["note"] = "la página no terminó de cargar en 15 s; se midió con el DOM disponible"
                    page.wait_for_timeout(3_000)
                    check["overflow"] = capture_overflow_evidence(page, day_dir / "screenshots" / f"{site.id}-mobile-overflow-recheck.jpg")
                    own = {}
                    for item in failures:
                        if is_first_party(item["url"], site.url):
                            own.setdefault(item["url"], dict(item, kind=failure_kind(item)))
                    check["failed_resources"] = list(own.values())
                except Exception as error:
                    check["error"] = short_error(error)
            context.close()
            record.setdefault("rechecks", []).append(check)
            record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append({"id": site.id, **check})
            if index < len(sites) - 1:
                time.sleep(2)
        browser.close()
    return results
