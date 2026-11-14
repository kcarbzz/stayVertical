// Escapa texto antes de insertarlo como HTML, para que un valor del JSON
// nunca pueda inyectar etiquetas o scripts.
const esc = v => String(v).replace(/[&<>"']/g, c =>
  ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const $ = id => document.getElementById(id);

const ETIQUETAS = {
  pendiente_media: ['Pendiente media', '°'],
  pendiente_std: ['Pendiente, desv. estándar', '°'],
  pendiente_p90: ['Pendiente P90', '°'],
  curvatura_abs_media: ['Curvatura |C| media', '1/km'],
  curvatura_abs_p90: ['Curvatura |C| P90', '1/km'],
  rugosidad_mediana: ['Rugosidad mediana', 'm'],
  rugosidad_p90: ['Rugosidad P90', 'm'],
  rugosidad_std: ['Rugosidad, desv. estándar', 'm'],
};
// La curvatura viene en 1/m; se muestra en 1/km para que sea legible.
const valor = (k, v) => (k.startsWith('curvatura') ? v * 1000 : v).toFixed(2);
const coord = p => `${Math.abs(p.lat).toFixed(3)}° ${p.lat < 0 ? 'S' : 'N'}, ${Math.abs(p.lon).toFixed(3)}° ${p.lon < 0 ? 'O' : 'E'}`;

const mapa = L.map('mapa', {worldCopyJump: true}).setView([20, -40], 2);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution: '&copy; OpenStreetMap'}).addTo(mapa);
const capa = L.layerGroup().addTo(mapa);
let datos, cuerpo, ref, marcas = [];

// Cuadrado del parche sobre el mapa (lado en metros, centrado en lat/lon).
function huella(p, lado) {
  const dLat = lado / 2 / 111320, dLon = dLat / Math.cos(p.lat * Math.PI / 180);
  return [[p.lat - dLat, p.lon - dLon], [p.lat + dLat, p.lon + dLon]];
}

function tablaFicha(a, b) {
  const filas = datos.rasgos.map(k => {
    const [nombre, unidad] = ETIQUETAS[k] || [k, ''];
    return `<tr><td>${esc(nombre)}</td><td>${valor(k, a.ficha[k])}</td>` +
      (b ? `<td>${valor(k, b.ficha[k])}</td>` : '') + `<td class="u">${esc(unidad)}</td></tr>`;
  }).join('');
  const cab = b ? `<tr><th></th><th>${esc(cuerpo.nombre)}</th><th>Tierra</th><th></th></tr>` : '';
  return `<table>${cab}${filas}</table>`;
}

function elegirCandidato(i, volar = true) {
  const c = ref.top[i];
  document.querySelectorAll('.cand').forEach((e, j) => e.classList.toggle('sel', j === i));
  marcas.forEach((m, j) => m.setStyle({fillColor: j === i ? '#f0b429' : '#3b82f6'}));
  $('detalle').innerHTML = `
    <h3>Comparación con el puesto ${c.puesto}</h3>
    <div class="par">
      <figure><img src="${esc(ref.img)}" alt=""><figcaption>${esc(cuerpo.nombre)} · ${esc(ref.id)}</figcaption></figure>
      <figure><img class="rot${c.rotacion_grados}" src="${esc(c.img)}" alt=""><figcaption>${esc(c.lugar)}<br>girado ${c.rotacion_grados}°</figcaption></figure>
    </div>
    <p class="mut">Relieve sin la inclinación general. Los colores se ajustan a cada imagen:
      el desnivel residual es de ${ref.relieve_residual_m} m en ${esc(cuerpo.nombre)} y de ${c.relieve_residual_m} m en la Tierra.</p>
    <table>
      <tr><td>Distancia física (8 rasgos)</td><td>${c.distancia_fisica}</td><td class="u">puesto ${c.puesto_fisico} de ${ref.n_candidatos}</td></tr>
      <tr><td>Correlación de forma</td><td>${c.corr_forma}</td><td class="u">puesto ${c.puesto_forma} de ${ref.n_candidatos}</td></tr>
      <tr><td>Score combinado</td><td class="score">${c.score_final}</td><td class="u">menor = mejor</td></tr>
    </table>
    ${tablaFicha(ref, c)}`;
  if (volar) {
    mapa.flyToBounds(huella(c, datos.config.parche_m * 4), {duration: 0.8});
    marcas[i].openPopup();
  }
}

