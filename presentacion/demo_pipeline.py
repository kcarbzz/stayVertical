"""Demostración en vivo del pipeline de visión de Stay Vertical.

Corre el motor real (stayvertical/) sobre imágenes de prueba que ya están en el repositorio,
sin descargar nada, y muestra cada paso del procesamiento:

  0. Entrada        el sitio de referencia (recorte LOLA de 3 km a 80 m/px) y las imágenes de prueba (DEM terrestres a 80 m/px)
  1. Preproceso     relleno de huecos con la transformada de distancia y suavizado gaussiano
  2. Descriptores   pendiente (gradiente), curvatura (laplaciano) y rugosidad (residuo del plano local)
  3. Ventanas       ventana deslizante de 3 km con 50 % de solape → un vector de 8 rasgos por ventana
  4. Nivel 1        normalización mediana/IQR y distancia ponderada al sitio (vecino más cercano)
  5. Nivel 2        correlación cruzada normalizada (NCC) sin plano, probando 4 giros, solo en los finalistas
  6. Ranking        puntaje 0,5 × físico + 0,5 × forma, y supresión de no máximos

Uso (desde la raíz del repositorio):

  python presentacion/demo_pipeline.py                       # Malapert contra las 50 imágenes de prueba
  python presentacion/demo_pipeline.py --sitio haworth
  python presentacion/demo_pipeline.py --imagen data/resultados/tierra_Teide.tif   # una sola imagen
  python presentacion/demo_pipeline.py --control             # prueba de control: recortar, girar y volver a encontrar
  python presentacion/demo_pipeline.py --mostrar             # además abre cada figura en una ventana

Las figuras quedan en presentacion/salida/. Requiere numpy, scipy, matplotlib y tifffile.
"""

import argparse
import glob
import os
import sys
import time

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import matplotlib                                                     # noqa: E402
if "--mostrar" not in sys.argv:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt                                       # noqa: E402
import logging                                                        # noqa: E402
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
from matplotlib.colors import LightSource                            # noqa: E402
from matplotlib.patches import Rectangle                             # noqa: E402
import tifffile                                                      # noqa: E402
from scipy import ndimage as ndi                                     # noqa: E402

from stayvertical.features import CARACTERISTICAS, _rellenar, mapas_pixel   # noqa: E402
from stayvertical.barrido import (Base, _sin_plano, _suavizar, correlacion_forma,  # noqa: E402
                                  parches_de_tesela, puntuar_sitio, sitio_desde_dem)

RES_M, TAM = 80.0, 38                     # 80 m por píxel; 38 px ≈ 3 km
SALIDA = os.path.join(RAIZ, "presentacion", "salida")

# Paleta de la presentación
NAVY, GOLD, INK, MUTED, CREAM = "#16203A", "#E8B13A", "#16203A", "#4A5470", "#FFFFFF"
plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
    "font.size": 11, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlecolor": INK,
    "axes.edgecolor": "#B7C2E0", "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "figure.facecolor": CREAM, "axes.facecolor": CREAM, "savefig.facecolor": CREAM,
})
NOMBRES_CORTOS = ["pend. media", "pend. desv.", "pend. p90", "curv. media", "curv. p90",
                  "rug. mediana", "rug. p90", "rug. desv."]


# ----------------------------------------------------------------------------- utilidades

def paso(n, titulo):
    print(f"\n\033[1;33mPASO {n}\033[0m  {titulo}")


def relieve(ax, Z, titulo=None, cmap="gist_earth", barra=False):
    """Dibuja un DEM con sombreado (hillshade) para que la forma se lea a simple vista."""
    Zf = np.where(np.isfinite(Z), Z, np.nanmean(Z))
    ls = LightSource(azdeg=315, altdeg=40)
    rgb = ls.shade(Zf, cmap=plt.get_cmap(cmap), blend_mode="soft", vert_exag=2.0,
                   dx=RES_M, dy=RES_M)
    ax.imshow(rgb)
    if barra:
        im = ax.imshow(Zf, cmap=cmap, alpha=0)
        cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        cb.set_label("altura (m)")
    ax.set_xticks([]); ax.set_yticks([])
    if titulo:
        ax.set_title(titulo)


def mapa(ax, M, titulo, cmap, etiqueta, vmax_pct=99):
    im = ax.imshow(M, cmap=cmap, vmin=np.nanpercentile(M, 1), vmax=np.nanpercentile(M, vmax_pct))
    cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label(etiqueta)
    ax.set_title(titulo); ax.set_xticks([]); ax.set_yticks([])


