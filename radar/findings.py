"""Hallazgos agregados de una medición: lo que la web cuenta antes de la tabla.

Solo se calculan conteos y medianas objetivas sobre los sitios que se pudieron
medir; la redacción final la hace la web en español e inglés.
"""

from __future__ import annotations

from collections import Counter
from statistics import mean, median


def _median(values: list[float]) -> float | None:
    present = [v for v in values if v is not None]
    return round(median(present), 1) if present else None


def build_findings(records: list[dict], top_rules: int = 8) -> dict:
    measured = [r for r in records if (r.get("scores") or {}).get("overall") is not None]

    rule_sites: Counter[str] = Counter()
    rule_info: dict[str, dict] = {}
    for record in measured:
        for rule in (record.get("wcag") or {}).get("rules", []):
            rule_sites[rule["rule"]] += 1
            rule_info.setdefault(rule["rule"], {"criteria": rule.get("criteria", []), "impact": rule.get("impact")})
    rules = [
        {"rule": rule, "sites": count, **rule_info[rule]}
        for rule, count in sorted(rule_sites.items(), key=lambda item: (-item[1], item[0]))[:top_rules]
    ]

    mobile = [r.get("mobile") or {} for r in measured]
    lighthouse_mobile = [((r.get("lighthouse") or {}).get("mobile") or {}).get("categories", {}) for r in measured]

    by_category: dict[str, list[int]] = {}
    for record in measured:
        by_category.setdefault(record["category"], []).append(record["scores"]["overall"])

    return {
        "sites_measured": len(measured),
        "sites_with_critical_rule": sum(
            1 for r in measured if any(x.get("impact") == "critical" for x in (r.get("wcag") or {}).get("rules", []))
        ),
        "sites_with_any_wcag_rule": sum(1 for r in measured if (r.get("wcag") or {}).get("rules_count")),
        "top_rules": rules,
        "sites_with_mobile_overflow": sum(1 for m in mobile if (m.get("overflow_px") or 0) > 0),
        "sites_without_viewport_meta": sum(1 for m in mobile if m and m.get("viewport_meta") is False),
        "sites_with_failed_resources": sum(1 for r in measured if (r.get("failed_resources_first_party") or 0) > 0),
        "median_overall": _median([r["scores"]["overall"] for r in measured]),
        "median_accessibility": _median([r["scores"].get("accessibility") for r in measured]),
        "median_mobile_performance": _median([c.get("performance") for c in lighthouse_mobile]),
        "median_desktop_performance": _median([r["scores"].get("performance") for r in measured]),
        "by_category": sorted(
            ({"category": k, "sites": len(v), "average_overall": round(mean(v), 1)} for k, v in by_category.items()),
            key=lambda c: (-c["average_overall"], c["category"]),
        ),
    }
