"""Auditoría de los resultados del equipo (HackNASA): ¿lo que se calculó es coherente y qué tan sólido es?

Uso:  .venv/bin/python scripts/auditoria/auditar.py --datos <z1> --revision <z2>
  <z1>: carpeta con los CSV/GeoTIFF de 'HackNASA_8_Luna_10_Marte_Resultados'
  <z2>: carpeta de 'HackNASA_Revision_18_Sitios'
Requiere numpy, scipy y tifffile (solo para el recálculo de Marte; si falta, esa parte se omite).
Solo lee datos; no ejecuta nada de los archivos.
"""
import argparse, collections, csv, os, statistics
import numpy as np
from scipy import ndimage as ndi

CAR = ['pendiente_media', 'pendiente_std', 'pendiente_p90', 'curvatura_abs_media', 'curvatura_abs_p90', 'rugosidad_mediana', 'rugosidad_p90', 'rugosidad_std']
PESOS = np.array([1 / 9] * 3 + [1 / 6] * 2 + [1 / 9] * 3)
RES, TAM, BORDE = 200.0, 15, 5
leer = lambda p: list(csv.DictReader(open(p, encoding="utf-8")))


def seccion(t): print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def estructura_del_puntaje(a):
    seccion("1. Estructura del puntaje y sensibilidad al peso físico/forma")
    for cuerpo, archivo, col in (("Luna", "rankings_8_luna_tierra_80m.csv", "sitio_lunar"), ("Marte", "rankings_10_marte_tierra_200m.csv", "sitio_marte")):
        por = collections.defaultdict(list)
        for r in leer(os.path.join(a.datos, archivo)):
            por[r[col]].append({"reg": r["region"], "fis": float(r["fisica_global_01"]), "geo": float(r["geometrica_fija_01"]), "dist": float(r["distancia_fisica"]), "score": float(r["score_final"]), "corr": float(r["corr_forma"])})
        e = next(iter(por.values()))
        print(f"\n{cuerpo}: término físico (percentil) entre 0 y {max(x['fis'] for x in e):.2f}; término de forma entre {min(x['geo'] for x in e):.2f} y {max(x['geo'] for x in e):.2f}")
        mono = all([x["fis"] for x in sorted(l, key=lambda x: x["dist"])] == sorted(x["fis"] for x in l) for l in por.values())
        print(f"  'fisica_global_01' es un percentil monótono con la distancia (no la distancia): {mono}")
        base = {s: min(l, key=lambda x: .5 * x["fis"] + .5 * x["geo"]) for s, l in por.items()}
        for w in (0.0, 0.25, 0.75, 1.0):
            gan = {s: min(l, key=lambda x: w * x["fis"] + (1 - w) * x["geo"]) for s, l in por.items()}
            print(f"  peso físico {w:.2f}: mismo ganador que con 0.5 en {sum(gan[s]['reg'] == base[s]['reg'] for s in por)}/{len(por)} sitios")
        print("  brecha #1–#2 y zonas distintas a ≤0.01 del mejor:")
        for s, l in por.items():
            l2 = sorted(l, key=lambda x: x["score"]); b = l2[0]["score"]
            print(f"    {s:<11} brecha {l2[1]['score'] - b:.4f} | zonas a ≤0.01: {len({x['reg'] for x in l2 if x['score'] - b <= 0.01})}")


