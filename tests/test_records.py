import json

from conftest import make_record
from radar import parsers
from radar.auditor import SecurityLog, finish_record, public_error
from radar.config import Site
from radar.history import build_history, write_history
from radar.runner import build_summary


def page(score, failed=(), viewport="desktop", screenshot=None, url="u", third_party=0):
    violations = [{"rule": "r", "impact": "serious", "criteria": ["1.1.1"], "elements": 2}] if score < 100 else []
    p = {
        "url": url,
        "viewport": viewport,
        "axe": {"score": score, "violations": violations},
        "failed_resources": list(failed),
        "third_party_failures": third_party,
    }
    if screenshot:
        p["screenshot"] = screenshot
    return p


def test_finish_record_full(lhr_mobile):
    summary, _ = parsers.parse_lighthouse(lhr_mobile)
    lh = parsers.median_lighthouse([summary, summary, summary])
    failed = [{"url": "https://www.dane.gov.co/x.png", "status": 404, "first_party": True}]
    record = make_record(
        pages=[page(84, failed, third_party=5, url="https://www.dane.gov.co/"), page(100, url="https://www.dane.gov.co/a")],
        mobile={"viewport_meta": True, "horizontal_overflow": True, "scroll_width": 400, "screen_width": 390},
        lighthouse={"mobile": lh, "desktop": lh},
    )
    finish_record(record)
    assert record["failed_resources_first_party"] == 1
    assert record["third_party_failures"] == 5  # se registran pero no restan
    assert record["scores"]["failed_resources"] == 90
    assert record["mobile"]["overflow_px"] == 10
    assert record["scores"]["mobile"] == 95  # Lighthouse móvil 100 - 5 por 10 px
    assert record["wcag"]["rules_count"] == 1
    assert record["wcag"]["cases"] == 2
    assert record["scores"]["overall"] is not None
    assert record["status"] == "ok"
    assert record["light"] in {"verde", "amarillo", "rojo"}


def test_finish_record_without_pages_is_no_response():
    record = finish_record(make_record(errors=["inicio (escritorio): no se pudo conectar con el sitio"]))
    assert record["status"] == "sin_respuesta"
    assert record["scores"]["overall"] is None
    assert record["light"] == "sin_dato"


def test_finish_record_partial_when_errors():
    record = finish_record(make_record(pages=[page(90)], errors=["Lighthouse (mobile): falló"]))
    assert record["status"] == "parcial"


def test_certificate_errors_are_kept_private():
    security = SecurityLog()
    site = Site(id="x", name="X", url="https://x.gov.co/", category="E")
    error = Exception("Page.goto: net::ERR_CERT_DATE_INVALID at https://x.gov.co/")
    message = public_error(error, site, "inicio", security)
    assert message == "inicio: no se pudo cargar la página"
    assert security.items[0]["detail"].startswith("Page.goto: net::ERR_CERT")


def test_timeout_message_is_neutral():
    site = Site("x", "X", "https://x.gov.co/", "E")
    message = public_error(Exception("Timeout 45000ms exceeded."), site, "inicio", SecurityLog())
    assert message == "inicio: la página no terminó de cargar a tiempo"


def lighthouse(perf):
    run = {"categories": {"performance": perf, "accessibility": 90, "best_practices": 80, "seo": 90},
           "metrics": {}, "failed_audits": {}}
    return {"mobile": parsers.median_lighthouse([run]), "desktop": parsers.median_lighthouse([run])}


def records_for_summary():
    a = finish_record(make_record(
        "dane", pages=[page(100, screenshot="screenshots/dane-desktop.jpg")],
        mobile={"scroll_width": 390, "screen_width": 390}, lighthouse=lighthouse(80),
    ))
    b = finish_record(make_record(
        "dian", pages=[page(60)], mobile={"scroll_width": 980, "screen_width": 390}, lighthouse=lighthouse(60),
    ))
    c = finish_record(make_record("icbf"))
    return [c, b, a]


