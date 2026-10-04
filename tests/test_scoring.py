import pytest

from radar import scoring


def test_axe_score_penalizes_once_per_rule():
    findings = [{"impact": "critical"}, {"impact": "serious"}, {"impact": "moderate"}, {"impact": "minor"}]
    assert scoring.axe_score(findings) == 100 - 10 - 6 - 3 - 1
    assert scoring.axe_score([]) == 100
    assert scoring.axe_score([{"impact": "critical"}] * 20) == 0


def test_links_score():
    assert scoring.links_score(0) == 100
    assert scoring.links_score(3) == 70
    assert scoring.links_score(50) == 0


@pytest.mark.parametrize("meta,overflow,expected", [
    (True, False, 100), (True, True, 50), (False, False, 50), (False, True, 0), (None, None, None),
])
def test_mobile_score(meta, overflow, expected):
    assert scoring.mobile_score(meta, overflow) == expected


def lh(perf, a11y, bp, seo):
    return {"categories": {"performance": perf, "accessibility": a11y, "best_practices": bp, "seo": seo}}


def test_component_scores_combines_sources():
    components = scoring.component_scores(
        axe_scores=[80, 90],
        lighthouse={"mobile": lh(40, 70, 90, 80), "desktop": lh(90, 90, 100, 100)},
        broken_count=1,
        mobile=100,
    )
    assert components == {
        "accessibility": 82,  # 0.5 * 85 (axe) + 0.5 * 80 (Lighthouse) = 82.5 -> 82 (redondeo bancario)
        "performance": 60,  # 0.6 * 40 + 0.4 * 90
        "best_practices": 95,
        "seo": 90,
        "links": 90,
        "mobile": 100,
    }


def test_component_scores_with_missing_lighthouse():
    components = scoring.component_scores(
        axe_scores=[70], lighthouse={"mobile": None, "desktop": None}, broken_count=0, mobile=50
    )
    assert components["accessibility"] == 70
    assert components["performance"] is None
    assert components["seo"] is None


def test_weights_add_up_to_one():
    assert sum(scoring.WEIGHTS.values()) == pytest.approx(1.0)


def test_overall_score_weighted():
    components = {"accessibility": 100, "performance": 50, "best_practices": 100, "seo": 100, "links": 100, "mobile": 100}
    assert scoring.overall_score(components) == round(100 - 0.25 * 50)


def test_overall_renormalizes_missing_components():
    components = {"accessibility": 80, "performance": None, "best_practices": None, "seo": None, "links": 100, "mobile": 60}
    # Peso disponible 0.5: (80*0.3 + 100*0.1 + 60*0.1) / 0.5 = 80
    assert scoring.overall_score(components) == 80


def test_overall_is_none_with_low_coverage():
    components = {"accessibility": 90, "performance": None, "best_practices": None, "seo": None, "links": None, "mobile": 100}
    assert scoring.overall_score(components) is None


@pytest.mark.parametrize("overall,expected", [
    (95, "verde"), (80, "verde"), (79, "amarillo"), (50, "amarillo"), (49, "rojo"), (None, "sin_dato"),
])
def test_light(overall, expected):
    assert scoring.light(overall) == expected


def test_rank_handles_ties_and_missing():
    entries = [
        {"id": "c", "overall": 70}, {"id": "a", "overall": 90}, {"id": "x", "overall": None},
        {"id": "b", "overall": 70}, {"id": "d", "overall": 50},
    ]
    ranked = scoring.rank(entries)
    assert [(e["id"], e["rank"]) for e in ranked] == [("a", 1), ("b", 2), ("c", 2), ("d", 4), ("x", None)]
