"""Construye data/history.json (evolución semana a semana) y data/latest.json.

Las mediciones se guardan separadas por ubicación de origen (data/<origen>/<fecha>/),
porque el rendimiento depende de desde dónde se mide: una serie solo se compara
consigo misma. latest.json apunta a la última medición de la serie oficial.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ORIGIN_DIR = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def build_history(summaries: list[dict], origin: str | None = None) -> dict:
    """Historia de UNA serie (un mismo origen de medición)."""
    summaries = sorted(summaries, key=lambda s: s["date"])
    sites: dict[str, dict] = {}
    runs = []
    for summary in summaries:
        prefix = f"{origin}/" if origin else ""
        runs.append(
            {
                "date": summary["date"],
                "summary": f"{prefix}{summary['date']}/summary.json",
                "sites_audited": summary.get("sites_audited"),
                "average_overall": summary.get("average_overall"),
                "lights": summary.get("lights"),
            }
        )
        for row in summary.get("sites", []):
            entry = sites.setdefault(row["id"], {"name": row["name"], "category": row["category"], "url": row["url"], "series": []})
            entry.update(name=row["name"], category=row["category"], url=row["url"])
            entry["series"].append({"date": summary["date"], "overall": row.get("overall"), "rank": row.get("rank"), "light": row.get("light")})
    for entry in sites.values():
        series = [p for p in entry["series"] if p["overall"] is not None]
        entry["change"] = series[-1]["overall"] - series[-2]["overall"] if len(series) >= 2 else None
    return {"runs": runs, "sites": sites}


def pick_latest(origins: dict[str, dict], official: str) -> tuple[str, dict] | None:
    """Última medición de la serie oficial; si aún no tiene ninguna, la más reciente de cualquier serie."""
    if origins.get(official, {}).get("runs"):
        return official, origins[official]["runs"][-1]
    candidates = [(name, data["runs"][-1]) for name, data in origins.items() if data["runs"]]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[1]["date"])


def read_series(data_dir: Path) -> dict[str, list[dict]]:
    series: dict[str, list[dict]] = {}
    for origin_dir in sorted(data_dir.iterdir()) if data_dir.exists() else []:
        if not origin_dir.is_dir() or not ORIGIN_DIR.match(origin_dir.name) or DATE_DIR.match(origin_dir.name):
            continue
        for day in sorted(origin_dir.iterdir()):
            path = day / "summary.json"
            if day.is_dir() and DATE_DIR.match(day.name) and path.exists():
                series.setdefault(origin_dir.name, []).append(json.loads(path.read_text(encoding="utf-8")))
    return series


def write_history(data_dir: Path, official_origin: str = "github-actions") -> dict:
    origins = {
        name: {**build_history(summaries, name), "measured_from": summaries[-1].get("measurement", {}).get("from")}
        for name, summaries in read_series(data_dir).items()
    }
    history = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "official_origin": official_origin,
        "origins": origins,
    }
    (data_dir / "history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest = pick_latest(origins, official_origin)
    if latest:
        origin, run = latest
        (data_dir / "latest.json").write_text(
            json.dumps(
                {"origin": origin, "official": origin == official_origin, "date": run["date"], "summary": run["summary"]},
                ensure_ascii=False, indent=2,
            ) + "\n",
            encoding="utf-8",
        )
    return history
