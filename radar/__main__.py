"""CLI del Radar .gov.co.

    python -m radar verify                 # comprueba que los sitios respondan
    python -m radar run --only dian,dane   # audita y guarda data/AAAA-MM-DD/
    python -m radar history                # reconstruye data/history.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # consola de Windows
    parser = argparse.ArgumentParser(prog="radar")
    parser.add_argument("--sites", default="sites.yaml")
    parser.add_argument("--data", default="data")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    run = sub.add_parser("run")
    run.add_argument("--only", help="IDs separados por coma")
    run.add_argument("--limit", type=int, help="Auditar solo los primeros N sitios")
    run.add_argument("--date", help="Fecha de la carpeta de salida (AAAA-MM-DD)")
    sub.add_parser("history")
    args = parser.parse_args(argv)

    settings, sites = load_config(args.sites)
    if getattr(args, "only", None):
        wanted = [s.strip() for s in args.only.split(",") if s.strip()]
        unknown = set(wanted) - {s.id for s in sites}
        if unknown:
            parser.error(f"IDs desconocidos: {sorted(unknown)}")
        sites = [s for s in sites if s.id in wanted]
    if getattr(args, "limit", None):
        sites = sites[: args.limit]

    if args.command == "verify":
        from .verify import verify_sites

        results = verify_sites(settings, sites)
        ok = sum(1 for r in results if r["allowed"] and r.get("status") and 200 <= r["status"] < 400)
        print(f"\n{ok}/{len(results)} sitios responden y permiten la visita")
        return 0
    if args.command == "run":
        from .runner import run_audit

        run_audit(settings, sites, Path(args.data), args.date)
        return 0
    if args.command == "history":
        from .history import write_history

        history = write_history(Path(args.data))
        print(json.dumps({"runs": len(history["runs"])}, ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
