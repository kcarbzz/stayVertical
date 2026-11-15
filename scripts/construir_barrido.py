"""Convierte la salida de scripts/barrido.py en docs/barrido.json, que es lo que lee la web.

Uso:  python3 -I scripts/construir_barrido.py --marte CARPETA --luna CARPETA
Cada carpeta contiene candidatos_<cuerpo>.csv, sitios_<cuerpo>.csv, recortes_<cuerpo>.npz y meta_<cuerpo>.json.
Solo lee datos. Se puede dar un solo cuerpo.
"""
import argparse, base64, csv, json, os, sys

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from stayvertical.barrido import _sin_plano, _suavizar
DOCS = os.path.join(RAIZ, "docs")
POR_SITIO = 12          # candidatos que se publican por sitio
CON_RELIEVE = 5         # de ellos, cuántos llevan su relieve para la comparación visual

FRANJAS = {
    "puna_altiplano": ("Puna y Altiplano", "Puna and Altiplano"), "sahara_central": ("Sáhara central", "Central Sahara"),
    "arabia": ("Península arábiga", "Arabian Peninsula"), "namib": ("Namib", "Namib"),
    "australia_central": ("Australia central", "Central Australia"), "tibet_qaidam": ("Tíbet y Qaidam", "Tibet and Qaidam"),
    "gobi": ("Gobi", "Gobi"), "mojave_gran_cuenca": ("Mojave y Gran Cuenca", "Mojave and Great Basin"),
    "islandia": ("Islandia", "Iceland"), "artico_canada": ("Ártico canadiense", "Canadian Arctic"),
    "svalbard": ("Svalbard", "Svalbard"), "valles_secos": ("Tierra Victoria y Valles Secos (Antártida)", "Victoria Land and Dry Valleys (Antarctica)"),
}
COBERTURA_EN = {"sin dato": "no data", "bosque": "forest", "matorral": "shrubland", "pastizal": "grassland", "cultivos": "cropland",
                "construido": "built-up", "suelo desnudo o vegetación escasa": "bare or sparse vegetation", "nieve y hielo": "snow and ice",
                "agua": "water", "humedal": "wetland", "manglar": "mangrove", "musgo y liquen": "moss and lichen"}


def leer(ruta):
    return list(csv.DictReader(open(ruta, encoding="utf-8")))


def en_anillo(lat, lon, anillo):
    dentro = False
    for i in range(len(anillo)):
        (xi, yi), (xj, yj) = anillo[i][:2], anillo[i - 1][:2]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            dentro = not dentro
    return dentro


def pais_de(lat, lon, paises):
    """Nombre (es, en) del país que contiene el punto, según docs/paises.geojson; None si cae fuera."""
    for f in paises:
        g = f["geometry"]
        for pol in ([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]):
            if en_anillo(lat, lon, pol[0]) and not any(en_anillo(lat, lon, h) for h in pol[1:]):
                return f["properties"]["nombre"], f["properties"]["en"]
    return None


def codificar(Z):
    """Relieve -> bytes de 0 a 255 (de la cota más baja a la más alta del cuadro) en base64, más su rango en metros."""
    Z = np.asarray(Z, dtype=float)
    ok = np.isfinite(Z)
    if not ok.any():
        return None
    lo, hi = float(Z[ok].min()), float(Z[ok].max())
    q = np.zeros(Z.shape, dtype="uint8")
    q[ok] = np.round((Z[ok] - lo) / (hi - lo) * 254).astype("uint8") + 1 if hi > lo else 128     # 0 = hueco
    return {"n": int(Z.shape[0]), "min": round(lo, 1), "max": round(hi, 1), "datos": base64.b64encode(q.tobytes()).decode("ascii")}


def forma(Z):
    """El relieve tal como lo compara el algoritmo: sin su inclinación general y suavizado."""
    R = _sin_plano(Z)
    return codificar(_suavizar(R)) if R is not None else None


