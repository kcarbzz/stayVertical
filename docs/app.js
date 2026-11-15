const $ = id => document.getElementById(id);
/* Versión de los archivos: sale del ?v= de este script (la pone scripts/subir_version.py) y evita que el navegador use datos viejos. */
const V = (document.currentScript && new URL(document.currentScript.src).searchParams.get('v')) || String(Date.now());
const traer = (ruta) => fetch(`${ruta}?v=${V}`, { cache: 'no-cache' }).then(r => { if (!r.ok) throw new Error(ruta + ' ' + r.status); return r.json(); });
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const progreso = (p, t) => { $('progreso').style.width = p + '%'; if (t) $('carga-texto').textContent = t; };
const norm = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

const TILES = {
  luna: { url: 'https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/{z}/{y}/{x}.jpg', cred: 'NASA/GSFC/ASU · LRO WAC' },
  marte: { url: 'https://trek.nasa.gov/tiles/Mars/EQ/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/default/default028mm/{z}/{y}/{x}.jpg', cred: 'NASA/JPL-Caltech · USGS · Viking MDIM 2.1' },
};
const COLOR = { acc: '#5ec8ff', sol: '#ffd166' };
const CUERPOS = ['tierra', 'luna', 'marte'];

let datos, TIERRA, CLIMA = null;              // TIERRA: continentes con sus países (hijas)
const estado = { modo: 'region', gemelo: null, capa: 'ninguna', soloViables: false, candidatos: [],
  ref: { cuerpo: 'luna', zona: null, pais: null }, dest: { cuerpo: 'tierra', zona: null, pais: null } };
const M = { ref: null, dest: null };   // { mapa, cuerpo, capa, zonas }
const SUF = { ref: 'ref', dest: 'dest' };

const nombre = id => I18N.t('c.' + id);
const nm = o => I18N.nm(o);
const par = () => datos.cruces[`${estado.ref.cuerpo}-${estado.dest.cuerpo}`];

/* ---------- geometría ---------- */
function mayorPoligono(geom) {
  const polys = geom.type === 'Polygon' ? [geom.coordinates] : geom.coordinates;
  const caja = p => { let a = 90, b = 180, c = -90, d = -180; p[0].forEach(([x, y]) => { a = Math.min(a, y); c = Math.max(c, y); b = Math.min(b, x); d = Math.max(d, x); }); return [a, b, c, d]; };
  return polys.map(caja).sort((u, v) => (v[2] - v[0]) * (v[3] - v[1]) - (u[2] - u[0]) * (u[3] - u[1]))[0];
}
function enPoligono(pt, anillo) {   // pt = [lat, lon]; anillo = [[lon, lat], ...]
  let dentro = false;
  for (let i = 0, j = anillo.length - 1; i < anillo.length; j = i++) {
    const [xi, yi] = anillo[i], [xj, yj] = anillo[j];
    if ((yi > pt[0]) !== (yj > pt[0]) && pt[1] < (xj - xi) * (pt[0] - yi) / (yj - yi) + xi) dentro = !dentro;
  }
  return dentro;
}
function puntoEnPais(pt, feat) {
  const g = feat.geometry, polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
  return polys.some(p => enPoligono(pt, p[0]) && !p.slice(1).some(h => enPoligono(pt, h)));
}
const dentroCaja = (c, b) => c[0] >= b[0] && c[0] <= b[2] && c[1] >= b[1] && c[1] <= b[3];
const aLimites = b => [[b[0], b[1]], [b[2], b[3]]];

function caja(c, cuerpo) {
  const dl = cuerpo === 'luna' ? 4 : 8, lat0 = Math.max(c[0] - dl, -90), lat1 = Math.min(c[0] + dl, 90);
  return Math.abs(c[0]) > 80 ? [lat0, -180, lat1, 180] : [lat0, c[1] - 8, lat1, c[1] + 8];
}

/* ---------- árbol de regiones ---------- */
function nodos(cuerpo) {
  if (cuerpo === 'tierra') return TIERRA;
  return datos.conocidas[cuerpo].map(c => ({ id: c.id, nombre: c.nombre, nombre_en: c.nombre_en, coord: c.coord, detalle: c.detalle, detalle_en: c.detalle_en, bbox: caja(c.coord, cuerpo) }));
}
const zSel = l => nodos(estado[l].cuerpo).find(n => n.id === estado[l].zona) || null;
const pSel = l => { const z = zSel(l); return z && z.hijas ? z.hijas.find(h => h.id === estado[l].pais) || null : null; };
const primero = cuerpo => nodos(cuerpo)[0].id;