def recalculo_marte(a):
    seccion("2. Recálculo independiente de la etapa física de Marte (desde los GeoTIFF)")
    try:
        import tifffile
    except ImportError:
        print("  (omitido: falta tifffile)"); return

    def caracteristicas(H, dx, dy, ventana=5):          # transcrita del cuaderno (PASO 14)
        z = np.asarray(H, dtype='float64'); valid = np.isfinite(z)
        z0 = z[tuple(ndi.distance_transform_edt(~valid, return_indices=True, return_distances=False))] if not valid.all() else z.copy()
        suave = ndi.gaussian_filter(z0, 1, mode='reflect'); gy, gx = np.gradient(suave, dy, dx)
        p = np.degrees(np.arctan(np.hypot(gx, gy)))
        cur = np.gradient(np.gradient(suave, dx, axis=1), dx, axis=1) + np.gradient(np.gradient(suave, dy, axis=0), dy, axis=0)
        r = ventana // 2; yy, xx = np.mgrid[-r:r + 1, -r:r + 1]; xx = xx * dx; yy = yy * dy; n = ventana ** 2
        vx, vy = np.mean(xx ** 2), np.mean(yy ** 2)
        mz = ndi.uniform_filter(z0, ventana, mode='reflect'); mz2 = ndi.uniform_filter(z0 * z0, ventana, mode='reflect')
        covx = ndi.correlate(z0, xx / n, mode='reflect'); covy = ndi.correlate(z0, yy / n, mode='reflect')
        rug = np.sqrt(np.maximum(mz2 - mz * mz - covx * covx / vx - covy * covy / vy, 0))
        m = ndi.uniform_filter(valid.astype(float), ventana, mode='constant', cval=0) > .999
        for arr in (p, cur, rug): arr[~m] = np.nan
        return p, cur, rug

    def vector(H):
        p, c, r = (x[BORDE:BORDE + TAM, BORDE:BORDE + TAM] for x in caracteristicas(H, RES, RES))
        ok = np.isfinite(p) & np.isfinite(c) & np.isfinite(r); pp, cc, rr = p[ok], np.abs(c[ok]), r[ok]
        return np.array([pp.mean(), pp.std(), np.percentile(pp, 90), cc.mean(), np.percentile(cc, 90), np.median(rr), np.percentile(rr, 90), rr.std()])

    vec = leer(os.path.join(a.datos, "vectores_tierra_200m.csv"))
    X = np.array([[float(r[c]) for c in CAR] for r in vec]); ids = np.array([r["parche_id"] for r in vec]); reg = np.array([r["region"] for r in vec])
    med = np.median(X, axis=0); iqr = np.percentile(X, 75, axis=0) - np.percentile(X, 25, axis=0)
    esc = np.where(iqr > 1e-12, iqr, 1.0); XN = (X - med) / esc
    dist = lambda vn, w=PESOS: ((XN - vn) ** 2 * w).sum(axis=1) / w.sum()
    rk = collections.defaultdict(list)
    for r in leer(os.path.join(a.datos, "rankings_10_marte_tierra_200m.csv")): rk[r["sitio_marte"]].append(r)
    diag = {r["sitio"]: r for r in leer(os.path.join(a.revision, "diagnostico_18_sitios.csv")) if r["cuerpo"] == "Marte"}
    V = {}
    print(f"  Base terrestre: {len(X)} parches. {'sitio':<11}{'pend. mía/equipo':>19}{'rug. mía/equipo':>18}{'|Δdist| máx':>13}{'top-500 iguales':>17}")
    for s, filas in rk.items():
        V[s] = vector(tifffile.imread(os.path.join(a.datos, "marte_geotiffs", f"marte_{s}_200m.tif")).astype("float64"))
        d = dist((V[s] - med) / esc); por_id = dict(zip(ids, d))
        mio = {ids[i] for i in np.lexsort((ids, d))[:500]}; suyo = {r["parche_id"] for r in filas}
        dmax = max(abs(por_id[r["parche_id"]] - float(r["distancia_fisica"])) for r in filas)
        print(f"  {'':<22}{s:<11}{V[s][0]:>8.2f}/{float(diag[s]['pendiente_planeta']):<8.2f}{V[s][5]:>8.2f}/{float(diag[s]['rugosidad_planeta']):<8.2f}{dmax:>12.1e}{len(mio & suyo):>14}/500")

    seccion("3. ¿Cada sitio de Marte cae dentro del rango de la base terrestre? (validez absoluta)")
    base = np.array([(lambda d: d.min())(np.where(reg == reg[i], np.inf, dist(XN[i]))) for i in range(0, len(XN), 3)])
    tip = float(np.median(base))
    print(f"  Distancia típica entre un parche terrestre y su vecino más cercano de otra zona: {tip:.4f}")
    print(f"  {'sitio':<11}{'pend.':>8}{'pctl Tierra':>13}{'rug.':>8}{'pctl Tierra':>13}{'dist. mín.':>12}{'× la típica':>13}")
    for s, v in V.items():
        dmin = dist((v - med) / esc).min()
        print(f"  {s:<11}{v[0]:>7.1f}°{(X[:, 0] < v[0]).mean() * 100:>12.0f}%{v[5]:>7.1f}m{(X[:, 5] < v[5]).mean() * 100:>12.0f}%{dmin:>12.4f}{dmin / tip:>12.1f}x")

    seccion("4. Sensibilidad de la etapa física a los pesos de los 8 rasgos")
    for nombre, w in {"iguales (1/8)": np.full(8, 1 / 8), "solo pendiente+rugosidad": np.array([1, 1, 1, 0, 0, 1, 1, 1]) / 6.0, "curvatura x2": np.array([1 / 9] * 3 + [1 / 3] * 2 + [1 / 9] * 3)}.items():
        sol = [len(set(np.argsort(dist((V[s] - med) / esc))[:50]) & set(np.argsort(dist((V[s] - med) / esc, w))[:50])) for s in V]
        print(f"  {nombre:<26} solapamiento de los 50 mejores parches: media {np.mean(sol):.0f}/50 (mín {min(sol)}, máx {max(sol)})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--datos", required=True); ap.add_argument("--revision", required=True)
    a = ap.parse_args()
    estructura_del_puntaje(a); recalculo_marte(a)
