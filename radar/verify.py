"""Verifica que cada sitio de sites.yaml responda y que robots.txt permita visitarlo.

Hace como máximo dos peticiones por sitio (robots.txt y la página de inicio).
"""

from __future__ import annotations

import time

from playwright.sync_api import sync_playwright

from .browser import fetch_robots_with_browser, new_context, short_error
from .config import Settings, Site


def verify_sites(settings: Settings, sites: list[Site]) -> list[dict]:
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for index, site in enumerate(sites):
            if index:
                time.sleep(2)  # hosts distintos; pausa corta solo por cortesía
            context = new_context(browser)
            page = context.new_page()
            robots, robots_state = fetch_robots_with_browser(page, site.url)
            row = {"id": site.id, "url": site.url, "robots": robots_state, "allowed": robots.allowed(site.url)}
            if row["allowed"]:
                time.sleep(settings.pause_seconds)
                try:
                    response = page.goto(site.url, wait_until="domcontentloaded")
                    row["status"] = response.status if response else None
                    row["final_url"] = page.url
                except Exception as error:
                    row["status"] = None
                    row["error"] = short_error(error)
            context.close()
            print(_format(row), flush=True)
            results.append(row)
        browser.close()
    return results


def _format(row: dict) -> str:
    ok = row.get("status") and 200 <= row["status"] < 400
    mark = "OK " if ok and row["allowed"] else "-- "
    detail = row.get("error") or f"HTTP {row.get('status')} -> {row.get('final_url', '')}"
    if not row["allowed"]:
        detail = "robots.txt no permite visitar la página de inicio"
    return f"{mark}{row['id']:<24} {row['robots']:<45} {detail}"
