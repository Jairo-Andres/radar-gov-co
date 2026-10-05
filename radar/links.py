"""Selección de páginas internas y clasificación de recursos fallidos."""

from __future__ import annotations

from typing import Callable
from urllib.parse import urldefrag, urlparse

SKIPPED_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar", ".7z",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".mp3", ".mp4", ".avi", ".csv", ".xml",
)
# Nunca se visitan páginas de acceso, cuentas, búsquedas ni administración.
SKIPPED_KEYWORDS = (
    "login", "logon", "signin", "sign-in", "logout", "ingresar", "iniciar-sesion", "iniciarsesion",
    "admin", "wp-admin", "wp-login", "registro", "register", "cuenta", "account", "carrito", "cart",
    "buscar", "busqueda", "search", "mailto:", "javascript:", "tel:",
)
# Fallos de red que no son culpa del sitio (navegación cancelada, etc.).
IGNORED_FAILURES = ("net::ERR_ABORTED", "net::ERR_BLOCKED_BY_CLIENT", "NS_BINDING_ABORTED")


def _bare_host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _normalize(url: str) -> str:
    """Clave para detectar repetidas: sin ancla, sin 'www.' y sin barra final."""
    url, _ = urldefrag(url)
    return f"{_bare_host(url)}{urlparse(url).path.rstrip('/')}"


def pick_internal_pages(
    home_url: str,
    hrefs: list[str],
    allowed: Callable[[str], bool],
    count: int,
    home_aliases: tuple[str, ...] = (),
) -> list[str]:
    """Primeras `count` páginas del mismo sitio, en orden de aparición, que robots.txt permita.
    `home_aliases` son otras URL del inicio (p. ej. a dónde redirige) para no visitarlo dos veces."""
    home_host = _bare_host(home_url)
    seen = {_normalize(home_url), *(_normalize(a) for a in home_aliases)}
    picked: list[str] = []
    for href in hrefs:
        if len(picked) >= count:
            break
        if not href:
            continue
        lowered = href.lower()
        if any(k in lowered for k in SKIPPED_KEYWORDS):
            continue
        parsed = urlparse(href)
        if parsed.scheme not in ("http", "https") or parsed.query:
            continue
        if _bare_host(href) != home_host:
            continue
        if parsed.path.lower().endswith(SKIPPED_EXTENSIONS):
            continue
        normalized = _normalize(href)
        if normalized in seen or not allowed(href):
            continue
        seen.add(normalized)
        picked.append(href.split("#")[0])
    return picked


def is_ignored_failure(error_text: str | None) -> bool:
    return bool(error_text) and any(token in error_text for token in IGNORED_FAILURES)


def unique_failed(pages: list[dict]) -> list[dict]:
    """Une los recursos fallidos de todas las páginas visitadas sin repetir URL."""
    seen: dict[str, dict] = {}
    for page in pages:
        for item in page.get("failed_resources", []):
            seen.setdefault(item["url"], item)
    return list(seen.values())


def is_first_party(url: str, home_url: str) -> bool:
    host, home = _bare_host(url), _bare_host(home_url)
    return host == home or host.endswith("." + home)
