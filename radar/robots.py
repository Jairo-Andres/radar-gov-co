"""Respeto de robots.txt con el User-Agent del Radar."""

from __future__ import annotations

import urllib.error
import urllib.request
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from .config import ROBOTS_AGENT, USER_AGENT


class Robots:
    """robots.txt de un host. Si no existe (404) se permite todo; si no se puede
    leer por otro motivo (403, 5xx, red) se asume prohibido, por prudencia."""

    def __init__(self, text: str | None, allow_all: bool = False, disallow_all: bool = False):
        self._parser = RobotFileParser()
        self.allow_all = allow_all
        self.disallow_all = disallow_all
        if text is not None:
            self._parser.parse(text.splitlines())

    @classmethod
    def from_text(cls, text: str) -> "Robots":
        return cls(text)

    def allowed(self, url: str) -> bool:
        if self.disallow_all:
            return False
        if self.allow_all:
            return True
        return self._parser.can_fetch(ROBOTS_AGENT, url)

    def crawl_delay(self) -> float | None:
        if self.allow_all or self.disallow_all:
            return None
        delay = self._parser.crawl_delay(ROBOTS_AGENT)
        return float(delay) if delay is not None else None


def robots_url_for(site_url: str) -> str:
    parsed = urlparse(site_url)
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"


def robots_from_response(status: int | None, text: str | None, error: str | None = None) -> tuple[Robots, str]:
    """Interpreta la respuesta a /robots.txt. Devuelve (Robots, estado legible)."""
    if error is not None or status is None:
        return Robots(None, disallow_all=True), f"robots.txt no disponible ({error or 'sin respuesta'})"
    if 200 <= status < 300:
        body = text or ""
        # Algunos portales responden 200 con una página HTML en vez de robots.txt.
        if "<html" in body[:500].lower():
            return Robots(None, allow_all=True), "robots.txt devuelve HTML (se trata como inexistente)"
        return Robots.from_text(body), "ok"
    if status in (404, 410):
        return Robots(None, allow_all=True), f"sin robots.txt ({status})"
    return Robots(None, disallow_all=True), f"robots.txt no disponible ({status})"


def fetch_robots(site_url: str, timeout: float = 20) -> tuple[Robots, str]:
    """Lee robots.txt con urllib (sin navegador)."""
    request = urllib.request.Request(robots_url_for(site_url), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return robots_from_response(response.status, response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as error:
        return robots_from_response(error.code, None)
    except Exception as error:  # red, DNS, TLS
        return robots_from_response(None, None, type(error).__name__)
