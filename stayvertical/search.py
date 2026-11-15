"""Búsqueda de gemelos: normalización, índice exacto y pasadas grueso→fino."""

import numpy as np
from scipy.spatial import cKDTree

from .features import (PESOS, mapas_pixel, vector_8, reducir, tabla_cuadros)


class Normalizador:
    """Mediana/IQR compartidos entre cuerpos, para que sean comparables."""

    def ajustar(self, *tablas):
        X = np.vstack(tablas)
        self.mediana = np.median(X, axis=0)
        q75, q25 = np.percentile(X, [75, 25], axis=0)
        iqr = q75 - q25
        self.escala = np.where(iqr > 0, iqr, 1.0)
        return self

    def __call__(self, X):
        """Normaliza y aplica los pesos: la distancia euclídea resultante es
        la distancia cuadrática ponderada del notebook (en raíz)."""
        return (np.atleast_2d(X) - self.mediana) / self.escala * np.sqrt(PESOS)


class Indice:
    """Vecino más cercano EXACTO (KD-tree) sobre una tabla de cuadros."""

    def __init__(self, X, norm):
        self.norm = norm
        self.arbol = cKDTree(norm(X))

    def vecinos(self, consulta, k=10):
        d, i = self.arbol.query(self.norm(consulta)[0], k=k)
        return np.atleast_1d(d), np.atleast_1d(i)


def vector_cuadro(H, res_m):
    """Las 8 características de un cuadro suelto (p. ej. el sitio lunar)."""
    return vector_8(*mapas_pixel(H, res_m))


def buscar_grueso_fino(H, res_m, objetivo, tam_km, factor=4, fraccion=0.1,
                       k=10, mascara=None):
    """Busca en el DEM `H` los cuadros que se parecen a `objetivo`.

    1. Pasada gruesa: DEM reducido `factor` veces, todos los cuadros.
    2. Se conserva la `fraccion` más parecida.
    3. Pasada fina: solo esos cuadros se recalculan a la resolución original.

    `objetivo` es el DEM del cuadro a imitar, a la misma resolución que `H`.
    Devuelve (resultados, estadisticas).
    """
    res_g = res_m * factor
    Hg = reducir(H, factor)
    mg = None
    if mascara is not None:
        mg = reducir(mascara.astype(float), factor) > 0.5
    Xg, cg, _ = tabla_cuadros(Hg, res_g, tam_km, mascara=mg)
    if len(Xg) == 0:
        return [], {"gruesos": 0, "finos": 0}

    obj_g = vector_cuadro(reducir(objetivo, factor), res_g)
    ng = Normalizador().ajustar(Xg)
    orden = np.argsort(((ng(Xg) - ng(obj_g)) ** 2).sum(axis=1))
    conservar = orden[: max(int(len(Xg) * fraccion), k)]

    # Pasada fina: solo los cuadros conservados.
    tam = max(int(round(tam_km * 1000.0 / res_m)), 6)
    mitad = tam // 2
    Xf, centros = [], []
    for idx in conservar:
        fi, fj = int(cg[idx][0]) * factor, int(cg[idx][1]) * factor
        i0, j0 = fi - mitad, fj - mitad
        if i0 < 0 or j0 < 0 or i0 + tam > H.shape[0] or j0 + tam > H.shape[1]:
            continue
        v = vector_cuadro(H[i0:i0 + tam, j0:j0 + tam], res_m)
        if v is None:
            continue
        Xf.append(v)
        centros.append((fi, fj))
    if not Xf:
        return [], {"gruesos": len(Xg), "finos": 0}
    Xf = np.array(Xf)

    obj_f = vector_cuadro(objetivo, res_m)
    nf = Normalizador().ajustar(Xf)
    d, i = Indice(Xf, nf).vecinos(obj_f, k=min(k, len(Xf)))
    resultados = [{"centro": centros[j], "distancia": float(dd)}
                  for dd, j in zip(np.atleast_1d(d), np.atleast_1d(i))]
    return resultados, {"gruesos": len(Xg), "finos": len(Xf)}
