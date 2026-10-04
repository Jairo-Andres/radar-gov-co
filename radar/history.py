"""Construye data/history.json (evolución semana a semana) y data/latest.json."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def build_history(summaries: list[dict]) -> dict:
    summaries = sorted(summaries, key=lambda s: s["date"])
    sites: dict[str, dict] = {}
    runs = []
    for summary in summaries:
        runs.append(
            {
                "date": summary["date"],
                "summary": f"{summary['date']}/summary.json",
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


def write_history(data_dir: Path) -> dict:
    summaries = []
    for day in sorted(data_dir.iterdir()) if data_dir.exists() else []:
        path = day / "summary.json"
        if day.is_dir() and DATE_DIR.match(day.name) and path.exists():
            summaries.append(json.loads(path.read_text(encoding="utf-8")))
    history = build_history(summaries)
    history["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (data_dir / "history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if history["runs"]:
        latest = history["runs"][-1]
        (data_dir / "latest.json").write_text(
            json.dumps({"date": latest["date"], "summary": latest["summary"]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return history
