"""Barrido de franjas de la Tierra: el algoritmo, no una lista a mano, decide dónde están los candidatos.

Este módulo no descarga nada. Recibe teselas ya leídas (un DEM en metros sobre una cuadrícula local) y:

1. `parches_de_tesela`  calcula las 8 características de todos los cuadros de una tesela.
2. `Base`               junta los cuadros de todas las teselas y los normaliza (mediana e IQR terrestres).
3. `puntuar_sitio`      etapa física (distancia a los 8 rasgos) + etapa de forma (correlación con rotaciones)
                        sobre los `candidatos` más cercanos, con el mismo puntaje que usa el equipo:
                        0,5 × percentil físico + 0,5 × (1 − correlación) / 2. Menor es mejor.
4. `regiones`           agrupa cuadros vecinos para no contar el mismo paisaje varias veces.

La descarga (Copernicus DEM y ESA WorldCover) está en scripts/barrido.py.
"""

import numpy as np
from scipy.spatial import cKDTree

from .features import mapas_pixel, vector_8, ficha, tabla_cuadros
from .regions import agrupar
from .search import Normalizador

# Clases de ESA WorldCover que no pueden ser análogo de la Luna ni de Marte:
# bosque (10), cultivos (40), construido (50), agua (80), humedal (90) y manglar (95).
CLASES_EXCLUIDAS = (10, 40, 50, 80, 90, 95)
CLASES = {0: "sin dato", 10: "bosque", 20: "matorral", 30: "pastizal", 40: "cultivos", 50: "construido",
          60: "suelo desnudo o vegetación escasa", 70: "nieve y hielo", 80: "agua", 90: "humedal",
          95: "manglar", 100: "musgo y liquen"}


def ventana_central(A, tam):
    """El cuadro de `tam` × `tam` píxeles del centro de `A`."""
    i0, j0 = (A.shape[0] - tam) // 2, (A.shape[1] - tam) // 2
    if i0 < 0 or j0 < 0:
        raise ValueError(f"El DEM del sitio ({A.shape}) es menor que el cuadro ({tam} px).")
    return A[i0:i0 + tam, j0:j0 + tam]


def sitio_desde_dem(H, res_m, tam_px):
    """Vector de 8 rasgos, ficha y relieve del cuadro central de un sitio (Luna o Marte).

    Los rasgos se calculan sobre todo el DEM (con su borde) y se resumen solo en el cuadro central,
    igual que en el cuaderno del equipo.
    """
    H = np.asarray(H, dtype=float)
    p, c, r = (ventana_central(m, tam_px) for m in mapas_pixel(H, res_m))
    v = vector_8(p, c, r)
    if v is None:
        raise ValueError("El cuadro central del sitio no tiene píxeles válidos.")
    return {"vector": v, "ficha": ficha(p, r), "relieve": ventana_central(H, tam_px).copy()}


def parches_de_tesela(H, res_m, tam_px, solape=0.5, clases=None, excluir=CLASES_EXCLUIDAS, min_validos=0.85):
    """Las 8 características de todos los cuadros de una tesela.

    `clases` es el mapa de cobertura (códigos de ESA WorldCover) sobre la misma cuadrícula; los píxeles de las
    clases de `excluir` no cuentan, y un cuadro con menos de `min_validos` de píxeles útiles se descarta.
    Devuelve (X, centros, fichas, dominante): `dominante` es la clase de cobertura más frecuente de cada cuadro.
    """
    mascara = np.isin(clases, excluir) if clases is not None else None
    if not np.isfinite(H).any():
        return np.empty((0, 8)), np.empty((0, 2), dtype=int), [], np.empty(0, dtype=int)
    X, centros, fichas = tabla_cuadros(H, res_m, tam_px * res_m / 1000.0, solape=solape, mascara=mascara, min_validos=min_validos)
    dominante = np.zeros(len(X), dtype=int)
    if clases is not None and len(X):
        m = tam_px // 2
        for k, (i, j) in enumerate(centros):
            v = clases[i - m:i - m + tam_px, j - m:j - m + tam_px].ravel()
            dominante[k] = np.bincount(v, minlength=101).argmax()
    return (X.reshape(-1, 8), np.asarray(centros, dtype=int).reshape(-1, 2), fichas, dominante)


