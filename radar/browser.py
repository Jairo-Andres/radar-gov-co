"""Utilidades de navegador compartidas por la verificación y la auditoría."""

from __future__ import annotations

from playwright.sync_api import Browser, BrowserContext, Page

from .config import NAV_TIMEOUT_MS, USER_AGENT
from .robots import Robots, robots_from_response, robots_url_for

DESKTOP = {"viewport": {"width": 1366, "height": 768}}
# Tamaño de un teléfono de gama media (390x844, como un iPhone 12-15).
MOBILE = {
    "viewport": {"width": 390, "height": 844},
    "device_scale_factor": 2,
    "is_mobile": True,
    "has_touch": True,
}


def new_context(browser: Browser, mobile: bool = False) -> BrowserContext:
    options = dict(MOBILE if mobile else DESKTOP)
    context = browser.new_context(
        user_agent=USER_AGENT,
        locale="es-CO",
        # Permite inyectar axe-core aunque el sitio tenga Content-Security-Policy.
        bypass_csp=True,
        # Nunca se aceptan certificados inválidos: un visitante normal tampoco lo haría.
        ignore_https_errors=False,
        **options,
    )
    context.set_default_navigation_timeout(NAV_TIMEOUT_MS)
    return context


def fetch_robots_with_browser(page: Page, site_url: str) -> tuple[Robots, str]:
    """Lee robots.txt con el mismo navegador (misma pila TLS que la auditoría)."""
    try:
        response = page.goto(robots_url_for(site_url), wait_until="domcontentloaded")
    except Exception as error:
        return robots_from_response(None, None, short_error(error))
    if response is None:
        return robots_from_response(None, None, "sin respuesta")
    try:
        text = response.text()
    except Exception:
        text = ""
    return robots_from_response(response.status, text)


def short_error(error: Exception) -> str:
    """Primera línea del error de Playwright, sin el log de llamadas."""
    return str(error).strip().splitlines()[0][:200] if str(error).strip() else type(error).__name__
