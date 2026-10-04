# Radar .gov.co

[Español](#español) · [English](#english)

---

## Español

Auditoría semanal y automática de la calidad de 30 portales públicos colombianos: accesibilidad (WCAG 2.1 AA), rendimiento, buenas prácticas, SEO, recursos rotos y versión móvil. Los resultados quedan en JSON por fecha para publicarlos como ranking en una web (fase 2, diseño "El radar").

### Qué mide

| Componente | Peso | Fuente |
|---|---|---|
| Accesibilidad | 30 % | 50 % axe-core (WCAG 2.1 A y AA, hasta 3 páginas, escritorio y móvil) + 50 % Lighthouse accesibilidad |
| Rendimiento | 25 % | Lighthouse: 60 % móvil + 40 % escritorio (mobile-first) |
| Buenas prácticas | 15 % | Lighthouse, promedio móvil y escritorio |
| SEO | 10 % | Lighthouse, promedio móvil y escritorio |
| Recursos rotos | 10 % | Recursos del propio sitio (imágenes, scripts, estilos, páginas) que responden con error al cargar las páginas visitadas |
| Versión móvil | 10 % | En 390 px: declara `meta viewport` adaptable (50) y no se desborda a lo ancho (50) |

### Metodología de puntuación (versión 1)

- Cada componente va de 0 a 100.
- **axe-core:** cada página parte de 100 y resta una vez por cada regla incumplida según su impacto: crítico 10, grave 6, moderado 3, menor 1. Se promedian las páginas.
- **Recursos rotos:** 100 menos 10 por cada recurso propio roto (sin repetir URL). Los recursos de terceros se registran pero no restan.
- **Nota global:** promedio ponderado de los componentes disponibles. Si falta más de la mitad del peso (por ejemplo, el sitio no cargó), no se asigna nota.
- **Semáforo:** verde ≥ 80, amarillo 50–79, rojo < 50.
- **Ranking:** de mayor a menor nota; los empates comparten puesto (1, 2, 2, 4).

El código está en [`radar/scoring.py`](radar/scoring.py) y los pesos se publican en cada `summary.json`.

### Límites éticos y legales (Ley 1273 de 2009)

El Radar se comporta como un visitante normal:

- **Máximo 3 páginas por sitio** (inicio + 2 internas), impuesto en el código aunque `sites.yaml` pida más.
- **Pausa de al menos 3 segundos** antes de cada carga (5 s por defecto, o el `Crawl-delay` de robots.txt si es mayor). Los sitios se auditan uno por uno.
- **Una vez por semana.**
- **Respeta `robots.txt`.** Si robots.txt no permite la página de inicio, o no se puede leer (403, 5xx), el sitio se omite.
- **User-Agent identificable:** `RadarGovCo/1.0 (proyecto academico; linkedin.com/in/jairo-andres31-analyst)`.
- **Nada de** pruebas de carga, escaneo de vulnerabilidades, inicios de sesión ni envío de formularios. Las páginas internas excluyen accesos, cuentas, búsquedas y URLs con parámetros.
- **Hallazgos de seguridad:** si algo aparece por casualidad (certificados, HTTPS, cabeceras de seguridad de Lighthouse), no se publica: se guarda en `private/` (ignorado por git) para avisar a la entidad o a ColCERT.
- **Redacción objetiva:** "No cumple el criterio WCAG 1.1.1 (regla image-alt)", sin juicios sobre las entidades.

Tráfico por sitio y semana: robots.txt, el inicio cargado 4 veces (escritorio y móvil con Playwright, móvil y escritorio con Lighthouse) y hasta 2 páginas internas.

### Cómo ejecutarlo

Requisitos: Python 3.12, Node 20+ y Google Chrome (Lighthouse lo usa).

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows (en Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
npm ci
python -m playwright install chromium

python -m radar verify                       # comprueba que los sitios respondan y robots.txt
python -m radar run --only dian,dane         # audita algunos sitios
python -m radar run                          # audita los 30 (≈ 1 a 1,5 h por las pausas)
python -m radar history                      # reconstruye data/history.json
python -m pytest                             # tests del auditor (sin llamar a sitios reales)
```

### Datos que produce

```
data/
├── latest.json                 # {"date": "...", "summary": "AAAA-MM-DD/summary.json"}
├── history.json                # evolución semana a semana por sitio (nota, puesto, semáforo, cambio)
└── AAAA-MM-DD/
    ├── summary.json            # ranking del día: una fila por sitio con sus puntuaciones
    ├── sites/<id>.json         # detalle: páginas, incumplimientos WCAG, Lighthouse, recursos rotos
    └── screenshots/<id>-desktop.jpg, <id>-mobile.jpg
```

Correr `run` con `--only` el mismo día agrega sitios al resumen de esa fecha sin borrar los anteriores.

### Despliegue

- **Ejecución semanal:** [`.github/workflows/radar.yml`](.github/workflows/radar.yml) corre los tests, audita los lunes a las 6:00 a. m. (hora de Colombia) y guarda `data/` con un commit. También se puede lanzar a mano desde *Actions → Radar semanal → Run workflow*, opcionalmente con IDs.
- **Web del ranking (fase 2):** se publicará en Vercel leyendo `data/latest.json`, `summary.json` e `history.json`.

### Qué revisar si algo se cae

| Síntoma | Qué revisar |
|---|---|
| El workflow no corrió | GitHub desactiva los cron tras 60 días sin actividad en el repo: reactívalo en *Actions*. |
| Muchos sitios con `sin_respuesta` desde GitHub Actions | Algunos dominios .gov.co bloquean IP de centros de datos. Ejecuta `python -m radar run` en local y sube `data/` con un commit. |
| `Lighthouse (...) falló` | Que Chrome esté instalado. Se puede forzar otro con la variable `RADAR_CHROME_PATH`. |
| Un sitio aparece `omitido_robots` | Su robots.txt cambió o no se puede leer; se respeta, no se fuerza. |
| Un sitio cambió de dominio | Corre `python -m radar verify` y actualiza `sites.yaml`. |
| El repo crece mucho | Las capturas son JPEG (~50–150 KB c/u, 60 por semana). Si molesta, se pueden mover a un almacenamiento aparte. |

### Limitaciones

- "Recursos rotos" no recorre todos los enlaces del sitio (eso rompería el límite de 3 páginas): mide lo que falla al cargar las páginas visitadas.
- axe-core detecta automáticamente una parte de los problemas de accesibilidad; no sustituye una revisión manual.
- Lighthouse varía entre ejecuciones (red, carga del servidor); la tendencia semanal es más confiable que un dato aislado.
- Los títulos de las auditorías de Lighthouse se guardan en español (`--locale=es`); los textos de axe-core quedan en inglés en `help_en`.

---

## English

Weekly, automated quality audit of 30 Colombian government websites: accessibility (WCAG 2.1 AA), performance, best practices, SEO, broken resources and mobile readiness. Results are stored as dated JSON to be published as a ranking website (phase 2, "The radar" design).

### What it measures

| Component | Weight | Source |
|---|---|---|
| Accessibility | 30% | 50% axe-core (WCAG 2.1 A and AA, up to 3 pages, desktop and mobile) + 50% Lighthouse accessibility |
| Performance | 25% | Lighthouse: 60% mobile + 40% desktop (mobile-first) |
| Best practices | 15% | Lighthouse, mobile/desktop average |
| SEO | 10% | Lighthouse, mobile/desktop average |
| Broken resources | 10% | The site's own resources (images, scripts, styles, pages) that fail while loading the visited pages |
| Mobile | 10% | At 390 px: responsive `meta viewport` (50) and no horizontal overflow (50) |

### Scoring methodology (version 1)

- Every component is 0–100.
- **axe-core:** each page starts at 100 and loses points once per failed rule by impact: critical 10, serious 6, moderate 3, minor 1. Pages are averaged.
- **Broken resources:** 100 minus 10 per broken first-party resource (unique URLs). Third-party resources are recorded but not penalized.
- **Overall:** weighted average of the available components; no overall score if more than half of the weight is missing.
- **Traffic light:** green ≥ 80, yellow 50–79, red < 50.
- **Ranking:** highest score first; ties share a position (1, 2, 2, 4).

### Ethical and legal limits (Colombian Law 1273 of 2009)

The Radar behaves like a regular visitor: at most 3 pages per site (enforced in code), a pause of at least 3 seconds before every page load, one run per week, `robots.txt` respected (sites are skipped when it disallows the homepage or cannot be read), and an identifiable User-Agent. No load testing, vulnerability scanning, logins or form submissions. Security-related findings found by chance are never published: they go to the git-ignored `private/` folder to be reported to the entity or ColCERT. Findings are written objectively ("Does not meet WCAG success criterion 1.1.1").

### How to run it

Requirements: Python 3.12, Node 20+ and Google Chrome (used by Lighthouse). See the commands in the Spanish section above: `verify`, `run [--only ids]`, `history` and `pytest`.

### Deployment

- **Weekly run:** the GitHub Actions workflow runs the tests, audits every Monday at 6:00 a.m. Colombia time and commits `data/`. It can also be triggered manually (*Run workflow*).
- **Ranking website (phase 2):** Vercel, reading `data/latest.json`, `summary.json` and `history.json`.

### Troubleshooting

- **Workflow didn't run:** GitHub disables scheduled workflows after 60 days without repository activity; re-enable it in *Actions*.
- **Many `sin_respuesta` (no response) sites in GitHub Actions:** some .gov.co domains block data-center IPs. Run it locally and commit `data/`.
- **`Lighthouse (...) falló`:** make sure Chrome is installed, or set `RADAR_CHROME_PATH`.
- **`omitido_robots`:** the site's robots.txt disallows the visit or can't be read; it is respected, never bypassed.

### Limitations

Broken-resource detection only covers the visited pages, automated accessibility testing finds only part of the issues, and Lighthouse scores vary between runs, so weekly trends are more reliable than a single value.

---

Autor: Jairo Andrés Sierra · [LinkedIn](https://www.linkedin.com/in/jairo-andres31-analyst)
