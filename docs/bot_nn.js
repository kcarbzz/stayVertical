/* Clasificador de intenciones de Vertikal Bot: red neuronal pequeña (texto -> intención).
   Los pesos están en bot_modelo.json (int8, ~156 KB) y se entrenan con entrenamiento/entrenar.py.
   La normalización y los hashes deben ser idénticos a los de ese script. */
const BotNN = (() => {
  let M = null;

  const normalizar = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/%/g, ' pct ').replace(/[0-9]+/g, ' 0 ').replace(/[^a-z ]/g, ' ').replace(/\s+/g, ' ').trim();

  function fnv(t) {
    let h = 2166136261;
    for (let i = 0; i < t.length; i++) { h ^= t.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
    return h >>> 0;
  }

  function caracteristicas(texto, dim) {
    const s = normalizar(texto), cont = new Map(), p = ' ' + s + ' ';
    const suma = k => cont.set(k, (cont.get(k) || 0) + 1);
    for (const n of [2, 3, 4]) for (let i = 0; i + n <= p.length; i++) suma(fnv(p.slice(i, i + n)) % dim);
    for (const w of s.split(' ')) if (w) suma(fnv('w:' + w) % dim);
    let norma = 0; for (const v of cont.values()) norma += v * v;
    norma = Math.sqrt(norma) || 1;
    return [...cont].map(([k, v]) => [k, v / norma]);
  }

  const deq = (o, T = Float32Array) => { const a = new T(o.q.length); for (let i = 0; i < a.length; i++) a[i] = o.q[i] * o.e; return a; };

  function cargar(json) {
    M = { dim: json.dim, h: json.ocultas, intents: json.intents, vocab: new Set(json.vocab || []), w1: deq(json.w1), b1: deq(json.b1), w2: deq(json.w2), b2: deq(json.b2) };
    return M;
  }

  /* Devuelve [[intención, probabilidad], ...] de mayor a menor, o null si el modelo no está cargado. */
  function clasificar(texto) {
    if (!M) return null;
    const { dim, h: H, intents, w1, b1, w2, b2 } = M, K = intents.length;
    const oc = Float32Array.from(b1);
    for (const [k, v] of caracteristicas(texto, dim)) { const o = k * H; for (let j = 0; j < H; j++) oc[j] += v * w1[o + j]; }
    const z = Float32Array.from(b2);
    for (let j = 0; j < H; j++) { const a = oc[j] > 0 ? oc[j] : 0; if (a) for (let c = 0; c < K; c++) z[c] += a * w2[j * K + c]; }
    const mx = Math.max(...z); let s = 0; const e = Array.from(z, v => { const x = Math.exp(v - mx); s += x; return x; });
    return intents.map((n, c) => [n, e[c] / s]).sort((a, b) => b[1] - a[1]);
  }

  /* Fracción de palabras de la pregunta que aparecieron en el entrenamiento. Con texto desconocido
     (p. ej. letras al azar) la red puede responder con falsa seguridad; esto sirve para no fiarse de ella. */
  function fraccionConocida(texto) {
    const w = normalizar(texto).split(' ').filter(x => x.length > 1);
    if (!M || !w.length) return 0;
    return w.filter(x => M.vocab.has(x)).length / w.length;
  }

  return { cargar, clasificar, fraccionConocida, normalizar, get listo() { return !!M; } };
})();
if (typeof module !== 'undefined') module.exports = BotNN;
