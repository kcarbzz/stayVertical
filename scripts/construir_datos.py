"""Construye docs/resultados.json (y copia las imágenes) a partir de los archivos del equipo.

Entradas (no se ejecuta nada de ellas, solo se leen datos):
  --datos      carpeta con los CSV de "HackNASA_8_Luna_10_Marte_Resultados"
  --revision   carpeta con "HackNASA_Revision_18_Sitios" (diagnóstico e imágenes de comparación)
  --cuaderno   HackNASA_a.ipynb (de él solo se leen las 50 zonas terrestres, como literal)
Uso:  python3 -I scripts/construir_datos.py --datos D --revision R --cuaderno N.ipynb
"""
import argparse, ast, csv, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utm import utm_a_latlon, epsg_a_zona

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(RAIZ, "docs")

# nombre (es, en) de cada zona terrestre
NOMBRES = {
 "Monterrey": ("Monterrey", "Monterrey"), "SierraNevada": ("Sierra Nevada", "Sierra Nevada"),
 "RockyMountains": ("Montañas Rocosas", "Rocky Mountains"), "Everest": ("Everest", "Everest"),
 "Matterhorn": ("Cervino (Matterhorn)", "Matterhorn"), "Aconcagua": ("Aconcagua", "Aconcagua"),
 "CordilleraBlanca": ("Cordillera Blanca", "Cordillera Blanca"), "Drakensberg": ("Drakensberg", "Drakensberg"),
 "Toubkal": ("Toubkal", "Toubkal"), "Elbrus": ("Elbrus", "Elbrus"), "Teide": ("Teide", "Teide"), "Etna": ("Etna", "Etna"),
 "Vesuvio": ("Vesubio", "Vesuvius"), "Fuji": ("Monte Fuji", "Mount Fuji"), "Kilimanjaro": ("Kilimanjaro", "Kilimanjaro"),
 "Cotopaxi": ("Cotopaxi", "Cotopaxi"), "Popocatepetl": ("Popocatépetl", "Popocatépetl"),
 "MountStHelens": ("Monte Santa Helena", "Mount St. Helens"), "MaunaLoa": ("Mauna Loa", "Mauna Loa"), "Bromo": ("Bromo", "Bromo"),
 "Atacama": ("Desierto de Atacama", "Atacama Desert"), "Sossusvlei": ("Sossusvlei", "Sossusvlei"),
 "WhiteDesert": ("Desierto Blanco", "White Desert"), "KhongorynEls": ("Khongoryn Els", "Khongoryn Els"),
 "WadiRum": ("Wadi Rum", "Wadi Rum"), "RubAlKhali": ("Rub' al Jali", "Rub' al Khali"),
 "DeathValley": ("Valle de la Muerte", "Death Valley"), "KelsoDunes": ("Dunas de Kelso", "Kelso Dunes"),
 "SalarUyuni": ("Salar de Uyuni", "Salar de Uyuni"), "BadainJaran": ("Badain Jaran", "Badain Jaran"),
 "MeteorCrater": ("Cráter Meteoro (Barringer)", "Meteor Crater"), "LonarCrater": ("Cráter Lonar", "Lonar Crater"),
 "WolfeCreekCrater": ("Cráter Wolfe Creek", "Wolfe Creek Crater"), "RoterKamm": ("Roter Kamm", "Roter Kamm"),
 "RiesCrater": ("Cráter Ries", "Ries Crater"), "Vredefort": ("Vredefort", "Vredefort"), "Ngorongoro": ("Ngorongoro", "Ngorongoro"),
 "NewberryCaldera": ("Caldera Newberry", "Newberry Caldera"), "Pinatubo": ("Pinatubo", "Pinatubo"),
 "Yellowstone": ("Yellowstone", "Yellowstone"), "GrandCanyon": ("Gran Cañón", "Grand Canyon"),
 "BryceCanyon": ("Cañón Bryce", "Bryce Canyon"), "ZionCanyon": ("Cañón Zion", "Zion Canyon"),
 "CopperCanyon": ("Cañón del Cobre", "Copper Canyon"), "FishRiverCanyon": ("Cañón del río Fish", "Fish River Canyon"),
 "ColcaCanyon": ("Cañón del Colca", "Colca Canyon"), "KingsCanyonAustralia": ("Kings Canyon (Australia)", "Kings Canyon (Australia)"),
 "GreatPlainsKansas": ("Grandes Llanuras (Kansas)", "Great Plains (Kansas)"), "Altiplano": ("Altiplano", "Altiplano"),
 "TibetanPlateau": ("Meseta tibetana", "Tibetan Plateau"),
}
CATEGORIAS = {"Montañas": ("Montañas", "Mountains"), "Volcanes": ("Volcanes", "Volcanoes"), "Desiertos": ("Desiertos", "Deserts"),
              "Crateres_calderas": ("Cráteres y calderas", "Craters and calderas"), "Canones_mesetas": ("Cañones y mesetas", "Canyons and plateaus")}


