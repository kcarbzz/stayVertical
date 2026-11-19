# Presentación final · Visión por Computadora

| Archivo | Qué es |
|---|---|
| `Stay_Vertical_Presentacion_Final.pptx` | La presentación (29 diapositivas, con notas del orador en cada una). |
| `demo_pipeline.py` | Demostración en vivo: corre el motor real (`stayvertical/`) sobre imágenes de prueba del repositorio y muestra cada paso del pipeline. |
| `generar_capturas.py` | Genera las capturas del código, con su número de línea real, que usa la presentación. |
| `salida/` | Figuras de la demo (`paso*.png`, `control_plantilla.png`), capturas del código (`codigo_*.png`) y capturas de la web y de la terminal. |

## Demostración en vivo

Desde la raíz del repositorio (no necesita internet):

```bash
pip install numpy scipy matplotlib tifffile
```

```bash
python presentacion/demo_pipeline.py
```

```bash
python presentacion/demo_pipeline.py --control
```

```bash
python presentacion/demo_pipeline.py --sitio haworth --mostrar
```

- Sin argumentos: el sitio lunar Malapert contra las 50 imágenes de prueba de `data/resultados/tierra_*.tif` (DEM a 80 m/px). Imprime los pasos 0 a 6 con tiempos (unos 2 s en total) y guarda una figura por paso en `presentacion/salida/`.
- `--control`: recorta una ventana del Teide, la gira 90°, le suma una inclinación y 1500 m, y la vuelve a encontrar con la correlación (r = 1,000 en la posición exacta).
- `--sitio`: cualquiera de los 8 sitios lunares (haworth, malapert, degerlache, nobile, cabeus, shackleton, faustini, shoemaker).
- `--imagen ruta.tif`: usar otra imagen de prueba (repetible).
- `--mostrar`: abre cada figura en una ventana además de guardarla.

Para regenerar las capturas del código tras cambiarlo:

```bash
pip install pygments pillow
```

```bash
python presentacion/generar_capturas.py
```

---

# Presentación final · Inteligencia Artificial 2

Todo está en `presentacion/ia2/`.

| Archivo | Qué es |
|---|---|
| `Stay_Vertical_IA2_Presentacion_Final.pptx` | La presentación (37 diapositivas, con notas del orador en cada una). |
| `demo_ia.py` | Demostración en vivo con el modelo real del bot (`docs/bot_modelo.json`) y el motor real. |
| `bot_decision.js` | Puente a Node: pasa frases por el bot completo de la web (`docs/asistente.js`: red, reglas, umbrales y guardas). |
| `salida/` | Figuras de la demo, capturas del código (`codigo_*.png`) y capturas de la terminal. |

## Demostración en vivo

Desde la raíz del repositorio (no necesita internet; Node.js es opcional y da la decisión del bot completo):

```bash
pip install numpy matplotlib scipy tifffile
```

```bash
python presentacion/ia2/demo_ia.py bot
```

```bash
python presentacion/ia2/demo_ia.py bot "¿de dónde salen los mapas?"
```

```bash
python presentacion/ia2/demo_ia.py evaluar
```

```bash
python presentacion/ia2/demo_ia.py curvas
```

```bash
python presentacion/ia2/demo_ia.py motor
```

- `bot`: cada frase pasa por los 5 pasos (normalizar, n-gramas con hashing, capa oculta de las 3 redes, softmax y promedio, decisión con umbrales). Sin frases, usa cinco de ejemplo: una clara, una dudosa, una que resuelven las reglas, un error real de la red y letras al azar.
- `evaluar`: las 160 frases del conjunto ciego 2 (77,5 % la red sola), matriz de confusión, exactitud por intención y el compromiso entre responder y acertar según el umbral.
- `curvas`: reentrena UNA red (semilla 7) con el bucle del proyecto y registra pérdida y exactitud por época (≈ 10 s).
- `motor`: recuperar y reordenar contra las 50 imágenes de prueba y sensibilidad del ganador al peso del puntaje (≈ 12 s).
- `--mostrar` abre cada figura en una ventana.

Capturas del código de IA 2:

```bash
python presentacion/generar_capturas.py --conjunto ia2
```
