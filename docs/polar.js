/* Proyección estereográfica polar del polo sur lunar (esfera de 1737,4 km, escala verdadera en el polo, 0° hacia arriba y 90° E a la derecha).
   Es la misma de los mosaicos polares de NASA Trek y del modelo de elevación del equipo (LDEM_80S).
   La unidad del mapa es "metros / RES0", con RES0 = tamaño de píxel del nivel 0 de NASA Trek (8561,953 m): así los niveles de zoom
   de Leaflet (CRS.Simple) coinciden con los niveles de las teselas y no hace falta ninguna librería de proyecciones. */
const Polar = (() => {
  const R = 1737400, RES0 = 8561.953, ORIGEN = 1095930 / RES0;     // ORIGEN = 128 unidades: esquina superior izquierda de la cuadrícula de Trek
  const rad = g => g * Math.PI / 180;
  /* [lat, lon] -> [y, x] en unidades del mapa (el orden de L.CRS.Simple: lat = y, lng = x) */
  const aPolar = ([lat, lon]) => { const rho = 2 * R * Math.tan(rad(90 + lat) / 2); return [rho * Math.cos(rad(lon)) / RES0, rho * Math.sin(rad(lon)) / RES0]; };
  /* [y, x] -> [lat, lon] (inversa; sirve para comprobar) */
  const dePolar = ([y, x]) => { const rho = Math.hypot(x, y) * RES0; return [-90 + 2 * Math.atan(rho / (2 * R)) * 180 / Math.PI, Math.atan2(x, y) * 180 / Math.PI]; };
  return { R, RES0, ORIGEN, aPolar, dePolar };
})();
if (typeof module !== 'undefined') module.exports = Polar;
