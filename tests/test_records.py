import json

from conftest import make_record
from radar import parsers
from radar.auditor import SecurityLog, finish_record, public_error
from radar.config import Site
from radar.history import build_history, write_history
from radar.runner import build_summary


def page(score, broken=(), viewport="desktop", screenshot=None):
    p = {
        "url": "u",
        "viewport": viewport,
        "axe": {"score": score, "violations": [{"rule": "r"}] if score < 100 else []},
        "broken": list(broken),
    }
    if screenshot:
        p["screenshot"] = screenshot
    return p


def test_finish_record_full(lhr_mobile):
    summary, _ = parsers.parse_lighthouse(lhr_mobile)
    broken = [
        {"url": "https://www.dane.gov.co/x.png", "first_party": True},
        {"url": "https://cdn.example.com/y.js", "first_party": False},
    ]
    record = make_record(
        pages=[page(84, broken), page(100)],
        mobile={"viewport_meta": True, "horizontal_overflow": False},
        lighthouse={"mobile": summary, "desktop": summary},
    )
    finish_record(record)
    assert record["broken_first_party"] == 1  # los recursos de terceros no restan
    assert record["scores"]["links"] == 90
    assert record["scores"]["mobile"] == 100
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


def records_for_summary():
    a = finish_record(make_record(
        "dane", pages=[page(100, screenshot="screenshots/dane-desktop.jpg")],
        mobile={"viewport_meta": True, "horizontal_overflow": False},
    ))
    b = finish_record(make_record("dian", pages=[page(60)], mobile={"viewport_meta": False, "horizontal_overflow": True}))
    c = finish_record(make_record("icbf"))
    return [c, b, a]


def test_build_summary_ranks_and_counts():
    summary = build_summary(records_for_summary(), "2026-10-05")
    assert [(s["id"], s["rank"]) for s in summary["sites"]] == [("dane", 1), ("dian", 2), ("icbf", None)]
    assert summary["sites_audited"] == 3
    assert summary["lights"]["sin_dato"] == 1
    assert summary["sites"][0]["screenshots"] == ["screenshots/dane-desktop.jpg"]
    assert summary["sites"][0]["detail"] == "sites/dane.json"
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


def test_write_history_reads_date_folders(tmp_path):
    for date in ("2026-10-05", "2026-10-12"):
        folder = tmp_path / date
        folder.mkdir()
        summary = build_summary(records_for_summary(), date)
        (folder / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (tmp_path / "notas").mkdir()  # las carpetas que no son fechas se ignoran
    history = write_history(tmp_path)
    assert len(history["runs"]) == 2
    latest = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert latest == {"date": "2026-10-12", "summary": "2026-10-12/summary.json"}