def leer(ruta):
    return list(csv.DictReader(open(ruta, encoding="utf-8")))


def centros_del_cuaderno(ruta):
    nb = json.load(open(ruta, encoding="utf-8"))
    for c in nb["cells"]:
        m = re.search(r"CENTROS_TERRESTRES = (\[.*?\])\n", "".join(c["source"]), re.S)
        if m:
            return {n: (lat, lon, cat) for n, lon, lat, cat in ast.literal_eval(m.group(1))}   # solo literales
    raise SystemExit("No encontré CENTROS_TERRESTRES en el cuaderno")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", required=True); ap.add_argument("--revision", required=True); ap.add_argument("--cuaderno", required=True)
    a = ap.parse_args()

    centros = centros_del_cuaderno(a.cuaderno)
    faltan = [n for n in centros if n not in NOMBRES]
    assert not faltan, f"Faltan nombres para: {faltan}"
    vec = leer(os.path.join(a.datos, "vectores_tierra_200m.csv"))
    vec_por_id = {r["parche_id"]: r for r in vec}
    crs = {}
    for r in vec: crs.setdefault(r["region"], r["crs"])

    def latlon(r):
        reg = r["region"]
        zona, norte = epsg_a_zona(crs[reg]) if reg in crs else (int((centros[reg][1] + 180) // 6) + 1, centros[reg][0] >= 0)
        lat, lon = utm_a_latlon(float(r["x"]), float(r["y"]), zona, norte)
        # control: el parche debe quedar cerca del centro de su zona (recorte de ~13 km)
        clat, clon = centros[reg][:2]
        assert abs(lat - clat) < 0.2 and abs(lon - clon) < 0.3 / max(0.25, abs(__import__("math").cos(__import__("math").radians(clat)))), f"coordenada fuera de zona: {r['parche_id']}"
        return [round(lat, 4), round(lon, 4)]

    previo = json.load(open(os.path.join(DOCS, "resultados.json"), encoding="utf-8"))
    conocidas = previo["conocidas"]
    diag = {(r["cuerpo"].lower(), r["sitio"]): r for r in leer(os.path.join(a.revision, "diagnostico_18_sitios.csv"))}
    resumen = {r["sitio_lunar"]: r for r in leer(os.path.join(a.datos, "resumen_8_luna_80m.csv"))}
    resumen.update({r["sitio_marte"]: r for r in leer(os.path.join(a.datos, "resumen_10_marte_200m.csv"))})
    estados = {r["id"]: r for r in leer(os.path.join(a.datos, "estado_8_luna.csv")) + leer(os.path.join(a.datos, "estado_10_marte.csv"))}
    assert all(r["estado"] == "DEM OK" for r in estados.values()), "hay sitios sin DEM OK"

    os.makedirs(os.path.join(DOCS, "img"), exist_ok=True)
    cruces = {}
    for cuerpo, archivo, col, res in (("luna", "rankings_8_luna_tierra_80m.csv", "sitio_lunar", 80), ("marte", "rankings_10_marte_tierra_200m.csv", "sitio_marte", 200)):
        filas = leer(os.path.join(a.datos, archivo))
        por_sitio = {}
        for r in filas: por_sitio.setdefault(r[col], []).append(r)
        regiones = []
        for k in conocidas[cuerpo]:
            sid = k["id"]
            lista = por_sitio[sid]
            d = diag[(cuerpo, sid)]
            vistos, gem = {}, []
            for rank, r in enumerate(lista, start=1):
                reg = r["region"]
                if reg in vistos:
                    vistos[reg]["n_top"] += 1; continue
                g = {"lugar": NOMBRES[reg][0], "lugar_en": NOMBRES[reg][1], "region": reg,
                     "categoria": CATEGORIAS[centros[reg][2]][0], "categoria_en": CATEGORIAS[centros[reg][2]][1],
                     "coord": latlon(r), "score": round(float(r["score_final"]), 6), "corr": round(float(r["corr_forma"]), 3),
                     "rot": int(float(r["rotacion_grados"])), "rank": rank, "n_top": 1}
                if cuerpo == "marte":                      # los vectores terrestres a 200 m sí están para todos los candidatos
                    v = vec_por_id[r["parche_id"]]
                    g["ficha"] = {"pendiente_media": round(float(v["pendiente_media"]), 1), "rugosidad_m": round(float(v["rugosidad_mediana"]), 1)}
                vistos[reg] = g; gem.append(g)
            top = gem[0]
            top["ficha"] = {"pendiente_media": round(float(d["pendiente_tierra"]), 1), "rugosidad_m": round(float(d["rugosidad_tierra"]), 1)}
            top["dif"] = {"pendiente": round(float(d["diferencia_pendiente"]), 1), "rugosidad": round(float(d["diferencia_rugosidad"]), 1)}
            img = f"img/{cuerpo}_{sid}_comparacion.png"
            shutil.copy(os.path.join(a.revision, f"{cuerpo}_{sid}_comparacion.png"), os.path.join(DOCS, img))
            ent = {"id": sid, "nombre": k["nombre"], "nombre_en": k["nombre_en"], "mejor": k["coord"],
                   "ficha": {"pendiente_media": round(float(d["pendiente_planeta"]), 1), "rugosidad_m": round(float(d["rugosidad_planeta"]), 1)},
                   "revision": d["revision_prioritaria"] == "True", "img": img, "n_evaluados": int(resumen[sid]["parches_evaluados"]),
                   "resolucion_m": res, "gemelos": gem}
            if cuerpo == "marte":
                t5 = f"img/top5_marte_{sid}.png"
                shutil.copy(os.path.join(a.datos, "graficas", f"top5_marte_{sid}.png"), os.path.join(DOCS, t5)); ent["img_top5"] = t5
            regiones.append(ent)
        cruces[f"{cuerpo}-tierra"] = {"regiones": regiones}

    meta = json.load(open(os.path.join(a.datos, "metadatos_18_sitios.json"), encoding="utf-8"))
    salida = {
        "muestra": False, "exploratorio": True, "version": "Resultados del equipo (HackNASA), exploratorios",
        "metodo": {"fuente_tierra": meta["fuente_tierra"], "fuente_luna": meta["fuente_luna"], "fuente_marte": meta["fuente_marte"],
                   "res_luna_m": meta["resolucion_luna_m"], "res_marte_m": meta["resolucion_marte_y_tierra_remuestreada_m"],
                   "ventana_luna_m": meta["ventana_luna_m"], "ventana_marte_m": meta["ventana_marte_m"], "candidatos": 500,
                   "zonas_tierra": len(centros), "observacion": meta["observacion"]},
        "cuerpos": previo["cuerpos"], "continentes": previo["continentes"], "conocidas": conocidas,
        "cruces": cruces}
    json.dump(salida, open(os.path.join(DOCS, "resultados.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    tam = os.path.getsize(os.path.join(DOCS, "resultados.json"))
    print(f"docs/resultados.json: {tam/1024:.0f} KB | sitios: {sum(len(c['regiones']) for c in cruces.values())} | imágenes copiadas: {len(os.listdir(os.path.join(DOCS, 'img')))}")
    for k, c in cruces.items():
        print(" ", k, [(e['id'], len(e['gemelos']), e['gemelos'][0]['lugar'], e['gemelos'][0]['score']) for e in c['regiones']][:3], "...")


if __name__ == "__main__":
    main()
