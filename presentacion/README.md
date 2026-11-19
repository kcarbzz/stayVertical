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
