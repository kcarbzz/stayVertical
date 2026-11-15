/* Lógica del semáforo climático (funciones puras, sin DOM).
   Los umbrales viven en clima.json (provisionales, ajustables); aquí solo se aplican. */
const Clima = (() => {
  function estado(v, u) {
    if (v == null || Number.isNaN(v)) return 'sin';
    if (u.tipo === 'mayor_peor') return v >= u.dificil ? 'dificil' : v >= u.atencion ? 'atencion' : 'ok';
    if (u.tipo === 'menor_peor') return v <= u.dificil ? 'dificil' : v <= u.atencion ? 'atencion' : 'ok';
    if (u.tipo === 'rango') {
      const [a0, a1] = u.atencion, [d0, d1] = u.dificil;
      return (v < d0 || v > d1) ? 'dificil' : (v < a0 || v > a1) ? 'atencion' : 'ok';
    }
    return 'sin';
  }

  /* region: {v:{id:valor}}; variables: lista de clima.json -> [{id, valor, estado}] */
  const evaluar = (region, variables) => variables.map(x => ({ id: x.id, valor: region.v[x.id], estado: estado(region.v[x.id], x.umbral) }));

  const resumen = factores => factores.reduce((r, f) => { if (r[f.estado] != null) r[f.estado]++; return r; }, { ok: 0, atencion: 0, dificil: 0, sin: 0 });

  /* Semáforo global PROVISIONAL: verde (0 difíciles y ≤3 en atención), ámbar (1–2 difíciles o ≥4 en atención), rojo (≥3 difíciles). */
  const semaforo = r => (r.dificil >= 3 ? 'rojo' : (r.dificil >= 1 || r.atencion >= 4) ? 'ambar' : 'verde');

  /* Escala neutra azul -> amarillo -> rojo (no implica bueno/malo). */
  function color(valor, min, max) {
    const t = max > min ? Math.min(1, Math.max(0, (valor - min) / (max - min))) : 0.5;
    const A = [59, 130, 196], B = [255, 209, 102], C = [229, 105, 79];
    const mezcla = (p, q, k) => p.map((x, i) => Math.round(x + (q[i] - x) * k));
    const c = t < 0.5 ? mezcla(A, B, t * 2) : mezcla(B, C, (t - 0.5) * 2);
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  }

  const rango = (regiones, id) => { const x = Object.values(regiones).map(r => r.v[id]); return [Math.min(...x), Math.max(...x)]; };

  return { estado, evaluar, resumen, semaforo, color, rango };
})();
if (typeof module !== 'undefined') module.exports = Clima;
