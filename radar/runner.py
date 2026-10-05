"""Orquesta una corrida: audita los sitios en serie y escribe data/AAAA-MM-DD/."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import scoring
from .auditor import SecurityLog, audit_site
from .config import LIGHTHOUSE_RUNS, MAX_PAGES_PER_SITE, USER_AGENT, Settings, Site
from .history import write_history

COLOMBIA = timezone(timedelta(hours=-5))  # Colombia no tiene horario de verano
PRIVATE_DIR = Path("private")


def today() -> str:
    return datetime.now(COLOMBIA).date().isoformat()


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_summary(records: list[dict], date: str, measured_from: str | None = None) -> dict:
    """Resumen del día que consume la web: una fila por sitio con sus puntuaciones."""
    rows = []
    for r in records:
        rows.append(
            {
                "id": r["id"],
                "name": r["name"],
                "category": r["category"],
                "url": r["url"],
                "status": r["status"],
                "overall": r.get("scores", {}).get("overall"),
                "light": r.get("light", "sin_dato"),
                "scores": r.get("scores", {}),
                "wcag_rules": (r.get("wcag") or {}).get("rules_count"),
                "wcag_cases": (r.get("wcag") or {}).get("cases"),
                "failed_resources_first_party": r.get("failed_resources_first_party"),
                "screenshots": [p["screenshot"] for p in r.get("pages", []) if p.get("screenshot")],
                "detail": f"sites/{r['id']}.json",
            }
        )
    ranked = scoring.rank(rows)
    overalls = [r["overall"] for r in ranked if r["overall"] is not None]
    return {
        "date": date,
        "methodology_version": scoring.METHODOLOGY_VERSION,
        "weights": scoring.WEIGHTS,
        "user_agent": USER_AGENT,
        "measurement": measurement_info(records, measured_from),
        "sites_audited": len(ranked),
        "average_overall": round(sum(overalls) / len(overalls)) if overalls else None,
        "lights": {k: sum(1 for r in ranked if r["light"] == k) for k in ("verde", "amarillo", "rojo", "sin_dato")},
        "sites": ranked,
    }


def measurement_info(records: list[dict], measured_from: str | None) -> dict:
    versions = sorted({
        lh["lighthouse_version"]
        for r in records for lh in (r.get("lighthouse") or {}).values()
        if lh and lh.get("lighthouse_version")
    })
    return {
        "from": measured_from or "sin dato",
        "lighthouse_versions": versions,
        "lighthouse_runs_per_view": LIGHTHOUSE_RUNS,
        "lighthouse_aggregate": "mediana",
        "lighthouse_conditions": "móvil: limitación simulada por defecto de Lighthouse (red 4G lenta y CPU 4x); "
                                 "escritorio: preset desktop de Lighthouse",
        "max_pages_per_site": MAX_PAGES_PER_SITE,
    }


def load_day_records(day_dir: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((day_dir / "sites").glob("*.json"))]


def run_audit(
    settings: Settings, sites: list[Site], data_dir: Path, date: str | None = None, measured_from: str | None = None
) -> dict:
    date = date or today()
    day_dir = data_dir / date
    screenshots = day_dir / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    security = SecurityLog()
    notes_path = PRIVATE_DIR / f"security-notes-{date}.json"
    # Las notas de otros sitios del mismo día (corridas parciales con --only) se conservan.
    audited_ids = {s.id for s in sites}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for index, site in enumerate(sites, start=1):
            print(f"[{index}/{len(sites)}] {site.name}", flush=True)
            try:
                record = audit_site(browser, site, settings, screenshots, security)
            except Exception as error:  # un sitio nunca tumba la corrida completa
                record = {"id": site.id, "name": site.name, "category": site.category, "url": site.url,
                          "status": "error", "pages": [], "errors": [f"error inesperado: {type(error).__name__}"],
                          "scores": {}, "light": "sin_dato"}
            write_json(day_dir / "sites" / f"{site.id}.json", record)
            # Se guarda tras cada sitio para no perder avisos si la corrida se corta.
            # Se relee el archivo antes de escribir para no pisar otra corrida del mismo día.
            others = [n for n in _read_notes(notes_path) if n.get("site") not in audited_ids]
            if others or security.items:
                write_json(notes_path, others + security.items)
            print(f"  -> {record.get('scores', {}).get('overall')} ({record['status']})", flush=True)
        browser.close()

    # El resumen incluye todos los sitios de ese día (permite corridas parciales con --only).
    summary = build_summary(load_day_records(day_dir), date, measured_from)
    write_json(day_dir / "summary.json", summary)
    write_history(data_dir)

    if security.items:
        print(f"\nAVISO: {len(security.items)} posibles hallazgos de seguridad guardados en "
              f"private/security-notes-{date}.json (no se publican).")
    return summary


def _read_notes(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
