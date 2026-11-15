"""Búsqueda rápida APROXIMADA con algoritmo genético (modo opcional).

Un individuo es una posición (fila, columna). La función `costo` la evalúa
el llamador (calcula las 8 características ahí y mide la distancia al objetivo).
Usa islas independientes para devolver varios óptimos y no uno solo.
Es estocástico: con la misma semilla da el mismo resultado.
"""

import numpy as np


def genetico(costo, limites, individuos=40, generaciones=25, islas=4,
             semilla=0, separacion=10.0, k=5):
    """Minimiza `costo((fila, col))` dentro de `limites` = (fmax, cmax).

    Devuelve (mejores, n_evaluaciones): `mejores` son hasta `k` posiciones
    separadas al menos `separacion` píxeles, de menor a mayor costo.
    """
    rng = np.random.default_rng(semilla)
    fmax, cmax = limites
    cache, evaluaciones = {}, 0

    def evaluar(p):
        nonlocal evaluaciones
        clave = (int(round(p[0])), int(round(p[1])))
        if clave not in cache:
            evaluaciones += 1
            cache[clave] = costo(clave)
        return cache[clave]

    finales = []
    for _ in range(islas):
        pob = np.column_stack([rng.uniform(0, fmax, individuos),
                               rng.uniform(0, cmax, individuos)])
        for g in range(generaciones):
            c = np.array([evaluar(p) for p in pob])
            orden = np.argsort(c)
            elite = pob[orden[: max(individuos // 4, 2)]]
            sigma = max(fmax, cmax) * 0.15 * (1 - g / generaciones) + 1.0
            hijos = []
            while len(hijos) < individuos - len(elite):
                a, b = elite[rng.integers(len(elite), size=2)]
                t = rng.uniform(0, 1)
                h = t * a + (1 - t) * b + rng.normal(0, sigma, 2)
                hijos.append(np.clip(h, [0, 0], [fmax - 1, cmax - 1]))
            pob = np.vstack([elite, hijos])
        finales.extend(pob.tolist())

    # Se queda con los mejores distintos entre sí.
    c = np.array([evaluar(p) for p in finales])
    elegidos = []
    for i in np.argsort(c):
        p = np.array(finales[i])
        if all(np.hypot(*(p - q)) >= separacion for q, _ in elegidos):
            elegidos.append((p, c[i]))
        if len(elegidos) == k:
            break
    mejores = [{"centro": (int(round(p[0])), int(round(p[1]))),
                "costo": float(cc)} for p, cc in elegidos]
    return mejores, evaluaciones