function enZonaDestino(c) {
  const p = pSel('dest'), z = zSel('dest');
  if (p) return puntoEnPais(c, p.feat);
  return z ? dentroCaja(c, z.bbox) : true;
}
function entradaActual() {
  const p = par(); if (!p || estado.modo === 'subir') return null;
  const z = zSel('ref');
  return (z && p.regiones.find(e => e.id === z.id)) || p.regiones[0];
}

/* ---------- mapas ---------- */
function nuevoMapa(div, cuerpo, previo) {
  if (previo) previo.mapa.remove();
  let mapa;
  if (cuerpo === 'tierra') {
    mapa = L.map(div, { minZoom: 1 });
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' }).addTo(mapa);
    mapa.setView([15, -30], 2);
  } else {
    mapa = L.map(div, { crs: L.CRS.EPSG4326, minZoom: 0, maxZoom: 8, zoomSnap: 0.25, maxBounds: [[-95, -190], [95, 190]] });
    L.tileLayer(TILES[cuerpo].url, { maxNativeZoom: 7, noWrap: true, attribution: TILES[cuerpo].cred }).addTo(mapa);
    mapa.fitBounds([[-90, -180], [90, 180]]);
  }
  requestAnimationFrame(() => { if (mapa._loaded) mapa.invalidateSize(); });
  return { mapa, cuerpo, capa: L.layerGroup().addTo(mapa), zonas: L.layerGroup().addTo(mapa), clima: L.layerGroup().addTo(mapa) };
}
const estiloPoligono = (act, tenue) => ({ color: act ? COLOR.sol : COLOR.acc, weight: act ? 2 : 1, fillColor: act ? COLOR.sol : COLOR.acc, fillOpacity: act ? 0.35 : tenue ? 0.14 : 0.18 });
const punto = (c, act, cap, nom, alClic) => L.circleMarker(c, { radius: act ? 9 : 7, color: act ? COLOR.sol : COLOR.acc, weight: 2, fillColor: act ? COLOR.sol : COLOR.acc, fillOpacity: act ? 0.9 : 0.35 })
  .addTo(cap).bindTooltip(esc(nom), { permanent: act, direction: 'top' }).on('click', alClic);

function dibujarTierra(l) {
  const cap = M[l].zonas, z = zSel(l), p = pSel(l);
  if (!z) {
    const grupos = {};
    TIERRA.forEach(c => c.hijas.forEach(h => {
      const ly = L.geoJSON(h.feat, { style: estiloPoligono(false, true) }).addTo(cap).bindTooltip(esc(nm(c)), { sticky: true });
      (grupos[c.id] ||= []).push(ly);
      ly.on('mouseover', () => grupos[c.id].forEach(x => x.setStyle(estiloPoligono(true))));
      ly.on('mouseout', () => grupos[c.id].forEach(x => x.setStyle(estiloPoligono(false, true))));
      ly.on('click', () => elegirNodo(l, c.id));
    }));
  } else {
    z.hijas.forEach(h => {
      const act = p && p.id === h.id;
      L.geoJSON(h.feat, { style: estiloPoligono(act, !!p && !act) }).addTo(cap).bindTooltip(esc(nm(h)), { sticky: true })
        .on('click', () => elegirNodo(l, z.id, h.id));
    });
  }
}
function dibujarPuntos(l) {
  const cap = M[l].zonas, z = zSel(l);
  nodos(estado[l].cuerpo).forEach(n => {
    const act = z && z.id === n.id;
    if (act && l === 'dest') L.rectangle(aLimites(n.bbox), { color: COLOR.sol, weight: 2, fillOpacity: 0.1 }).addTo(cap);
    punto(n.coord, act, cap, nm(n), () => elegirNodo(l, n.id));
  });
}
function dibujarLado(l) {
  M[l].zonas.clearLayers();
  if (l === 'ref') {
    $('sobre-ref').hidden = estado.modo !== 'subir';
    if (estado.modo === 'subir') return;
  }
  (estado[l].cuerpo === 'tierra' ? dibujarTierra : dibujarPuntos)(l);
}

