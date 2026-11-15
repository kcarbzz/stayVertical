"""Barrido de franjas de la Tierra en busca de análogos de los sitios de la Luna o de Marte.

En vez de comparar con 50 zonas elegidas a mano, recorre franjas enteras (cientos de kilómetros) y deja que el
algoritmo encuentre los cuadros que más se parecen a cada sitio. Pensado para Google Colab.

Datos (se descargan solos desde Microsoft Planetary Computer, sin cuenta):
  - Relieve:   Copernicus DEM GLO-30 (30 m) o GLO-90 (90 m), programa Copernicus de la UE con la ESA.
  - Cobertura: ESA WorldCover 2021 (10 m), para descartar bosque, cultivos, ciudades, agua, nieve y hielo.

Instalación en Colab:
  !pip install -q rasterio pystac-client planetary-computer

Uso (una ejecución por cuerpo):
  !python scripts/barrido.py --listar
  !python scripts/barrido.py --cuerpo marte --franjas puna_altiplano,islandia --salida barrido_marte
  !python scripts/barrido.py --cuerpo luna  --franjas puna_altiplano,islandia --salida barrido_luna

Los sitios no hay que prepararlos: el script lee las coordenadas de los 18 sitios en docs/resultados.json y recorta
cada uno de la fuente oficial (Luna: NASA LOLA LDEM_80S a 80 m; Marte: mezcla HRSC/MOLA de USGS a 200 m).
Con --sitios se pueden dar GeoTIFF propios en su lugar: uno por sitio, en metros, a la resolución de comparación
y con el sitio en el centro (marte_jezero_200m.tif -> jezero).

Se puede interrumpir y volver a lanzar: las teselas ya procesadas se guardan en <salida>/cache y no se repiten.

Salida (en la carpeta --salida):
  candidatos_<cuerpo>.csv   los mejores cuadros por sitio, una fila por región, con coordenadas y puntaje
  sitios_<cuerpo>.csv       los 8 rasgos de cada sitio y si queda fuera del rango de lo barrido (su cuadro más
                            parecido está más lejos que el 99 % de las distancias entre cuadros terrestres vecinos)
  recortes_<cuerpo>.npz     relieve del sitio y de sus mejores candidatos (para las imágenes de comparación)
  meta_<cuerpo>.json        parámetros, fuentes, franjas, número de teselas y de cuadros
"""
import argparse, csv, glob, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stayvertical.features import CARACTERISTICAS
from stayvertical.barrido import (Base, CLASES, CLASES_EXCLUIDAS, parches_de_tesela, puntuar_sitio, regiones, sitio_desde_dem)

# Franjas predefinidas: (sur, oeste, norte, este) en grados. Se pueden añadir otras con --caja.
FRANJAS = {
    "puna_altiplano":    (-28, -70, -18, -65),   # Atacama, Puna y Altiplano
    "sahara_central":    (19, 5, 27, 20),        # Hoggar, Tibesti y mares de arena
    "arabia":            (17, 44, 24, 56),       # Rub' al Jali y montañas de Omán
    "namib":             (-28, 14, -19, 18),
    "australia_central": (-27, 126, -21, 136),
    "tibet_qaidam":      (32, 84, 39, 97),
    "gobi":              (39, 97, 45, 108),
    "mojave_gran_cuenca": (34, -119, 40, -112),
    "islandia":          (63, -25, 67, -13),
    "artico_canada":     (74, -97, 81, -78),     # islas Devon y Axel Heiberg
    "svalbard":          (76, 10, 81, 28),
    "valles_secos":      (-79, 158, -76, 166),   # Antártida (sin mapa de cobertura: no se descarta nada)
}
PREDETERMINADO = {"luna": dict(res=80.0, tam_px=38), "marte": dict(res=200.0, tam_px=15)}
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Fuentes oficiales del relieve de los sitios (las mismas del equipo). Se leen por bloques, sin descargar el archivo entero.
FUENTE_SITIOS = {
    "luna": dict(url="https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF", radio=1737400.0, nombre="NASA LOLA LDEM_80S_80MPP_ADJ"),
    "marte": dict(url="https://planetarymaps.usgs.gov/mosaic/Mars/HRSC_MOLA_Blend/Mars_HRSC_MOLA_BlendDEM_Global_200mp_v2.tif", radio=3396190.0,
                  nombre="USGS HRSC/MOLA blend DEM v2 (NASA MOLA + ESA HRSC)"),
}
BORDE_PX = 5          # margen alrededor del cuadro del sitio, como en el cuaderno del equipo


