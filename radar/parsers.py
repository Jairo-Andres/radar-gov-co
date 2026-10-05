"""Convierte los resultados crudos de axe-core y Lighthouse al formato publicado.

Todo lo que pueda considerarse un hallazgo de seguridad se separa aquí y nunca
llega a data/: va a private/ (ignorado por git) para avisar a Jairo.
"""

from __future__ import annotations

import re
from statistics import median

AXE_IMPACTS = ("critical", "serious", "moderate", "minor")

# Auditorías de Lighthouse relacionadas con seguridad. Sus resultados no se
# publican (la puntuación agregada de "buenas prácticas" sí).
SECURITY_AUDITS = frozenset(
    {
        "is-on-https",
        "redirects-http",
        "csp-xss",
        "has-hsts",
        "origin-isolation",
        "clickjacking-mitigation",
        "trusted-types-xss",
        "no-vulnerable-libraries",
    }
)
# Auditorías que tampoco se publican (pueden mencionar detalles de cookies o de
# contenido mixto), pero que no son por sí mismas un hallazgo de seguridad.
UNPUBLISHED_AUDITS = SECURITY_AUDITS | {
    "third-party-cookies",
    "inspector-issues",
    "notification-on-start",
    "geolocation-on-start",
}

LIGHTHOUSE_CATEGORIES = {
    "performance": "performance",
    "accessibility": "accessibility",
    "best-practices": "best_practices",
    "seo": "seo",
}

LIGHTHOUSE_METRICS = {
    "first-contentful-paint": "fcp_ms",
    "largest-contentful-paint": "lcp_ms",
    "total-blocking-time": "tbt_ms",
    "cumulative-layout-shift": "cls",
    "speed-index": "speed_index_ms",
}

_CRITERION_TAG = re.compile(r"^wcag(\d)(\d)(\d+)$")


def wcag_criteria(tags: list[str]) -> list[str]:
    """['wcag2a', 'wcag111', 'wcag1410'] -> ['1.1.1', '1.4.10']."""
    criteria = []
    for tag in tags:
        match = _CRITERION_TAG.match(tag)
        if match:
            criteria.append(".".join(match.groups()))
    return criteria


def wcag_level(tags: list[str]) -> str | None:
    if any(t in ("wcag2aa", "wcag21aa", "wcag22aa") for t in tags):
        return "AA"
    if any(t in ("wcag2a", "wcag21a", "wcag22a") for t in tags):
        return "A"
    return None


def describe_violation(rule_id: str, criteria: list[str]) -> str:
    """Redacción objetiva del hallazgo, sin juicios sobre la entidad."""
    if criteria:
        label = "el criterio" if len(criteria) == 1 else "los criterios"
        return f"No cumple {label} WCAG {', '.join(criteria)} (regla {rule_id})"
    return f"No cumple la regla {rule_id} de axe-core"


def parse_axe(result: dict, max_targets: int = 3) -> list[dict]:
    """Resultado de axe.run() -> lista de incumplimientos, de más a menos grave."""
    findings = []
    for violation in result.get("violations", []):
        tags = violation.get("tags", [])
        criteria = wcag_criteria(tags)
        nodes = violation.get("nodes", [])
        findings.append(
            {
                "rule": violation["id"],
                "impact": violation.get("impact") or "minor",
                "criteria": criteria,
                "level": wcag_level(tags),
                "description": describe_violation(violation["id"], criteria),
                "help_en": violation.get("help", ""),
                "help_url": violation.get("helpUrl", ""),
                "elements": len(nodes),
                "examples": [_target(n) for n in nodes[:max_targets]],
            }
        )
    order = {impact: i for i, impact in enumerate(AXE_IMPACTS)}
    findings.sort(key=lambda f: (order.get(f["impact"], len(order)), -f["elements"], f["rule"]))
    return findings


def _target(node: dict) -> str:
    target = node.get("target") or []
    flat = [t if isinstance(t, str) else " ".join(t) for t in target]
    return " > ".join(flat)[:200]


def _score_100(score: float | None) -> int | None:
    return None if score is None else round(score * 100)