function mostrarRef(id) {
  ref = cuerpo.referencias.find(r => r.id === id);
  $('ficha').innerHTML = `<p class="mut">Centro: ${coord(ref)} · parche de ${(datos.config.parche_m / 1000).toFixed(2)} km de lado</p>`;
  capa.clearLayers();
  marcas = [];
  const lista = $('lista');
  const filtro = ref.n_candidatos < datos.parches_tierra
    ? `<p class="mut">De ${datos.parches_tierra} parches terrestres, los ${ref.n_candidatos} más cercanos en los 8 rasgos pasan a la comparación de forma.</p>` : '';
  lista.innerHTML = `<h3>Los ${ref.top.length} mejores parches terrestres</h3>${filtro}`;
  // Se dibujan del último al primero para que el puesto 1 quede encima.
  [...ref.top].reverse().forEach(c => {
    L.rectangle(huella(c, datos.config.parche_m), {color: '#f0b429', weight: 1, fillOpacity: 0.15}).addTo(capa);
    marcas[c.puesto - 1] = L.circleMarker([c.lat, c.lon], {radius: 9, color: '#fff', weight: 1.5, fillColor: '#3b82f6', fillOpacity: 0.95})
      .addTo(capa)
      .bindTooltip(String(c.puesto), {permanent: true, direction: 'center', className: 'num'})
      .bindPopup(`<b>${c.puesto}. ${esc(c.lugar)}</b><br>${esc(c.id)}<br>Score ${c.score_final}`)
      .on('click', () => elegirCandidato(c.puesto - 1));
  });
  ref.top.forEach((c, i) => {
    const d = document.createElement('button');
    d.className = 'cand';
    d.innerHTML = `<img class="rot${c.rotacion_grados}" src="${esc(c.img)}" alt="">
      <span><b>${c.puesto}. ${esc(c.lugar)}</b>${c.categoria ? ` <span class="cat">${esc(c.categoria)}</span>` : ''}<br>
      <span class="score">score ${c.score_final}</span> · física ${c.distancia_fisica} · forma ${c.corr_forma}</span>`;
    d.onclick = () => elegirCandidato(i);
    lista.appendChild(d);
  });
  elegirCandidato(0, false);
  mapa.fitBounds(L.latLngBounds(ref.top.map(c => [c.lat, c.lon])).pad(0.3), {maxZoom: 11});
}

function mostrarCuerpo(nombre) {
  cuerpo = datos.cuerpos.find(c => c.nombre === nombre);
  document.querySelectorAll('#cuerpos button').forEach(b => b.classList.toggle('sel', b.textContent === nombre));
  const sel = $('ref');
  sel.innerHTML = '';
  cuerpo.referencias.forEach(r =>
    sel.add(new Option(`${r.id} · pendiente ${r.ficha.pendiente_media.toFixed(1)}° · mejor: ${r.top[0].region}`, r.id)));
  const s = cuerpo.sensibilidad.map(f =>
    `<tr><td>${Math.round(f.peso_fisico * 100)} %</td><td>${Math.round(f.mismo_top1 * 100)} %</td><td>${Math.round(f.jaccard_top3 * 100)} %</td></tr>`).join('');
  $('notas').innerHTML = `
    <h3>¿Cuánto depende del peso elegido?</h3>
    <table><tr><th>Peso físico</th><th>Mismo nº 1</th><th>Top 3 en común</th></tr>${s}</table>
    <p class="mut">Comparado con el 50/50 usado aquí, promediando las ${cuerpo.referencias.length} referencias de ${esc(cuerpo.nombre)}.</p>
    <h3>Cómo leer esto</h3>
    <p class="mut">El catálogo terrestre tiene ${datos.parches_tierra} parches de ${datos.regiones_tierra.length} zonas
      (${[...new Set(datos.regiones_tierra.map(r => r.categoria).filter(Boolean))].map(c => esc(c.toLowerCase())).join(', ')}).
      El score solo ordena dentro de ese catálogo: no es un porcentaje de parecido ni una validación geológica,
      y compara únicamente relieve a ${datos.config.resolucion_m} m por píxel.</p>
    <p class="mut">Datos: Copernicus DEM GLO-30 (Tierra), NASA LRO/LOLA (Luna), ESA/DLR Mars Express HRSC (Marte).</p>`;
  mostrarRef(cuerpo.referencias[0].id);
}

fetch('resultados.json').then(r => r.json()).then(d => {
  datos = d;
  $('aviso').hidden = !d.muestra;
  d.cuerpos.forEach(c => {
    const b = document.createElement('button');
    b.textContent = c.nombre;
    b.onclick = () => mostrarCuerpo(c.nombre);
    $('cuerpos').appendChild(b);
  });
  $('ref').onchange = e => mostrarRef(e.target.value);
  mostrarCuerpo(d.cuerpos[0].nombre);
});
