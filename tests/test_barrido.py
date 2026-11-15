"""Pruebas del barrido con terreno sintético (sin descargar nada)."""

import unittest

import numpy as np

from stayvertical.barrido import (Base, correlacion_forma, parches_de_tesela, puntuar_sitio, regiones,
                                  sitio_desde_dem, ventana_central)

RES, TAM = 80.0, 38


def terreno(n, amplitud, longitud, semilla):
    """Colinas suaves: amplitud (m) y longitud de onda (px) controlan el relieve."""
    rng = np.random.default_rng(semilla)
    f = np.fft.fft2(rng.normal(size=(n, n)))
    ky, kx = np.meshgrid(np.fft.fftfreq(n), np.fft.fftfreq(n), indexing="ij")
    z = np.real(np.fft.ifft2(f * np.exp(-(kx ** 2 + ky ** 2) * (longitud ** 2))))
    return z / z.std() * amplitud


class PruebasSitio(unittest.TestCase):
    def test_ventana_central(self):
        A = np.arange(100).reshape(10, 10)
        np.testing.assert_array_equal(ventana_central(A, 4), A[3:7, 3:7])
        with self.assertRaises(ValueError):
            ventana_central(A, 12)

    def test_sitio_resume_solo_el_cuadro_central(self):
        H = terreno(TAM + 10, 40, 4, 1)
        s = sitio_desde_dem(H, RES, TAM)
        self.assertEqual(s["vector"].shape, (8,))
        self.assertEqual(s["relieve"].shape, (TAM, TAM))
        np.testing.assert_array_equal(s["relieve"], H[5:5 + TAM, 5:5 + TAM])


class PruebasForma(unittest.TestCase):
    def test_mismo_relieve_girado_e_inclinado_correlaciona_1(self):
        a = terreno(TAM, 30, 4, 2)
        yy, xx = np.mgrid[:TAM, :TAM]
        b = np.rot90(a, 1) + 3.0 * xx - 2.0 * yy + 500           # girado 90°, con otra inclinación y otra altura
        c, rot = correlacion_forma(a, b)
        self.assertAlmostEqual(c, 1.0, 6)
        self.assertEqual(rot, 270)                               # hay que girar b otros 270° para volver a a

    def test_relieves_distintos_correlacionan_poco(self):
        c, _ = correlacion_forma(terreno(TAM, 30, 4, 3), terreno(TAM, 30, 4, 4))
        self.assertLess(c, 0.6)

    def test_plano_no_rompe(self):
        c, _ = correlacion_forma(np.zeros((TAM, TAM)), terreno(TAM, 30, 4, 5))
        self.assertTrue(np.isnan(c))

    def test_demasiados_huecos_no_se_compara(self):
        a = terreno(TAM, 30, 4, 6); a[:, :10] = np.nan
        self.assertTrue(np.isnan(correlacion_forma(a, terreno(TAM, 30, 4, 7))[0]))