def _sin_plano(Z):
    """Quita la inclinación general (mejor plano) y los huecos; devuelve el relieve centrado."""
    Z = np.asarray(Z, dtype=float)
    ok = np.isfinite(Z)
    if ok.sum() < 3:
        return np.zeros_like(Z)
    yy, xx = np.mgrid[:Z.shape[0], :Z.shape[1]]
    A = np.column_stack([xx[ok], yy[ok], np.ones(ok.sum())])
    coef, *_ = np.linalg.lstsq(A, Z[ok], rcond=None)
    R = Z - (coef[0] * xx + coef[1] * yy + coef[2])
    R[~ok] = 0.0
    return R


def correlacion_forma(a, b):
    """Mayor correlación entre dos relieves sin su inclinación, probando giros de 0, 90, 180 y 270°.

    Devuelve (correlación, giro en grados).
    """
    A = _sin_plano(a)
    na = np.sqrt((A ** 2).sum())
    mejor = (-1.0, 0)
    for k in range(4):
        B = _sin_plano(np.rot90(b, k))
        nb = np.sqrt((B ** 2).sum())
        c = float((A * B).sum() / (na * nb)) if na > 0 and nb > 0 else 0.0
        if c > mejor[0]:
            mejor = (c, 90 * k)
    return mejor


class Base:
    """Todos los cuadros terrestres del barrido, normalizados con su propia mediana e IQR."""

    def __init__(self, X):
        self.X = np.asarray(X, dtype=float).reshape(-1, 8)
        if len(self.X) < 2:
            raise ValueError("El barrido no produjo cuadros suficientes.")
        self.norm = Normalizador().ajustar(self.X)
        self.XN = self.norm(self.X)

    def distancias(self, vector):
        """Distancia física de cada cuadro al sitio: Σ peso × (diferencia normalizada)²."""
        return ((self.XN - self.norm(vector)) ** 2).sum(axis=1)

    def vecindad(self, muestra=5000, semilla=0):
        """Distancia de un cuadro terrestre a su vecino más parecido: (mediana, percentil 99) sobre una muestra.

        La mediana es la distancia "típica". El percentil 99 sirve de límite: un sitio cuyo cuadro más parecido
        queda más lejos que eso está fuera del rango de lo barrido (se extrapola).
        """
        rng = np.random.default_rng(semilla)
        idx = rng.choice(len(self.XN), size=min(muestra, len(self.XN)), replace=False)
        d, _ = cKDTree(self.XN).query(self.XN[idx], k=2)
        return float(np.median(d[:, 1] ** 2)), float(np.percentile(d[:, 1] ** 2, 99))


def puntuar_sitio(base, sitio, relieve_de, candidatos=500, peso_fisico=0.5):
    """Etapa física + etapa de forma para un sitio.

    `relieve_de(i)` devuelve el relieve (tam × tam) del cuadro `i` de la base.
    Devuelve una lista de dicts ordenada por puntaje: indice, dist_fisica, fisica_01, corr, rot, score.
    """
    d = base.distancias(sitio["vector"])
    orden = np.argsort(d, kind="stable")
    salida = []
    for puesto, i in enumerate(orden[:candidatos]):
        corr, rot = correlacion_forma(sitio["relieve"], relieve_de(int(i)))
        fis = puesto / len(d)                                   # percentil dentro de TODA la base
        salida.append({"indice": int(i), "dist_fisica": float(d[i]), "fisica_01": float(fis), "corr": corr, "rot": rot,
                       "score": float(peso_fisico * fis + (1 - peso_fisico) * (1 - corr) / 2)})
    return sorted(salida, key=lambda r: r["score"])


def a_km(lat, lon):
    """Coordenadas planas aproximadas en km (solo para medir vecindad entre cuadros cercanos)."""
    lat, lon = np.asarray(lat, dtype=float), np.asarray(lon, dtype=float)
    return np.column_stack([lon * 111.32 * np.cos(np.radians(lat)), lat * 110.57])


def regiones(filas, lat, lon, radio_km):
    """Deja un cuadro por región: de los cuadros a `radio_km` o menos entre sí, el de mejor puntaje.

    `filas` es la salida de `puntuar_sitio`; `lat` y `lon` son los de toda la base.
    Añade a cada fila `cuadros` (tamaño de su región) y devuelve las filas elegidas, ordenadas por puntaje.
    """
    if not filas:
        return []
    idx = np.array([f["indice"] for f in filas])
    etiquetas = agrupar(a_km(lat[idx], lon[idx]), radio_km)
    elegidas = {}
    for f, e in zip(filas, etiquetas):                          # filas ya viene ordenada: el primero de cada región es el mejor
        if e not in elegidas:
            elegidas[e] = {**f, "cuadros": 0}
        elegidas[e]["cuadros"] += 1
    return sorted(elegidas.values(), key=lambda r: r["score"])
