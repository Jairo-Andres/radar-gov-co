"""CLI del Radar .gov.co.

    python -m radar verify                 # comprueba que los sitios respondan
    python -m radar run --only dian,dane   # audita y guarda data/AAAA-MM-DD/
    python -m radar history                # reconstruye data/history.json
    python -m radar og                     # regenera la imagen para compartir (web/og-image.png)
    python -m radar recheck --only dnp --date 2026-10-04   # re-verifica una anomalía en móvil
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .config import ORIGIN_PATTERN, load_config


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # consola de Windows
    parser = argparse.ArgumentParser(prog="radar")
    parser.add_argument("--sites", default="sites.yaml")
    parser.add_argument("--data", default="data")
    parser.add_argument(
        "--origin",
        default=os.environ.get("RADAR_ORIGIN", "local-co"),
        help="Serie de medición (desde dónde se mide), p. ej. local-co o github-actions. También: RADAR_ORIGIN",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    run = sub.add_parser("run")
    run.add_argument("--only", help="IDs separados por coma")
    run.add_argument("--limit", type=int, help="Auditar solo los primeros N sitios")
    run.add_argument("--date", help="Fecha de la carpeta de salida (AAAA-MM-DD)")
    run.add_argument(
        "--measured-from",
        default=os.environ.get("RADAR_MEASURED_FROM", "equipo local"),
        help="Desde dónde se mide (se publica en summary.json). También: variable RADAR_MEASURED_FROM",
    )
    sub.add_parser("history")
    sub.add_parser("og", help="Regenera web/og-image.png con la última medición")
    recheck = sub.add_parser("recheck", help="Vuelve a verificar el inicio en móvil de algunos sitios")
    recheck.add_argument("--only", required=True, help="IDs separados por coma")
    recheck.add_argument("--date", required=True, help="Medición a la que se agrega la verificación (AAAA-MM-DD)")
    args = parser.parse_args(argv)

    settings, sites = load_config(args.sites)
    if not ORIGIN_PATTERN.match(args.origin):
        parser.error(f"--origin no válido: {args.origin} (minúsculas, números y guiones)")
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

        run_audit(settings, sites, Path(args.data), args.date, args.measured_from, args.origin)
        return 0
    if args.command == "recheck":
        from .evidence import recheck_sites

        for row in recheck_sites(settings, sites, Path(args.data) / args.origin / args.date):
            overflow = row.get("overflow", {})
            print(f"{row['id']}: desborde {overflow.get('overflow_px')} px, "
                  f"recursos propios con error: {len(row.get('failed_resources', []))} {row.get('error', '')}")
        return 0
    if args.command == "og":
        from .og import render_og_image

        print(f"Imagen generada: {render_og_image()}")
        return 0
    if args.command == "history":
        from .history import write_history

        history = write_history(Path(args.data), settings.official_origin)
        print(json.dumps({k: len(v["runs"]) for k, v in history["origins"].items()}, ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
