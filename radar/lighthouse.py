"""Ejecuta Lighthouse (CLI de Node) sobre la página de inicio."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from .config import USER_AGENT

ROOT = Path(__file__).resolve().parent.parent
LIGHTHOUSE_CLI = ROOT / "node_modules" / "lighthouse" / "cli" / "index.js"
TIMEOUT_SECONDS = 180


def run_lighthouse(url: str, form_factor: str, chrome_path: str | None = None) -> dict:
    """Devuelve el LHR (JSON de Lighthouse). Lanza RuntimeError si falla."""
    if not LIGHTHOUSE_CLI.exists():
        raise RuntimeError("Lighthouse no está instalado: ejecuta `npm ci`")
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "report.json"
        command = [
            "node",
            str(LIGHTHOUSE_CLI),
            url,
            "--output=json",
            f"--output-path={output}",
            "--quiet",
            "--only-categories=performance,accessibility,best-practices,seo",
            f"--emulated-user-agent={USER_AGENT}",
            "--max-wait-for-load=45000",
            "--locale=es",
            "--chrome-flags=--headless=new --no-first-run --disable-extensions",
        ]
        if form_factor == "desktop":
            command.append("--preset=desktop")
        # Usa el Chrome instalado en el equipo (chrome-launcher lo encuentra solo).
        # RADAR_CHROME_PATH permite forzar otro navegador si hace falta.
        env = dict(os.environ)
        chrome_path = chrome_path or os.environ.get("RADAR_CHROME_PATH")
        if chrome_path:
            env["CHROME_PATH"] = chrome_path
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=TIMEOUT_SECONDS, env=env,
        )
        if not output.exists():
            lines = (completed.stderr or completed.stdout or "").strip().splitlines()
            errors = [line for line in lines if "error" in line.lower()] or lines[-1:] or ["sin salida"]
            raise RuntimeError(f"Lighthouse {form_factor} falló: {errors[0].strip()[:200]}")
        return json.loads(output.read_text(encoding="utf-8"))
