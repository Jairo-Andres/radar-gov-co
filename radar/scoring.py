"""Metodología de puntuación del Radar (versión 1).

Cada componente va de 0 a 100. La nota global es un promedio ponderado de los
componentes disponibles; si falta más de la mitad del peso, no hay nota global.
"""

from __future__ import annotations

from statistics import mean

METHODOLOGY_VERSION = 1

# Penalización por cada regla de axe incumplida (una vez por regla, no por elemento).
AXE_PENALTY = {"critical": 10, "serious": 6, "moderate": 3, "minor": 1}
BROKEN_RESOURCE_PENALTY = 10

WEIGHTS = {
    "accessibility": 0.30,
    "performance": 0.25,
    "best_practices": 0.15,
    "seo": 0.10,
    "links": 0.10,
    "mobile": 0.10,
}
MIN_COVERAGE = 0.5

# Semáforo del radar.
GREEN_FROM = 80
YELLOW_FROM = 50


def axe_score(findings: list[dict]) -> int:
    penalty = sum(AXE_PENALTY.get(f.get("impact"), AXE_PENALTY["minor"]) for f in findings)
    return max(0, 100 - penalty)


def links_score(broken_count: int) -> int:
    return max(0, 100 - BROKEN_RESOURCE_PENALTY * broken_count)


def mobile_score(has_viewport_meta: bool | None, horizontal_overflow: bool | None) -> int | None:
    """50 puntos por declarar viewport adaptable y 50 por no desbordar a lo ancho en 390 px."""
    if has_viewport_meta is None and horizontal_overflow is None:
        return None
    score = 0
    if has_viewport_meta:
        score += 50
    if horizontal_overflow is False:
        score += 50
    return score


def _avg(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return mean(present) if present else None


def _weighted(pairs: list[tuple[float | None, float]]) -> float | None:
    present = [(v, w) for v, w in pairs if v is not None]
    if not present:
        return None
    total = sum(w for _, w in present)
    return sum(v * w for v, w in present) / total


def component_scores(
    axe_scores: list[int],
    lighthouse: dict[str, dict | None],
    broken_count: int | None,
    mobile: int | None,
) -> dict[str, int | None]:
    """lighthouse = {"mobile": {"categories": {...}}, "desktop": {...}} (cualquiera puede faltar)."""

    def lh(form: str, key: str) -> float | None:
        data = lighthouse.get(form) or {}
        return (data.get("categories") or {}).get(key)

    lh_a11y = _avg([lh("mobile", "accessibility"), lh("desktop", "accessibility")])
    components = {
        "accessibility": _weighted([(_avg(list(axe_scores)), 0.5), (lh_a11y, 0.5)]),
        # Mobile-first: el móvil pesa más en rendimiento.
        "performance": _weighted([(lh("mobile", "performance"), 0.6), (lh("desktop", "performance"), 0.4)]),
        "best_practices": _avg([lh("mobile", "best_practices"), lh("desktop", "best_practices")]),
        "seo": _avg([lh("mobile", "seo"), lh("desktop", "seo")]),
        "links": None if broken_count is None else links_score(broken_count),
        "mobile": mobile,
    }
    return {k: (None if v is None else round(v)) for k, v in components.items()}


def overall_score(components: dict[str, int | None]) -> int | None:
    coverage = sum(WEIGHTS[k] for k, v in components.items() if v is not None and k in WEIGHTS)
    if coverage < MIN_COVERAGE:
        return None
    value = _weighted([(components.get(k), w) for k, w in WEIGHTS.items()])
    return None if value is None else round(value)


def light(overall: int | None) -> str:
    if overall is None:
        return "sin_dato"
    if overall >= GREEN_FROM:
        return "verde"
    if overall >= YELLOW_FROM:
        return "amarillo"
    return "rojo"


def rank(entries: list[dict]) -> list[dict]:
    """Ordena por nota global (desc) y asigna puesto con empates (1, 2, 2, 4).
    Los sitios sin nota van al final y sin puesto."""
    scored = sorted((e for e in entries if e.get("overall") is not None), key=lambda e: (-e["overall"], e["id"]))
    unscored = sorted((e for e in entries if e.get("overall") is None), key=lambda e: e["id"])
    previous, position = None, 0
    for index, entry in enumerate(scored, start=1):
        if entry["overall"] != previous:
            position, previous = index, entry["overall"]
        entry["rank"] = position
    for entry in unscored:
        entry["rank"] = None
    return scored + unscored
