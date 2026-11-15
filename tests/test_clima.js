/* Pruebas del semáforo climático con los datos reales de docs/clima.json (node tests/test_clima.js). */
const assert = require('assert'), fs = require('fs'), path = require('path');
const raiz = path.join(__dirname, '..');
const Clima = require(path.join(raiz, 'docs', 'clima.js'));
const datos = JSON.parse(fs.readFileSync(path.join(raiz, 'docs', 'clima.json'), 'utf-8'));
let ok = 0, fallos = 0;
const prueba = (n, f) => { try { f(); ok++; console.log('  ok  ', n); } catch (e) { fallos++; console.log('  FALLA', n, '\n       ', e.message); } };
const ev = (reg) => Object.fromEntries(Clima.evaluar(datos.regiones[reg], datos.variables).map(f => [f.id, f.estado]));

prueba('mayor_peor: bordes (atención en el umbral, difícil en el umbral)', () => {
  const u = { tipo: 'mayor_peor', atencion: 38, dificil: 45 };
  assert.deepStrictEqual([37.99, 38, 44.99, 45].map(v => Clima.estado(v, u)), ['ok', 'atencion', 'atencion', 'dificil']);
});
prueba('menor_peor: bordes', () => {
  const u = { tipo: 'menor_peor', atencion: 75, dificil: 60 };
  assert.deepStrictEqual([75.01, 75, 60.01, 60].map(v => Clima.estado(v, u)), ['ok', 'atencion', 'atencion', 'dificil']);
});
prueba('rango: dentro, fuera por abajo y por arriba, y muy fuera', () => {
  const u = { tipo: 'rango', atencion: [100, 1500], dificil: [25, 3000] };
  assert.deepStrictEqual([500, 50, 2000, 10, 3500].map(v => Clima.estado(v, u)), ['ok', 'atencion', 'atencion', 'dificil', 'dificil']);
});
prueba('valor ausente -> "sin" (no inventa estado)', () => { assert.strictEqual(Clima.estado(undefined, { tipo: 'mayor_peor', atencion: 1, dificil: 2 }), 'sin'); });
prueba('datos: 50 regiones y 13 variables, sin valores ausentes', () => {
  assert.strictEqual(Object.keys(datos.regiones).length, 50); assert.strictEqual(datos.variables.length, 13);
  for (const r of Object.values(datos.regiones)) { assert.strictEqual(r.mensual.length, 12); for (const v of datos.variables) assert.ok(Number.isFinite(r.v[v.id]), v.id); }
});
prueba('Everest: presión baja = difícil (gran altitud)', () => assert.strictEqual(ev('Everest').presion_kpa, 'dificil'));
prueba("Rub' al Khali: temperatura máxima extrema = difícil", () => assert.strictEqual(ev('RubAlKhali').t_max_ext_c, 'dificil'));
prueba('Atacama: lluvia casi nula = atención (no difícil)', () => assert.strictEqual(ev('Atacama').lluvia_anual_mm, 'atencion'));
prueba('Monterrey: temperatura máxima 37,6 °C = ok (bajo el umbral de 38)', () => assert.strictEqual(ev('Monterrey').t_max_ext_c, 'ok'));
prueba('el semáforo global no es degenerado (hay verdes, ámbares y rojos)', () => {
  const c = {}; for (const r of Object.values(datos.regiones)) { const s = Clima.semaforo(Clima.resumen(Clima.evaluar(r, datos.variables))); c[s] = (c[s] || 0) + 1; }
  console.log('         reparto:', JSON.stringify(c));
  assert.ok(c.verde > 0 && c.ambar > 0 && c.rojo > 0, JSON.stringify(c));
});
prueba('resumen suma 13 factores', () => {
  const r = Clima.resumen(Clima.evaluar(datos.regiones.Teide, datos.variables)); assert.strictEqual(r.ok + r.atencion + r.dificil + r.sin, 13);
});
prueba('escala de color: extremos distintos y valor fuera de rango se recorta', () => {
  assert.notStrictEqual(Clima.color(0, 0, 10), Clima.color(10, 0, 10)); assert.strictEqual(Clima.color(-5, 0, 10), Clima.color(0, 0, 10));
  assert.ok(/^rgb\(/.test(Clima.color(5, 5, 5)));
});
prueba('rango de una variable coincide con los datos (T media entre −2,9 y 29,9 °C)', () => {
  const [a, b] = Clima.rango(datos.regiones, 't_media_c'); assert.ok(Math.abs(a - (-2.88)) < 0.01 && Math.abs(b - 29.89) < 0.01, `${a} ${b}`);
});
console.log(`\n${ok} bien, ${fallos} con falla`); process.exit(fallos ? 1 : 0);