def cuerpo_desde(carpeta, cuerpo, paises):
    meta = json.load(open(os.path.join(carpeta, f"meta_{cuerpo}.json"), encoding="utf-8"))
    rec = np.load(os.path.join(carpeta, f"recortes_{cuerpo}.npz"))
    por_sitio = {}
    for r in leer(os.path.join(carpeta, f"candidatos_{cuerpo}.csv")):
        por_sitio.setdefault(r["sitio"], []).append(r)
    sitios = {}
    for s in leer(os.path.join(carpeta, f"sitios_{cuerpo}.csv")):
        sid, cand = s["sitio"], []
        for r in sorted(por_sitio.get(sid, []), key=lambda r: int(r["puesto"]))[:POR_SITIO]:
            lat, lon, puesto = float(r["lat"]), float(r["lon"]), int(r["puesto"])
            p = pais_de(lat, lon, paises)
            fr = FRANJAS.get(r["franja"], (r["franja"], r["franja"]))
            g = {"puesto": puesto, "coord": [round(lat, 4), round(lon, 4)], "franja": fr[0], "franja_en": fr[1],
                 "pais": p[0] if p else None, "pais_en": p[1] if p else None,
                 "score": round(float(r["score"]), 4), "corr": round(float(r["corr"]), 3), "rot": int(float(r["rot"])),
                 "dist_fisica": round(float(r["dist_fisica"]), 5),
                 "ficha": {"pendiente_media": round(float(r["pendiente_media"]), 1), "rugosidad_m": round(float(r["rugosidad_m"]), 1)},
                 "cobertura": r["cobertura"], "cobertura_en": COBERTURA_EN.get(r["cobertura"], r["cobertura"]), "cuadros": int(r["cuadros_region"])}
            clave = f"cand__{sid}__{puesto}"
            if puesto <= CON_RELIEVE and clave in rec.files:
                Z = np.rot90(rec[clave], g["rot"] // 90)                              # ya girado como mejor coincide con el sitio
                g["relieve"], g["forma"] = codificar(Z), forma(Z)
            cand.append(g)
        sitios[sid] = {"ficha": {"pendiente_media": round(float(s["pendiente_media"]), 1), "rugosidad_m": round(float(s["rugosidad_mediana"]), 1)},
                       "fuera_de_rango": s["fuera_de_rango"] == "True", "veces_la_tipica": float(s["veces_la_tipica"]) if s["veces_la_tipica"] else None,
                       "relieve": codificar(rec[f"sitio__{sid}"]), "forma": forma(rec[f"sitio__{sid}"]), "candidatos": cand}
    m = {k: meta[k] for k in ("res_m", "tam_px", "candidatos", "teselas", "cuadros", "fuente_sitios", "fuente_relieve", "fuente_cobertura", "clases_excluidas")}
    m["teselas_fallidas"] = len(meta.get("teselas_fallidas", []))
    m["franjas"] = [{"id": k, "nombre": FRANJAS.get(k, (k, k))[0], "nombre_en": FRANJAS.get(k, (k, k))[1], "caja": v} for k, v in meta["franjas"].items()]
    return {"meta": m, "sitios": sitios}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--marte"); ap.add_argument("--luna"); a = ap.parse_args()
    if not (a.marte or a.luna): ap.error("da al menos --marte o --luna")
    paises = json.load(open(os.path.join(DOCS, "paises.geojson"), encoding="utf-8"))["features"]
    salida = {"cruces": {}}
    for cuerpo, carpeta in (("luna", a.luna), ("marte", a.marte)):
        if carpeta:
            salida["cruces"][f"{cuerpo}-tierra"] = cuerpo_desde(carpeta, cuerpo, paises)
    ruta = os.path.join(DOCS, "barrido.json")
    json.dump(salida, open(ruta, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"docs/barrido.json: {os.path.getsize(ruta) / 1024:.0f} KB")
    for k, c in salida["cruces"].items():
        print(f"  {k}: {c['meta']['cuadros']} cuadros de {c['meta']['teselas']} teselas | " + ", ".join(f"{s}: {len(v['candidatos'])}" for s, v in c["sitios"].items()))


if __name__ == "__main__":
    main()