/* ---------- elecciones ---------- */
function elegirNodo(l, zona, pais = null) {
  estado[l].zona = zona; estado[l].pais = pais; cambiar();
  const m = M[l].mapa, z = zSel(l), p = pSel(l), cuerpo = estado[l].cuerpo;
  if (!z) { cuerpo === 'tierra' ? m.setView([15, -30], 2) : m.fitBounds([[-90, -180], [90, 180]]); return; }
  if (cuerpo !== 'tierra') { m.setView(z.coord, l === 'ref' ? 4 : 3); return; }
  m.fitBounds(aLimites(p ? p.bbox : z.bbox), { padding: [20, 20], maxZoom: 6 });
}
function cambiarCuerpo(l, id) {
  estado[l] = { cuerpo: id, zona: l === 'ref' ? primero(id) : null, pais: null };
  cambiar();
}

/* ---------- controles ---------- */
function fichas(cont, ids, valor, alElegir) {
  cont.innerHTML = ids.map(id => `<button type="button" class="ficha" data-id="${id}" aria-pressed="${id === valor}"><span class="orbe ${id}"></span>${esc(nombre(id))}</button>`).join('');
  cont.querySelectorAll('button').forEach(b => b.onclick = () => alElegir(b.dataset.id));
}
function buscador(l, itemsFn, alElegir) {
  const q = $('q-' + SUF[l]), ul = $('l-' + SUF[l]);
  let visibles = [];
  const mostrar = () => {
    const t = norm(q.value.trim());
    visibles = itemsFn().filter(i => !t || norm(i.nombre + ' ' + (i.alt || '') + ' ' + (i.detalle || '')).includes(t)).slice(0, 12);
    ul.innerHTML = visibles.map((i, k) => `<li role="option" data-k="${k}"><span>${esc(i.nombre)}</span><small>${esc(i.detalle || '')}</small></li>`).join('') || `<li><small>${esc(I18N.t('sinCoincidencias'))}</small></li>`;
    ul.hidden = false;
  };
  const elegir = k => { const i = visibles[k]; if (!i) return; q.value = ''; ul.hidden = true; q.blur(); alElegir(i); };
  q.oninput = q.onfocus = mostrar;
  q.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); elegir(0); } if (e.key === 'Escape') ul.hidden = true; };
  q.onblur = () => setTimeout(() => ul.hidden = true, 150);
  ul.onmousedown = e => { const li = e.target.closest('li[data-k]'); if (li) { e.preventDefault(); elegir(+li.dataset.k); } };
}
function itemsLado(l) {
  const c = estado[l].cuerpo;
  if (c !== 'tierra') return nodos(c).map(n => ({ nombre: nm(n), alt: I18N.alt(n), detalle: (I18N.lang === 'en' && n.detalle_en) || n.detalle || nombre(c), z: n.id }));
  return TIERRA.flatMap(n => [{ nombre: nm(n), alt: I18N.alt(n), detalle: I18N.t('continente'), z: n.id }, ...n.hijas.map(h => ({ nombre: nm(h), alt: I18N.alt(h), detalle: nm(n), z: n.id, p: h.id }))]);
}
function alElegirItem(l, i) {
  elegirNodo(l, i.z, i.p || null);
}

function migas(l) {
  const z = zSel(l), p = pSel(l), items = [];
  if (l === 'dest') items.push([I18N.t('todo', nombre(estado.dest.cuerpo)), () => elegirNodo('dest', null)]);
  if (z) items.push([nm(z), () => elegirNodo(l, z.id)]);
  if (p) items.push([nm(p), null]);
  const cont = $('migas-' + SUF[l]);
  cont.innerHTML = items.map(([n], k) => (k ? '<span class="sep">›</span>' : '') + `<button type="button" ${k === items.length - 1 ? 'aria-current="true"' : ''}>${esc(n)}</button>`).join('');
  cont.querySelectorAll('button').forEach((b, k) => b.onclick = items[k][1]);
}

function controles() {
  fichas($('f-origen'), CUERPOS.filter(c => c !== estado.dest.cuerpo), estado.ref.cuerpo, id => cambiarCuerpo('ref', id));
  fichas($('f-destino'), CUERPOS.filter(c => c !== estado.ref.cuerpo), estado.dest.cuerpo, id => cambiarCuerpo('dest', id));
  const modos = ['region', 'subir'].map(v => [v, I18N.t('modo.' + v)]);
  $('t-modo').innerHTML = modos.map(([v, n]) => `<button type="button" data-m="${v}" aria-pressed="${estado.modo === v}">${n}</button>`).join('');
  $('t-modo').querySelectorAll('button').forEach(b => b.onclick = () => { estado.modo = b.dataset.m; cambiar(); });
  migas('ref'); migas('dest');
  $('q-ref').disabled = estado.modo === 'subir';
}

