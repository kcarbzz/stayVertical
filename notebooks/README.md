# Notebooks (Google Colab)

| Archivo | Qué es |
|---|---|
| `HackNASA_50.ipynb` | Pipeline completo con 50 regiones terrestres: descarga los DEM de Tierra, Luna y Marte, calcula los 8 descriptores por parche, los rankings y exporta el ZIP de resultados. |
| `DOCUMENTO_TECNICO.md` | Documento maestro del proyecto: metodología, ecuaciones, los 39 pasos, limitaciones y plan de trabajo. Describe la versión anterior, de 4 regiones. |

Abrir en Colab: https://colab.research.google.com/github/kcarbzz/stayVertical/blob/main/notebooks/HackNASA_50.ipynb

## De Colab a la web

1. Ejecutar el notebook entero. El paso 39 descarga `Resultados_HackNASA_Tierra_Luna_Marte.zip`.
2. Descomprimir el ZIP en `data/resultados/` (sustituyendo lo que haya).
3. Desde la raíz del repo:

   ```bash
   pip install -r requirements.txt
   ```

   ```bash
   python scripts/exportar_web.py
   ```

   Esto regenera `docs/resultados.json` y las miniaturas de `docs/parches/`.
4. Hacer commit de `data/resultados/` y `docs/`.

## Diferencias con el documento técnico

`data/resultados/` viene de `HackNASA_50.ipynb`, posterior a lo que describe `DOCUMENTO_TECNICO.md`:

- **Catálogo terrestre:** 50 regiones y 2 579 parches (antes 4 y 170), en cinco familias: montañas, volcanes, desiertos, cráteres y calderas, cañones y mesetas.
- **Filtro previo:** `CANDIDATOS_GEOM = 80`. Solo los 80 parches más cercanos en los 8 rasgos pasan a la correlación de forma, y los puestos y el score se calculan dentro de esos 80.
- **Marte:** el recorte se reproyecta a una equirectangular local (paso 10B), por lo que tiene 56 parches en vez de 64.

El notebook anterior (`HackNASA_Automatico_39_Pasos_Sin_Drive.ipynb`) sigue en el historial de Git.
