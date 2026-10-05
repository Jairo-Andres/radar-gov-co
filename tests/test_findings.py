from conftest import make_record
from radar.findings import build_findings


def rule(name, impact, criteria=("1.1.1",)):
    return {"rule": name, "impact": impact, "criteria": list(criteria), "cases": 1}


def record(site_id, overall, rules=(), overflow=0, meta=True, failed=0, mobile_perf=50, category="Ministerio"):
    return make_record(
        site_id,
        category=category,
        scores={"overall": overall, "accessibility": overall, "performance": 70},
        wcag={"rules_count": len(rules), "rules": list(rules)},
        mobile={"overflow_px": overflow, "viewport_meta": meta},
        lighthouse={"mobile": {"categories": {"performance": mobile_perf}}, "desktop": None},
        failed_resources_first_party=failed,
    )


def test_findings_counts_sites_not_cases():
    records = [
        record("a", 90, [rule("link-name", "serious"), rule("image-alt", "critical")], overflow=6, mobile_perf=40),
        record("b", 70, [rule("link-name", "serious")], failed=2, mobile_perf=60, category="Alcaldía"),
        record("c", 50, [rule("color-contrast", "serious", ("1.4.3",))], overflow=590, meta=False, mobile_perf=30),
        make_record("d", scores={"overall": None}),  # sin nota: no cuenta
    ]
    findings = build_findings(records)
    assert findings["sites_measured"] == 3
    assert findings["sites_with_critical_rule"] == 1
    assert findings["sites_with_any_wcag_rule"] == 3
    assert findings["top_rules"][0] == {"rule": "link-name", "sites": 2, "criteria": ["1.1.1"], "impact": "serious"}
    assert findings["sites_with_mobile_overflow"] == 2
    assert findings["sites_without_viewport_meta"] == 1
    assert findings["sites_with_failed_resources"] == 1
    assert findings["median_overall"] == 70
    assert findings["median_mobile_performance"] == 40
    # Empate en promedio: se ordena por nombre.
    assert findings["by_category"] == [
        {"category": "Alcaldía", "sites": 1, "average_overall": 70.0},
        {"category": "Ministerio", "sites": 2, "average_overall": 70.0},
    ]


def test_findings_empty():
    findings = build_findings([])
    assert findings["sites_measured"] == 0
    assert findings["top_rules"] == []
    assert findings["median_overall"] is None
