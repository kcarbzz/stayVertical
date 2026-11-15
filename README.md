# Stay Vertical

Proyecto para el NASA Space Apps Challenge 2026: *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*.
Elige un sitio de la Luna o de Marte y mira qué zonas de la Tierra se le parecen en relieve, con su clima y viabilidad.

Web: https://stay-vertical.wiki

## Qué muestra la web

- **18 sitios de referencia:** 8 del polo sur lunar (LOLA, 80 m) y 10 de Marte (mezcla HRSC/MOLA de USGS, 200 m).
- **50 zonas terrestres** candidatas (Copernicus DEM GLO-30), ordenadas por parecido de relieve.
- **Mapa lunar en proyección polar sur** con capas de NASA Trek (relieve LOLA e imagen LRO WAC); Marte usa el mosaico Viking.
- **Ficha de analogía** por candidato: separa la fidelidad (forma del relieve, pendiente, frío, aridez y presión del aire frente al sitio) de la logística, dice para qué serviría la zona, qué no reproduce la Tierra y qué falta por evaluar. Marca además las zonas ya usadas como análogo y las poco usadas.
- **Barrido automático:** junto al catálogo de 50 zonas, la web muestra los candidatos que encontró el algoritmo al recorrer franjas enteras de la Tierra, sin lista previa, con la comparación visual del relieve del sitio y del candidato.
- **Hallazgos:** resumen de las zonas que más se repiten entre los 3 primeros candidatos, destacando las poco usadas como análogo.
- **Lista corta y avisos:** las zonas a ≤0,01 del mejor puntaje se marcan como equivalentes, y se avisa cuando el mejor candidato queda lejos de la pendiente del sitio.
- **Clima y viabilidad** de cada zona (NASA POWER, 2021-2025) con un semáforo de umbrales provisionales.
- **Vertikal Bot:** una red neuronal pequeña que corre en el navegador y explica los resultados mostrados.
- Selector de idioma ES/EN.

Los resultados son exploratorios: comparan relieve dentro de un catálogo de 50 zonas, no validan geología. Los límites están en `AUDITORIA_RESULTADOS.md`.

## Estructura

| Carpeta | Qué contiene |
|---|---|
| `docs/` | Web estática (GitHub Pages desde `main`): `resultados.json`, `clima.json`, `barrido.json` (candidatos del barrido automático), `analogia.json` (valores de referencia de la Luna y Marte y lista de análogos ya usados), modelo del bot e imágenes de comparación |
| `stayvertical/` | Motor en Python: características de relieve, barrido de franjas, búsqueda grueso→fino, agrupación en regiones y algoritmo genético |
| `scripts/` | `barrido.py` recorre franjas enteras de la Tierra y busca análogos sin lista previa (ver abajo); `construir_datos.py` y `construir_clima.py` generan los JSON de la web; `subir_version.py` renueva la caché; `auditoria/` reproduce la auditoría |
| `entrenamiento/` | Ejemplos y entrenamiento del clasificador de Vertikal Bot |
| `tests/` | Pruebas del motor (pytest) y del bot, el clima, la proyección polar y la ficha de analogía (Node) |
| `notebooks/`, `data/resultados/` | Corrida anterior del análisis (16 parches de referencia); ya no alimenta la web |
| `backend/` | API opcional en FastAPI, aún sin uso |

## Desarrollo local

Web:

```bash
python3 -m http.server 8000 --directory docs
```

Tras cambiar archivos de `docs/`:

```bash
python3 scripts/subir_version.py
```

Pruebas:

```bash
pip install -r requirements.txt pytest && python3 -m pytest tests/test_motor.py tests/test_barrido.py
```

```bash
node tests/test_bot.js && node tests/test_clima.js && node tests/test_polar.js && node tests/test_analogia.js && node tests/test_barrido_web.js
```

## Barrido de franjas de la Tierra

`scripts/barrido.py` sustituye la lista de 50 zonas elegidas a mano: recorre franjas de cientos de kilómetros y deja que el algoritmo encuentre los cuadros que más se parecen a cada sitio de la Luna o de Marte. Usa Copernicus DEM para el relieve y ESA WorldCover para descartar bosque, cultivos, ciudades, agua, nieve y hielo; los dos se descargan solos desde Microsoft Planetary Computer.

En Google Colab:

```bash
pip install -q rasterio pystac-client planetary-computer
```

```bash
python scripts/barrido.py --listar
```

```bash
python scripts/barrido.py --cuerpo marte --franjas puna_altiplano,islandia --salida barrido_marte
```

Los sitios no hay que prepararlos: el script recorta los 18 de `docs/resultados.json` de su fuente oficial (NASA LOLA a 80 m para la Luna y la mezcla HRSC/MOLA de USGS a 200 m para Marte). El resultado queda en `candidatos_<cuerpo>.csv`, `sitios_<cuerpo>.csv`, `recortes_<cuerpo>.npz` y `meta_<cuerpo>.json`. Si se interrumpe, al relanzarlo continúa donde iba.

Para llevarlo a la web:

```bash
python3 -I scripts/construir_barrido.py --marte barrido_marte --luna barrido_luna
```

Eso escribe `docs/barrido.json`, que la web muestra en la pestaña «Barrido automático». La salida del barrido publicado (once franjas, 745 teselas por cuerpo) está guardada en `data/barrido/`.

El puntaje del barrido es 0,5 × la diferencia real en los 8 rasgos + 0,5 × (1 − correlación de forma) / 2. Se diferencia del catálogo de 50 zonas en el primer término: allí es la posición del cuadro en la lista, que con millones de cuadros vale casi cero y dejaba ganar a candidatos mucho menos empinados que el sitio. Con `--fisica percentil` se recupera la fórmula anterior.

Límites: compara solo relieve; los cuadros que cruzan el borde entre dos teselas de 1° no se evalúan; la Antártida no tiene mapa de cobertura, así que ahí no se descarta nada y un candidato puede estar sobre hielo.

## Seguridad de la web

`docs/index.html` lleva una Content Security Policy y carga Leaflet 1.9.4 desde cdnjs con `integrity` (SRI). Si se añade otra librería o un servidor de mapas, hay que sumar su dominio a la CSP; si se cambia la versión de Leaflet, hay que recalcular los dos hashes.
