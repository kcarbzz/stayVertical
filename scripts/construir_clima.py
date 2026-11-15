"""Construye docs/clima.json a partir del paquete 'HackNASA_OVERLAY_CLIMA_50_WEB' (NASA POWER, 2021-2025).

Solo lee datos (CSV/JSON). Los umbrales del semáforo son PROVISIONALES: los definimos nosotros para poder mirar
la viabilidad de forma transparente; no son normas de ingeniería y se pueden ajustar aquí o en docs/clima.json.
Uso:  python3 -I scripts/construir_clima.py --paquete CARPETA_DEL_ZIP
"""
import argparse, csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from construir_datos import NOMBRES, CATEGORIAS

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")

# id, nombre es, nombre en, unidad, descripción es, descripción en, umbral
# umbral: tipo "mayor_peor" | "menor_peor" -> atencion, dificil ; tipo "rango" -> atencion [min,max], dificil [min,max]
VARIABLES = [
 ("t_media_c", "Temperatura media", "Mean temperature", "°C", "Temperatura media del aire.", "Mean air temperature.", {"tipo": "rango", "atencion": [0, 30], "dificil": [-10, 35]}),
 ("t_max_ext_c", "Temperatura máxima extrema", "Extreme maximum temperature", "°C", "Mayor temperatura máxima diaria de los 5 años.", "Highest daily maximum temperature in the 5 years.", {"tipo": "mayor_peor", "atencion": 38, "dificil": 45}),
 ("t_min_ext_c", "Temperatura mínima extrema", "Extreme minimum temperature", "°C", "Menor temperatura mínima diaria de los 5 años.", "Lowest daily minimum temperature in the 5 years.", {"tipo": "menor_peor", "atencion": -15, "dificil": -30}),
 ("lluvia_anual_mm", "Lluvia anual", "Annual rainfall", "mm", "Precipitación media por año.", "Mean precipitation per year.", {"tipo": "rango", "atencion": [100, 1500], "dificil": [25, 3000]}),
 ("dias_lluvia_anio", "Días de lluvia al año", "Rainy days per year", "días", "Días con precipitación apreciable por año.", "Days with measurable precipitation per year.", {"tipo": "mayor_peor", "atencion": 150, "dificil": 220}),
 ("racha_lluviosa_max_dias", "Racha lluviosa máxima", "Longest rainy spell", "días", "Mayor número de días lluviosos seguidos.", "Longest run of consecutive rainy days.", {"tipo": "mayor_peor", "atencion": 14, "dificil": 30}),
 ("dias_calor_35_anio", "Días de calor (≥35 °C)", "Hot days (≥35 °C)", "días", "Días al año con máxima de 35 °C o más.", "Days per year with a maximum of 35 °C or more.", {"tipo": "mayor_peor", "atencion": 30, "dificil": 100}),
 ("dias_helada_anio", "Días de helada", "Frost days", "días", "Días al año con mínima bajo 0 °C.", "Days per year with a minimum below 0 °C.", {"tipo": "mayor_peor", "atencion": 60, "dificil": 150}),
 ("viento_10m_ms", "Viento medio (10 m)", "Mean wind (10 m)", "m/s", "Velocidad media diaria del viento a 10 m.", "Mean daily wind speed at 10 m.", {"tipo": "mayor_peor", "atencion": 6, "dificil": 9}),
 ("dias_viento_10ms_anio", "Días de viento fuerte (≥10 m/s)", "Strong-wind days (≥10 m/s)", "días", "Días al año con viento medio de 10 m/s o más (los datos son medias diarias: no incluyen ráfagas).", "Days per year with mean wind of 10 m/s or more (daily means: gusts not included).", {"tipo": "mayor_peor", "atencion": 3, "dificil": 15}),
 ("humedad_rel_pct", "Humedad relativa", "Relative humidity", "%", "Humedad relativa media.", "Mean relative humidity.", {"tipo": "rango", "atencion": [25, 85], "dificil": [10, 95]}),
 ("solar_kwh_m2_dia", "Radiación solar", "Solar radiation", "kWh/m²/día", "Energía solar media recibida; sirve como recurso para paneles.", "Mean solar energy received; a resource for solar panels.", {"tipo": "menor_peor", "atencion": 4.0, "dificil": 3.0}),
 ("presion_kpa", "Presión atmosférica", "Atmospheric pressure", "kPa", "Presión media en superficie: baja presión indica gran altitud.", "Mean surface pressure: low pressure indicates high altitude.", {"tipo": "menor_peor", "atencion": 75, "dificil": 60}),
]
MENSUAL = [("temperatura_media_c", "t"), ("lluvia_mm_mes_media", "lluvia"), ("humedad_rel_pct", "hum"), ("viento_10m_ms", "viento"), ("solar_kwh_m2_dia", "solar"), ("dias_lluvia_estimados_mes", "dias_lluvia")]

leer = lambda p: list(csv.DictReader(open(p, encoding="utf-8")))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--paquete", required=True); a = ap.parse_args()
    anual = leer(os.path.join(a.paquete, "clima_50_nasa_power.csv")); mensual = leer(os.path.join(a.paquete, "clima_mensual_50.csv"))
    res = json.load(open(os.path.join(a.paquete, "resumen.json"), encoding="utf-8"))
    assert res["regiones_ok"] == res["regiones_totales"] == len(anual) == 50, "el paquete no tiene las 50 regiones OK"
    meses = {}
    for r in mensual: meses.setdefault(r["region"], []).append(r)
    reg = {}
    for r in anual:
        n = r["region"]
        assert n in NOMBRES, f"región sin nombre: {n}"
        assert r["estado"] == "OK" and len(meses[n]) == 12, f"datos incompletos: {n}"
        v = {k[0]: round(float(r[k[0]]), 2) for k in VARIABLES}
        reg[n] = {"nombre": NOMBRES[n][0], "nombre_en": NOMBRES[n][1], "categoria": CATEGORIAS[r["categoria"]][0], "categoria_en": CATEGORIAS[r["categoria"]][1],
                  "lat": float(r["lat"]), "lon": float(r["lon"]), "v": v,
                  "mensual": [{**{c: round(float(m[col]), 2) for col, c in MENSUAL}, "mes": int(m["mes"])} for m in sorted(meses[n], key=lambda m: int(m["mes"]))]}
    salida = {
        "fuente": res["fuente"], "periodo": res["periodo"], "resolucion": "meteorología ~0,5° × 0,625° (≈ 55 km); solar ~1°",
        "nota": "Caracterización climática exploratoria con NASA POWER. No certifica viabilidad de construcción: son promedios de una celda de ~55 km, no el microclima del sitio.",
        "umbrales_provisionales": True,
        "umbrales_nota": "Umbrales definidos por el equipo de desarrollo, provisionales y ajustables; no son normas de ingeniería.",
        "variables": [{"id": i, "nombre": n, "nombre_en": ne, "unidad": u, "desc": d, "desc_en": de, "umbral": um} for i, n, ne, u, d, de, um in VARIABLES],
        "regiones": reg}
    json.dump(salida, open(os.path.join(DOCS, "clima.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"docs/clima.json: {os.path.getsize(os.path.join(DOCS, 'clima.json'))/1024:.0f} KB | regiones {len(reg)} | variables {len(VARIABLES)}")


if __name__ == "__main__":
    main()