def test_build_summary_ranks_and_counts():
    summary = build_summary(records_for_summary(), "2026-10-05", "equipo local")
    assert summary["measurement"]["from"] == "equipo local"
    assert [(s["id"], s["rank"]) for s in summary["sites"]] == [("dane", 1), ("dian", 2), ("icbf", None)]
    assert summary["sites_audited"] == 3
    assert summary["lights"]["sin_dato"] == 1
    assert summary["sites"][0]["screenshots"] == ["screenshots/dane-desktop.jpg"]
    assert summary["sites"][0]["detail"] == "sites/dane.json"
    assert summary["sites"][1]["wcag_rules"] == 1 and summary["sites"][1]["wcag_cases"] == 2
    assert summary["measurement"]["lighthouse_runs_per_view"] == 3
    assert summary["measurement"]["lighthouse_aggregate"] == "mediana"
    expected_avg = round((summary["sites"][0]["overall"] + summary["sites"][1]["overall"]) / 2)
    assert summary["average_overall"] == expected_avg


def test_history_tracks_weekly_change():
    first = build_summary(records_for_summary(), "2026-10-05")
    second = json.loads(json.dumps(first))
    second["date"] = "2026-10-12"
    second["sites"][0]["overall"] -= 5
    history = build_history([second, first])  # el orden de entrada no importa
    assert [r["date"] for r in history["runs"]] == ["2026-10-05", "2026-10-12"]
    assert history["sites"]["dane"]["change"] == -5
    assert history["sites"]["icbf"]["change"] is None
    assert len(history["sites"]["dian"]["series"]) == 2


def write_run(root, origin, date):
    folder = root / origin / date
    folder.mkdir(parents=True)
    summary = build_summary(records_for_summary(), date, "prueba", origin)
    (folder / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


def test_write_history_keeps_series_by_origin(tmp_path):
    write_run(tmp_path, "local-co", "2026-10-05")
    write_run(tmp_path, "github-actions", "2026-10-12")
    write_run(tmp_path, "github-actions", "2026-10-19")
    (tmp_path / "notas").mkdir()  # carpetas sin fechas adentro se ignoran
    history = write_history(tmp_path, "github-actions")
    assert set(history["origins"]) == {"local-co", "github-actions"}
    assert len(history["origins"]["github-actions"]["runs"]) == 2
    # El cambio semanal solo compara dentro de la misma serie.
    assert history["origins"]["local-co"]["sites"]["dane"]["change"] is None
    latest = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert latest == {"origin": "github-actions", "official": True, "date": "2026-10-19",
                      "summary": "github-actions/2026-10-19/summary.json"}


def test_latest_falls_back_when_official_series_is_empty(tmp_path):
    write_run(tmp_path, "local-co", "2026-10-04")
    write_history(tmp_path, "github-actions")
    latest = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert latest["origin"] == "local-co"
    assert latest["official"] is False
    assert latest["summary"] == "local-co/2026-10-04/summary.json"


def test_only_http_errors_are_penalized():
    failed = [
        {"url": "https://www.dane.gov.co/a.png", "status": 404, "first_party": True},
        {"url": "https://www.dane.gov.co/b.js", "status": None, "error": "net::ERR_CONNECTION_RESET", "first_party": True},
        {"url": "https://www.dane.gov.co/c.css", "status": 403, "first_party": True},
    ]
    record = finish_record(make_record(pages=[page(100, failed)]))
    assert record["failed_resources_first_party"] == 1
    assert record["failed_resources_unverified"] == 2
    assert record["scores"]["failed_resources"] == 90


def test_verified_overflow_lowers_penalty_only():
    lh = lighthouse(60)
    base = dict(pages=[page(100)], lighthouse=lh)
    measured = finish_record(make_record(mobile={"scroll_width": 478, "screen_width": 390}, **base))
    verified = finish_record(make_record(
        mobile={"scroll_width": 478, "screen_width": 390, "overflow_px_verified": 4}, **base))
    higher = finish_record(make_record(
        mobile={"scroll_width": 394, "screen_width": 390, "overflow_px_verified": 50}, **base))
    assert measured["mobile"]["overflow_px"] == 88
    assert verified["mobile"]["overflow_px"] == 4
    assert verified["scores"]["mobile"] == 58
    assert higher["mobile"]["overflow_px"] == 4  # nunca sube por una re-verificación