/* ---------- resultado ---------- */
const t = (k, ...a) => I18N.t(k, ...a);
const nums = f => f ? `<dl><dt>${t('pendiente')}</dt><dd>${I18N.num(f.pendiente_media)}°</dd><dt>${t('rugosidad')}</dt><dd>${I18N.num(f.rugosidad_m)} m</dd></dl>` : '';
const fmt3 = x => I18N.num(Number(Number(x).toFixed(3)));
const fmt2 = x => I18N.num(Number(Number(x).toFixed(2)));
const lugarDe = g => nm({ nombre: g.lugar, nombre_en: g.lugar_en });
const catDe = g => (I18N.lang === 'en' && g.categoria_en) || g.categoria || '';

/* ---------- clima ---------- */
const SEMCOLOR = { verde: '#4cc38a', ambar: '#ffd166', rojo: '#e5694f' };
const VAR = id => CLIMA.variables.find(v => v.id === id);
const nombreVar = v => (I18N.lang === 'en' && v.nombre_en) || v.nombre;
const descVar = v => (I18N.lang === 'en' && v.desc_en) || v.desc;
const climaDe = reg => (CLIMA && CLIMA.regiones[reg]) || null;
const _cacheEval = new Map();
function evalDe(reg) {
  const r = climaDe(reg); if (!r) return null;
  if (!_cacheEval.has(reg)) { const f = Clima.evaluar(r, CLIMA.variables), res = Clima.resumen(f); _cacheEval.set(reg, { f, res, sem: Clima.semaforo(res) }); }
  return _cacheEval.get(reg);
}
const num1 = x => I18N.num(Math.round(x * 10) / 10);

function llenarCapas() {
  const sel = $('capa-clima'); if (!sel || !CLIMA) return;
  const op = [['ninguna', t('sinCapa')], ...CLIMA.variables.map(v => [v.id, `${nombreVar(v)} (${v.unidad})`]), ['viab', t('capaViab')]];
  sel.innerHTML = op.map(([v, n]) => `<option value="${esc(v)}">${esc(n)}</option>`).join('');
  sel.value = estado.capa;
}

function dibujarClima() {
  const m = M.dest, ctl = $('clima-ctl'), ley = $('leyenda-clima');
  m.clima.clearLayers();
  const hay = !!CLIMA && estado.dest.cuerpo === 'tierra';
  ctl.hidden = !hay;
  if (!hay || estado.capa === 'ninguna') { ley.hidden = true; return; }
  const viab = estado.capa === 'viab', v = viab ? null : VAR(estado.capa);
  const [mn, mx] = viab ? [0, 1] : Clima.rango(CLIMA.regiones, v.id);
  for (const [id, r] of Object.entries(CLIMA.regiones)) {
    const e = evalDe(id);
    const relleno = viab ? SEMCOLOR[e.sem] : Clima.color(r.v[v.id], mn, mx);
    const texto = viab ? `${nm(r)} · ${t('sem.' + e.sem)} (${t('resumenFactores', e.res.ok, e.res.atencion, e.res.dificil)})` : `${nm(r)}: ${I18N.num(r.v[v.id])} ${v.unidad}`;
    L.circleMarker([r.lat, r.lon], { radius: 9, color: '#0b1020', weight: 1.5, fillColor: relleno, fillOpacity: 0.95 }).addTo(m.clima)
      .bindTooltip(esc(texto), { direction: 'top' }).on('click', () => abrirClima(id));
  }
  ley.hidden = false;
  ley.innerHTML = viab
    ? `<b>${esc(t('leyViab'))}</b>` + [['verde', 'leyVerde'], ['ambar', 'leyAmbar'], ['rojo', 'leyRojo']].map(([c, k]) => `<div class="sw"><span class="punto ${c}"></span>${esc(t(k))}</div>`).join('')
    : `<b>${esc(nombreVar(v))} (${esc(v.unidad)})</b><div class="barra-g"></div><div class="extremos"><span>${I18N.num(mn)}</span><span>${I18N.num(mx)}</span></div>`;
}

