import pytest

from radar import scoring


def test_axe_score_penalizes_once_per_rule():
    findings = [{"impact": "critical"}, {"impact": "serious"}, {"impact": "moderate"}, {"impact": "minor"}]
    assert scoring.axe_score(findings) == 100 - 10 - 6 - 3 - 1
    assert scoring.axe_score([]) == 100
    assert scoring.axe_score([{"impact": "critical"}] * 20) == 0


def test_failed_resources_score():
    assert scoring.failed_resources_score(0) == 100
    assert scoring.failed_resources_score(3) == 70
    assert scoring.failed_resources_score(50) == 0


@pytest.mark.parametrize("scroll,screen,expected", [(405, 390, 15), (390, 390, 0), (380, 390, 0), (None, 390, None)])
def test_overflow_px(scroll, screen, expected):
    assert scoring.overflow_px(scroll, screen) == expected


@pytest.mark.parametrize("px,expected", [(None, 0), (0, 0), (1, 0.5), (6, 3), (15, 7.5), (590, 50)])
def test_overflow_penalty_is_gradual_without_tolerance(px, expected):
    assert scoring.overflow_penalty(px) == expected


def test_mobile_score_combines_lighthouse_and_overflow():
    assert scoring.mobile_score(66, 15) == 58  # 66 - 7,5 = 58,5 -> 58 (redondeo bancario)
    assert scoring.mobile_score(66, 0) == 66
    assert scoring.mobile_score(33, 0) == 33  # sin desborde no hay 100 regalado
    assert scoring.mobile_score(30, 590) == 0
    assert scoring.mobile_score(80, None) == 80  # sin medición de desborde: solo Lighthouse
    assert scoring.mobile_score(None, 0) is None  # sin Lighthouse no hay nota móvil


def lh(perf, a11y, bp, seo):
    return {"categories": {"performance": perf, "accessibility": a11y, "best_practices": bp, "seo": seo}}


def test_component_scores_combines_sources():
    components = scoring.component_scores(
        axe_scores=[80, 90],
        lighthouse={"mobile": lh(40, 70, 90, 80), "desktop": lh(90, 90, 100, 100)},
        failed_count=1,
        mobile_overflow_px=10,
    )
    assert components == {
        "accessibility": 82,  # 0.5 * 85 (axe) + 0.5 * 80 (Lighthouse) = 82,5 -> 82
        "mobile": 35,  # 40 (Lighthouse móvil) - 5 (10 px de desborde)
        "performance": 90,  # Lighthouse escritorio
        "best_practices": 95,
        "seo": 90,
        "failed_resources": 90,
    }


def test_component_scores_with_missing_lighthouse():
    components = scoring.component_scores(
        axe_scores=[70], lighthouse={"mobile": None, "desktop": None}, failed_count=0, mobile_overflow_px=0
    )
    assert components["accessibility"] == 70
    assert components["performance"] is None
    assert components["mobile"] is None
    assert components["seo"] is None


def test_weights_add_up_to_one_and_accessibility_weighs_most():
    assert sum(scoring.WEIGHTS.values()) == pytest.approx(1.0)
    assert scoring.WEIGHTS["accessibility"] == max(scoring.WEIGHTS.values())
    assert all(scoring.WEIGHTS["accessibility"] > w for k, w in scoring.WEIGHTS.items() if k != "accessibility")


def full(**overrides):
    components = {k: 100 for k in scoring.WEIGHTS}
    components.update(overrides)
    return components


def test_overall_score_weighted():
    assert scoring.overall_score(full(performance=50)) == round(100 - 0.15 * 50)
    assert scoring.overall_score(full(accessibility=0)) == 65


def test_overall_renormalizes_missing_components():
    components = full(accessibility=80, mobile=None, performance=None, seo=60)
    # Peso disponible 0.65: (80*0.35 + 100*0.10 + 60*0.10 + 100*0.10) / 0.65 = 83,08
    assert scoring.overall_score(components) == 83


def test_overall_is_none_with_low_coverage():
    components = {k: None for k in scoring.WEIGHTS}
    components.update(accessibility=90, failed_resources=100)
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
