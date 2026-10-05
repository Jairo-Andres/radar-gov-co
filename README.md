# Radar .gov.co

[Español](#español) · [English](#english)

---

## Español

Auditoría semanal y automática de la calidad de 30 portales públicos colombianos: accesibilidad (WCAG 2.1 AA), versión móvil, rendimiento, buenas prácticas, SEO y recursos fallidos. Los resultados quedan en JSON por fecha para publicarlos como ranking en una web (fase 2, diseño "El radar").

### Nota global: componentes y pesos (metodología versión 2)

| Componente | Peso | Cómo se calcula |
|---|---|---|
| **Accesibilidad** | **35 %** | 50 % axe-core (WCAG 2.1 A y AA) + 50 % Lighthouse accesibilidad (promedio de móvil y escritorio) |
| **Móvil** | 20 % | Rendimiento móvil de Lighthouse (mediana de 3) **menos** 0,5 puntos por cada píxel de desborde horizontal a 390 px (tope de 50) |
| **Rendimiento** | 15 % | Rendimiento de Lighthouse en escritorio (mediana de 3) |
| **Buenas prácticas** | 10 % | Lighthouse, promedio de las medianas de móvil y escritorio |
| **SEO** | 10 % | Lighthouse, promedio de las medianas de móvil y escritorio |
| **Recursos fallidos** | 10 % | 100 menos 10 por cada recurso propio que falla al cargar las páginas visitadas |

- La accesibilidad pesa más que cualquier otro componente: es el foco del proyecto.
- El rendimiento móvil se usa solo en "Móvil" y el de escritorio solo en "Rendimiento", para no contar dos veces la misma medición.
- Cada componente va de 0 a 100. La nota global es el promedio ponderado de los componentes disponibles; si falta más de la mitad del peso (por ejemplo, el sitio no cargó), no se asigna nota.
- **Semáforo:** verde ≥ 80, amarillo 50–79, rojo < 50.
- **Ranking:** de mayor a menor nota; los empates comparten puesto (1, 2, 2, 4).

Los pesos están en [`radar/scoring.py`](radar/scoring.py) y se publican en cada `summary.json`.

### Detalle de cada medición

**Accesibilidad (axe-core).** Se revisan las 3 páginas visitadas en escritorio y la página de inicio en móvil, con las reglas WCAG 2.1 A y AA. Cada página parte de 100 y resta una vez por cada regla incumplida según su impacto (crítico 10, grave 6, moderado 3, menor 1): 40 imágenes sin texto alternativo cuentan como una sola regla incumplida. Por sitio se publican dos números distintos:

- `wcag_rules`: reglas WCAG **distintas** incumplidas (una regla que falla en varias páginas cuenta una vez).
- `wcag_cases`: **total de casos** (elementos afectados). Si una página se revisó en escritorio y en móvil, por cada regla se toma la vista con más casos, sin sumar ambas.

Los hallazgos se redactan de forma objetiva: "No cumple el criterio WCAG 1.1.1 (regla image-alt)".

**Móvil.** Vista de 390 × 844 px. El desborde horizontal se mide como `scrollWidth − ancho de pantalla` y penaliza de forma gradual desde el primer píxel, sin tolerancia (6 px restan 3 puntos; una página sin `meta viewport`, que se dibuja a 980 px, resta el tope de 50). Si Lighthouse móvil no pudo medir, no hay nota móvil.

**Rendimiento y Lighthouse.** Lighthouse varía bastante entre ejecuciones, así que se corre **3 veces por vista** (móvil y escritorio) sobre la página de inicio y se publica la **mediana** de cada categoría y métrica (`performance_runs` guarda las 3 notas de rendimiento). Las auditorías fallidas que se listan vienen de la corrida mediana. Condiciones: en móvil, la limitación simulada por defecto de Lighthouse (red 4G lenta y CPU 4x); en escritorio, el preset `desktop`.

**Desde dónde se mide.** Los tiempos dependen de la red de origen, así que cada `summary.json` guarda `measurement.from`:

- Ejecución local: `--measured-from` o la variable `RADAR_MEASURED_FROM` (por defecto, "equipo local").
- GitHub Actions: "GitHub Actions (ubuntu-latest, centro de datos de GitHub; región no garantizada)".

Solo se comparan semanas medidas desde el mismo origen.

**Recursos fallidos.** Son los recursos (imágenes, scripts, hojas de estilo, fuentes, páginas) que responden con error (código ≥ 400) o no cargan por un error de red **mientras se cargan las 3 páginas visitadas**. No se recorren los demás enlaces del sitio, porque eso rompería el límite de 3 páginas: es una muestra, no un inventario de enlaces rotos.

**Regla de terceros.** Solo restan los recursos del propio dominio de la entidad y sus subdominios. Los que fallan en dominios de terceros (CDN externos, analítica, widgets) se cuentan en `third_party_failures` pero no bajan la nota, porque la entidad no siempre los controla. Las cancelaciones normales del navegador (`net::ERR_ABORTED`) no cuentan.

### Límites éticos y legales (Ley 1273 de 2009)

El Radar se comporta como un visitante normal:

- **Máximo 3 páginas distintas por sitio** (inicio + 2 internas), impuesto en el código aunque `sites.yaml` pida más.
- **Pausa de al menos 3 segundos antes de cada carga** (5 s por defecto, o el `Crawl-delay` de robots.txt si es mayor). Todo es secuencial: un sitio a la vez y una carga a la vez.
- **Una vez por semana.**
- **Respeta `robots.txt`.** Si robots.txt no permite la página de inicio, o no se puede leer (403, 5xx), el sitio se omite.
- **User-Agent identificable:** `RadarGovCo/1.0 (proyecto academico; linkedin.com/in/jairo-andres31-analyst)`.
- **Nada de** pruebas de carga, escaneo de vulnerabilidades, inicios de sesión ni envío de formularios. Las páginas internas excluyen accesos, cuentas, búsquedas y URLs con parámetros.
- **Hallazgos de seguridad:** si algo aparece por casualidad (errores de certificado, HTTPS, cabeceras de seguridad de Lighthouse), no se publica: se guarda en `private/` (ignorado por git) para avisar a la entidad o a ColCERT.

Tráfico por sitio y semana: 1 lectura de robots.txt, 8 cargas de la página de inicio (escritorio y móvil con Playwright, y 3 de Lighthouse por cada vista) y 1 carga de cada una de las 2 páginas internas. Son 11 cargas en unos 3 minutos (medido en la prueba del 2026-10-04), siempre con pausa entre una y otra.

### Sitios auditados y excluidos

Los 30 sitios están en [`sites.yaml`](sites.yaml): Presidencia, el portal GOV.CO, 12 ministerios, 8 entidades nacionales (DIAN, Registraduría, DANE, DNP, ICBF, Policía, Migración Colombia y Supersalud), Procuraduría, Contraloría y 6 alcaldías (Bogotá, Medellín, Cali, Barranquilla, Cartagena y Bucaramanga). Se verificaron el 2026-10-04 con `python -m radar verify`: de 44 candidatos, 41 respondían y permitían la visita.

Excluidos en esa verificación:

| Sitio | Motivo |
|---|---|
| Ministerio TIC (mintic.gov.co) | robots.txt responde 403; si no se puede leer, se asume que no permite la visita |
| Ministerio de Igualdad (minigualdad.gov.co) | Dominio caído: no resuelve en DNS |
| Superintendencia de Industria y Comercio (sic.gov.co) | robots.txt no permite visitar la página de inicio |

Los otros 11 que respondieron quedaron como reserva, comentados en `sites.yaml`.

### Cómo ejecutarlo

Requisitos: Python 3.12, Node 20+ y Google Chrome (Lighthouse lo usa).

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows (en Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
npm ci
python -m playwright install chromium

python -m radar verify                                   # comprueba que los sitios respondan y robots.txt
python -m radar run --only dian,dane                     # audita algunos sitios
python -m radar run --measured-from "equipo local, Bogotá"   # audita los 30 (≈ 1,5 h por las pausas)
python -m radar history                                  # reconstruye data/history.json
python -m radar og                                       # regenera la imagen para compartir (web/og-image.png)
python -m pytest                                         # tests del auditor (sin llamar a sitios reales)
python -m pytest tests_web                               # tests de la web: Playwright + axe-core sobre un servidor local
python -m http.server 8000                               # ver la web en http://localhost:8000/web/
```

### Datos que produce

```
data/
├── latest.json                 # {"date": "...", "summary": "AAAA-MM-DD/summary.json"}
├── history.json                # evolución semana a semana por sitio (nota, puesto, semáforo, cambio)
└── AAAA-MM-DD/
    ├── summary.json            # ranking del día, pesos, condiciones de medición y una fila por sitio
    ├── sites/<id>.json         # detalle: páginas, reglas WCAG, Lighthouse (mediana y corridas), recursos fallidos
    └── screenshots/<id>-desktop.jpg, <id>-mobile.jpg
```

Correr `run` con `--only` el mismo día agrega sitios al resumen de esa fecha sin borrar los anteriores.

### Despliegue

- **Ejecución semanal:** [`.github/workflows/radar.yml`](.github/workflows/radar.yml) corre los tests, audita los lunes a las 6:00 a. m. (hora de Colombia) y guarda `data/` con un commit. También se puede lanzar a mano desde *Actions → Radar semanal → Run workflow*, opcionalmente con IDs. Tiene un límite de 330 minutos.
- **CI:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) corre en cada push los tests del auditor y los de la web, incluido un análisis de axe-core sobre la propia web (debe dar 0 incumplimientos WCAG).

### Web del ranking ("El radar")

Página estática en [`web/`](web/) (HTML, CSS y JavaScript, sin frameworks) que lee `data/latest.json`, el `summary.json` de esa fecha, `history.json` y la ficha de cada sitio:

- **Radar animado:** cada punto es un portal. La distancia al centro depende de la nota (cada anillo son 10 puntos y el borde es 50 o menos) y el sector, del tipo de entidad. Con `prefers-reduced-motion` se apaga la animación.
- **Hallazgos de la semana** calculados en `summary.json` (`findings`): cuántos portales incumplen al menos una regla WCAG, las reglas más comunes contadas por sitio, desborde en móvil, medianas y nota por tipo de entidad.
- **Por qué importa:** la [Resolución 1519 de 2020 de MinTIC](https://www.cancilleria.gov.co/sites/default/files/Normograma/docs/resolucion_mintic_1519_2020.htm) (art. 3) exige WCAG 2.1 AA a los sujetos obligados desde el 1 de enero de 2022.
- **Tabla de posiciones** con filtro por tipo de entidad. En móvil muestra solo puesto, portal, nota y reglas WCAG.
- **Español e inglés:** botón ES/EN, enlace directo con `?lang=en`, y por defecto el idioma del navegador. Los textos están en `web/i18n.js`.
- **Vista previa al compartir:** `og-image.png` (1200×630) se genera con `python -m radar og` a partir de `web/og.html` y el workflow semanal la regenera con los datos nuevos.
- **Ficha por sitio** con capturas, componentes de la nota, reglas WCAG explicadas en lenguaje claro, LCP, desborde móvil y evolución semanal. Se puede enlazar directamente con `#id`, por ejemplo `#dian`.
- **Identidad visual común "Rutas + Cota":** el Radar es la **línea Q** (QA). `web/tokens.css`, `web/components.css`, el monograma y los favicons son copias sin modificar de `identidad-visual/fase-2` (v1.0). `web/brand.css` solo traduce esos tokens al radar. Los estados siempre llevan forma, texto y color: bueno ≥ 80 (círculo), regular 50–79 (triángulo) y malo < 50 (cuadrado). La página fuerza el tema oscuro (`data-theme="dark"`), porque el concepto es una pantalla de radar.
- Si se actualiza la identidad, hay que volver a copiar esos archivos; no se editan aquí.

**Despliegue en Vercel (plan Hobby):**

1. En Vercel: *Add New → Project → Import* el repo `radar-gov-co`.
2. Deja *Root Directory* en la raíz. [`vercel.json`](vercel.json) ya define el build: copia `web/` y `data/` a `dist/`, sin instalar dependencias.
3. *Deploy*. Desde ahí, cada push a `main` (incluidos los commits semanales del workflow con datos nuevos) publica una versión nueva sola.

Si la web muestra "No se pudieron cargar los resultados", revisa que `data/latest.json` exista en el último deploy y que el build haya copiado `data/` (pestaña *Build Logs* en Vercel).

### Qué revisar si algo se cae

| Síntoma | Qué revisar |
|---|---|
| El workflow no corrió | GitHub desactiva los cron tras 60 días sin actividad en el repo: reactívalo en *Actions*. |
| El workflow se cortó por tiempo | Revisa si algún sitio tiene un `Crawl-delay` alto en robots.txt; divide la corrida con `--only`. |
| Muchos sitios con `sin_respuesta` desde GitHub Actions | Algunos dominios .gov.co bloquean IP de centros de datos. Ejecuta `python -m radar run` en local y sube `data/` con un commit. |
| `Lighthouse (...): N de 3 corridas no pudieron analizar la página` | Que Chrome esté instalado (se puede forzar otro con `RADAR_CHROME_PATH`). Si las 3 fallan, esa vista queda sin dato. |
| Un sitio aparece `omitido_robots` | Su robots.txt cambió o no se puede leer; se respeta, no se fuerza. |
| Un sitio cambió de dominio | Corre `python -m radar verify` y actualiza `sites.yaml`. |
| El repo crece mucho | Las capturas son JPEG (~50–150 KB c/u, 60 por semana). Si molesta, se pueden mover a un almacenamiento aparte. |

### Limitaciones

- "Recursos fallidos" solo cubre las 3 páginas visitadas por sitio.
- axe-core detecta automáticamente una parte de los problemas de accesibilidad; no sustituye una revisión manual.
- Aun con la mediana de 3 corridas, el rendimiento depende de la red de origen y de la carga del servidor ese día; la tendencia semanal es más confiable que un dato aislado.
- Los títulos de las auditorías de Lighthouse se guardan en español (`--locale=es`); los textos de ayuda de axe-core quedan en inglés en `help_en`.

---

## English

Weekly, automated quality audit of 30 Colombian government websites: accessibility (WCAG 2.1 AA), mobile, performance, best practices, SEO and failed resources. Results are stored as dated JSON to be published as a ranking website (phase 2, "The radar" design).

### Overall score: components and weights (methodology version 2)

| Component | Weight | How it is computed |
|---|---|---|
| **Accessibility** | **35%** | 50% axe-core (WCAG 2.1 A and AA) + 50% Lighthouse accessibility (mobile/desktop average) |
| **Mobile** | 20% | Lighthouse mobile performance (median of 3) **minus** 0.5 points per pixel of horizontal overflow at 390 px (capped at 50) |
| **Performance** | 15% | Lighthouse desktop performance (median of 3) |
| **Best practices** | 10% | Lighthouse, average of the mobile and desktop medians |
| **SEO** | 10% | Lighthouse, average of the mobile and desktop medians |
| **Failed resources** | 10% | 100 minus 10 per first-party resource that fails while loading the visited pages |

Accessibility carries the most weight. Mobile performance only feeds "Mobile" and desktop performance only feeds "Performance", so the same measurement is never counted twice. The overall score is the weighted average of the available components (none if more than half of the weight is missing). Traffic light: green ≥ 80, yellow 50–79, red < 50. Ties share a position.

### Measurement details

- **axe-core:** each page starts at 100 and loses points once per failed rule by impact (critical 10, serious 6, moderate 3, minor 1). Each site reports `wcag_rules` (distinct WCAG rules failed) and, separately, `wcag_cases` (total affected elements, taking the larger of the desktop and mobile views of the same page instead of adding both).
- **Mobile:** 390 × 844 px viewport. Overflow is `scrollWidth − screen width`, penalized gradually from the first pixel with no tolerance.
- **Lighthouse:** 3 runs per view (mobile and desktop) on the homepage; the median of each category and metric is published, and the listed failed audits come from the median run. Mobile uses Lighthouse's default simulated throttling (slow 4G, 4x CPU); desktop uses the `desktop` preset.
- **Where it is measured from:** stored in `measurement.from` in every `summary.json` (`--measured-from` or `RADAR_MEASURED_FROM` locally; the GitHub Actions data center in CI). Only weeks measured from the same origin should be compared.
- **Failed resources:** resources that return an error (≥ 400) or fail with a network error **while loading the 3 visited pages only**. It is a sample, not a full broken-link crawl.
- **Third-party rule:** only resources on the entity's own domain and subdomains are penalized. Failures on third-party domains (external CDNs, analytics, widgets) are recorded in `third_party_failures` but do not lower the score.

### Ethical and legal limits (Colombian Law 1273 of 2009)

The Radar behaves like a regular visitor:

- At most 3 distinct pages per site, enforced in code.
- A pause of at least 3 seconds before every load, with everything run sequentially.
- One run per week.
- `robots.txt` is respected: a site is skipped when robots.txt disallows the homepage or cannot be read.
- An identifiable User-Agent.
- No load testing, vulnerability scanning, logins or form submissions.
- Security-related findings found by chance are never published: they go to the git-ignored `private/` folder.

Per site and week, that adds up to 11 page loads in about 3 minutes.

### Audited and excluded sites

The 30 sites are listed in `sites.yaml`. They were verified on 2026-10-04, when 41 of 44 candidates responded and allowed the visit. Three were excluded:

- **MinTIC:** robots.txt returns 403.
- **MinIgualdad:** the domain is down and does not resolve in DNS.
- **SIC:** robots.txt disallows the homepage.

### How to run it

Requirements: Python 3.12, Node 20+ and Google Chrome. See the commands in the Spanish section above: `verify`, `run [--only ids] [--measured-from ...]`, `history` and `pytest`.

### Deployment

- **Weekly run:** the GitHub Actions workflow runs the tests, audits every Monday at 6:00 a.m. Colombia time and commits `data/`. It can also be triggered manually.
- **CI:** `ci.yml` runs the auditor tests and the website tests (Playwright plus an axe-core scan of the website itself, which must report 0 WCAG violations) on every push.

### Ranking website ("The radar")

A static page in `web/` (plain HTML, CSS and JavaScript) reads `data/latest.json`, that day's `summary.json`, `history.json` and each site's detail file. It has three parts:

- **Animated radar:** distance to the center depends on the score and the sector on the type of entity. The animation is disabled with `prefers-reduced-motion`.
- **Leaderboard:** with a filter by type of entity.
- **Site sheet:** screenshots, score components, WCAG rules in plain language, LCP, mobile overflow and weekly trend. It can be deep-linked with `#id`.
- **Findings and "why it matters":** weekly headline numbers computed in `summary.json`, plus the legal basis (MinTIC Resolution 1519 of 2020 requires WCAG 2.1 AA since January 1, 2022).
- **Spanish and English:** ES/EN toggle, `?lang=en` links and browser-language default.
- **Share preview:** `og-image.png` is generated by `python -m radar og` and refreshed by the weekly workflow.
- **Shared "Rutas + Cota" identity:** the Radar is **line Q**. `tokens.css`, `components.css`, the monogram and the favicons are unmodified copies of the shared design system. Statuses always combine shape, text and color: good is a circle, fair a triangle and poor a square.

**Deploying to Vercel (Hobby plan):** import the repository, keep the root directory and deploy. `vercel.json` copies `web/` and `data/` into `dist/` without installing dependencies, so every push to `main`, including the weekly data commits, publishes a new version.

### Troubleshooting

- **The workflow didn't run:** GitHub disables scheduled workflows after 60 days without repository activity.
- **Many `sin_respuesta` (no response) sites in CI:** some .gov.co domains block data-center IPs. Run it locally and commit `data/`.
- **Lighthouse failures:** check that Chrome is installed, or set `RADAR_CHROME_PATH`.
- **`omitido_robots`:** robots.txt disallows the visit; it is respected, never bypassed.

---

Autor: Jairo Andrés Sierra · [LinkedIn](https://www.linkedin.com/in/jairo-andres31-analyst)