function grafLinea(vals, color) {
  const W = 300, H = 140, p = 26, mn = Math.min(...vals), mx = Math.max(...vals), d = mx - mn || 1;
  const x = i => p + i * (W - 2 * p) / 11, y = vv => H - 22 - (vv - mn) / d * (H - 44);
  const ms = t('meses').split(',');
  return `<svg viewBox="0 0 ${W} ${H}" role="img"><polyline fill="none" stroke="${color}" stroke-width="2.5" points="${vals.map((vv, i) => `${x(i)},${y(vv)}`).join(' ')}"/>`
    + vals.map((vv, i) => `<circle cx="${x(i)}" cy="${y(vv)}" r="2.6" fill="${color}"/>`).join('')
    + ms.map((mm, i) => `<text x="${x(i)}" y="${H - 6}" font-size="9" fill="#8f9bb8" text-anchor="middle">${esc(mm)}</text>`).join('')
    + `<text x="4" y="14" font-size="10" fill="#8f9bb8">${I18N.num(Math.round(mx * 10) / 10)}</text><text x="4" y="${H - 24}" font-size="10" fill="#8f9bb8">${I18N.num(Math.round(mn * 10) / 10)}</text></svg>`;
}
function grafBarras(vals, color) {
  const W = 300, H = 140, p = 26, mx = Math.max(...vals) || 1, bw = (W - 2 * p) / 12 - 3;
  const ms = t('meses').split(',');
  return `<svg viewBox="0 0 ${W} ${H}" role="img">`
    + vals.map((vv, i) => { const h = vv / mx * (H - 44); return `<rect x="${p + i * (W - 2 * p) / 12}" y="${H - 22 - h}" width="${bw}" height="${h}" rx="2" fill="${color}"/>`; }).join('')
    + ms.map((mm, i) => `<text x="${p + i * (W - 2 * p) / 12 + bw / 2}" y="${H - 6}" font-size="9" fill="#8f9bb8" text-anchor="middle">${esc(mm)}</text>`).join('')
    + `<text x="4" y="14" font-size="10" fill="#8f9bb8">${I18N.num(Math.round(mx))}</text><text x="4" y="${H - 24}" font-size="10" fill="#8f9bb8">0</text></svg>`;
}

function abrirClima(id) {
  const r = climaDe(id), e = evalDe(id); if (!r || !e) return;
  const filas = e.f.map(f => { const v = VAR(f.id); return `<tr title="${esc(descVar(v))}"><td>${esc(nombreVar(v))}</td><td>${I18N.num(f.valor)} ${esc(v.unidad)}</td><td><span class="punto ${f.estado}"></span> ${esc(t('est.' + f.estado))}</td></tr>`; }).join('');
  $('clima-cuerpo').innerHTML = `<h3>${esc(nm(r))}</h3><p class="mut">${esc((I18N.lang === 'en' && r.categoria_en) || r.categoria)} · ${I18N.num(r.lat)}°, ${I18N.num(r.lon)}°</p>`
    + `<div class="chip-sem"><span class="punto ${e.sem}"></span><b>${esc(t('sem.' + e.sem))}</b> · ${esc(t('resumenFactores', e.res.ok, e.res.atencion, e.res.dificil))}</div>`
    + `<h4>${esc(t('factores'))}</h4><table class="fact">${filas}</table>`
    + `<h4>${esc(t('mesAMes'))}</h4><div class="graf"><div><p class="mut peq">${esc(t('tempMensual'))}</p>${grafLinea(r.mensual.map(m => m.t), '#ffd166')}</div><div><p class="mut peq">${esc(t('lluviaMensual'))}</p>${grafBarras(r.mensual.map(m => m.lluvia), '#5ec8ff')}</div></div>`
    + `<p class="pie">${esc(t('pieClima', CLIMA.fuente, CLIMA.periodo, CLIMA.resolucion))}<br>${esc(t('avisoUmbrales'))}</p>`;
  $('clima-panel').showModal();
}

