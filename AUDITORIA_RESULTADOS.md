# Auditoría de los resultados (HackNASA: 8 sitios lunares + 10 marcianos)

Fecha: 2026-11-14. Alcance: revisar **qué se ejecutó** y **si lo obtenido es sólido**, usando los archivos del equipo
(`HackNASA_8_Luna_10_Marte_Resultados`, `HackNASA_Revision_18_Sitios`, `HackNASA_a.ipynb`).
Se reproduce con `scripts/auditoria/auditar.py` (solo lee datos; necesita numpy, scipy y tifffile).

## 1. Qué se ejecutó (según el cuaderno, verificado en lo posible)
- **Tierra:** 50 zonas elegidas a mano (49 con datos), recortes de ~13 km de Copernicus GLO-30. No es un barrido global.
- **Rasgos:** 8 números por parche (pendiente media/desv./p90, curvatura media/p90, rugosidad mediana/p90/desv.).
  Normalización con mediana e IQR **solo de la base terrestre**. Pesos: 1/9 (pendiente y rugosidad) y 1/6 (curvatura).
- **Física:** distancia cuadrática ponderada al vector del sitio; se queda con los 500 parches más cercanos.
- **Forma:** correlación del relieve sin la inclinación general, probando rotaciones de 0/90/180/270°.
- **Puntaje:** `0,5 × fisica_global_01 + 0,5 × (1 − correlación)/2`. Menor es mejor.
- Luna a 80 m (LOLA, 38 px = 3,04 km). Marte a 200 m (USGS HRSC/MOLA, 15 px = 3 km) con la Tierra remuestreada a 200 m.

## 2. Verificaciones que PASAN
| Comprobación | Resultado |
|---|---|
| Recalcular desde los GeoTIFF los 8 números de los 10 sitios de Marte | Coinciden con la entrega (pendiente y rugosidad idénticas) |
| Recalcular las distancias físicas de Marte contra los 3 010 parches terrestres | Diferencia máxima ~1e-15; **los 500 candidatos son idénticos en los 10 sitios** |
| Orden de los rankings | Cada sitio viene ordenado de menor a mayor puntaje |
| Coordenadas de los candidatos (UTM → lat/lon) | Todos a ≤ 7,6 km del centro de su zona |
| Los pesos de los 8 rasgos | **Robustos**: cambiar a pesos iguales, o quitar curvatura, mantiene 41–48 de los 50 mejores parches |

## 3. Hallazgos (lo que limita la validez)
1. **"Chile gana en todas" no se reproduce en ninguna de las fuentes reales.** Revisé tres:
   (a) los 18 sitios nuevos: la zona chilena (Atacama) aparece 0 veces entre los 5 primeros;
   (b) el `resultados.json` publicado en stay-vertical.wiki (corrida anterior, 16 parches de referencia): ganan volcanes
   (Etna 3, Fuji 2, Vesubio 2, Teide 2…), tampoco Chile; (c) la página publicada muestra Fuji y Etna como #1.
   Solo ocurre en el dato de muestra que escribí yo en la primera versión local de la web (Atacama primero en todos los cruces):
   era un artefacto de ese dato inventado, no un resultado.
2. **El término físico del puntaje es un percentil, no una distancia.** Varía entre 0 y 0,20 dentro de los 500 candidatos,
   mientras que el término de forma varía entre 0,07 y 0,90. En la práctica **manda la forma**, aunque el peso nominal sea 50/50.
   Además el percentil no distingue si el mejor parche está cerca o lejos en términos absolutos.
3. **El ganador cambia con el peso 50/50.** Con peso físico 0,25 el #1 (por zona) cambia en 5 de 8 sitios lunares y en 2 de 10 marcianos;
   con 0,75 cambia en 3 de 8 lunares y en 6 de 10 marcianos. El 0,5 es "una decisión experimental" según el propio cuaderno.
4. **Casi no hay separación entre #1 y #2.** La brecha suele ser < 0,01 (Eberswalde: empate exacto, 0,0000). Hay 1–4 zonas distintas
   a ≤ 0,01 del mejor en todos los sitios. Presentar un único "gemelo" sobreafirma.
5. **Validez absoluta (Marte).** La distancia física mínima de cada sitio frente a la distancia típica entre parches terrestres:
   Gale **8,8 veces** la típica (pendiente 30° = percentil 98 de la Tierra: se extrapola); Valles Marineris 1,3×; los otros 8 sitios ≤ 0,2×.
6. **Sitios planos: empates físicos.** Meridiani, Oxia, Mawrth, Utopia, Olimpo y Hellas tienen distancias de ~1e-5 a 1e-4 a muchos
   parches terrestres. Físicamente son indistinguibles, así que el ganador lo decide la correlación de formas casi lisas.
7. **Pool terrestre sesgado.** Al menos 12 de las 50 zonas están en EE. UU. (≈ una cuarta parte; el Gran Cañón sería la 13.ª): 26 de las 90 plazas de top-5 y 1 267 de 4 000 candidatos lunares.
8. **Casos con diferencia absoluta grande y sin marca de revisión** (el equipo solo marcó Nobile y Shoemaker por correlación baja):
   Shackleton (pendiente 32,1° vs 18,1°), Faustini (20,7° vs 10,2°), Haworth (13,7° vs 4,1°), Gale (30,2° vs 20,7°; rugosidad 13,4 vs 31,3 m).

9. **La página publicada corresponde a una corrida anterior.** Sus 8 referencias lunares son parches de una misma ventana polar
   (lat −89,8 a −89,9) y sus 8 marcianas caen a ~0,3° entre sí (≈26,2° N, 14,1° O): no son los 18 sitios nombrados.
   Su propia tabla de sensibilidad llega a la misma conclusión que este análisis (con peso físico 0,25 el mismo #1 se mantiene
   en 75 % de las referencias lunares y 50 % de las marcianas; con 0,75, en 75 % y 63 %).

## 4. Lo que NO pude verificar
- **Luna:** la entrega no incluye los vectores de los sitios lunares ni de la base terrestre a 80 m. No se pudo repetir el recálculo.
- **Correlación de forma:** requiere los DEM de cada parche, que no están en la entrega.
- **Que el DEM de origen sea correcto** (LOLA, HRSC/MOLA, Copernicus): se asume.
- **Coordenadas de los sitios:** siguen siendo aproximadas; falta contrastarlas con una fuente oficial (Excel pendiente).

## 5. Recomendaciones (de mayor a menor impacto)
1. Guardar y mostrar la **distancia física absoluta** (y su razón frente a la típica) además del puntaje; marcar "fuera del rango terrestre" si > ~3×.
2. Presentar un **grupo de candidatos empatados** (≤ 0,01) en lugar de un único ganador.
3. Reportar la **sensibilidad al peso** (0,25 / 0,5 / 0,75) junto a cada resultado.
4. Pedir al equipo los **vectores de la Luna (80 m)** para repetir esta auditoría con los 8 sitios lunares.
5. Ampliar y **balancear el pool terrestre** (más terreno empinado y menos concentración en EE. UU.).
6. Para sitios planos, decir explícitamente que muchas zonas planas son equivalentes.
