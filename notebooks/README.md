# Notebooks (Google Colab)

Aquí van los notebooks del cálculo pesado (descarga y análisis de datos de NASA PDS).

Para abrir uno en Colab: `https://colab.research.google.com/github/kcarbzz/stayVertical/blob/main/notebooks/<archivo>.ipynb`

Las dependencias están en `requirements.txt` (raíz del repo). En Colab:

```python
!pip install -q -r https://raw.githubusercontent.com/kcarbzz/stayVertical/main/requirements.txt
```

El resultado final se exporta a `docs/resultados.json`, que es lo que lee la web. Mantened el mismo formato y poned `"muestra": false` cuando sean datos reales.
