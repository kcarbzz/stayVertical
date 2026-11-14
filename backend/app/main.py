"""API de stayVertical (opcional).

La web (docs/) funciona sola con docs/resultados.json. Este backend solo hace
falta si alguna consulta tiene que calcularse en vivo.
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="stayVertical API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://stay-vertical.wiki",
        "https://www.stay-vertical.wiki",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/site")
def site(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    # TODO: devolver pendiente, iluminación, temperatura, etc. a partir de los
    # rasters generados en los notebooks.
    return {"lat": lat, "lon": lon, "score": None}
