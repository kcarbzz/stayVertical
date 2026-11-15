/* Pruebas de la ficha de analogía (node tests/test_analogia.js). */
const assert = require('assert'), path = require('path'), fs = require('fs');
const Analogia = require(path.join(__dirname, '..', 'docs', 'analogia.js'));
const leer = f => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'docs', f), 'utf8'));
const clima = leer('clima.json'), datos = leer('resultados.json'), ana = leer('analogia.json');
let bien = 0, mal = 0;
const prueba = (n, f) => { try { f(); bien++; } catch (e) { mal++; console.error('FALLA: ' + n + '\n  ' + e.message); } };

const R = { a: { v: { x: 1 } }, b: { v: { x: 5 } }, c: { v: { x: 5 } }, d: { v: { x: 9 } } };
prueba('puesto: 1 = valor más bajo y los empates comparten puesto', () => {
  assert.deepStrictEqual(Analogia.puesto(R, 'a', 'x'), { puesto: 1, de: 4, valor: 1 });
  assert.strictEqual(Analogia.puesto(R, 'b', 'x').puesto, 2);
  assert.strictEqual(Analogia.puesto(R, 'c', 'x').puesto, 2);
  assert.strictEqual(Analogia.puesto(R, 'd', 'x').puesto, 4);
  assert.strictEqual(Analogia.puesto(R, 'z', 'x'), null);
});
prueba('tercio reparte el catálogo en tres', () => {
  assert.strictEqual(Analogia.tercio(1, 50), 'cerca'); assert.strictEqual(Analogia.tercio(17, 50), 'cerca');
  assert.strictEqual(Analogia.tercio(18, 50), 'medio'); assert.strictEqual(Analogia.tercio(34, 50), 'medio');
  assert.strictEqual(Analogia.tercio(35, 50), 'lejos'); assert.strictEqual(Analogia.tercio(50, 50), 'lejos');
});
prueba('forma según la correlación', () => {
  assert.strictEqual(Analogia.forma(0.77), 'alta'); assert.strictEqual(Analogia.forma(0.7), 'alta');
  assert.strictEqual(Analogia.forma(0.5), 'media'); assert.strictEqual(Analogia.forma(0.1), 'baja');
});
prueba('pendiente: similar hasta 3° y nula si falta un dato', () => {
  assert.deepStrictEqual(Analogia.pendiente({ pendiente_media: 13.7 }, { pendiente_media: 4.1 }), { ref: 13.7, zona: 4.1, dif: -9.6, estado: 'menor' });
  assert.strictEqual(Analogia.pendiente({ pendiente_media: 2 }, { pendiente_media: 4.5 }).estado, 'similar');
  assert.strictEqual(Analogia.pendiente({ pendiente_media: 2 }, { pendiente_media: 9 }).estado, 'mayor');
  assert.strictEqual(Analogia.pendiente({ pendiente_media: 2 }, undefined), null);
});
prueba('uso según la pendiente del sitio', () => {
  assert.strictEqual(Analogia.uso({ pendiente_media: 32.1 }), 'fuerte'); assert.strictEqual(Analogia.uso({ pendiente_media: 8 }), 'moderada');
  assert.strictEqual(Analogia.uso({ pendiente_media: 0.5 }), 'llano'); assert.strictEqual(Analogia.uso(null), null);
});
prueba('con los datos reales: la meseta tibetana es la zona más fría y la de menos presión', () => {
  assert.strictEqual(Analogia.puesto(clima.regiones, 'TibetanPlateau', 't_media_c').puesto, 1);
  assert.strictEqual(Analogia.puesto(clima.regiones, 'TibetanPlateau', 'presion_kpa').puesto, 1);
});
prueba('todos los candidatos publicados tienen perfil completo', () => {
  for (const par of Object.values(datos.cruces)) for (const e of par.regiones) for (const g of e.gemelos) {
    const p = Analogia.perfil(g, e, clima.regiones);
    assert.strictEqual(p.clima.length, 3, g.region); assert.ok(p.uso, e.id); assert.ok(['alta', 'media', 'baja'].includes(p.forma.estado));
  }
});
prueba('las zonas marcadas como análogo conocido existen en el catálogo y tienen motivo en los dos idiomas', () => {
  for (const [id, c] of Object.entries(ana.conocidos)) { assert.ok(clima.regiones[id], id); assert.ok(c.motivo && c.motivo_en, id); }
});
/* Regla del equipo: solo fuentes de agencias espaciales (NASA, ESA, JAXA, KASA). */
const AGENCIA = /^https:\/\/([a-z0-9-]+\.)*(nasa\.gov|esa\.int|jaxa\.jp|kasa\.go\.kr)\//;
prueba('todas las fuentes de la ficha son de una agencia espacial', () => {
  for (const [id, c] of Object.entries(ana.conocidos)) { assert.ok(c.fuente, id); assert.ok(AGENCIA.test(c.url), id + ' ' + c.url); }
  for (const c of ['luna', 'marte']) { assert.ok(ana.cuerpos[c].fuentes.length, c); for (const f of ana.cuerpos[c].fuentes) assert.ok(AGENCIA.test(f.url), f.url); }
});
prueba('hay valores de referencia para la Luna y para Marte', () => {
  for (const c of ['luna', 'marte']) for (const k of ['t_ref_c', 'presion_kpa', 'lluvia_mm', 'gravedad_ms2', 'fuentes']) assert.ok(ana.cuerpos[c][k] != null, c + '.' + k);
});
prueba('equivalentes cuenta los candidatos a 0,01 o menos del mejor', () => {
  assert.strictEqual(Analogia.equivalentes([{ score: 0.1 }, { score: 0.105 }, { score: 0.11 }, { score: 0.2 }]), 3);
  assert.strictEqual(Analogia.equivalentes([{ score: 0.1 }, { score: 0.2 }]), 1);
  assert.strictEqual(Analogia.equivalentes([]), 0);
});
prueba('brecha de pendiente: marca los cuatro sitios de la auditoría y ninguno más', () => {
  const marcados = [];
  for (const par of Object.values(datos.cruces)) for (const e of par.regiones) if (Analogia.brecha(e)) marcados.push(e.id);
  assert.deepStrictEqual(marcados.sort(), ['faustini', 'gale', 'haworth', 'shackleton']);
});
prueba('hallazgos: cuenta, ordena y recuerda el mejor sitio', () => {
  const g = (r, s) => ({ region: r, lugar: r, score: s });
  const h = Analogia.hallazgos([{ id: 's1', gemelos: [g('A', 1), g('B', 2), g('C', 3), g('D', 4)] }, { id: 's2', gemelos: [g('B', 1), g('A', 2), g('E', 3)] }, { id: 's3', gemelos: [g('B', 1)] }]);
  assert.deepStrictEqual(h[0], { region: 'B', lugar: 'B', lugar_en: undefined, top: 3, primero: 2, de: 3, sitio: 's2' });
  assert.deepStrictEqual([h[1].region, h[1].top, h[1].primero, h[1].sitio], ['A', 2, 1, 's1']);
  assert.ok(!h.some(x => x.region === 'D'));
});
prueba('hallazgos con los datos reales: Fuji en la Luna y Roter Kamm en Marte, 5 sitios cada uno', () => {
  const l = Analogia.hallazgos(datos.cruces['luna-tierra'].regiones)[0], m = Analogia.hallazgos(datos.cruces['marte-tierra'].regiones)[0];
  assert.deepStrictEqual([l.region, l.top, l.de], ['Fuji', 5, 8]); assert.deepStrictEqual([m.region, m.top, m.de], ['RoterKamm', 5, 10]);
});
const barrido = leer('barrido.json'), climaB = leer('clima_barrido.json');
prueba('puestoValor compara un valor suelto con el catálogo', () => {
  assert.deepStrictEqual(Analogia.puestoValor(R, 'x', 0), { puesto: 1, de: 5, masQue: 4, zonas: 4, valor: 0 });
  assert.deepStrictEqual(Analogia.puestoValor(R, 'x', 5), { puesto: 2, de: 5, masQue: 1, zonas: 4, valor: 5 });
  assert.strictEqual(Analogia.puestoValor(R, 'x', 100).masQue, 0);
  assert.strictEqual(Analogia.puestoValor(R, 'x', undefined), null);
});
prueba('todos los candidatos del barrido tienen perfil completo con su clima', () => {
  for (const [par, c] of Object.entries(barrido.cruces)) for (const e of datos.cruces[par].regiones) for (const g of c.sitios[e.id].candidatos) {
    const cl = climaB.puntos[`${g.coord[0].toFixed(5)},${g.coord[1].toFixed(5)}`];
    const p = Analogia.perfilPunto(g, e, cl, clima.regiones);
    assert.strictEqual(p.clima.length, 3, e.id); assert.ok(p.pendiente && p.uso, e.id);
    for (const d of p.clima) assert.ok(d.zonas === 50 && d.masQue >= 0 && d.masQue <= 50 && ['cerca', 'medio', 'lejos'].includes(d.estado), e.id);
  }
});
prueba('resumenBarrido: un mejor candidato por sitio, franjas ordenadas y sitios fuera de rango', () => {
  const g = (f, s) => ({ franja: f, franja_en: f, score: s });
  const r = Analogia.resumenBarrido({ a: { fuera_de_rango: true, candidatos: [g('X', 1), g('Y', 2)] }, b: { candidatos: [g('Y', 1)] }, c: { candidatos: [g('Y', 3)] }, d: { candidatos: [] } }, ['c', 'a', 'b', 'd']);
  assert.deepStrictEqual(r.filas.map(x => x.id), ['c', 'a', 'b']); assert.strictEqual(r.de, 3);
  assert.deepStrictEqual(r.porFranja.map(x => [x.franja, x.n]), [['Y', 2], ['X', 1]]); assert.deepStrictEqual(r.fuera, ['a']);
});
prueba('resumenBarrido con los datos reales: los cinco sitios fuera de rango', () => {
  const fuera = ['luna', 'marte'].flatMap(c => Analogia.resumenBarrido(barrido.cruces[`${c}-tierra`].sitios).fuera).sort();
  assert.deepStrictEqual(fuera, ['faustini', 'gale', 'haworth', 'shackleton', 'valles']);
});
console.log(`${bien} bien, ${mal} con falla`);
process.exit(mal ? 1 : 0);
