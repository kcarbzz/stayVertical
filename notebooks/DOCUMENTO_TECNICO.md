# Stay Vertical — Documento técnico

Proyecto para el NASA Space Apps Challenge 2026, reto *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*.

Web: https://stay-vertical.wiki · Código: https://github.com/kcarbzz/stayVertical

Este documento describe el estado actual del proyecto. La primera versión (4 regiones terrestres y un recorte por cuerpo) se conserva en `DOCUMENTO_TECNICO_v1.md`.

## 1. Qué hace

Dado un sitio de la Luna o de Marte, busca en la Tierra los terrenos de 3 km que más se le parecen en relieve y dice, dimensión por dimensión, en qué se parecen y en qué no.

Trabaja con 18 sitios de referencia: 8 del polo sur lunar (candidatos del programa Artemis y cráteres vecinos) y 10 de Marte (sitios de aterrizaje de rovers y regiones de interés).

Ofrece dos búsquedas:

- **Catálogo de 50 zonas.** Cincuenta zonas terrestres elegidas por el equipo (volcanes, desiertos, cráteres y calderas, cañones y mesetas, montañas), de unos 13 km cada una.
- **Barrido automático.** El algoritmo recorre once franjas enteras de la Tierra, sin lista previa de zonas, y decide él dónde están los candidatos.

## 2. Fuentes de datos

| Dato | Fuente | Resolución |
|---|---|---|
| Relieve de la Luna | NASA LOLA, `LDEM_80S_80MPP_ADJ` (polo sur) | 80 m |
| Relieve de Marte | Mezcla HRSC/MOLA v2 de USGS (NASA MOLA y ESA HRSC) | 200 m |
| Relieve de la Tierra | Copernicus DEM GLO-30 y GLO-90 (programa Copernicus de la UE, con la ESA) | 30 m y 90 m |
| Cobertura del suelo | ESA WorldCover 2021 | 10 m |
| Clima | NASA POWER, series diarias 2021–2025 | celda de unos 55 km |
| Mapas de fondo de la Luna y Marte | NASA Trek | — |
| Valores de referencia de la Luna y Marte | Fichas de NASA NSSDCA y LRO Diviner | — |

El relieve terrestre y la cobertura se descargan desde Microsoft Planetary Computer, que solo los distribuye.

## 3. Método

### 3.1 Comparación a la misma escala

La pendiente y la rugosidad dependen del tamaño del píxel, así que cada comparación se hace a una sola resolución: la Tierra se remuestrea a 80 m para compararla con la Luna y a 200 m para Marte. Todos los cuadros miden unos 3 km de lado (38 píxeles a 80 m, 15 píxeles a 200 m). Marte se pasa antes a una proyección local con la escala de la latitud de cada sitio.

### 3.2 Ocho rasgos por cuadro

| Grupo | Rasgos | Peso de cada uno |
|---|---|---|
| Pendiente | media, desviación y percentil 90 | 1/9 |
| Curvatura | media y percentil 90 del valor absoluto | 1/6 |
| Rugosidad | mediana, percentil 90 y desviación | 1/9 |

La pendiente sale del gradiente de la elevación suavizada. La curvatura es su segunda derivada. La rugosidad es la desviación de la elevación respecto al mejor plano local en una ventana de 5 × 5 píxeles. Cada rasgo se normaliza con la mediana y el rango intercuartílico de los cuadros terrestres.

### 3.3 Dos etapas

1. **Etapa física.** Distancia entre los ocho rasgos del sitio y los de cada cuadro terrestre. Pasan a la etapa siguiente los más cercanos.
2. **Etapa de forma.** A cada candidato se le quita la inclinación general (el mejor plano), se suaviza y se correlaciona con el relieve del sitio, probando cuatro giros: 0°, 90°, 180° y 270°.

### 3.4 Puntaje

En los dos casos, menor es mejor, y la mitad del puntaje es `(1 − correlación de forma) / 2`. La otra mitad difiere:

- **Catálogo:** la posición del cuadro en la lista ordenada por distancia física (un percentil).
- **Barrido:** la diferencia real en los ocho rasgos (la raíz de la distancia física).

El cambio se hizo porque, con millones de cuadros, el percentil vale casi cero para todos los candidatos y el puntaje lo decidía solo la forma: ganaban cuadros con buena correlación pero mucho menos empinados que el sitio. Por eso **los puntajes de las dos pestañas no son comparables entre sí**.

## 4. Barrido automático

`scripts/barrido.py` hace lo siguiente:

1. Recorta los 18 sitios de sus fuentes oficiales a partir de sus coordenadas.
2. Descarga el relieve y la cobertura de cada tesela de 1° de las franjas elegidas.
3. Descarta bosque, cultivos, zonas construidas, agua, humedales, manglares, nieve y hielo, y los cuadros con menos del 85 % de píxeles válidos.
4. Calcula los ocho rasgos de todos los cuadros, con un solape del 50 % entre vecinos.
5. Para cada sitio, pasa a la etapa de forma el 0,1 % de cuadros más parecidos.
6. Deja un candidato por región: de los cuadros a menos de unos 6 km entre sí, el mejor.

Franjas barridas: Puna y Altiplano, Islandia, Namib, Australia central, Ártico canadiense, Tierra Victoria y Valles Secos (Antártida), Sáhara central, península arábiga, Tíbet y Qaidam, Gobi, y Mojave y Gran Cuenca.

| Cuerpo | Teselas de 1° | Cuadros evaluados | Candidatos a la etapa de forma, por sitio |
|---|---|---|---|
| Luna | 745 | 2 455 713 | 2 456 |
| Marte | 745 | 2 229 494 | 2 229 |

Como control, los 18 sitios recortados por el script reproducen la pendiente y la rugosidad que ya publicaba la web; la única diferencia es de 0,1 m en la rugosidad de Jezero.

## 5. Resultados del barrido

Mejor candidato de cada sitio.

### Luna

| Sitio | Pendiente del sitio | Mejor candidato | Pendiente del candidato | Correlación | Puntaje | Fuera de rango |
|---|---|---|---|---|---|---|
| Haworth | 13,7° | Antártida (77,54° S, 162,13° E) | 13,2° | 0,89 | 0,146 | Sí |
| Macizo Malapert | 6,3° | Islandia (64,91° N, 14,71° O) | 5,7° | 0,94 | 0,065 | No |
| de Gerlache (borde) | 8,1° | Islandia (65,07° N, 21,52° O) | 9,1° | 0,80 | 0,114 | No |
| Nobile (borde) | 8,3° | Tíbet y Qaidam, China (38,22° N, 96,51° E) | 7,7° | 0,71 | 0,147 | No |
| Cerca de Cabeus | 8,1° | Tíbet y Qaidam, China (32,65° N, 87,65° E) | 7,2° | 0,79 | 0,129 | No |
| Shackleton | 32,1° | Antártida (77,55° S, 162,06° E) | 20,3° | 0,71 | 0,828 | Sí |
| Faustini | 20,7° | Puna y Altiplano, Chile (25,36° S, 68,86° O) | 18,0° | 0,86 | 0,236 | Sí |
| Shoemaker | 2,4° | Península arábiga, Arabia Saudita (19,32° N, 51,52° E) | 2,5° | 0,42 | 0,166 | No |

### Marte

| Sitio | Pendiente del sitio | Mejor candidato | Pendiente del candidato | Correlación | Puntaje | Fuera de rango |
|---|---|---|---|---|---|---|
| Cráter Jezero | 2,0° | Isla Devon, Canadá (75,40° N, 87,18° O) | 2,1° | 0,83 | 0,076 | No |
| Cráter Gale | 30,2° | Puna y Altiplano, Chile (21,89° S, 68,43° O) | 22,8° | 0,80 | 0,657 | Sí |
| Oxia Planum | 0,5° | Puna y Altiplano, Bolivia (19,05° S, 66,56° O) | 0,4° | 0,92 | 0,028 | No |
| Mawrth Vallis | 1,1° | Namib, Namibia (20,60° S, 17,07° E) | 1,1° | 0,90 | 0,045 | No |
| Meridiani Planum | 0,6° | Namib, Namibia (23,57° S, 15,77° E) | 0,7° | 0,87 | 0,051 | No |
| Cráter Eberswalde | 1,7° | Puna y Altiplano, Chile (23,19° S, 69,30° O) | 1,9° | 0,89 | 0,052 | No |
| Utopia Planitia | 0,4° | Sáhara central, Chad (21,37° N, 15,72° E) | 0,5° | 0,88 | 0,037 | No |
| Olympus Mons | 1,0° | Gobi, Mongolia (42,34° N, 104,94° E) | 1,1° | 0,90 | 0,041 | No |
| Valles Marineris | 15,8° | Antártida (77,51° S, 162,34° E) | 16,0° | 0,71 | 0,201 | Sí |
| Hellas Planitia | 1,4° | Namib, Namibia (26,21° S, 15,66° E) | 1,4° | 0,90 | 0,041 | No |

### Lectura