function pintar() {
  const tira = $('tira'), m = M.dest, e = entradaActual();
  m.capa.clearLayers(); estado.gemelo = null; estado.candidatos = [];
  if (estado.modo === 'subir') { tira.innerHTML = `<p class="vacio">${esc(t('subirPronto'))}</p>`; return; }
  if (!e) { tira.innerHTML = `<p class="vacio">${esc(t('sinDatos'))}</p>`; return; }
  let gem = e.gemelos.filter(g => enZonaDestino(g.coord));
  let ocultas = 0;
  if (estado.soloViables && CLIMA) { const antes = gem.length; gem = gem.filter(g => { const ev = evalDe(g.region); return !ev || ev.res.dificil === 0; }); ocultas = antes - gem.length; }
  estado.gemelo = gem[0] || null; estado.candidatos = gem;
  const cercanas = gem.filter(g => g.score - gem[0].score <= 0.01).length;
  const nota = cercanas >= 2 ? `<p class="nota dif">${esc(t('empate', cercanas))}</p>` : '';
  const enlaces = [e.img && `<a data-img="${esc(e.img)}">${esc(t('verComparacion'))}</a>`, e.img_top5 && `<a data-img="${esc(e.img_top5)}">${esc(t('verTop5'))}</a>`].filter(Boolean).join('');
  let html = `<div class="tarj ref"><span class="tag">${esc(t('referencia', nombre(estado.ref.cuerpo)))}</span><h4>${esc(nm(e))}</h4>${nums(e.ficha)}`
    + (e.n_evaluados ? `<p class="nota">${esc(t('evaluados', e.n_evaluados, e.resolucion_m))}</p>` : '')
    + nota
    + (ocultas ? `<p class="nota dif">${esc(t('ocultas', ocultas))}</p>` : '')
    + (e.revision ? `<span class="rev">${esc(t('revisar'))}</span>` : '')
    + (enlaces ? `<div class="ver">${enlaces}</div>` : '') + '</div>';
  if (!gem.length) html += `<p class="vacio">${esc(t('ningun'))}</p>`;
  gem.forEach((g, k) => {
    const ev = evalDe(g.region), cl = climaDe(g.region);
    const lineaClima = cl ? `<p class="cl"><span class="punto ${ev.sem}"></span>${esc(t('climaTarj', num1(cl.v.t_media_c), I18N.num(Math.round(cl.v.lluvia_anual_mm))))}</p>` : '';
    html += `<div class="tarjw"><button type="button" class="tarj" data-k="${k}" aria-pressed="${k === 0}"><span class="rk">#${g.rank}<small>${esc(t('puntaje'))} ${fmt3(g.score)} · ${esc(t('menorMejor'))}</small></span>`
      + `<h4>${esc(lugarDe(g))}</h4><p class="cat">${esc(catDe(g))}</p>`
      + `<dl><dt>${t('correlacion')}</dt><dd>${fmt2(g.corr)}</dd></dl>${nums(g.ficha)}`
      + (g.dif ? `<p class="nota dif">${esc(t('difs', I18N.num(g.dif.pendiente), I18N.num(g.dif.rugosidad)))}</p>` : '') + lineaClima + '</button>'
      + (cl ? `<button type="button" class="clima-btn" data-clima="${esc(g.region)}">${esc(t('verClima'))}</button>` : '') + '</div>';
  });
  tira.innerHTML = html;
  const marcas = gem.map(g => L.marker(g.coord).addTo(m.capa).bindPopup(`<b>${esc(lugarDe(g))}</b><br>${esc(t('puntaje'))}: ${fmt3(g.score)} · ${esc(t('correlacion'))}: ${fmt2(g.corr)}`));
  tira.querySelectorAll('button.tarj').forEach(b => b.onclick = () => {
    const k = +b.dataset.k; estado.gemelo = gem[k];
    tira.querySelectorAll('button.tarj').forEach(x => x.setAttribute('aria-pressed', x === b));
    m.mapa.setView(gem[k].coord, estado.dest.cuerpo === 'tierra' ? 8 : 4); marcas[k].openPopup();
  });
  tira.querySelectorAll('button[data-clima]').forEach(b => b.onclick = () => abrirClima(b.dataset.clima));
  tira.querySelectorAll('a[data-img]').forEach(a => a.onclick = () => { $('visor-img').src = a.dataset.img; $('visor').showModal(); });
}

function cambiar() {
  for (const l of ['ref', 'dest'])
    if (!M[l] || M[l].cuerpo !== estado[l].cuerpo) M[l] = nuevoMapa('mapa-' + SUF[l], estado[l].cuerpo, M[l]);
  controles(); dibujarLado('ref'); dibujarLado('dest'); dibujarClima(); pintar();
}

