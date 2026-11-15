"""UTM (WGS84) -> latitud/longitud. Series de Krüger; sin dependencias."""
import math

_A = 6378137.0
_F = 1 / 298.257223563
_N = _F / (2 - _F)
_K0 = 0.9996
_A1 = _A / (1 + _N) * (1 + _N ** 2 / 4 + _N ** 4 / 64)
_BETA = [0.5 * _N - 2 / 3 * _N ** 2 + 5 / 16 * _N ** 3,
         13 / 48 * _N ** 2 - 3 / 5 * _N ** 3,
         61 / 240 * _N ** 3]
_DELTA = [2 * _N - 2 / 3 * _N ** 2 - 2 * _N ** 3,
          7 / 3 * _N ** 2 - 8 / 5 * _N ** 3,
          56 / 15 * _N ** 3]


def utm_a_latlon(x, y, zona, norte=True):
    """x, y en metros (este, norte); devuelve (lat, lon) en grados."""
    e = x - 500000.0
    n = y if norte else y - 10000000.0
    xi, eta = n / (_K0 * _A1), e / (_K0 * _A1)
    xi_p, eta_p = xi, eta
    for j, b in enumerate(_BETA, start=1):
        xi_p -= b * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
        eta_p -= b * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
    chi = math.asin(math.sin(xi_p) / math.cosh(eta_p))
    lat = chi + sum(d * math.sin(2 * j * chi) for j, d in enumerate(_DELTA, start=1))
    lon0 = math.radians((zona - 1) * 6 - 180 + 3)
    lon = lon0 + math.atan2(math.sinh(eta_p), math.cos(xi_p))
    return math.degrees(lat), math.degrees(lon)


def epsg_a_zona(epsg):
    """'EPSG:32614' -> (14, True)."""
    c = int(str(epsg).split(":")[1])
    if 32601 <= c <= 32660: return c - 32600, True
    if 32701 <= c <= 32760: return c - 32700, False
    raise ValueError(f"No es UTM WGS84: {epsg}")
