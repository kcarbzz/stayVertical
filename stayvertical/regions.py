"""Agrupa cuadros vecinos que coinciden en regiones, con un grafo espacial."""

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree


def agrupar(centros, radio):
    """Une los cuadros a distancia <= radio (mismos píxeles que `centros`).

    Devuelve una etiqueta de región por cuadro. Evita contar como gemelos
    distintos a cuadros que son el mismo paisaje.
    """
    centros = np.asarray(centros, dtype=float)
    n = len(centros)
    if n == 0:
        return np.array([], dtype=int)
    pares = np.array(sorted(cKDTree(centros).query_pairs(radio)), dtype=int)
    if pares.size == 0:
        return np.arange(n)
    g = coo_matrix((np.ones(len(pares)), (pares[:, 0], pares[:, 1])),
                   shape=(n, n))
    return connected_components(g, directed=False)[1]


def mejor_por_region(centros, distancias, radio):
    """Una entrada por región: el cuadro más parecido y el tamaño de la región."""
    etiquetas = agrupar(centros, radio)
    salida = []
    for e in np.unique(etiquetas):
        miembros = np.where(etiquetas == e)[0]
        mejor = miembros[np.argmin(np.asarray(distancias)[miembros])]
        salida.append({"centro": tuple(np.asarray(centros)[mejor]),
                       "distancia": float(np.asarray(distancias)[mejor]),
                       "cuadros": int(len(miembros))})
    return sorted(salida, key=lambda r: r["distancia"])