- **Cinco sitios no tienen análogo de relieve en lo barrido:** Haworth, Shackleton, Faustini, Gale y Valles Marineris. «Fuera de rango» significa que su cuadro más parecido está más lejos que el 99 % de las distancias entre cuadros terrestres vecinos. Son laderas muy empinadas y a la vez lisas. Para Shackleton y Gale, ni el mejor candidato se acerca en pendiente.
- **Los sitios llanos de Marte tienen muchos equivalentes.** Hay tantos cuadros terrestres casi idénticos a una llanura marciana que el primer puesto cambia de franja al ampliar el área. Conviene leerlos como «hay terreno así en varios desiertos», no como un gemelo único.
- **Los resultados más estables** son Jezero en la isla Devon, y Malapert y de Gerlache en Islandia: se mantuvieron al pasar de seis a once franjas.
- **La isla Devon aparece sin que nadie la indicara.** En ella está el cráter Haughton, que el reto cita como análogo clásico de Marte; el candidato de Jezero queda a unos 70 km de ese cráter.

## 6. Clima y ficha de analogía

**Clima.** Para cada zona del catálogo y para cada candidato del barrido se calculan 13 factores a partir de NASA POWER (2021–2025): temperatura media y extremas, lluvia anual, días de lluvia, racha lluviosa máxima, días de calor y de helada, viento medio y días de viento fuerte, humedad, radiación solar y presión. Un semáforo provisional resume cuántos factores son favorables, de atención o difíciles.

**Ficha de analogía.** Separa dos cosas que no deben mezclarse:

- **Fidelidad:** cuánto se parece el lugar al sitio en forma del relieve, pendiente, temperatura, aridez y presión del aire, frente a los valores de referencia de la Luna y Marte.
- **Logística:** qué tan fácil es trabajar ahí, según el semáforo de clima.

Un lugar frío y seco se parece más a la Luna o a Marte, pero es más difícil para trabajar. El candidato de Jezero en la isla Devon lo ilustra: es más frío que las 50 zonas del catálogo y su semáforo de logística es rojo.

La ficha dice además para qué serviría el lugar según la pendiente del sitio, qué no puede reproducir la Tierra (gravedad, vacío o atmósfera tenue, radiación) y qué queda sin evaluar.

## 7. Límites

- **Solo se compara relieve.** No se evalúan geología ni minerales, hielo o agua, polvo y viento, iluminación ni subsuelo.
- **El barrido cubre once franjas, no toda la Tierra.**
- **En la Antártida no hay mapa de cobertura.** Ahí no se puede distinguir roca de hielo, y un candidato puede estar sobre un glaciar. Afecta a los mejores candidatos de Haworth, Shackleton y Valles Marineris.
- **La correlación de forma ignora la inclinación general.** Dos cuadros pueden correlacionar alto aunque sus laderas miren a lados distintos.
- **En el catálogo, el ganador es inestable.** Cambia con el peso entre las dos mitades del puntaje, y el primero y el segundo suelen estar a menos de 0,01. Por eso la web marca una lista corta de zonas equivalentes. El detalle está en `AUDITORIA_RESULTADOS.md`.
- **El clima es el de una celda de unos 55 km**, no el microclima del cuadro de 3 km, y los umbrales del semáforo son provisionales.
- **La clasificación «análogo ya usado» es provisional.** Marca 11 zonas del catálogo con uso documentado por NASA o ESA.
- **Los cuadros que cruzan el borde entre dos teselas de 1° no se evalúan.**
- **Los valores de referencia de la Luna y Marte son aproximados y por cuerpo**, no por sitio.

## 8. Cómo reproducirlo

Web en local:

```bash
python3 -m http.server 8000 --directory docs
```

Barrido (pensado para Google Colab; descarga los datos solo):

```bash
pip install -q rasterio pystac-client planetary-computer
```

```bash
python scripts/barrido.py --cuerpo marte --franjas puna_altiplano,islandia --salida barrido_marte
```

Datos de la web a partir del barrido:

```bash
python3 -I scripts/construir_barrido.py --marte barrido_marte --luna barrido_luna
```

Clima de los candidatos del barrido:

```bash
python3 scripts/construir_clima_barrido.py --hilos 4
```

Pruebas:

```bash
pip install -r requirements.txt pytest && python3 -m pytest tests/
```

```bash
node tests/test_bot.js && node tests/test_clima.js && node tests/test_polar.js && node tests/test_analogia.js && node tests/test_barrido_web.js
```

La salida del barrido publicado está en `data/barrido/`.

## 9. Dónde está cada cosa

| Carpeta | Contenido |
|---|---|
| `docs/` | La web y sus datos: `resultados.json` (catálogo), `barrido.json`, `clima.json`, `clima_barrido.json`, `analogia.json` |
| `stayvertical/` | Motor en Python: rasgos de relieve, barrido, búsqueda y agrupación en regiones |
| `scripts/` | Barrido, conversores a datos de web, clima y auditoría |
| `tests/` | Pruebas del motor y del barrido (Python) y de la web (Node) |
| `data/barrido/` | Salida del barrido publicado |
| `notebooks/` | Cuaderno de la versión anterior y este documento |
