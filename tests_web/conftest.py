"""Pruebas de la web del ranking: se sirve el repo en local y se abre con Playwright.

No toca ningún sitio externo: solo http://127.0.0.1 con los datos de data/.
"""

import functools
import http.server
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def base_url():
    handler = functools.partial(QuietHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/web/"
    server.shutdown()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    # Las fuentes de Google no son necesarias para probar: se bloquean para no salir a internet.
    context.route("**/fonts.googleapis.com/**", lambda route: route.abort())
    context.route("**/fonts.gstatic.com/**", lambda route: route.abort())
    page = context.new_page()
    yield page
    context.close()
