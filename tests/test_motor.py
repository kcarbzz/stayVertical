"""Pruebas con terreno sintético (sin descargar nada)."""

import unittest

import numpy as np

from stayvertical.features import (CARACTERISTICAS, tabla_cuadros, aptitud,
                                   mapas_pixel, ficha)
from stayvertical.search import (Normalizador, Indice, vector_cuadro,
                                 buscar_grueso_fino)
from stayvertical.regions import agrupar, mejor_por_region
from stayvertical.ga import genetico

RES = 80.0


def terreno(n, amplitud, longitud, semilla):
    """Colinas suaves: amplitud (m) y longitud de onda (px) controlan el relieve."""
    rng = np.random.default_rng(semilla)
    ruido = rng.normal(size=(n, n))
    f = np.fft.fft2(ruido)
    ky, kx = np.meshgrid(np.fft.fftfreq(n), np.fft.fftfreq(n), indexing="ij")
    f *= np.exp(-(kx ** 2 + ky ** 2) * (longitud ** 2))
    z = np.real(np.fft.ifft2(f))
    return z / z.std() * amplitud


class PruebasFeatures(unittest.TestCase):
    def test_plano_inclinado_tiene_pendiente_y_nada_de_rugosidad(self):
        x = np.arange(60) * RES
        H = np.tile(0.1 * x, (60, 1))          # pendiente = atan(0.1) ~ 5.71 grados
        p, c, r = mapas_pixel(H, RES)
        self.assertAlmostEqual(float(np.nanmedian(p)), np.degrees(np.arctan(0.1)), 2)
        self.assertLess(float(np.nanmedian(r)), 1e-6)

    def test_ocho_caracteristicas(self):
        X, _, _ = tabla_cuadros(terreno(120, 30, 3, 1), RES, 3.0)
        self.assertEqual(X.shape[1], len(CARACTERISTICAS))
        self.assertTrue(np.isfinite(X).all())

    def test_aptitud_prefiere_llano(self):
        llano = {"pendiente_media": 1, "frac_llana": 0.95, "rugosidad_m": 0.5}
        abrupto = {"pendiente_media": 20, "frac_llana": 0.1, "rugosidad_m": 6}
        self.assertGreater(aptitud(llano), aptitud(abrupto))

    def test_mascara_excluye_cuadros(self):
        H = terreno(120, 30, 3, 2)
        X0, _, _ = tabla_cuadros(H, RES, 3.0)
        m = np.zeros_like(H, dtype=bool)
        m[:, :60] = True                      # "océano" en la mitad izquierda
        X1, c1, _ = tabla_cuadros(H, RES, 3.0, mascara=m)
        self.assertLess(len(X1), len(X0))
        self.assertTrue((c1[:, 1] >= 60).all())


class PruebasBusqueda(unittest.TestCase):
    def test_kdtree_igual_a_fuerza_bruta(self):
        rng = np.random.default_rng(0)
        A = rng.normal(size=(500, 8)) * np.arange(1, 9)
        q = rng.normal(size=8) * np.arange(1, 9)
        n = Normalizador().ajustar(A)
        _, i = Indice(A, n).vecinos(q, k=5)
        bruta = np.argsort(((n(A) - n(q)) ** 2).sum(1))[:5]
        self.assertEqual(list(i), list(bruta))

    def test_encuentra_el_gemelo_plantado(self):
        # Tierra: terreno suave con un parche abrupto conocido plantado.
        tierra = terreno(400, 10, 6, 3)
        objetivo = terreno(38, 120, 1.5, 4)
        tierra[200:238, 100:138] = objetivo + tierra[200:238, 100:138].mean()
        res, est = buscar_grueso_fino(tierra, RES, objetivo, 3.0,
                                      factor=2, fraccion=0.2, k=3)
        self.assertTrue(res, "no devolvió resultados")
        fi, fj = res[0]["centro"]
        self.assertLess(abs(fi - 219), 25)
        self.assertLess(abs(fj - 119), 25)
        self.assertLess(est["finos"], est["gruesos"])   # el afinado ahorra trabajo


class PruebasRegionesYGenetico(unittest.TestCase):
    def test_agrupar_une_vecinos(self):
        centros = [(0, 0), (0, 5), (0, 10), (100, 100)]
        e = agrupar(centros, 6)
        self.assertEqual(e[0], e[1]); self.assertEqual(e[1], e[2])
        self.assertNotEqual(e[0], e[3])
        r = mejor_por_region(centros, [3, 1, 2, 9], 6)
        self.assertEqual(r[0]["cuadros"], 3)

    def test_genetico_cerca_del_optimo_con_pocas_evaluaciones(self):
        meta = np.array([70, 140])
        costo = lambda p: float(np.hypot(*(np.array(p) - meta)))
        mejores, n = genetico(costo, (200, 200), semilla=7, k=3)
        self.assertLess(mejores[0]["costo"], 6.0)
        self.assertLess(n, 200 * 200 * 0.3)
        mejores2, _ = genetico(costo, (200, 200), semilla=7, k=3)
        self.assertEqual(mejores, mejores2)            # reproducible


if __name__ == "__main__":
    unittest.main()