def decir(*a):
    print(*a, flush=True)


# ---------- lectura de datos (única parte que necesita red) ----------

def epsg_local(lat, lon):
    """Proyección en metros adecuada para una tesela: UTM, o estereográfica polar cerca de los polos."""
    if lat <= -80: return 3031
    if lat >= 84: return 3413
    zona = int((lon + 180) // 6) % 60 + 1
    return (32600 if lat >= 0 else 32700) + zona


class PlanetaryComputer:
    """Copernicus DEM y ESA WorldCover desde Microsoft Planetary Computer."""

    def __init__(self, dem):
        import planetary_computer, pystac_client
        self.pc = planetary_computer
        self.cat = pystac_client.Client.open(STAC)
        self.dem = dem

    def teselas(self, caja):
        s, o, n, e = caja
        d = 0.01                                    # las teselas sobresalen medio píxel: sin este margen entrarían las vecinas
        items = self.cat.search(collections=[self.dem], bbox=[o + d, s + d, e - d, n - d]).item_collection()
        return sorted(items, key=lambda it: it.id)

    def _cobertura(self, bbox):
        o, s, e, n = bbox
        d = 0.02
        items = list(self.cat.search(collections=["esa-worldcover"], bbox=[o + d, s + d, e - d, n - d]).items())
        if not items:
            return []
        reciente = max(str(it.properties.get("start_datetime") or it.datetime or "") for it in items)
        return [it for it in items if str(it.properties.get("start_datetime") or it.datetime or "") == reciente]

    def leer(self, item, res):
        """DEM y clases de cobertura de una tesela sobre una cuadrícula local en metros, a `res` m por píxel."""
        import rasterio
        from rasterio.warp import Resampling, calculate_default_transform, reproject
        o, s, e, n = item.bbox
        crs = f"EPSG:{epsg_local((s + n) / 2, (o + e) / 2)}"
        with rasterio.open(self.pc.sign(item).assets["data"].href) as src:
            tr, ancho, alto = calculate_default_transform(src.crs, crs, src.width, src.height, *src.bounds, resolution=res)
            H = np.full((alto, ancho), np.nan, dtype="float32")
            reproject(rasterio.band(src, 1), H, dst_transform=tr, dst_crs=crs, dst_nodata=np.nan, src_nodata=src.nodata, resampling=Resampling.average)
        clases = np.zeros((alto, ancho), dtype="uint8")
        hay = False
        for wc in self._cobertura(item.bbox):
            with rasterio.open(self.pc.sign(wc).assets["map"].href) as src:
                parte = np.zeros((alto, ancho), dtype="uint8")
                reproject(rasterio.band(src, 1), parte, dst_transform=tr, dst_crs=crs, dst_nodata=0, resampling=Resampling.mode)
                clases = np.where(parte > 0, parte, clases); hay = True
        return H, (clases if hay else None), tuple(tr)[:6], crs


def a_latlon(tr, crs, centros):
    """(fila, col) en píxeles -> (lat, lon)."""
    from rasterio.warp import transform
    if not len(centros):
        return np.empty(0), np.empty(0)
    a, b, c, d, e, f = tr
    col, fil = centros[:, 1] + 0.5, centros[:, 0] + 0.5
    xs, ys = a * col + b * fil + c, d * col + e * fil + f
    lon, lat = transform(crs, "EPSG:4326", xs.tolist(), ys.tolist())
    return np.array(lat), np.array(lon)


def leer_sitio(ruta, res):
    import rasterio
    with rasterio.open(ruta) as src:
        H = src.read(1).astype("float64")
        if src.nodata is not None:
            H[H == src.nodata] = np.nan
        px = abs(src.transform.a)
        if src.crs and not src.crs.is_geographic and px > 0 and abs(px - res) / res > 0.05:
            raise SystemExit(f"{ruta}: su píxel mide {px:.1f} m y la comparación es a {res:.0f} m. Exporta el sitio a esa resolución o cambia --res.")
    return H


def reintentar(f, veces=5):
    for k in range(veces):
        try:
            return f()
        except Exception:
            if k == veces - 1: raise
            time.sleep(2 * (k + 1))


def recortar_sitio(cuerpo, lat, lon, res, tam_px):
    """Relieve del sitio (cuadro + margen) leído de la fuente oficial, sobre una cuadrícula local en metros."""
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject, transform
    from rasterio.windows import Window
    F, n = FUENTE_SITIOS[cuerpo], tam_px + 2 * BORDE_PX
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="2"):
        with rasterio.open("/vsicurl/" + F["url"]) as src:
            if cuerpo == "luna":                                 # el archivo ya está en metros (estereográfica polar)
                x, y = transform(f"+proj=longlat +R={F['radio']} +no_defs", src.crs, [lon], [lat])
                if abs(abs(src.transform.a) - res) < 1e-6:       # misma resolución: se leen los píxeles tal cual
                    f, c = src.index(x[0], y[0])
                    H = src.read(1, window=Window(c - n // 2, f - n // 2, n, n), boundless=True, fill_value=np.nan).astype("float64")
                else:
                    H = np.full((n, n), np.nan, dtype="float32")
                    reproject(rasterio.band(src, 1), H, dst_transform=from_origin(x[0] - n / 2 * res, y[0] + n / 2 * res, res, res), dst_crs=src.crs,
                              dst_nodata=np.nan, resampling=Resampling.average)
            else:                                                # el archivo está en grados: se pasa a metros con la escala de la latitud del sitio
                crs = f"+proj=eqc +lat_ts={lat} +lat_0=0 +lon_0={lon} +R={F['radio']} +units=m +no_defs"
                H = np.full((n, n), np.nan, dtype="float32")
                reproject(rasterio.band(src, 1), H, dst_transform=from_origin(-n / 2 * res, np.radians(lat) * F["radio"] + n / 2 * res, res, res), dst_crs=crs,
                          dst_nodata=np.nan, resampling=Resampling.bilinear)
            H = np.asarray(H, dtype="float64")
            if src.nodata is not None and np.isfinite(src.nodata):
                H[H == src.nodata] = np.nan
    return H


def sitios_oficiales(cuerpo, res, tam_px, salida):
    """Los sitios de docs/resultados.json recortados de la fuente oficial. Se guardan para no volver a leerlos."""
    datos = json.load(open(os.path.join(RAIZ, "docs", "resultados.json"), encoding="utf-8"))
    publicada = {e["id"]: e["ficha"] for e in datos["cruces"][f"{cuerpo}-tierra"]["regiones"]}
    ruta = os.path.join(salida, f"sitios_{cuerpo}_{int(res)}m_{tam_px}px.npz")
    guardados = dict(np.load(ruta)) if os.path.exists(ruta) else {}
    sitios = {}
    decir(f"Sitios de {cuerpo} desde {FUENTE_SITIOS[cuerpo]['nombre']}:")
    for s in datos["conocidas"][cuerpo]:
        sid, (lat, lon) = s["id"], s["coord"]
        if sid not in guardados:
            guardados[sid] = reintentar(lambda: recortar_sitio(cuerpo, lat, lon, res, tam_px))
            np.savez_compressed(ruta, **guardados)
        sitios[sid] = sitio_desde_dem(guardados[sid], res, tam_px)
        f, p = sitios[sid]["ficha"], publicada.get(sid)
        decir(f"  {sid:<12} pendiente {f['pendiente_media']:.1f}° · rugosidad {f['rugosidad_m']:.1f} m"
              + (f"  (publicado: {p['pendiente_media']}° · {p['rugosidad_m']} m)" if p else ""))
    return sitios


def id_de(ruta):
    base = os.path.splitext(os.path.basename(ruta))[0]
    m = re.match(r"(?:luna|marte|moon|mars)_(.+?)(?:_\d+m)?$", base, re.I)
    return (m.group(1) if m else base).lower()


# ---------- pasada 1: rasgos de todos los cuadros ----------

def procesar_tesela(fuente, item, franja, a, cache):
    ruta = os.path.join(cache, f"{item.id}_{int(a.res)}m_{a.tam_px}px_{'-'.join(map(str, a.excluir)) if a.cobertura else 'todo'}.npz")
    if os.path.exists(ruta):
        return ruta, None
    for intento in range(3):
        try:
            H, clases, tr, crs = fuente.leer(item, a.res)
            break
        except Exception as err:                                     # red inestable: reintenta y, si no, sigue con las demás
            if intento == 2:
                return None, f"{item.id}: {type(err).__name__}: {err}"
            time.sleep(3 * (intento + 1))
    X, centros, fichas, dom = parches_de_tesela(H, a.res, a.tam_px, solape=a.solape, clases=clases if a.cobertura else None, excluir=a.excluir)
    lat, lon = a_latlon(tr, crs, centros)
    np.savez_compressed(ruta + ".tmp.npz", H=H, X=X, centros=centros, lat=lat, lon=lon, dominante=dom, franja=franja, con_cobertura=clases is not None,
                        pendiente=[f["pendiente_media"] for f in fichas], rugosidad=[f["rugosidad_m"] for f in fichas], llana=[f["frac_llana"] for f in fichas])
    os.replace(ruta + ".tmp.npz", ruta)
    return ruta, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listar", action="store_true", help="muestra las franjas predefinidas y termina")
    ap.add_argument("--cuerpo", choices=["luna", "marte"])
    ap.add_argument("--sitios", help='opcional: GeoTIFF propios de los sitios, entre comillas: "carpeta/*.tif". Sin esto se recortan de la fuente oficial')
    ap.add_argument("--franjas", default="", help="nombres separados por comas (ver --listar)")
    ap.add_argument("--caja", action="append", default=[], metavar="NOMBRE:SUR,OESTE,NORTE,ESTE", help="franja propia; se puede repetir")
    ap.add_argument("--salida", default="barrido")
    ap.add_argument("--res", type=float, help="metros por píxel de la comparación (Luna 80, Marte 200)")
    ap.add_argument("--tam-px", type=int, dest="tam_px", help="lado del cuadro en píxeles (Luna 38, Marte 15)")
    ap.add_argument("--solape", type=float, default=0.5, help="solape entre cuadros vecinos (0 a 0,9)")
    ap.add_argument("--candidatos", type=int, default=500, help="mínimo de cuadros que pasan de la etapa física a la de forma, por sitio")
    ap.add_argument("--fraccion", type=float, default=0.001, help="parte de la base que pasa a la etapa de forma (0,001 = el 0,1 %% más parecido); así barrer más área no deja fuera a los buenos candidatos")
    ap.add_argument("--fisica", choices=["distancia", "percentil"], default="distancia", help="término físico del puntaje: la diferencia real en los 8 rasgos (por defecto) o la posición en la base, como en el catálogo de 50 zonas")
    ap.add_argument("--top", type=int, default=25, help="regiones que se guardan por sitio")
    ap.add_argument("--radio-km", type=float, dest="radio_km", help="cuadros a esta distancia o menos son la misma región (por defecto, 2 cuadros)")
    ap.add_argument("--excluir", default=",".join(str(c) for c in CLASES_EXCLUIDAS), help="códigos de ESA WorldCover que se descartan (por defecto incluye 70, nieve y hielo)")
    ap.add_argument("--sin-cobertura", action="store_false", dest="cobertura", help="no descartar bosque, cultivos, ciudades ni agua")
    ap.add_argument("--dem", choices=["cop-dem-glo-30", "cop-dem-glo-90"], help="por defecto, 30 m para la Luna y 90 m para Marte")
    ap.add_argument("--hilos", type=int, default=4)
    ap.add_argument("--max-teselas", type=int, dest="max_teselas", help="para una prueba rápida: procesa solo las primeras N teselas")
    a = ap.parse_args()

    if a.listar:
        for n, (s, o, nn, e) in FRANJAS.items():
            decir(f"  {n:<20} lat {s:>4}..{nn:<4} lon {o:>5}..{e:<5} hasta {(nn - s) * (e - o)} teselas de 1°")
        return
    if not a.cuerpo:
        ap.error("falta --cuerpo (o usa --listar)")
    a.res = a.res or PREDETERMINADO[a.cuerpo]["res"]
    a.tam_px = a.tam_px or PREDETERMINADO[a.cuerpo]["tam_px"]
    a.dem = a.dem or ("cop-dem-glo-90" if a.res >= 90 else "cop-dem-glo-30")
    a.radio_km = a.radio_km or 2 * a.tam_px * a.res / 1000.0
    a.excluir = tuple(int(c) for c in a.excluir.split(",") if c.strip())

    cajas = {}
    for n in filter(None, a.franjas.split(",")):
        if n not in FRANJAS: ap.error(f"franja desconocida: {n} (ver --listar)")
        cajas[n] = FRANJAS[n]
    for c in a.caja:
        n, v = c.split(":"); cajas[n] = tuple(float(x) for x in v.split(","))
        if len(cajas[n]) != 4 or cajas[n][0] >= cajas[n][2] or cajas[n][1] >= cajas[n][3]: ap.error(f"caja mal escrita: {c}")
    if not cajas: ap.error("elige al menos una franja con --franjas o --caja")

    cache = os.path.join(a.salida, "cache"); os.makedirs(cache, exist_ok=True)
    if a.sitios:
        rutas = sorted(glob.glob(a.sitios))
        if not rutas: ap.error(f"ningún archivo coincide con {a.sitios}")
        sitios = {id_de(r): sitio_desde_dem(leer_sitio(r, a.res), a.res, a.tam_px) for r in rutas}
    else:
        sitios = sitios_oficiales(a.cuerpo, a.res, a.tam_px, a.salida)
    decir(f"Sitios de {a.cuerpo}: {', '.join(sitios)} | cuadro de {a.tam_px} px a {a.res:.0f} m ({a.tam_px * a.res / 1000:.2f} km)")
    fuente = PlanetaryComputer(a.dem)
    trabajo = []
    for n, caja in cajas.items():
        items = fuente.teselas(caja)
        decir(f"Franja {n}: {len(items)} teselas con tierra firme")
        trabajo += [(it, n) for it in items]
    vistos, unicos = set(), []
    for it, n in trabajo:
        if it.id not in vistos: vistos.add(it.id); unicos.append((it, n))
    if a.max_teselas: unicos = unicos[: a.max_teselas]

    t0, hechas, fallos, archivos = time.time(), 0, [], []
    with ThreadPoolExecutor(max_workers=max(a.hilos, 1)) as ex:
        for ruta, err in ex.map(lambda p: procesar_tesela(fuente, p[0], p[1], a, cache), unicos):
            hechas += 1
            if err: fallos.append(err)
            else: archivos.append(ruta)
            if hechas % 10 == 0 or hechas == len(unicos):
                decir(f"  teselas {hechas}/{len(unicos)} · {time.time() - t0:.0f} s · fallos {len(fallos)}")
    for f in fallos: decir("  FALLÓ", f)
    if not archivos: raise SystemExit("No se pudo leer ninguna tesela.")

    # ---------- pasada 2: base, etapa física y etapa de forma ----------
    X, lat, lon, pend, rug, llana, dom, tes, cen, franja, sin_cob = [], [], [], [], [], [], [], [], [], [], 0
    for k, ruta in enumerate(archivos):
        z = np.load(ruta)
        n = len(z["X"])
        sin_cob += not bool(z["con_cobertura"])
        if not n: continue
        X.append(z["X"]); lat.append(z["lat"]); lon.append(z["lon"]); pend.append(z["pendiente"]); rug.append(z["rugosidad"]); llana.append(z["llana"])
        dom.append(z["dominante"]); cen.append(z["centros"]); tes.append(np.full(n, k)); franja += [str(z["franja"])] * n
    X, lat, lon, pend, rug, llana, dom, tes, cen = (np.concatenate(v) for v in (X, lat, lon, pend, rug, llana, dom, tes, cen))
    base = Base(X); tipica, limite = base.vecindad()
    n_cand = max(a.candidatos, int(round(a.fraccion * len(X))))
    decir(f"Pasan a la etapa de forma los {n_cand} cuadros más parecidos de cada sitio.")
    decir(f"Base terrestre: {len(X)} cuadros de {len(archivos)} teselas ({sin_cob} sin mapa de cobertura). Distancia típica entre vecinos: {tipica:.4f}")

    abierta = {}
    def relieve_de(i):
        k = int(tes[i])
        if k not in abierta:
            if len(abierta) > 40: abierta.clear()
            abierta[k] = np.load(archivos[k])["H"]
        m = a.tam_px // 2
        return abierta[k][cen[i][0] - m: cen[i][0] - m + a.tam_px, cen[i][1] - m: cen[i][1] - m + a.tam_px]

    filas, resumen, recortes = [], [], {}
    for sid, s in sitios.items():
        cerca = np.argsort(base.distancias(s["vector"]), kind="stable")[:n_cand]
        ventanas = {int(i): relieve_de(int(i)).copy() for i in sorted(cerca, key=lambda i: tes[i])}      # se leen tesela a tesela, no saltando entre ellas
        r = regiones(puntuar_sitio(base, s, ventanas.__getitem__, candidatos=n_cand, fisica=a.fisica), lat, lon, a.radio_km)[: a.top]
        dmin = float(base.distancias(s["vector"]).min())
        resumen.append({"sitio": sid, **{c: round(float(v), 6) for c, v in zip(CARACTERISTICAS, s["vector"])},
                        "dist_fisica_min": round(dmin, 6), "veces_la_tipica": round(dmin / tipica, 2) if tipica > 0 else "", "fuera_de_rango": dmin > limite})
        recortes[f"sitio__{sid}"] = s["relieve"].astype("float32")
        for puesto, f in enumerate(r, start=1):
            i = f["indice"]
            filas.append({"sitio": sid, "puesto": puesto, "lat": round(float(lat[i]), 5), "lon": round(float(lon[i]), 5), "franja": franja[i],
                          "score": round(f["score"], 6), "fisica_rms": round(f["fisica_rms"], 6), "fisica_01": round(f["fisica_01"], 6), "dist_fisica": round(f["dist_fisica"], 6),
                          "corr": round(f["corr"], 4), "rot": f["rot"], "pendiente_media": round(float(pend[i]), 2), "rugosidad_m": round(float(rug[i]), 2),
                          "frac_llana": round(float(llana[i]), 3), "cuadros_region": f["cuadros"], "cobertura": CLASES.get(int(dom[i]), str(int(dom[i]))),
                          "tesela": os.path.basename(archivos[int(tes[i])]).split("_DEM")[0]})
            if puesto <= 5: recortes[f"cand__{sid}__{puesto}"] = ventanas[i].astype("float32")
        m = r[0] if r else None
        decir(f"  {sid:<12} mejor: " + (f"{lat[m['indice']]:.3f}, {lon[m['indice']]:.3f} · score {m['score']:.3f} · corr {m['corr']:.2f}" if m else "sin candidatos")
              + (" · FUERA DE RANGO: ningún cuadro barrido se le acerca" if dmin > limite else ""))

    def guardar_csv(nombre, datos):
        if not datos: return
        with open(os.path.join(a.salida, nombre), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(datos[0])); w.writeheader(); w.writerows(datos)
    guardar_csv(f"candidatos_{a.cuerpo}.csv", filas)
    guardar_csv(f"sitios_{a.cuerpo}.csv", resumen)
    np.savez_compressed(os.path.join(a.salida, f"recortes_{a.cuerpo}.npz"), **recortes)
    meta = {"cuerpo": a.cuerpo, "res_m": a.res, "tam_px": a.tam_px, "solape": a.solape, "candidatos": n_cand, "radio_km": a.radio_km,
            "fuente_sitios": "GeoTIFF propios" if a.sitios else FUENTE_SITIOS[a.cuerpo]["nombre"],
            "fuente_relieve": f"Copernicus DEM ({a.dem}) vía Microsoft Planetary Computer",
            "fuente_cobertura": "ESA WorldCover 2021 vía Microsoft Planetary Computer" if a.cobertura else None,
            "clases_excluidas": [CLASES.get(c, str(c)) for c in a.excluir] if a.cobertura else [],
            "franjas": {n: list(c) for n, c in cajas.items()}, "teselas": len(archivos), "teselas_fallidas": fallos, "teselas_sin_cobertura": int(sin_cob),
            "cuadros": int(len(X)), "distancia_tipica": tipica, "limite_fuera_de_rango": limite, "sitios": list(sitios),
            "fisica": a.fisica,
            "puntaje": ("0,5 × diferencia en los 8 rasgos (raíz de la distancia física) + 0,5 × (1 − correlación de forma) / 2; menor es mejor" if a.fisica == "distancia"
                        else "0,5 × percentil físico + 0,5 × (1 − correlación de forma) / 2; menor es mejor")}
    json.dump(meta, open(os.path.join(a.salida, f"meta_{a.cuerpo}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    decir(f"Listo en {time.time() - t0:.0f} s. Archivos en {a.salida}/: candidatos_{a.cuerpo}.csv, sitios_{a.cuerpo}.csv, recortes_{a.cuerpo}.npz, meta_{a.cuerpo}.json")


if __name__ == "__main__":
    main()
