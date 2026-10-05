"""Genera web/og-image.png (1200x630), la imagen que muestran LinkedIn y otras redes
al compartir la web. Usa la plantilla web/og.html con los datos de la última medición
y no sale a internet salvo para cargar las fuentes de Google."""

from __future__ import annotations

import functools
import http.server
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "web" / "og-image.png"


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def render_og_image(output: Path = OUTPUT) -> Path:
    handler = functools.partial(_QuietHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
            page.goto(f"http://127.0.0.1:{server.server_address[1]}/web/og.html")
            page.wait_for_selector("body[data-ready='1']", timeout=30_000)
            page.locator("#card").screenshot(path=str(output))
            browser.close()
    finally:
        server.shutdown()
    return output