def parse_lighthouse(lhr: dict, max_failed: int = 8) -> tuple[dict, list[dict]]:
    """LHR de Lighthouse -> (resumen publicable, hallazgos de seguridad privados)."""
    categories = lhr.get("categories", {})
    audits = lhr.get("audits", {})

    summary: dict = {"categories": {}, "metrics": {}, "failed_audits": {}}
    for lh_id, key in LIGHTHOUSE_CATEGORIES.items():
        summary["categories"][key] = _score_100((categories.get(lh_id) or {}).get("score"))

    for audit_id, key in LIGHTHOUSE_METRICS.items():
        value = (audits.get(audit_id) or {}).get("numericValue")
        if value is not None:
            summary["metrics"][key] = round(value, 3) if key == "cls" else round(value)

    security: list[dict] = []
    for lh_id, key in LIGHTHOUSE_CATEGORIES.items():
        failed = []
        for ref in (categories.get(lh_id) or {}).get("auditRefs", []):
            audit = audits.get(ref.get("id"))
            if not audit or not _is_failed(audit):
                continue
            if ref["id"] in SECURITY_AUDITS:
                security.append({"audit": ref["id"], "title": audit.get("title", ""), "score": audit.get("score")})
            if ref["id"] in UNPUBLISHED_AUDITS:
                continue
            if lh_id == "performance" and ref.get("group") == "metrics":
                continue  # las métricas ya se publican como números
            failed.append({"id": ref["id"], "title": audit.get("title", ""), "weight": ref.get("weight", 0)})
        failed.sort(key=lambda a: -a["weight"])
        summary["failed_audits"][key] = [{"id": a["id"], "title": a["title"]} for a in failed[:max_failed]]

    runtime_error = lhr.get("runtimeError")
    if runtime_error:
        summary["runtime_error"] = runtime_error.get("code")
    if lhr.get("lighthouseVersion"):
        summary["lighthouse_version"] = lhr["lighthouseVersion"]
    return summary, security


def _median(values: list[float]) -> float | None:
    return median(values) if values else None


def median_lighthouse(runs: list[dict]) -> dict | None:
    """Combina varias corridas de Lighthouse (ya parseadas y sin runtime_error) con la
    mediana de cada categoría y métrica. Las auditorías fallidas se toman de la corrida
    cuyo rendimiento es la mediana, para que el detalle sea coherente con la nota."""
    if not runs:
        return None
    combined: dict = {"runs": len(runs), "categories": {}, "metrics": {}}
    for key in LIGHTHOUSE_CATEGORIES.values():
        values = [r["categories"].get(key) for r in runs if r["categories"].get(key) is not None]
        value = _median(values)
        combined["categories"][key] = None if value is None else round(value)
    for key in LIGHTHOUSE_METRICS.values():
        values = [r["metrics"][key] for r in runs if r["metrics"].get(key) is not None]
        value = _median(values)
        if value is not None:
            combined["metrics"][key] = round(value, 3) if key == "cls" else round(value)
    combined["performance_runs"] = [r["categories"].get("performance") for r in runs]
    target = combined["categories"]["performance"]
    representative = min(
        runs,
        key=lambda r: abs((r["categories"].get("performance") or 0) - (target or 0)),
    )
    combined["failed_audits"] = representative.get("failed_audits", {})
    if any(r.get("lighthouse_version") for r in runs):
        combined["lighthouse_version"] = next(r["lighthouse_version"] for r in runs if r.get("lighthouse_version"))
    return combined


def wcag_summary(pages: list[dict]) -> dict:
    """Resume axe por sitio sin contar varias veces lo mismo.

    - rules: reglas WCAG distintas incumplidas en cualquier página o vista.
    - cases: total de elementos afectados. Si una página se revisó en escritorio y
      en móvil, por cada regla se toma la vista con más casos (no se suman ambas).
    """
    rules: dict[str, dict] = {}
    per_page_rule: dict[tuple[str, str], int] = {}
    for page in pages:
        for finding in (page.get("axe") or {}).get("violations", []):
            rule = finding["rule"]
            rules.setdefault(rule, {
                "rule": rule,
                "impact": finding.get("impact"),
                "criteria": finding.get("criteria", []),
                "description": finding.get("description", ""),
            })
            key = (page.get("url", ""), rule)
            per_page_rule[key] = max(per_page_rule.get(key, 0), finding.get("elements", 0))
    order = {impact: i for i, impact in enumerate(AXE_IMPACTS)}
    listed = sorted(rules.values(), key=lambda r: (order.get(r["impact"], len(order)), r["rule"]))
    for item in listed:
        item["cases"] = sum(n for (_, rule), n in per_page_rule.items() if rule == item["rule"])
    criteria = sorted({c for r in listed for c in r["criteria"]}, key=lambda c: [int(x) for x in c.split(".")])
    return {
        "rules_count": len(listed),
        "cases": sum(per_page_rule.values()),
        "criteria": criteria,
        "rules": listed,
    }


def _is_failed(audit: dict) -> bool:
    score = audit.get("score")
    mode = audit.get("scoreDisplayMode")
    if score is None or mode in ("notApplicable", "manual", "informative", "error"):
        return False
    return score < 0.9
