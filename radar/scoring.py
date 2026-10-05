"""Metodología de puntuación del Radar (versión 2).

Cada componente va de 0 a 100. La nota global es un promedio ponderado de los
componentes disponibles; si falta más de la mitad del peso, no hay nota global.
"""

from __future__ import annotations

from statistics import mean

METHODOLOGY_VERSION = 2

# Penalización por cada regla de axe incumplida en una página (una vez por regla,
# no por elemento: 40 imágenes sin alt son una sola regla incumplida).
AXE_PENALTY = {"critical": 10, "serious": 6, "moderate": 3, "minor": 1}
FAILED_RESOURCE_PENALTY = 10

# Desborde horizontal en móvil: 0,5 puntos por cada píxel que la página se sale
# de la pantalla de 390 px, sin tolerancia, con un tope de 50 puntos.
OVERFLOW_PENALTY_PER_PX = 0.5
MAX_OVERFLOW_PENALTY = 50

# La accesibilidad pesa más. El rendimiento móvil vive en "mobile" y el de
# escritorio en "performance", para no contar dos veces la misma medición.
WEIGHTS = {
    "accessibility": 0.35,
    "mobile": 0.20,
    "performance": 0.15,
    "best_practices": 0.10,
    "seo": 0.10,
    "failed_resources": 0.10,
}
MIN_COVERAGE = 0.5

# Semáforo del radar.
GREEN_FROM = 80
YELLOW_FROM = 50


def axe_score(findings: list[dict]) -> int:
    penalty = sum(AXE_PENALTY.get(f.get("impact"), AXE_PENALTY["minor"]) for f in findings)
    return max(0, 100 - penalty)


def failed_resources_score(failed_count: int) -> int:
    return max(0, 100 - FAILED_RESOURCE_PENALTY * failed_count)


def overflow_px(scroll_width: int | None, screen_width: int | None) -> int | None:
    if scroll_width is None or screen_width is None:
        return None
    return max(0, int(scroll_width) - int(screen_width))


def overflow_penalty(px: int | None) -> float:
    if not px:
        return 0.0
    return min(MAX_OVERFLOW_PENALTY, OVERFLOW_PENALTY_PER_PX * px)


def mobile_score(lighthouse_mobile_performance: float | None, px: int | None) -> int | None:
    """Rendimiento móvil de Lighthouse (mediana) menos la penalización por desborde.
    Sin dato de Lighthouse no hay nota móvil: el desborde solo no la representa."""
    if lighthouse_mobile_performance is None:
        return None
    return max(0, round(lighthouse_mobile_performance - overflow_penalty(px)))


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
    failed_count: int | None,
    mobile_overflow_px: int | None,
) -> dict[str, int | None]:
    """lighthouse = {"mobile": {"categories": {...}}, "desktop": {...}} con medianas (cualquiera puede faltar)."""

    def lh(form: str, key: str) -> float | None:
        data = lighthouse.get(form) or {}
        return (data.get("categories") or {}).get(key)

    lh_a11y = _avg([lh("mobile", "accessibility"), lh("desktop", "accessibility")])
    components = {
        "accessibility": _weighted([(_avg(list(axe_scores)), 0.5), (lh_a11y, 0.5)]),
        "mobile": mobile_score(lh("mobile", "performance"), mobile_overflow_px),
        "performance": lh("desktop", "performance"),
        "best_practices": _avg([lh("mobile", "best_practices"), lh("desktop", "best_practices")]),
        "seo": _avg([lh("mobile", "seo"), lh("desktop", "seo")]),
        "failed_resources": None if failed_count is None else failed_resources_score(failed_count),
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
