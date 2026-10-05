# Verificación de anomalías · 2026-10-05

Revisión de la medición del 2026-10-04 (serie `local-co`) antes de publicarla. La evidencia queda en cada ficha (`data/local-co/2026-10-04/sites/<id>.json`, campos `rechecks` y `mobile.evidence`) y en `data/local-co/2026-10-04/screenshots/`.

La re-verificación cargó solo la página de inicio en móvil (390 px), con una visita por sitio y pausa previa, y con el mismo User-Agent del Radar (`python -m radar recheck`). DNP y GOV.CO tuvieron un segundo intento porque el primero no cargó.

## 1. Nota móvil de Presidencia, DNP y GOV.CO

| Sitio | Medición del 04/10 | Re-verificación del 05/10 | Conclusión |
|---|---|---|---|
| Presidencia | 980 px de ancho (590 px de desborde) | Igual: no tiene `meta viewport`; el navegador dibuja la página a 980 px y la reduce al 40 % (`visualViewport.scale` = 0,40) | **Real.** Se mantiene la penalización máxima (50). La evidencia es la vista móvil reducida. |
| DNP | 478 px (88 px) | 394 px (4 px). La página no terminó de cargar en 15 s y se midió con el DOM disponible. | **No se reproduce igual.** Hay desborde, pero el tamaño depende de lo que alcanza a cargar. Se usa el valor confirmado más bajo: 4 px. |
| GOV.CO | 421 px (31 px) | 390 px (0 px). El CDN `cdn.www.gov.co` reinició la conexión en 2 scripts y el navegador bloqueó 1 hoja de estilos (ORB). | **No se confirma.** Se usa 0 px. |

Hubo además un error del auditor: los portales sin `meta viewport` dan una captura completa en blanco. Desde ahora, en ese caso la evidencia es la vista reducida tal como la ve el usuario.

Mejoras para las próximas mediciones:

- El desborde se lee dos veces, con 3 s de diferencia, y cuenta la menor lectura.
- Se guardan la captura de evidencia y los elementos que ensanchan la página. Los que están dentro de un contenedor que recorta no cuentan.

## 2. Recursos fallidos

| Sitio | Qué falla | Conclusión |
|---|---|---|
| MinSalud (0) | 11 respuestas 404 del propio sitio: una fuente, 4 llamadas a la API de SharePoint de años anteriores y hojas de estilo de componentes que ya no existen | **Real.** |
| ICBF (40) | 6 respuestas 404: scripts y estilos con la ruta literal `-module-directory-` (una variable sin reemplazar en la plantilla) y un ícono | **Real.** |
| MinAgricultura (40) | 6 respuestas 404 de fuentes tipográficas (govco, Work Sans) | **Real.** |
| GOV.CO (40) | 4 conexiones reiniciadas en `cdn.www.gov.co`, 1 bloqueo ORB y 1 fallo en `robi.and.gov.co` | **Error nuestro:** se contaba otra entidad (`and.gov.co`) como propia de `www.gov.co`, y los errores de red se penalizaban. Ahora da 100. |

Corrección general de la metodología: solo restan los errores HTTP (404, 500…). Los posibles bloqueos (401, 403, 429) y los errores de red se publican en `failed_resources_unverified`, pero no restan. Además del caso de GOV.CO, esto cambió 5 sitios con 403 o errores de red:

- Cartagena y Barranquilla: 403.
- MinAmbiente: un subdominio que no resuelve.
- Procuraduría: 403.
- MinJusticia: una conexión reiniciada.

## 3. Antes y después (medición del 2026-10-04)

| Sitio | Móvil | Rec. fallidos | Nota | Puesto |
|---|---|---|---|---|
| Presidencia de la República | 0 → 0 | 90 → 90 | 66 → 66 | 17 → 19 |
| Departamento Nacional de Planeación | 0 → 28 | 100 → 100 | 64 → 70 | 20 → 13 |
| Portal Único del Estado (GOV.CO) | 14 → 29 | 40 → 100 | 63 → 72 | 25 → 10 |
| Ministerio de Salud | 37 → 37 | 0 → 0 | 61 → 61 | 27 → 27 |
| ICBF | 49 → 49 | 40 → 40 | 64 → 64 | 20 → 23 |
| Ministerio de Agricultura | 59 → 59 | 40 → 40 | 74 → 74 | 8 → 9 |
| Alcaldía de Cartagena | 51 → 51 | 70 → 100 | 75 → 78 | 7 → 5 |
| Alcaldía de Barranquilla | 55 → 55 | 80 → 100 | 73 → 75 | 9 → 8 |
| Ministerio de Ambiente | 48 → 48 | 90 → 100 | 65 → 66 | 18 → 19 |
| Procuraduría | 54 → 54 | 90 → 100 | 65 → 66 | 18 → 19 |
| Ministerio de Justicia | 30 → 30 | 60 → 70 | 64 → 65 | 20 → 22 |

Los puestos de Presidencia, ICBF y MinAgricultura bajan solo porque otros sitios suben. El promedio general pasa de 69 a 70, y siguen 4 sitios con nota buena y ninguno con nota mala.

## 4. Desde dónde se mide

La medición del 2026-10-04 se hizo desde un PC en Colombia; el cron semanal corre en GitHub Actions, en un centro de datos que normalmente está en EE. UU. Cada ubicación queda como una serie aparte (`data/local-co/`, `data/github-actions/`) y nunca se mezclan. La serie oficial es `github-actions` (`sites.yaml`). Mientras no tenga mediciones, la web muestra la serie local y lo avisa. La explicación completa está en el README, en «Desde dónde se mide».