/* ---------- idioma ---------- */
function aplicarIdioma() {
  I18N.aplicar();
  $('idioma').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b.dataset.l === I18N.lang));
  $('sobre-ref').innerHTML = `<p><b>${esc(I18N.t('subirTitulo'))}</b> <span class="etiqueta">${esc(I18N.t('proximamente'))}</span></p><p>${esc(I18N.t('subirTexto'))}</p>`;
  $('rapidas').innerHTML = Asistente.rapidas().map(t => `<button type="button">${esc(t)}</button>`).join('');
  $('rapidas').querySelectorAll('button').forEach(b => b.onclick = () => preguntar(b.textContent));
  llenarCapas();
  if (datos) { _cacheEval.clear(); _zonasClima = null; cambiar(); }
}

/* ---------- Vertikal Bot ---------- */
/* Adaptador de datos para el bot: es el ÚNICO lugar que conoce el esquema del JSON.
   Si el JSON de producción cambia, se ajusta aquí y el bot no se toca. */
/* País y continente de cada una de las 50 zonas: punto en polígono con las fronteras de paises.geojson (Teide cae fuera del mapa de 1:110m y se asigna a mano). */
const OVERRIDE_PAIS = { Teide: ['España', 'Spain', 'europa'] };
let _info = null;
function infoZonas() {
  if (_info) return _info;
  _info = {};
  if (!CLIMA || !TIERRA) return _info;
  for (const [id, r] of Object.entries(CLIMA.regiones)) {
    let pais = null, cont = null;
    outer: for (const c of TIERRA) for (const h of c.hijas) if (puntoEnPais([r.lat, r.lon], h.feat)) { pais = h; cont = c; break outer; }
    if (!pais && OVERRIDE_PAIS[id]) { const [es, en_, cid] = OVERRIDE_PAIS[id]; cont = TIERRA.find(x => x.id === cid); pais = { nombre: es, nombre_en: en_ }; }
    _info[id] = { pais: pais && pais.nombre, pais_en: pais && pais.nombre_en, continente: cont && cont.nombre, continente_en: cont && cont.nombre_en };
  }
  return _info;
}
let _sitios = null;
function sitiosPor() {
  if (_sitios) return _sitios;
  _sitios = {};
  for (const cuerpo of ['luna', 'marte']) {
    const p = datos.cruces[`${cuerpo}-tierra`];
    if (p) _sitios[cuerpo] = p.regiones.map(r => ({ nombre: r.nombre, nombre_en: r.nombre_en, mejor: { lugar: r.gemelos[0].lugar, lugar_en: r.gemelos[0].lugar_en, score: r.gemelos[0].score, corr: r.gemelos[0].corr } }));
  }
  return _sitios;
}
let _zonasClima = null;
function zonasClima() {
  if (!CLIMA) return [];
  if (!_zonasClima) _zonasClima = Object.keys(CLIMA.regiones).map(id => { const r = CLIMA.regiones[id]; return { id, nombre: r.nombre, nombre_en: r.nombre_en, categoria: r.categoria, categoria_en: r.categoria_en, ...infoZonas()[id], lat: r.lat, lon: r.lon, clima: contextoClima({ region: id }) }; });
  return _zonasClima;
}
function contextoClima(g) {
  const r = g && climaDe(g.region), e = g && evalDe(g.region); if (!r || !e) return null;
  return { nombre: r.nombre, nombre_en: r.nombre_en, sem: e.sem, res: e.res,
           factores: e.f.map(f => { const v = VAR(f.id); return { id: f.id, nombre: v.nombre, nombre_en: v.nombre_en, valor: f.valor, unidad: v.unidad, estado: f.estado }; }) };
}
function contexto() {
  const z = pSel('dest') || zSel('dest');
  return { exploratorio: !!datos.exploratorio, metodo: datos.metodo, origen: nombre(estado.ref.cuerpo), destino: nombre(estado.dest.cuerpo), zona: z ? nm(z) : null,
           region: entradaActual(), candidatos: (estado.candidatos || []).map(g => ({ ...g, clima: contextoClima(g), ...(infoZonas()[g.region] || {}) })), gemelo: estado.gemelo,
           origenId: estado.ref.cuerpo, sitiosPor: sitiosPor(), paises: TIERRA.flatMap(c => c.hijas.map(h => ({ nombre: h.nombre, nombre_en: h.nombre_en }))), continentes: TIERRA.map(c => ({ nombre: c.nombre, nombre_en: c.nombre_en })),
           clima: contextoClima(estado.gemelo), zonasClima: zonasClima(), viabilidad: (estado.candidatos || []).map(g => { const e = evalDe(g.region); return e ? { lugar: g.lugar, lugar_en: g.lugar_en, sem: e.sem, dificiles: e.res.dificil, atencion: e.res.atencion } : null; }).filter(Boolean),
           climaMeta: CLIMA ? { periodo: CLIMA.periodo, resolucion: CLIMA.resolucion, fuente: CLIMA.fuente } : null };
}
function chat(texto, quien, sugerencias) {
  const d = document.createElement('div'); d.className = 'msg ' + quien; d.textContent = texto;
  if (sugerencias && sugerencias.length) {
    const caja = document.createElement('div'); caja.className = 'sug';
    sugerencias.forEach(q => {
      const b = document.createElement('button'); b.type = 'button';
      if (typeof q === 'string') { b.textContent = q; b.onclick = () => preguntar(q); }
      else { b.textContent = q.etiqueta; b.onclick = () => { b.disabled = true; b.remove(); chat(q.respuesta, 'bot'); }; }   // "Más detalle": muestra el texto ampliado
      caja.appendChild(b);
    });
    d.appendChild(caja);
  }
  $('chat').appendChild(d); $('chat').scrollTop = $('chat').scrollHeight;
}
function preguntar(t) { chat(t, 'yo'); const r = Asistente.responder(t, contexto()); chat(r.texto, 'bot', r.sugerencias); }
function abrirChat(v) { $('asistente').hidden = !v; $('abrir-chat').setAttribute('aria-expanded', v); if (v) $('pregunta').focus(); }

