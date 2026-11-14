// Escapa texto antes de insertarlo como HTML, para que un valor del JSON
// (nombre de sitio, lugar, etc.) nunca pueda inyectar etiquetas o scripts.
const esc = v => String(v).replace(/[&<>"']/g, c =>
  ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

const mapa = L.map('mapa').setView([20, 0], 2);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution: '&copy; OpenStreetMap'}).addTo(mapa);
let capa = L.layerGroup().addTo(mapa), datos;

const tabla = f => `<table>
  <tr><td>Pendiente media</td><td>${esc(f.pendiente_media)}°</td></tr>
  <tr><td>Fracción llana (&lt;5°)</td><td>${esc(Math.round(f.frac_llana*100))}%</td></tr>
  <tr><td>Rugosidad</td><td>${esc(f.rugosidad_m)} m</td></tr></table>`;

function mostrar(id) {
  const s = datos.sitios.find(x => x.id === id);
  capa.clearLayers();
  document.getElementById('ficha').innerHTML = `<h3>${esc(s.nombre)}</h3>` + tabla(s.ficha);
  const cont = document.getElementById('gemelos');
  cont.innerHTML = '<h3>Gemelos en la Tierra</h3>';
  s.gemelos.forEach((g, i) => {
    const m = L.marker(g.coord).addTo(capa).bindPopup(`<b>${esc(g.lugar)}</b><br>Score: ${esc(g.score)}`);
    const d = document.createElement('div');
    d.className = 'gem';
    d.innerHTML = `<b>${i+1}. ${esc(g.lugar)}</b><br><span class="score">score ${esc(g.score)}</span> (menor = más parecido)` + tabla(g.ficha);
    d.onclick = () => { mapa.setView(g.coord, 5); m.openPopup(); };
    cont.appendChild(d);
  });
  mapa.setView([20, 0], 2);
}

fetch('resultados.json').then(r => r.json()).then(d => {
  datos = d;
  document.getElementById('aviso').hidden = !d.muestra;
  const sel = document.getElementById('sitio');
  d.sitios.forEach(s => sel.add(new Option(s.nombre, s.id)));
  sel.onchange = () => mostrar(sel.value);
  mostrar(d.sitios[0].id);
});
