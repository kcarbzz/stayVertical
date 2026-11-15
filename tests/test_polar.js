/* Pruebas de la proyección polar (node tests/test_polar.js): debe reproducir las posiciones del modelo de elevación del equipo. */
const assert = require('assert'), fs = require('fs'), path = require('path');
const Polar = require(path.join(__dirname, '..', 'docs', 'polar.js'));
let ok = 0, fallos = 0;
const prueba = (n, f) => { try { f(); ok++; console.log('  ok  ', n); } catch (e) { fallos++; console.log('  FALLA', n, '\n       ', e.message); } };

prueba('el polo está en el origen', () => { const [y, x] = Polar.aPolar([-90, 0]); assert.ok(Math.abs(y) < 1e-9 && Math.abs(x) < 1e-9); });
prueba('0° de longitud queda arriba y 90° E a la derecha', () => {
  const [y0, x0] = Polar.aPolar([-85, 0]), [y90, x90] = Polar.aPolar([-85, 90]), [y180, x180] = Polar.aPolar([-85, 180]);
  assert.ok(y0 > 0 && Math.abs(x0) < 1e-9 && x90 > 0 && Math.abs(y90) < 1e-9 && y180 < 0 && Math.abs(x180) < 1e-9);
});
prueba('ida y vuelta (proyectar y des-proyectar) con error < 1e-9°', () => {
  for (const ll of [[-89.9, 129.2], [-86.9, -4], [-84.9, -35.5], [-75, 170]]) { const b = Polar.dePolar(Polar.aPolar(ll)); assert.ok(Math.abs(b[0] - ll[0]) < 1e-9 && Math.abs(b[1] - ll[1]) < 1e-9, JSON.stringify([ll, b])); }
});
prueba('a 75° S el radio es 457,5 km (el radio del mosaico LOLA de NASA Trek: ±457 440 m)', () => {
  const [y] = Polar.aPolar([-75, 0]); assert.ok(Math.abs(y * Polar.RES0 - 457440) < 300, y * Polar.RES0);
});
prueba('ORIGEN = 128 unidades (cuadrícula de Trek: 1 095 930 m / 8 561,953 m)', () => assert.ok(Math.abs(Polar.ORIGEN - 128) < 1e-3));
prueba('los 8 sitios lunares caen donde el equipo los tiene en su modelo de elevación (±3,5 km, tras el polo en el píxel 3775)', () => {
  // fila, columna del DEM LDEM_80S (7600×7600 a 80 m) según estado_8_luna.csv del equipo
  const dem = { haworth: [2602, 3693], malapert: [2260, 3851], degerlache: [3746, 3207], nobile: [2687, 5234], cabeus: [2200, 2651], shackleton: [3798, 3804], faustini: [3544, 4772], shoemaker: [3264, 4283] };
  const sitios = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'docs', 'resultados.json'))).conocidas.luna;
  assert.strictEqual(sitios.length, 8);
  for (const s of sitios) {
    const [fila, col] = dem[s.id], [y, x] = Polar.aPolar(s.coord);
    const dx = x * Polar.RES0 / 1000 - (col - 3775) * 0.08, dy = y * Polar.RES0 / 1000 - (3775 - fila) * 0.08;
    assert.ok(Math.hypot(dx, dy) < 3.5, `${s.id}: ${Math.hypot(dx, dy).toFixed(2)} km`);
  }
});
console.log(`\n${ok} bien, ${fallos} con falla`); process.exit(fallos ? 1 : 0);