async function iniciar() {
  progreso(15, I18N.t('cargandoDatos'));
  const [d, paises, clima] = await Promise.all([traer('resultados.json'), traer('paises.geojson'), traer('clima.json').catch(() => null)]);
  datos = d; CLIMA = clima;
  progreso(55, I18N.t('preparando'));
  TIERRA = datos.continentes.map(c => ({ ...c, hijas: paises.features.filter(f => f.properties.cont === c.id)
    .map(f => ({ id: f.properties.id, nombre: f.properties.nombre, nombre_en: f.properties.en, feat: f, bbox: mayorPoligono(f.geometry) }))
    .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es')) }));
  estado.ref.zona = primero('luna');
  $('aviso').hidden = !(datos.muestra || datos.exploratorio);
  $('cerrar-visor').onclick = () => $('visor').close();
  $('cerrar-clima').onclick = () => $('clima-panel').close();
  $('clima-panel').addEventListener('click', e => { if (e.target === $('clima-panel')) $('clima-panel').close(); });
  $('capa-clima').onchange = e => { estado.capa = e.target.value; dibujarClima(); };
  $('solo-viables').onchange = e => { estado.soloViables = e.target.checked; pintar(); };
  $('visor').addEventListener('click', e => { if (e.target === $('visor')) $('visor').close(); });


  buscador('ref', () => itemsLado('ref'), i => alElegirItem('ref', i));
  buscador('dest', () => itemsLado('dest'), i => alElegirItem('dest', i));

  $('abrir-chat').onclick = () => abrirChat($('asistente').hidden);
  $('cerrar-chat').onclick = () => abrirChat(false);
  $('idioma').querySelectorAll('button').forEach(b => b.onclick = () => { I18N.set(b.dataset.l); aplicarIdioma(); });
  $('form-chat').onsubmit = e => { e.preventDefault(); const t = $('pregunta').value.trim(); if (t) { preguntar(t); $('pregunta').value = ''; } };
  chat(I18N.t('saludo'), 'bot');

  aplicarIdioma();
  traer('bot_modelo.json').then(BotNN.cargar).catch(() => { /* sin red neuronal: el bot usa reglas */ });
  progreso(100, I18N.t('listo'));
  setTimeout(() => { $('carga').classList.add('fuera'); [M.ref, M.dest].forEach(m => m.mapa._loaded && m.mapa.invalidateSize()); }, 250);
  window.addEventListener('resize', () => [M.ref, M.dest].forEach(m => m.mapa._loaded && m.mapa.invalidateSize()));
}

iniciar().catch(err => { $('carga-texto').textContent = I18N.t('errorDatos'); console.error(err); });
