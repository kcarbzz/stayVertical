# Stay Vertical

Proyecto para el NASA Space Apps Challenge 2026: *Permanent Moon Base Locations (and Mars)*.
Elige un sitio lunar y mira dónde en la Tierra se parece su terreno.

Web: https://stay-vertical.wiki

## Estructura

| Carpeta | Qué contiene | Dónde corre |
|---|---|---|
| `docs/` | Web estática (Leaflet) + `resultados.json` | GitHub Pages desde `main` / `docs` |
| `notebooks/` | Análisis pesado (Earth Engine, rasterio…) | Google Colab |
| `backend/` | API opcional en Python (FastAPI) | Servidor aparte (Cloud Run, Render…) |

`requirements.txt` (raíz) son las dependencias de los notebooks; `backend/requirements.txt` las de la API.

## Desarrollo local

Web:

```bash
python3 -m http.server 8000 --directory docs
```

Backend:

```bash
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8001
```
