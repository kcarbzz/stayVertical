"""Las 8 características de relieve por cuadro, más la ficha de aterrizaje.

Todo se calcula con el mismo algoritmo en cualquier cuerpo, para que los
números de la Tierra, la Luna y Marte sean comparables.
"""

import numpy as np
from scipy import ndimage as ndi

CARACTERISTICAS = (
    "pendiente_media", "pendiente_std", "pendiente_p90",
    "curvatura_abs_media", "curvatura_abs_p90",
    "rugosidad_mediana", "rugosidad_p90", "rugosidad_std",
)

# Pesos del notebook: suman 1 (la curvatura pesa un poco más).
PESOS = np.array([1/9, 1/9, 1/9, 1/6, 1/6, 1/9, 1/9, 1/9])

UMBRAL_LLANO_GRADOS = 5.0


def _rellenar(H):
    """Rellena huecos con el valor válido más cercano (solo para derivar)."""
    H = np.asarray(H, dtype=np.float64)
    validos = np.isfinite(H)
    if not validos.any():
        raise ValueError("No hay elevaciones válidas.")
    if validos.all():
        return H, validos
    idx = ndi.distance_transform_edt(~validos, return_distances=False,
                                     return_indices=True)
    return H[tuple(idx)], validos


def mapas_pixel(H, res_m, ventana=5):
    """Pendiente (grados), |curvatura| (1/m) y rugosidad (m) por píxel."""
    z, validos = _rellenar(H)
    if min(z.shape) < ventana:
        raise ValueError("El mapa es demasiado pequeño.")

    zs = ndi.gaussian_filter(z, sigma=1.0, mode="reflect")
    gy, gx = np.gradient(zs, res_m)
    pendiente = np.degrees(np.arctan(np.hypot(gx, gy)))

    hxx = np.gradient(gx, res_m, axis=1)
    hyy = np.gradient(gy, res_m, axis=0)
    curvatura = np.abs(hxx + hyy)

    # Rugosidad = desviación respecto al mejor plano local (ventana x ventana).
    r = ventana // 2
    pos = np.arange(-r, r + 1, dtype=float) * res_m
    yy, xx = np.meshgrid(pos, pos, indexing="ij")
    n = ventana * ventana
    var_x, var_y = np.mean(xx ** 2), np.mean(yy ** 2)
    media = ndi.uniform_filter(z, ventana, mode="reflect")
    var_z = ndi.uniform_filter(z ** 2, ventana, mode="reflect") - media ** 2
    cov_x = ndi.correlate(z, xx / n, mode="reflect")
    cov_y = ndi.correlate(z, yy / n, mode="reflect")
    resid = var_z - cov_x ** 2 / var_x - cov_y ** 2 / var_y
    rugosidad = np.sqrt(np.clip(resid, 0.0, None))

    for m in (pendiente, curvatura, rugosidad):
        m[~validos] = np.nan
    return pendiente, curvatura, rugosidad


def vector_8(pendiente, curvatura, rugosidad):
    """Resume los mapas de un cuadro en las 8 características."""
    p, c, r = (a[np.isfinite(a)] for a in (pendiente, curvatura, rugosidad))
    if min(p.size, c.size, r.size) == 0:
        return None
    return np.array([
        p.mean(), p.std(), np.percentile(p, 90),
        c.mean(), np.percentile(c, 90),
        np.median(r), np.percentile(r, 90), r.std(),
    ])


def ficha(pendiente, rugosidad):
    """Datos legibles para la web: lo que importa al aterrizar y moverse."""
    p, r = pendiente[np.isfinite(pendiente)], rugosidad[np.isfinite(rugosidad)]
    return {
        "pendiente_media": float(p.mean()),
        "frac_llana": float((p < UMBRAL_LLANO_GRADOS).mean()),
        "rugosidad_m": float(np.median(r)),
    }


def reducir(H, factor):
    """Baja la resolución promediando bloques (pasada gruesa)."""
    if factor == 1:
        return np.asarray(H, dtype=float)
    f = int(factor)
    h, w = (np.asarray(H).shape[0] // f) * f, (np.asarray(H).shape[1] // f) * f
    B = np.asarray(H, dtype=float)[:h, :w].reshape(h // f, f, w // f, f)
    with np.errstate(all="ignore"):
        return np.nanmean(B, axis=(1, 3))


def tabla_cuadros(H, res_m, tam_km, solape=0.5, mascara=None, min_validos=0.85):
    """Divide el DEM en cuadros y calcula sus 8 características.

    Devuelve (X, centros, fichas): X es (N, 8); centros son (fila, col) en
    píxeles del DEM; fichas es una lista de dicts. Un cuadro se descarta si
    menos de `min_validos` de sus píxeles son válidos (y no están en la
    máscara; mascara=True significa "excluir": océano, bosque denso...).
    """
    pend, curv, rug = mapas_pixel(H, res_m)
    tam = max(int(round(tam_km * 1000.0 / res_m)), 6)
    paso = max(int(round(tam * (1.0 - solape))), 1)
    filas, cols = pend.shape
    X, centros, fichas = [], [], []
    for i in range(0, filas - tam + 1, paso):
        for j in range(0, cols - tam + 1, paso):
            s = (slice(i, i + tam), slice(j, j + tam))
            p, c, r = pend[s], curv[s], rug[s]
            ok = np.isfinite(p)
            if mascara is not None:
                ok &= ~mascara[s]
            if ok.mean() < min_validos:
                continue
            p, c, r = (np.where(ok, a, np.nan) for a in (p, c, r))
            v = vector_8(p, c, r)
            if v is None:
                continue
            X.append(v)
            centros.append((i + tam // 2, j + tam // 2))
            fichas.append(ficha(p, r))
    return np.array(X), np.array(centros), fichas


def aptitud(f):
    """Aptitud provisional para 'aterrizar y moverse' (0 a 1).

    Combina fracción llana (más es mejor), pendiente media y rugosidad
    (menos es mejor). Es un criterio de RELIEVE: no considera iluminación,
    hielo ni visibilidad de la Tierra. Los umbrales son provisionales y deben
    validarse contra criterios publicados antes de presentarlos como oficiales.
    """
    llana = f["frac_llana"]
    pend = 1.0 - min(f["pendiente_media"] / 15.0, 1.0)
    rug = 1.0 - min(f["rugosidad_m"] / 5.0, 1.0)
    return float(0.5 * llana + 0.3 * pend + 0.2 * rug)
