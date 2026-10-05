from radar import parsers


def test_wcag_criteria_extracts_success_criteria_and_ignores_levels():
    tags = ["cat.text-alternatives", "wcag2a", "wcag111", "wcag21aa", "wcag1410", "section508"]
    assert parsers.wcag_criteria(tags) == ["1.1.1", "1.4.10"]


def test_wcag_level():
    assert parsers.wcag_level(["wcag2a"]) == "A"
    assert parsers.wcag_level(["wcag2a", "wcag21aa"]) == "AA"
    assert parsers.wcag_level(["best-practice"]) is None


def test_describe_violation_is_objective():
    assert parsers.describe_violation("image-alt", ["1.1.1"]) == "No cumple el criterio WCAG 1.1.1 (regla image-alt)"
    assert parsers.describe_violation("x", ["1.3.1", "4.1.2"]).startswith("No cumple los criterios WCAG 1.3.1, 4.1.2")
    assert parsers.describe_violation("x", []) == "No cumple la regla x de axe-core"


def test_parse_axe_fixture(axe_raw):
    findings = parsers.parse_axe(axe_raw)
    by_rule = {f["rule"]: f for f in findings}
    assert set(by_rule) == {"image-alt", "html-has-lang"}
    image_alt = by_rule["image-alt"]
    assert image_alt["criteria"] == ["1.1.1"]
    assert image_alt["impact"] == "critical"
    assert image_alt["elements"] == 1
    assert image_alt["description"].startswith("No cumple el criterio WCAG 1.1.1")


def test_parse_axe_sorts_by_impact_then_elements():
    raw = {"violations": [
        {"id": "b", "impact": "minor", "tags": [], "nodes": [{}]},
        {"id": "a", "impact": "critical", "tags": [], "nodes": [{}]},
        {"id": "c", "impact": "critical", "tags": [], "nodes": [{}, {}, {}]},
    ]}
    assert [f["rule"] for f in parsers.parse_axe(raw)] == ["c", "a", "b"]


def test_parse_axe_limits_examples_and_handles_missing_impact():
    nodes = [{"target": [f"#n{i}"]} for i in range(10)]
    raw = {"violations": [{"id": "r", "impact": None, "tags": [], "nodes": nodes}]}
    finding = parsers.parse_axe(raw, max_targets=2)[0]
    assert finding["impact"] == "minor"
    assert finding["elements"] == 10
    assert finding["examples"] == ["#n0", "#n1"]


def test_parse_lighthouse_categories_and_metrics(lhr_mobile):
    summary, _ = parsers.parse_lighthouse(lhr_mobile)
    assert summary["categories"] == {"performance": 100, "accessibility": 53, "best_practices": 96, "seo": 83}
    assert set(summary["metrics"]) == {"fcp_ms", "lcp_ms", "tbt_ms", "cls", "speed_index_ms"}
    a11y_ids = [a["id"] for a in summary["failed_audits"]["accessibility"]]
    assert "image-alt" in a11y_ids and "html-has-lang" in a11y_ids


def test_parse_lighthouse_never_publishes_security_audits(lhr_mobile):
    summary, security = parsers.parse_lighthouse(lhr_mobile)
    published = [a["id"] for audits in summary["failed_audits"].values() for a in audits]
    assert not set(published) & parsers.UNPUBLISHED_AUDITS
    assert [s["audit"] for s in security] == ["is-on-https"]


def test_parse_lighthouse_skips_metrics_in_failed_audits():
    lhr = {
        "categories": {"performance": {"score": 0.4, "auditRefs": [
            {"id": "largest-contentful-paint", "weight": 25, "group": "metrics"},
            {"id": "render-blocking", "weight": 0},
        ]}},
        "audits": {
            "largest-contentful-paint": {"title": "LCP", "score": 0.1, "scoreDisplayMode": "numeric", "numericValue": 8123.4},
            "render-blocking": {"title": "Recursos que bloquean", "score": 0, "scoreDisplayMode": "metricSavings"},
        },
    }
    summary, security = parsers.parse_lighthouse(lhr)
    assert summary["categories"]["performance"] == 40
    assert summary["categories"]["seo"] is None
    assert summary["metrics"] == {"lcp_ms": 8123}
    assert summary["failed_audits"]["performance"] == [{"id": "render-blocking", "title": "Recursos que bloquean"}]
    assert security == []