def guardar(fig, nombre, mostrar):
    os.makedirs(SALIDA, exist_ok=True)
    ruta = os.path.join(SALIDA, nombre)
    fig.savefig(ruta, dpi=200, bbox_inches="tight")
    print(f"   figura → {os.path.relpath(ruta, RAIZ)}")
    if mostrar:
        plt.show()
    plt.close(fig)


def nombre_imagen(ruta):
    return os.path.basename(ruta).replace("tierra_", "").replace(".tif", "")


def cargar_sitio(nombre):
    d = np.load(os.path.join(RAIZ, "data", "barrido", "recortes_luna.npz"))
    clave = f"sitio__{nombre}"
    if clave not in d:
        sitios = sorted(k.split("__")[1] for k in d if k.startswith("sitio__"))
        raise SystemExit(f"Sitio desconocido: {nombre}. Opciones: {', '.join(sitios)}")
    return d[clave].astype(float)


# ----------------------------------------------------------------------------- pasos

def paso_entrada(Hsitio, nombre, imagenes, total, mostrar):
    paso(0, "Entrada: el DEM es una imagen de un solo canal (cada píxel = altura en metros)")
    print(f"   sitio lunar «{nombre}»: {Hsitio.shape[0]}×{Hsitio.shape[1]} px a {RES_M:.0f} m/px "
          f"= {Hsitio.shape[0] * RES_M / 1000:.1f} km, alturas {np.nanmin(Hsitio):.0f} a {np.nanmax(Hsitio):.0f} m")
    print(f"   imágenes de prueba (Tierra): {total} DEM de Copernicus remuestreados a {RES_M:.0f} m/px")

    H0 = imagenes[0][1]
    fig, ax = plt.subplots(1, 3, figsize=(13, 4.2), gridspec_kw={"width_ratios": [1, 1, 1.05]})
    relieve(ax[0], Hsitio, f"Sitio: {nombre.capitalize()} (Luna)\n{Hsitio.shape[0]}×{Hsitio.shape[1]} px · 3 km")
    relieve(ax[1], H0, f"Imagen de prueba: {imagenes[0][0]}\n{H0.shape[0]}×{H0.shape[1]} px · "
                       f"{H0.shape[0] * RES_M / 1000:.0f} km")
    # Zoom a los valores crudos: la imagen es una matriz de alturas
    i0, j0 = H0.shape[0] // 2, H0.shape[1] // 2
    Z = H0[i0:i0 + 6, j0:j0 + 6]
    ax[2].imshow(Z, cmap="gist_earth")
    for (i, j), v in np.ndenumerate(Z):
        ax[2].text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=9.5,
                   color="white" if v < Z.mean() else NAVY, fontweight="bold")
    ax[2].set_title("Zoom 6×6 px: valores del píxel\n(metros sobre el nivel de referencia)")
    ax[2].set_xticks([]); ax[2].set_yticks([])
    rect = Rectangle((j0 - 0.5, i0 - 0.5), 6, 6, fill=False, ec=GOLD, lw=2.5)
    ax[1].add_patch(rect)
    fig.tight_layout()
    guardar(fig, "paso0_entrada.png", mostrar)


