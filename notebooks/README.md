# Notebooks (Google Colab)

| Archivo | Qué es |
|---|---|
| `HackNASA_Automatico_39_Pasos_Sin_Drive.ipynb` | Pipeline completo: descarga los DEM de Tierra, Luna y Marte, calcula los 8 descriptores por parche, los rankings y exporta el ZIP de resultados. |
| `DOCUMENTO_TECNICO.md` | Documento maestro del proyecto: metodología, ecuaciones, los 39 pasos, limitaciones y plan de trabajo. |

Abrir en Colab: https://colab.research.google.com/github/kcarbzz/stayVertical/blob/main/notebooks/HackNASA_Automatico_39_Pasos_Sin_Drive.ipynb

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

## Nota sobre las cifras

`data/resultados/` viene de una ejecución posterior a la que describe `DOCUMENTO_TECNICO.md`. En esta, el recorte de Marte ya se reproyecta a una equirectangular local (paralelo estándar en la latitud del recorte), por lo que tiene 56 parches en vez de 64 y los scores marcianos cambian un poco respecto a las tablas del documento.
