# Stay Vertical

Proyecto para el NASA Space Apps Challenge 2026: *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*.
Elige un sitio de la Luna o de Marte y mira qué zonas de la Tierra se le parecen en relieve, con su clima y viabilidad.

Web: https://stay-vertical.wiki

## Qué muestra la web

- **18 sitios de referencia:** 8 del polo sur lunar (LOLA, 80 m) y 10 de Marte (mezcla HRSC/MOLA de USGS, 200 m).
- **50 zonas terrestres** candidatas (Copernicus DEM GLO-30), ordenadas por parecido de relieve.
- **Clima y viabilidad** de cada zona (NASA POWER, 2021-2025) con un semáforo de umbrales provisionales.
- **Vertikal Bot:** una red neuronal pequeña que corre en el navegador y explica los resultados mostrados.
- Selector de idioma ES/EN.

Los resultados son exploratorios: comparan relieve dentro de un catálogo de 50 zonas, no validan geología. Los límites están en `AUDITORIA_RESULTADOS.md`.

## Estructura

| Carpeta | Qué contiene |
|---|---|
| `docs/` | Web estática (GitHub Pages desde `main`): `resultados.json`, `clima.json`, modelo del bot e imágenes de comparación |
| `stayvertical/` | Motor en Python: características de relieve, búsqueda grueso→fino, agrupación en regiones y algoritmo genético |
| `scripts/` | `construir_datos.py` y `construir_clima.py` generan los JSON de la web; `subir_version.py` renueva la caché; `auditoria/` reproduce la auditoría |
| `entrenamiento/` | Ejemplos y entrenamiento del clasificador de Vertikal Bot |
| `tests/` | Pruebas del motor (pytest) y del bot y el clima (Node) |
| `notebooks/`, `data/resultados/` | Corrida anterior del análisis (16 parches de referencia); ya no alimenta la web |
| `backend/` | API opcional en FastAPI, aún sin uso |

## Desarrollo local

Web:

```bash
python3 -m http.server 8000 --directory docs
```

Tras cambiar archivos de `docs/`:

```bash
python3 scripts/subir_version.py
```

Pruebas:

```bash
pip install -r requirements.txt pytest && python3 -m pytest tests/test_motor.py
```

```bash
node tests/test_bot.js && node tests/test_clima.js
```
