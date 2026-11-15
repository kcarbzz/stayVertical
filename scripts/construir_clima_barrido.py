#!/usr/bin/env python3
"""Caracterización climática REAL de candidatos del barrido Stay Vertical.

Fuentes: NASA POWER daily point API, 2021-01-01 a 2025-12-31.
No sustituye datos faltantes por los del catálogo manual.
Uso (en la raíz del repo): python scripts/construir_clima_barrido.py --hilos 4
Admite reanudación: cada respuesta exitosa queda en data/clima_barrido_cache/.
"""
import argparse
import concurrent.futures
import datetime as dt
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs' / 'barrido.json'
OUT = ROOT / 'docs' / 'clima_barrido.json'
CACHE = ROOT / 'data' / 'clima_barrido_cache'
START, END = '20210101', '20251231'
PARAMETERS = ['T2M', 'T2M_MAX', 'T2M_MIN', 'PRECTOTCORR', 'WS10M', 'RH2M', 'ALLSKY_SFC_SW_DWN', 'PS']
VARIABLES = ['t_media_c', 't_max_ext_c', 't_min_ext_c', 'lluvia_anual_mm', 'dias_lluvia_anio', 'racha_lluviosa_max_dias', 'dias_calor_35_anio', 'dias_helada_anio', 'viento_10m_ms', 'dias_viento_10ms_anio', 'humedad_rel_pct', 'solar_kwh_m2_dia', 'presion_kpa']


def clave(coord):
    return f'{float(coord[0]):.5f},{float(coord[1]):.5f}'


def numerico(x):
    try:
        y = float(x)
    except (ValueError, TypeError):
        return None
    return y if math.isfinite(y) and y > -900 else None


def datos_punto(lat, lon, reintentos):
    CACHE.mkdir(parents=True, exist_ok=True)
    k = clave((lat, lon))
    ruta = CACHE / (k.replace(',', '_') + '.json')
    if ruta.is_file():
        try:
            o = json.loads(ruta.read_text(encoding='utf-8'))
            if isinstance(o.get('properties', {}).get('parameter'), dict):
                return o
        except (ValueError, OSError):
            pass
    args = {
        'parameters': ','.join(PARAMETERS), 'community': 'RE',
        'longitude': f'{lon:.5f}', 'latitude': f'{lat:.5f}',
        'start': START, 'end': END, 'format': 'JSON',
    }
    url = 'https://power.larc.nasa.gov/api/temporal/daily/point?' + urllib.parse.urlencode(args)
    last_error = None
    for intento in range(reintentos):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'StayVertical-HackNASA/1.0'})
            with urllib.request.urlopen(req, timeout=32) as respuesta:
                o = json.load(respuesta)
            if not isinstance(o.get('properties', {}).get('parameter'), dict):
                raise ValueError('NASA POWER no devolvió las series diarias esperadas')
            ruta.write_text(json.dumps(o), encoding='utf-8')
            return o
        except (OSError, ValueError, urllib.error.URLError) as exc:
            last_error = exc
            if intento + 1 < reintentos:
                time.sleep(1.5 * (intento + 1))
    raise RuntimeError(f'{k}: {last_error}')


def promedio(xs):
    a = [v for v in xs if v is not None]
    return sum(a) / len(a) if a else None