def paso_preproceso(mostrar):
    paso(1, "Preproceso: rellenar huecos (transformada de distancia) y suavizado gaussiano σ = 1 px")
    H = tifffile.imread(os.path.join(RAIZ, "data", "resultados", "marte_recorte_80m.tif")).astype(float)
    huecos = ~np.isfinite(H)
    print(f"   recorte de Marte con huecos: {huecos.sum()} píxeles sin dato ({huecos.mean():.1%})")
    t = time.perf_counter()
    z, validos = _rellenar(H)
    zs = ndi.gaussian_filter(z, sigma=1.0, mode="reflect")
    print(f"   relleno + suavizado en {1000 * (time.perf_counter() - t):.1f} ms")

    # Recorte alrededor de los huecos para que se vean
    ii, jj = np.where(huecos)
    ci, cj = int(np.median(ii)), int(np.median(jj))
    r = 30
    s = (slice(max(ci - r, 0), ci + r), slice(max(cj - r, 0), cj + r))
    fig, ax = plt.subplots(1, 3, figsize=(13, 4.4))
    vmin, vmax = np.nanpercentile(H[s], 1), np.nanpercentile(H[s], 99)
    A = np.ma.masked_invalid(H[s])
    cm = plt.get_cmap("gist_earth").copy(); cm.set_bad("#E5484D")
    ax[0].imshow(A, cmap=cm, vmin=vmin, vmax=vmax)
    ax[0].set_title(f"1a · Original con huecos (rojo)\n{huecos.sum()} px sin dato")
    ax[1].imshow(z[s], cmap="gist_earth", vmin=vmin, vmax=vmax)
    ax[1].contour(huecos[s], levels=[0.5], colors=[GOLD], linewidths=1.5)
    ax[1].set_title("1b · Relleno con el vecino válido\nmás cercano (distance_transform_edt)")
    ax[2].imshow(zs[s], cmap="gist_earth", vmin=vmin, vmax=vmax)
    ax[2].set_title("1c · Suavizado gaussiano σ = 1 px\n(quita ruido antes de derivar)")
    for a in ax:
        a.set_xticks([]); a.set_yticks([])
    fig.tight_layout()
    guardar(fig, "paso1_preproceso.png", mostrar)


def paso_descriptores(nombre_img, H, mostrar):
    paso(2, "Descriptores por píxel: gradiente → pendiente, laplaciano → curvatura, residuo del plano → rugosidad")
    t = time.perf_counter()
    p, c, r = mapas_pixel(H, RES_M)
    print(f"   3 mapas de {H.shape[0]}×{H.shape[1]} px en {1000 * (time.perf_counter() - t):.1f} ms "
          f"(pendiente media {np.nanmean(p):.1f}°, rugosidad mediana {np.nanmedian(r):.1f} m)")
    fig, ax = plt.subplots(1, 4, figsize=(17, 4.2))
    relieve(ax[0], H, f"Entrada: {nombre_img}")
    mapa(ax[1], p, r"Pendiente = $\arctan\,\|\nabla z\|$", "magma", "grados")
    mapa(ax[2], c, r"Curvatura = $|\nabla^2 z|$", "viridis", "1/m", vmax_pct=98)
    mapa(ax[3], r, "Rugosidad = residuo del plano 5×5", "cividis", "metros", vmax_pct=98)
    fig.tight_layout()
    guardar(fig, "paso2_descriptores.png", mostrar)
    return p, c, r