def test_parse_lighthouse_reports_runtime_error():
    summary, _ = parsers.parse_lighthouse({"categories": {}, "audits": {}, "runtimeError": {"code": "NO_FCP"}})
    assert summary["runtime_error"] == "NO_FCP"
    assert summary["categories"]["performance"] is None


def test_unpublished_but_not_security_audits_raise_no_alert():
    lhr = {
        "categories": {"best-practices": {"score": 0.7, "auditRefs": [
            {"id": "third-party-cookies", "weight": 1}, {"id": "errors-in-console", "weight": 1},
        ]}},
        "audits": {
            "third-party-cookies": {"title": "Cookies de terceros", "score": 0, "scoreDisplayMode": "binary"},
            "errors-in-console": {"title": "Errores en consola", "score": 0, "scoreDisplayMode": "binary"},
        },
    }
    summary, security = parsers.parse_lighthouse(lhr)
    assert summary["failed_audits"]["best_practices"] == [{"id": "errors-in-console", "title": "Errores en consola"}]
    assert security == []


def lh_run(perf, a11y=90, lcp=3000, failed=None, version="13.5.0"):
    return {
        "categories": {"performance": perf, "accessibility": a11y, "best_practices": 80, "seo": None},
        "metrics": {"lcp_ms": lcp, "cls": 0.1},
        "failed_audits": failed or {"performance": [{"id": f"run-{perf}", "title": "t"}]},
        "lighthouse_version": version,
    }


def test_median_lighthouse_uses_median_of_three_runs():
    combined = parsers.median_lighthouse([lh_run(30, lcp=29000), lh_run(70, lcp=5000), lh_run(55, lcp=8000)])
    assert combined["runs"] == 3
    assert combined["categories"] == {"performance": 55, "accessibility": 90, "best_practices": 80, "seo": None}
    assert combined["metrics"] == {"lcp_ms": 8000, "cls": 0.1}
    assert combined["performance_runs"] == [30, 70, 55]
    # El detalle viene de la corrida mediana, coherente con la nota publicada.
    assert combined["failed_audits"]["performance"][0]["id"] == "run-55"
    assert combined["lighthouse_version"] == "13.5.0"


def test_median_lighthouse_with_two_runs_and_none():
    combined = parsers.median_lighthouse([lh_run(40), lh_run(60)])
    assert combined["runs"] == 2
    assert combined["categories"]["performance"] == 50
    assert parsers.median_lighthouse([]) is None


def axe_page(url, *findings):
    return {"url": url, "axe": {"violations": [
        {"rule": rule, "impact": impact, "criteria": criteria, "description": "d", "elements": n}
        for rule, impact, criteria, n in findings
    ]}}


def test_wcag_summary_counts_distinct_rules_and_cases():
    pages = [
        axe_page("https://x.gov.co/", ("image-alt", "critical", ["1.1.1"], 21), ("color-contrast", "serious", ["1.4.3"], 20)),
        axe_page("https://x.gov.co/a", ("image-alt", "critical", ["1.1.1"], 7), ("list", "serious", ["1.3.1"], 1)),
        # El inicio en móvil repite reglas: por regla cuenta la vista con más casos.
        axe_page("https://x.gov.co/", ("image-alt", "critical", ["1.1.1"], 4), ("color-contrast", "serious", ["1.4.3"], 25)),
    ]
    summary = parsers.wcag_summary(pages)
    assert summary["rules_count"] == 3
    assert summary["cases"] == 21 + 25 + 7 + 1
    assert summary["criteria"] == ["1.1.1", "1.3.1", "1.4.3"]
    by_rule = {r["rule"]: r["cases"] for r in summary["rules"]}
    assert by_rule == {"image-alt": 28, "color-contrast": 25, "list": 1}
    assert summary["rules"][0]["rule"] == "image-alt"  # crítica primero


def test_wcag_summary_empty():
    assert parsers.wcag_summary([{"url": "u"}]) == {"rules_count": 0, "cases": 0, "criteria": [], "rules": []}


def test_wcag_criteria_sort_numerically():
    pages = [axe_page("u", ("a", "minor", ["1.4.10"], 1), ("b", "minor", ["1.4.3"], 1))]
    assert parsers.wcag_summary(pages)["criteria"] == ["1.4.3", "1.4.10"]