class PruebasBarrido(unittest.TestCase):
    def setUp(self):
        # Tres teselas suaves y, escondido en la segunda, un cuadro abrupto alineado con la rejilla (paso de 19 px).
        self.teselas = [terreno(400, 15, 6, s) for s in (10, 11, 12)]
        self.joya = terreno(TAM + 10, 220, 2.5, 99)
        self.fi, self.fj = 19 * 6, 19 * 9
        self.teselas[1][self.fi - 5:self.fi + TAM + 5, self.fj - 5:self.fj + TAM + 5] = self.joya
        X, self.cen, self.tes = [], [], []
        for k, H in enumerate(self.teselas):
            x, c, fichas, dom = parches_de_tesela(H, RES, TAM)
            self.assertEqual(len(x), len(fichas)); self.assertEqual(len(x), len(dom))
            X.append(x); self.cen.append(c); self.tes.append(np.full(len(x), k))
        self.cen, self.tes = np.concatenate(self.cen), np.concatenate(self.tes)
        self.base = Base(np.concatenate(X))

    def relieve_de(self, i):
        f, c = self.cen[i] - TAM // 2
        return self.teselas[self.tes[i]][f:f + TAM, c:c + TAM]

    def test_encuentra_el_cuadro_escondido_aunque_el_sitio_este_girado(self):
        sitio = sitio_desde_dem(np.rot90(self.joya, 1), RES, TAM)
        r = puntuar_sitio(self.base, sitio, self.relieve_de, candidatos=50)
        m = r[0]
        self.assertEqual(int(self.tes[m["indice"]]), 1)
        np.testing.assert_array_equal(self.cen[m["indice"]], [self.fi + TAM // 2, self.fj + TAM // 2])
        self.assertGreater(m["corr"], 0.999)
        self.assertEqual(m["fisica_01"], 0.0)                    # también es el más cercano en los 8 rasgos
        self.assertLess(m["score"], r[1]["score"])
        self.assertTrue(all(x["score"] <= y["score"] for x, y in zip(r, r[1:])))

    def test_un_sitio_que_no_se_parece_a_nada_queda_fuera_de_rango(self):
        raro = sitio_desde_dem(terreno(TAM + 10, 3000, 2, 7), RES, TAM)
        tipica, limite = self.base.vecindad()
        self.assertLess(tipica, limite)
        self.assertGreater(self.base.distancias(raro["vector"]).min(), limite)
        normal = sitio_desde_dem(terreno(TAM + 10, 15, 6, 13), RES, TAM)                 # un terreno como los de la base sí está en rango
        self.assertLess(self.base.distancias(normal["vector"]).min(), limite)

    def test_cobertura_descarta_cuadros_y_da_la_clase_dominante(self):
        H = self.teselas[0]
        clases = np.full(H.shape, 60, dtype="uint8")
        clases[:, :200] = 80                                     # agua en la mitad izquierda
        x0, _, _, _ = parches_de_tesela(H, RES, TAM)
        x1, c1, _, dom = parches_de_tesela(H, RES, TAM, clases=clases)
        self.assertLess(len(x1), len(x0))
        self.assertTrue((c1[:, 1] >= 200).all())
        self.assertTrue((dom == 60).all())

    def test_tesela_vacia_no_rompe(self):
        x, c, f, d = parches_de_tesela(np.full((100, 100), np.nan), RES, TAM)
        self.assertEqual((len(x), len(c), len(f), len(d)), (0, 0, 0, 0))

    def test_regiones_deja_el_mejor_cuadro_de_cada_grupo(self):
        filas = [{"indice": 0, "score": 0.1}, {"indice": 1, "score": 0.2}, {"indice": 2, "score": 0.3}]
        lat, lon = np.array([10.0, 10.01, 12.0]), np.array([20.0, 20.01, 20.0])      # los dos primeros están a ~1,6 km
        r = regiones(filas, lat, lon, radio_km=6)
        self.assertEqual([(x["indice"], x["cuadros"]) for x in r], [(0, 2), (2, 1)])
        self.assertEqual(regiones([], lat, lon, 6), [])


class PruebasConversor(unittest.TestCase):
    """scripts/construir_barrido.py: lo que convierte la salida del barrido en datos para la web."""

    def setUp(self):
        import os, sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
        import construir_barrido
        self.c = construir_barrido

    def test_codificar_va_de_1_a_255_y_marca_los_huecos_con_0(self):
        import base64
        Z = np.array([[0.0, 50.0], [100.0, np.nan]])
        r = self.c.codificar(Z)
        self.assertEqual((r["n"], r["min"], r["max"]), (2, 0.0, 100.0))
        self.assertEqual(list(base64.b64decode(r["datos"])), [1, 128, 255, 0])
        self.assertIsNone(self.c.codificar(np.full((2, 2), np.nan)))
        self.assertEqual(set(base64.b64decode(self.c.codificar(np.ones((2, 2)))["datos"])), {128})      # cuadro plano

    def test_pais_de(self):
        cuadrado = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]                                     # [lon, lat]
        hueco = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
        paises = [{"properties": {"nombre": "Uno", "en": "One"}, "geometry": {"type": "Polygon", "coordinates": [cuadrado, hueco]}}]
        self.assertEqual(self.c.pais_de(2, 2, paises), ("Uno", "One"))
        self.assertIsNone(self.c.pais_de(5, 5, paises))             # dentro del hueco
        self.assertIsNone(self.c.pais_de(20, 20, paises))


if __name__ == "__main__":
    unittest.main()
