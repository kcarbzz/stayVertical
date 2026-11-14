# Stay Vertical

Proyecto para el NASA Space Apps Challenge 2026: *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*.
Elige un terreno de la Luna o de Marte y mira qué parches de la Tierra se le parecen en relieve.

Web: https://stay-vertical.wiki

## Cómo funciona

1. El notebook descarga modelos de elevación: Copernicus DEM GLO-30 (Tierra), NASA LRO/LOLA (Luna) y ESA/DLR Mars Express HRSC (Marte), y los lleva a 80 m por píxel.
2. Corta cada terreno en parches de 3,04 km y resume cada uno en 8 descriptores de pendiente, curvatura y rugosidad.
3. Para cada parche lunar o marciano ordena los parches terrestres combinando la distancia entre descriptores y la correlación de forma (con rotaciones de 0, 90, 180 y 270°).
4. `scripts/exportar_web.py` convierte esos resultados en lo que muestra la web.

Los resultados son exploratorios: un ranking de relieve dentro de un catálogo pequeño, no una validación geológica. El detalle está en `notebooks/DOCUMENTO_TECNICO.md`.

## Estructura

| Carpeta | Qué contiene | Dónde corre |
|---|---|---|
| `docs/` | Web estática (Leaflet), `resultados.json` y miniaturas en `parches/` | GitHub Pages desde `main` / `docs` |
| `notebooks/` | Notebook del análisis y documento técnico | Google Colab |
| `data/resultados/` | Salida del notebook: CSV, recortes GeoTIFF, figuras | — |
| `scripts/` | `exportar_web.py`: de `data/resultados/` a `docs/` | Local |
| `backend/` | API opcional en Python (FastAPI), aún sin uso | Servidor aparte |

`requirements.txt` (raíz) son las dependencias del notebook y del script; `backend/requirements.txt` las de la API.

## Desarrollo local

Web:

```bash
python3 -m http.server 8000 --directory docs
```

Backend:

```bash
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8001
```
