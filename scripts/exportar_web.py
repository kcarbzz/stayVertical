"""Convierte los resultados del notebook (data/resultados/) en lo que lee la web.

Genera:
  docs/resultados.json   referencias de Luna/Marte con su Top-N terrestre
  docs/parches/*.png     miniatura del relieve residual de cada parche mostrado

Uso:
  python scripts/exportar_web.py [--entrada data/resultados] [--salida docs] [--top 10]
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from matplotlib import colormaps
from PIL import Image
from pyproj import CRS, Transformer

RASGOS = [
    "pendiente_media", "pendiente_std", "pendiente_p90",
    "curvatura_abs_media", "curvatura_abs_p90",
    "rugosidad_mediana", "rugosidad_p90", "rugosidad_std",
]
NOMBRES_REGION = {
    "Monterrey": "Monterrey, México",
    "Atacama": "Atacama, Chile",
    "Teide": "Teide, Tenerife (España)",
    "MeteorCrater": "Meteor Crater, Arizona (EE. UU.)",
}
LADO_MINIATURA = 152


def a_lonlat(tabla):
    """Añade lat/lon del centro de cada parche a partir de su CRS proyectado."""
    lat, lon = np.empty(len(tabla)), np.empty(len(tabla))
    for crs_txt, grupo in tabla.groupby("crs"):
        crs = CRS.from_user_input(crs_txt)
        t = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
        lo, la = t.transform(grupo["x"].values, grupo["y"].values)
        pos = tabla.index.get_indexer(grupo.index)
        lon[pos], lat[pos] = lo, la
    tabla["lat"], tabla["lon"] = lat.round(5), lon.round(5)
    return tabla


def sin_plano(z):
    """Resta el plano de mínimos cuadrados (igual que el paso 27 del notebook)."""
    v = np.isfinite(z)
    yy, xx = np.indices(z.shape)
    A = np.column_stack([xx[v], yy[v], np.ones(v.sum())])
    a, b, c = np.linalg.lstsq(A, z[v], rcond=None)[0]
    return z - (a * xx + b * yy + c)


def miniatura(dem, fila, col, lado, destino):
    res = sin_plano(dem[fila:fila + lado, col:col + lado].astype(float))
    v = np.isfinite(res)
    lim = np.nanpercentile(np.abs(res[v]), 99) or 1.0
    norm = np.clip((np.where(v, res, 0) / lim + 1) / 2, 0, 1)
    rgb = (colormaps["terrain"](norm)[..., :3] * 255).astype(np.uint8)
    rgb[~v] = 40
    Image.fromarray(rgb).resize((LADO_MINIATURA, LADO_MINIATURA), Image.BICUBIC).save(destino, optimize=True)
    return float(np.nanmax(res) - np.nanmin(res))


def ficha(fila):
    return {k: float(f"{fila[k]:.4g}") for k in RASGOS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", default="data/resultados")
    ap.add_argument("--salida", default="docs")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()
    ent, sal = Path(args.entrada), Path(args.salida)
    dir_png = sal / "parches"
    dir_png.mkdir(parents=True, exist_ok=True)
    for viejo in dir_png.glob("*.png"):
        viejo.unlink()

    config = json.loads((ent / "configuracion.json").read_text())
    lado = round(config["parche_m"] / config["resolucion_m"])

    vectores = pd.concat(
        [pd.read_csv(ent / f"vectores_{n}.csv") for n in ("tierra", "luna", "marte")],
        ignore_index=True,
    )
    vectores = a_lonlat(vectores).set_index("parche_id")
    rankings = pd.read_csv(ent / "rankings_completos.csv")
    sens = pd.read_csv(ent / "sensibilidad_pesos.csv")

    dems = {}

    def dem_de(v):
        if v["cuerpo"] == "Tierra":
            nombre = f"tierra_{v['region']}.tif"
        else:
            nombre = f"{v['cuerpo'].lower()}_recorte_80m.tif"
        if nombre not in dems:
            with rasterio.open(ent / nombre) as src:
                dems[nombre] = src.read(1)
        return dems[nombre]

    hechas = {}

    def parche_json(pid):
        v = vectores.loc[pid]
        if pid not in hechas:
            hechas[pid] = miniatura(dem_de(v), int(v["fila"]), int(v["col"]), lado, dir_png / f"{pid}.png")
        return {
            "id": pid, "lat": v["lat"], "lon": v["lon"],
            "img": f"parches/{pid}.png", "relieve_residual_m": round(hechas[pid], 1),
            "ficha": ficha(v),
        }

    cuerpos = []
    for cuerpo, del_cuerpo in rankings.groupby("cuerpo", sort=False):
        referencias = []
        for ref, r in del_cuerpo.groupby("referencia", sort=False):
            r = r.sort_values("score_final")
            candidatos = []
            for puesto, (_, c) in enumerate(r.head(args.top).iterrows(), 1):
                cand = parche_json(c["parche_id"])
                cand.update({
                    "puesto": puesto,
                    "region": c["region"],
                    "lugar": NOMBRES_REGION.get(c["region"], c["region"]),
                    "distancia_fisica": round(c["distancia_fisica"], 4),
                    "corr_forma": round(c["corr_forma"], 4),
                    "rotacion_grados": int(c["rotacion_grados"]),
                    "puesto_fisico": int(round(c["rango_fisico"] * (len(r) - 1))) + 1,
                    "puesto_forma": int(round(c["rango_forma"] * (len(r) - 1))) + 1,
                    "score_final": round(c["score_final"], 4),
                })
                candidatos.append(cand)
            entrada = parche_json(ref)
            entrada["n_candidatos"] = len(r)
            entrada["top"] = candidatos
            referencias.append(entrada)
        s = sens[sens["cuerpo"] == cuerpo].groupby("peso_fisico")[["mismo_top1", "jaccard_top3"]].mean()
        cuerpos.append({
            "nombre": cuerpo,
            "referencias": referencias,
            "sensibilidad": [
                {"peso_fisico": float(p), "mismo_top1": round(f["mismo_top1"], 4), "jaccard_top3": round(f["jaccard_top3"], 4)}
                for p, f in s.iterrows()
            ],
        })

    tierra = vectores[vectores["cuerpo"] == "Tierra"]
    salida = {
        "muestra": False,
        "config": config,
        "rasgos": RASGOS,
        "regiones_tierra": [
            {"region": reg, "lugar": NOMBRES_REGION.get(reg, reg), "parches": len(g),
             "lat": round(g["lat"].mean(), 4), "lon": round(g["lon"].mean(), 4)}
            for reg, g in tierra.groupby("region")
        ],
        "cuerpos": cuerpos,
    }
    (sal / "resultados.json").write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")))
    print(f"{sal / 'resultados.json'}: {sum(len(c['referencias']) for c in cuerpos)} referencias, {len(hechas)} miniaturas")


if __name__ == "__main__":
    main()