def calcular(payload, lat, lon):
    raw = payload['properties']['parameter']
    faltantes = [p for p in PARAMETERS if p not in raw]
    if faltantes:
        raise ValueError('Parámetros faltantes: ' + ','.join(faltantes))
    fechas = sorted(set().union(*(set(raw[p]) for p in PARAMETERS)))
    dias = []
    for fecha in fechas:
        if len(fecha) != 8 or fecha < START or fecha > END:
            continue
        row = {'fecha': dt.datetime.strptime(fecha, '%Y%m%d').date()}
        for p in PARAMETERS:
            row[p] = numerico(raw[p].get(fecha))
        dias.append(row)
    if len(dias) < 1700 or any(sum(r[p] is not None for r in dias) < 1600 for p in PARAMETERS):
        raise ValueError('Cobertura temporal insuficiente para calcular 13 indicadores')

    lluvia_anual, lluvia_dias, calor, heladas, viento_fuerte = [], [], [], [], []
    for anio in range(2021, 2026):
        bloque = [d for d in dias if d['fecha'].year == anio]
        def n(c): return sum(d[c] is not None for d in bloque)
        if min(n(p) for p in PARAMETERS) < 300:
            raise ValueError(f'Faltan >65 días de información en {anio}')
        lluvia_anual.append(sum(d['PRECTOTCORR'] or 0 for d in bloque))
        lluvia_dias.append(sum(d['PRECTOTCORR'] is not None and d['PRECTOTCORR'] >= 1 for d in bloque))
        calor.append(sum(d['T2M_MAX'] is not None and d['T2M_MAX'] >= 35 for d in bloque))
        heladas.append(sum(d['T2M_MIN'] is not None and d['T2M_MIN'] < 0 for d in bloque))
        viento_fuerte.append(sum(d['WS10M'] is not None and d['WS10M'] >= 10 for d in bloque))
    racha, max_racha = 0, 0
    for d in dias:
        if d['PRECTOTCORR'] is None:
            racha = 0
        elif d['PRECTOTCORR'] >= 1:
            racha += 1
            max_racha = max(max_racha, racha)
        else:
            racha = 0
    vals = {
        't_media_c': promedio(d['T2M'] for d in dias),
        't_max_ext_c': max(d['T2M_MAX'] for d in dias if d['T2M_MAX'] is not None),
        't_min_ext_c': min(d['T2M_MIN'] for d in dias if d['T2M_MIN'] is not None),
        'lluvia_anual_mm': promedio(lluvia_anual),
        'dias_lluvia_anio': promedio(lluvia_dias),
        'racha_lluviosa_max_dias': max_racha,
        'dias_calor_35_anio': promedio(calor),
        'dias_helada_anio': promedio(heladas),
        'viento_10m_ms': promedio(d['WS10M'] for d in dias),
        'dias_viento_10ms_anio': promedio(viento_fuerte),
        'humedad_rel_pct': promedio(d['RH2M'] for d in dias),
        'solar_kwh_m2_dia': promedio(d['ALLSKY_SFC_SW_DWN'] for d in dias),
        'presion_kpa': promedio(d['PS'] for d in dias),
    }
    if any(v is None or not math.isfinite(v) for v in vals.values()):
        raise ValueError('Indicadores numéricos incompletos')
    mensual = []
    for mes in range(1, 13):
        m = [d for d in dias if d['fecha'].month == mes]
        por_anio = [sum(d['PRECTOTCORR'] or 0 for d in m if d['fecha'].year == anio) for anio in range(2021, 2026)]
        mensual.append({'mes': mes, 't': round(promedio(d['T2M'] for d in m), 2), 'lluvia': round(promedio(por_anio), 2)})
    return {
        'nombre': f'Barrido automático ({lat:.3f}°, {lon:.3f}°)',
        'nombre_en': f'Automatic sweep ({lat:.3f}°, {lon:.3f}°)',
        'categoria': 'Barrido automático', 'categoria_en': 'Automatic sweep',
        'lat': lat, 'lon': lon,
        'v': {k: round(float(v), 2) for k, v in vals.items()},
        'mensual': mensual, 'estado': 'OK',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hilos', type=int, default=4)
    parser.add_argument('--reintentos', type=int, default=2)
    args = parser.parse_args()
    barrido = json.loads(BASE.read_text(encoding='utf-8'))
    coordenadas = {}
    for cruce in barrido['cruces'].values():
        for s in cruce['sitios'].values():
            for candidato in s['candidatos']:
                c = candidato['coord']
                coordenadas[clave(c)] = (float(c[0]), float(c[1]))
    print(f'Consultando {len(coordenadas)} coordenadas distintas de NASA POWER (2021-2025)')
    previos = {}
    if OUT.is_file():
        try:
            previos = json.loads(OUT.read_text(encoding='utf-8')).get('puntos', {})
        except (OSError, ValueError):
            pass
    resultados = {k: v for k, v in previos.items() if k in coordenadas and v.get('estado') == 'OK'}
    errores = {}

    def procesar(item):
        k, (lat, lon) = item
        try:
            return k, calcular(datos_punto(lat, lon, max(1, args.reintentos)), lat, lon), None
        except Exception as exc:
            return k, None, str(exc)

    pendientes = [(k, c) for k, c in coordenadas.items() if k not in resultados]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.hilos)) as pool:
        for i, (k, data, err) in enumerate(pool.map(procesar, pendientes), 1):
            if data is not None:
                resultados[k] = data
            else:
                errores[k] = err
            if i % 10 == 0 or i == len(pendientes):
                print(f'{i}/{len(pendientes)} consultas nuevas, con datos {len(resultados)}/{len(coordenadas)}', flush=True)

    out = {
        'fuente': 'NASA POWER (series diarias por coordenada; no heredadas del catálogo)',
        'periodo': f'{START}-{END}',
        'resolucion': 'NASA POWER: celda climática global; no microclima local',
        'nota': 'Evaluación climática EXPLORATORIA de las coordenadas del barrido; umbrales provisionales, sin certificación de construcción.',
        'puntos': resultados,
        'pendientes': errores,
        'total_candidatos_unicos': len(coordenadas),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    print(f'{OUT}: {len(resultados)}/{len(coordenadas)} puntos con mediciones; pendientes {len(errores)}')
    if errores:
        print('Vuelve a ejecutar el mismo comando para reintentar solamente los pendientes.')


if __name__ == '__main__':
    main()