def paso_ventanas(imagenes, nombre_img, H, mostrar):
    paso(3, f"Ventana deslizante de {TAM} px ({TAM * RES_M / 1000:.1f} km) con 50 % de solape → 8 rasgos por ventana")
    t = time.perf_counter()
    X, centros, origen = [], [], []
    for k, (nom, Hk) in enumerate(imagenes):
        Xk, ck, _, _ = parches_de_tesela(Hk, RES_M, TAM, solape=0.5)
        X.append(Xk); centros.append(ck); origen += [k] * len(Xk)
    X, centros, origen = np.vstack(X), np.vstack(centros), np.array(origen)
    print(f"   {len(X)} ventanas en {len(imagenes)} imágenes, en {time.perf_counter() - t:.2f} s")

    # Figura: rejilla de ventanas sobre la imagen elegida + el vector de una ventana
    k_img = [n for n, _ in imagenes].index(nombre_img)
    sel = np.where(origen == k_img)[0]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1, 1.25]})
    relieve(ax[0], H, f"{nombre_img}: {len(sel)} ventanas de {TAM}×{TAM} px, paso {TAM // 2} px")
    for n, (ci, cj) in enumerate(centros[sel]):
        ax[0].add_patch(Rectangle((cj - TAM // 2 - 0.5, ci - TAM // 2 - 0.5), TAM, TAM, fill=False,
                                  ec="white", lw=0.8, alpha=0.75))
    ci, cj = centros[sel[len(sel) // 2]]
    ax[0].add_patch(Rectangle((cj - TAM // 2 - 0.5, ci - TAM // 2 - 0.5), TAM, TAM, fill=False, ec=GOLD, lw=3))
    v = X[sel[len(sel) // 2]]
    colores = [NAVY] * 3 + ["#2F6DB5"] * 2 + [GOLD] * 3
    escala = np.median(X, axis=0)
    ax[1].barh(range(8), v / escala, color=colores)
    for i, val in enumerate(v):
        txt = f"{val:.2e}" if val < 0.01 else f"{val:.2f}"
        ax[1].text(v[i] / escala[i] + 0.03, i, txt, va="center", fontsize=10, color=INK)
    ax[1].set_yticks(range(8)); ax[1].set_yticklabels(NOMBRES_CORTOS)
    ax[1].invert_yaxis()
    ax[1].set_xlabel("valor relativo a la mediana de todas las ventanas")
    ax[1].set_title("Vector de 8 rasgos de la ventana dorada (pooling)")
    ax[1].spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    guardar(fig, "paso3_ventanas.png", mostrar)
    return X, centros, origen


def paso_nivel1(sitio, base, X, mostrar, finalistas):
    paso(4, "Nivel 1: normalizar (mediana, IQR) y ordenar por distancia ponderada en 8 dimensiones")
    t = time.perf_counter()
    d = base.distancias(sitio["vector"])
    orden = np.argsort(d)
    print(f"   {len(d)} distancias en {1000 * (time.perf_counter() - t):.2f} ms; pasan {finalistas} finalistas "
          f"a la etapa de forma (distancia ≤ {d[orden[finalistas - 1]]:.4f})")
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.4), gridspec_kw={"width_ratios": [1.15, 1]})
    vs = base.norm(sitio["vector"])[0]
    vc = base.XN[orden[0]]
    vl = base.XN[orden[-1]]
    x = np.arange(8)
    ax[0].bar(x - 0.27, vs, 0.27, color=GOLD, label="sitio lunar")
    ax[0].bar(x, vc, 0.27, color=NAVY, label="ventana más cercana")
    ax[0].bar(x + 0.27, vl, 0.27, color="#B7C2E0", label="ventana más lejana")
    ax[0].axhline(0, color=MUTED, lw=0.8)
    ax[0].set_xticks(x); ax[0].set_xticklabels(NOMBRES_CORTOS, rotation=35, ha="right")
    ax[0].set_ylabel("(x − mediana) / IQR × √peso")
    ax[0].set_title("Vectores normalizados: el sitio y dos ventanas")
    ax[0].legend(frameon=False, fontsize=10)
    ax[0].spines[["top", "right"]].set_visible(False)
    ax[1].hist(np.log10(d + 1e-9), bins=40, color="#B7C2E0", edgecolor="white")
    corte = np.log10(d[orden[finalistas - 1]] + 1e-9)
    ax[1].axvline(corte, color=GOLD, lw=2.5)
    ax[1].text(corte, ax[1].get_ylim()[1] * 0.92, f"  top {finalistas}\n  pasan a nivel 2", color=INK,
               fontsize=10, va="top")
    ax[1].set_xlabel("log₁₀ distancia al sitio")
    ax[1].set_ylabel("número de ventanas")
    ax[1].set_title(f"Distancia de las {len(d)} ventanas al sitio")
    ax[1].spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    guardar(fig, "paso4_nivel1.png", mostrar)
    return d, orden


def paso_nivel2(sitio, relieve_de, mejor, nombre_mejor, mostrar):
    paso(5, "Nivel 2: template matching con NCC de media cero, probando giros de 0°, 90°, 180° y 270°")
    a, b = sitio["relieve"], relieve_de(mejor)
    A, B = _suavizar(_sin_plano(a)), _suavizar(_sin_plano(b))
    rhos = []
    for k in range(4):
        G = np.rot90(B, k)
        aa, bb = A - np.nanmean(A), G - np.nanmean(G)
        ok = np.isfinite(aa) & np.isfinite(bb)
        rhos.append(float(np.dot(aa[ok], bb[ok]) / (np.linalg.norm(aa[ok]) * np.linalg.norm(bb[ok]))))
    corr, rot = correlacion_forma(a, b)
    for k, rho in enumerate(rhos):
        marca = "  ← mejor" if 90 * k == rot else ""
        print(f"   giro {90 * k:>3}°: r = {rho:+.3f}{marca}")
    fig, ax = plt.subplots(2, 4, figsize=(15, 7.6))
    relieve(ax[0, 0], a, "Sitio: relieve original")
    relieve(ax[0, 1], b, f"Candidato: {nombre_mejor}")
    lim = np.nanpercentile(np.abs(A), 99)
    ax[0, 2].imshow(A, cmap="RdBu_r", vmin=-lim, vmax=lim); ax[0, 2].set_title("Sitio sin plano + gauss")
    ax[0, 3].imshow(B, cmap="RdBu_r", vmin=-lim, vmax=lim); ax[0, 3].set_title("Candidato sin plano + gauss")
    for k in range(4):
        axk = ax[1, k]
        axk.imshow(np.rot90(B, k), cmap="RdBu_r", vmin=-lim, vmax=lim)
        mejor_k = 90 * k == rot
        axk.set_title(f"giro {90 * k}°   r = {rhos[k]:+.2f}", color=GOLD if mejor_k else INK)
        if mejor_k:
            for s in axk.spines.values():
                s.set_edgecolor(GOLD); s.set_linewidth(4)
    for axk in ax.ravel():
        axk.set_xticks([]); axk.set_yticks([])
    fig.tight_layout()
    guardar(fig, "paso5_nivel2_ncc.png", mostrar)


def nms(filas, centros, origen, radio_px):
    """Supresión de no máximos: de las ventanas de la misma imagen a menos de `radio_px`, queda la mejor."""
    elegidas = []
    for f in filas:
        i = f["indice"]
        if any(origen[e["indice"]] == origen[i] and
               np.hypot(*(centros[e["indice"]] - centros[i])) < radio_px for e in elegidas):
            continue
        elegidas.append(f)
    return elegidas


def paso_ranking(sitio, nombre, filas, nombres, centros, origen, relieve_de, mostrar, top=5):
    paso(6, "Ranking: puntaje = 0,5 × diferencia física + 0,5 × (1 − r) / 2  (menor es mejor) y NMS")
    unicas = nms(filas, centros, origen, radio_px=TAM)
    print(f"   {len(filas)} finalistas → {len(unicas)} tras quitar ventanas solapadas de la misma zona")
    print(f"   {'#':>2}  {'imagen':<18} {'ventana (fila,col)':<19} {'físico':>7} {'r':>6} {'giro':>5} {'puntaje':>8}")
    for n, f in enumerate(unicas[:top], 1):
        i = f["indice"]
        print(f"   {n:>2}  {nombres[origen[i]]:<18} {str(tuple(int(v) for v in centros[i])):<19} {f['fisica_rms']:7.3f} "
              f"{f['corr']:6.2f} {f['rot']:4d}° {f['score']:8.4f}")
    fig, ax = plt.subplots(1, top + 1, figsize=(3.0 * (top + 1), 3.6))
    relieve(ax[0], sitio["relieve"], f"Sitio: {nombre.capitalize()}")
    for s in ax[0].spines.values():
        s.set_edgecolor(GOLD); s.set_linewidth(4)
    for n, f in enumerate(unicas[:top], 1):
        relieve(ax[n], np.rot90(relieve_de(f["indice"]), f["rot"] // 90),
                f"#{n} {nombres[origen[f['indice']]]}\nr = {f['corr']:.2f} · puntaje {f['score']:.3f}")
    fig.tight_layout()
    guardar(fig, "paso6_ranking.png", mostrar)
    return unicas


def prueba_control(imagenes, mostrar):
    paso("C", "Prueba de control: recorto una ventana de una imagen, la giro 90°, le cambio la inclinación y la busco")
    nom, H = next((n, h) for n, h in imagenes if n == "Teide")
    i0, j0 = 62, 48                                          # una ventana que no cae en la rejilla de 19 px
    plantilla = H[i0:i0 + TAM, j0:j0 + TAM]
    yy, xx = np.mgrid[:TAM, :TAM]
    consulta = np.rot90(plantilla, 1) + 4.0 * xx - 2.5 * yy + 1500.0
    print(f"   plantilla: {nom}, esquina (fila {i0}, col {j0}); consulta = giro 90° + plano + 1500 m")
    t = time.perf_counter()
    mejor = (-1, None, 0)
    mapa_r = np.full((H.shape[0] - TAM + 1, H.shape[1] - TAM + 1), np.nan)
    for i in range(0, mapa_r.shape[0], 2):                   # NCC densa con paso de 2 px
        for j in range(0, mapa_r.shape[1], 2):
            r, rot = correlacion_forma(consulta, H[i:i + TAM, j:j + TAM])
            mapa_r[i, j] = r
            if r > mejor[0]:
                mejor = (r, (i, j), rot)
    print(f"   NCC en {np.isfinite(mapa_r).sum()} posiciones en {time.perf_counter() - t:.1f} s")
    print(f"   máximo r = {mejor[0]:.4f} en (fila {mejor[1][0]}, col {mejor[1][1]}) con giro {mejor[2]}° "
          f"→ {'ENCONTRADA' if mejor[1] == (i0, j0) else 'no coincide'}")
    fig, ax = plt.subplots(1, 3, figsize=(13, 4.3), gridspec_kw={"width_ratios": [0.8, 1, 1.1]})
    relieve(ax[0], consulta, "Consulta: ventana girada 90°\n+ inclinación + 1500 m")
    relieve(ax[1], H, f"Imagen de búsqueda: {nom}")
    ax[1].add_patch(Rectangle((mejor[1][1] - 0.5, mejor[1][0] - 0.5), TAM, TAM, fill=False, ec=GOLD, lw=3))
    ax[1].set_title(f"Imagen de búsqueda: {nom}\nmáximo r = {mejor[0]:.3f}, giro {mejor[2]}°")
    Rp = np.where(np.isfinite(mapa_r), mapa_r, np.nan)
    Rp = Rp[::2, ::2]
    im = ax[2].imshow(Rp, cmap="RdBu_r", vmin=-1, vmax=1)
    ax[2].plot(mejor[1][1] / 2, mejor[1][0] / 2, "o", mfc="none", mec=GOLD, ms=16, mew=3)
    plt.colorbar(im, ax=ax[2], fraction=0.046, pad=0.03).set_label("r (NCC)")
    ax[2].set_title("Mapa de correlación en cada posición")
    ax[2].set_xticks([]); ax[2].set_yticks([])
    fig.tight_layout()
    guardar(fig, "control_plantilla.png", mostrar)


# ----------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sitio", default="malapert", help="sitio lunar de referencia (por defecto malapert)")
    ap.add_argument("--imagen", action="append", help="DEM de prueba (.tif a 80 m/px); repetible. "
                                                      "Por defecto, las 50 de data/resultados/")
    ap.add_argument("--muestra", default="Teide", help="imagen que se usa para dibujar los pasos 2 y 3")
    ap.add_argument("--finalistas", type=int, default=150, help="ventanas que pasan del nivel 1 al nivel 2")
    ap.add_argument("--control", action="store_true", help="solo la prueba de control con una plantilla girada")
    ap.add_argument("--mostrar", action="store_true", help="abrir cada figura en una ventana")
    args = ap.parse_args()

    rutas = args.imagen or sorted(glob.glob(os.path.join(RAIZ, "data", "resultados", "tierra_*.tif")))
    imagenes = [(nombre_imagen(r), tifffile.imread(r).astype(float)) for r in rutas]
    if not imagenes:
        raise SystemExit("No hay imágenes de prueba.")

    print("\033[1mStay Vertical · demostración del pipeline de visión\033[0m")
    t0 = time.perf_counter()
    if args.control:
        prueba_control(imagenes, args.mostrar)
        return

    Hsitio = cargar_sitio(args.sitio)
    sitio = sitio_desde_dem(Hsitio, RES_M, TAM)
    nombres = [n for n, _ in imagenes]
    muestra = args.muestra if args.muestra in nombres else nombres[0]
    Hm = dict(imagenes)[muestra]

    paso_entrada(Hsitio, args.sitio, [(muestra, Hm)], len(imagenes), args.mostrar)
    paso_preproceso(args.mostrar)
    paso_descriptores(muestra, Hm, args.mostrar)
    X, centros, origen = paso_ventanas(imagenes, muestra, Hm, args.mostrar)
    base = Base(X)

    def relieve_de(i):
        ci, cj = centros[i]
        H = imagenes[origen[i]][1]
        return H[ci - TAM // 2:ci - TAM // 2 + TAM, cj - TAM // 2:cj - TAM // 2 + TAM]

    fin = min(args.finalistas, len(X))
    paso_nivel1(sitio, base, X, args.mostrar, fin)
    t = time.perf_counter()
    filas = puntuar_sitio(base, sitio, relieve_de, candidatos=fin)
    print(f"   (puntuar_sitio: {fin} correlaciones × 4 giros en {time.perf_counter() - t:.2f} s)")
    paso_nivel2(sitio, relieve_de, filas[0]["indice"], nombres[origen[filas[0]["indice"]]], args.mostrar)
    paso_ranking(sitio, args.sitio, filas, nombres, centros, origen, relieve_de, args.mostrar)
    print(f"\nTotal: {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
