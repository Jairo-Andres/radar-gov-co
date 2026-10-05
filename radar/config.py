"""Configuración del Radar: sitios a auditar y límites éticos."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml

USER_AGENT = "RadarGovCo/1.0 (proyecto academico; linkedin.com/in/jairo-andres31-analyst)"
# Token que se busca en robots.txt (primera palabra del User-Agent).
ROBOTS_AGENT = "RadarGovCo"

# Límites de tráfico de visitante normal (Ley 1273 de 2009). No se pueden subir
# desde sites.yaml: el código los impone aunque la configuración pida más.
MAX_PAGES_PER_SITE = 3
MIN_PAUSE_SECONDS = 3.0
DEFAULT_PAUSE_SECONDS = 5.0
NAV_TIMEOUT_MS = 45_000
# Lighthouse varía entre corridas: se mide 3 veces por vista y se usa la mediana.
# Son cargas extra de la misma página de inicio (no páginas nuevas) y llevan pausa.
LIGHTHOUSE_RUNS = 3


@dataclass
class Site:
    id: str
    name: str
    url: str
    category: str
    pages: list[str] = field(default_factory=list)

    @property
    def host(self) -> str:
        return urlparse(self.url).hostname or ""


@dataclass
class Settings:
    pause_seconds: float = DEFAULT_PAUSE_SECONDS
    max_pages: int = MAX_PAGES_PER_SITE


def _validate_site(raw: dict) -> Site:
    for key in ("id", "name", "url", "category"):
        if not raw.get(key):
            raise ValueError(f"Sitio sin '{key}': {raw}")
    host = urlparse(raw["url"]).hostname or ""
    if not host.endswith(".gov.co") and host != "gov.co":
        raise ValueError(f"{raw['id']}: solo se auditan dominios .gov.co ({host})")
    return Site(
        id=raw["id"],
        name=raw["name"],
        url=raw["url"],
        category=raw["category"],
        pages=list(raw.get("pages") or []),
    )


def load_config(path: str | Path) -> tuple[Settings, list[Site]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw_settings = data.get("settings") or {}
    settings = Settings(
        pause_seconds=max(MIN_PAUSE_SECONDS, float(raw_settings.get("pause_seconds", DEFAULT_PAUSE_SECONDS))),
        max_pages=max(1, min(MAX_PAGES_PER_SITE, int(raw_settings.get("max_pages", MAX_PAGES_PER_SITE)))),
    )
    sites = [_validate_site(s) for s in data.get("sites") or []]
    ids = [s.id for s in sites]
    duplicated = {i for i in ids if ids.count(i) > 1}
    if duplicated:
        raise ValueError(f"IDs repetidos en sites.yaml: {sorted(duplicated)}")
    return settings, sites
