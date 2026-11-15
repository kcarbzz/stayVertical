/* Comprueba docs/barrido.json, lo que la web muestra en «Barrido automático» (node tests/test_barrido_web.js). */
const assert = require('assert'), path = require('path'), fs = require('fs');
const leer = f => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'docs', f), 'utf8'));
const barrido = leer('barrido.json'), datos = leer('resultados.json');
let bien = 0, mal = 0;
const prueba = (n, f) => { try { f(); bien++; } catch (e) { mal++; console.error('FALLA: ' + n + '\n  ' + e.message); } };
const relieveOk = (r, n) => r && r.n === n && Buffer.from(r.datos, 'base64').length === n * n && r.max >= r.min;

for (const [par, c] of Object.entries(barrido.cruces)) {
  const cuerpo = par.split('-')[0], ids = datos.conocidas[cuerpo].map(s => s.id), n = c.meta.tam_px;
  prueba(`${par}: están todos los sitios de la web`, () => assert.deepStrictEqual(Object.keys(c.sitios).sort(), [...ids].sort()));
  prueba(`${par}: el relieve de cada sitio coincide con la ficha publicada`, () => {
    for (const e of datos.cruces[par].regiones) {
      const s = c.sitios[e.id];
      assert.ok(Math.abs(s.ficha.pendiente_media - e.ficha.pendiente_media) <= 0.11, `${e.id} pendiente ${s.ficha.pendiente_media} / ${e.ficha.pendiente_media}`);
      assert.ok(Math.abs(s.ficha.rugosidad_m - e.ficha.rugosidad_m) <= 0.11, `${e.id} rugosidad`);
      assert.ok(relieveOk(s.relieve, n) && relieveOk(s.forma, n), e.id);
    }
  });
  prueba(`${par}: candidatos ordenados, con coordenadas dentro de una franja barrida`, () => {
    for (const [id, s] of Object.entries(c.sitios)) {
      assert.ok(s.candidatos.length > 0, id);
      s.candidatos.forEach((g, k) => {
        assert.strictEqual(g.puesto, k + 1, id);
        if (k) assert.ok(g.score >= s.candidatos[k - 1].score, `${id} #${g.puesto}`);
        assert.ok(g.corr <= 1 && g.corr >= -1 && [0, 90, 180, 270].includes(g.rot), id);
        assert.ok(c.meta.franjas.some(f => g.coord[0] >= f.caja[0] && g.coord[0] <= f.caja[2] && g.coord[1] >= f.caja[1] && g.coord[1] <= f.caja[3]), `${id} #${g.puesto} ${g.coord}`);
        if (g.relieve) assert.ok(relieveOk(g.relieve, n) && relieveOk(g.forma, n), `${id} #${g.puesto}`);
      });
      assert.ok(s.candidatos[0].relieve, id);
    }
  });
  prueba(`${par}: el barrido cubre más de una franja y miles de cuadros`, () => {
    const usadas = new Set(Object.values(c.sitios).flatMap(s => s.candidatos.map(g => g.franja)));
    assert.ok(c.meta.cuadros > 100000, 'cuadros ' + c.meta.cuadros); assert.ok(usadas.size > 1, [...usadas].join());
  });
}
console.log(`${bien} bien, ${mal} con falla`);
process.exit(mal ? 1 : 0);
