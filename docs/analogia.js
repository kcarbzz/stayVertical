/* Ficha de analogía (funciones puras, sin DOM).
   Separa FIDELIDAD (cuánto se parece la zona terrestre al sitio de la Luna o Marte, dimensión por dimensión)
   de LOGÍSTICA (el semáforo de clima.js). Los cortes son provisionales y solo sirven para dar una lectura en palabras. */
const Analogia = (() => {
  /* Dimensiones climáticas: en la Luna y en Marte todo es más frío, más seco y con menos aire que en la Tierra,
     así que "más cerca" siempre es el valor más bajo. */
  const DIMS = [
    { id: 'frio', variable: 't_media_c' },
    { id: 'aridez', variable: 'lluvia_anual_mm' },
    { id: 'aire', variable: 'presion_kpa' },
  ];

  /* Puesto de una zona dentro del catálogo (1 = valor más bajo). Los empates comparten el mejor puesto. */
  function puesto(regiones, id, variable) {
    const r = regiones[id]; if (!r || r.v[variable] == null) return null;
    const vals = Object.values(regiones).map(x => x.v[variable]).filter(x => x != null);
    return { puesto: 1 + vals.filter(x => x < r.v[variable]).length, de: vals.length, valor: r.v[variable] };
  }
  /* Tercio del catálogo: 'cerca' (tercio más bajo), 'medio' o 'lejos'. */
  const tercio = (p, de) => (p <= Math.ceil(de / 3) ? 'cerca' : p <= Math.ceil(2 * de / 3) ? 'medio' : 'lejos');

  /* Forma del relieve según la correlación (cortes provisionales). */
  const forma = corr => (corr >= 0.7 ? 'alta' : corr >= 0.4 ? 'media' : 'baja');
  /* Pendiente de la zona frente a la del sitio: null si falta alguna. */
  function pendiente(ref, zona) {
    if (!ref || !zona || ref.pendiente_media == null || zona.pendiente_media == null) return null;
    const d = Math.round((zona.pendiente_media - ref.pendiente_media) * 10) / 10;
    return { ref: ref.pendiente_media, zona: zona.pendiente_media, dif: d, estado: Math.abs(d) <= 3 ? 'similar' : d < 0 ? 'menor' : 'mayor' };
  }

  /* Para qué sirve un sitio de referencia según su pendiente media. */
  const uso = ficha => (!ficha || ficha.pendiente_media == null ? null : ficha.pendiente_media >= 15 ? 'fuerte' : ficha.pendiente_media >= 5 ? 'moderada' : 'llano');

  /* Perfil completo de un candidato. g = gemelo de resultados.json; e = entrada del sitio de referencia. */
  function perfil(g, e, regiones) {
    return {
      forma: { corr: g.corr, estado: forma(g.corr) },
      pendiente: pendiente(e.ficha, g.ficha),
      clima: DIMS.map(d => { const p = puesto(regiones, g.region, d.variable); return p && { id: d.id, ...p, estado: tercio(p.puesto, p.de) }; }).filter(Boolean),
      uso: uso(e.ficha),
    };
  }

  /* Un valor suelto (un candidato del barrido) frente al catálogo: cuántas zonas del catálogo quedan por encima de él.
     `puesto` es el que ocuparía si se añadiera al catálogo (1 = valor más bajo). */
  function puestoValor(regiones, variable, valor) {
    if (valor == null || !Number.isFinite(valor)) return null;
    const vals = Object.values(regiones).map(x => x.v[variable]).filter(x => x != null);
    return { puesto: 1 + vals.filter(x => x < valor).length, de: vals.length + 1, masQue: vals.filter(x => x > valor).length, zonas: vals.length, valor };
  }

  /* Perfil de un candidato del barrido automático. g = candidato de barrido.json; e = sitio de referencia;
     clima = su punto de clima_barrido.json; regiones = el catálogo, que sirve de vara de medir para el clima. */
  function perfilPunto(g, e, clima, regiones) {
    return {
      forma: { corr: g.corr, estado: forma(g.corr) },
      pendiente: pendiente(e.ficha, g.ficha),
      clima: DIMS.map(d => { const p = puestoValor(regiones, d.variable, clima && clima.v[d.variable]); return p && { id: d.id, ...p, estado: tercio(p.puesto, p.de) }; }).filter(Boolean),
      uso: uso(e.ficha),
    };
  }

  /* Resumen del barrido de un cuerpo. sitios = barrido.cruces[...].sitios; orden = ids en el orden de la web.
     Devuelve el mejor candidato de cada sitio, cuántos primeros puestos reúne cada franja y qué sitios quedan fuera de rango. */
  function resumenBarrido(sitios, orden) {
    const filas = (orden || Object.keys(sitios)).filter(id => sitios[id] && sitios[id].candidatos.length)
      .map(id => ({ id, fuera: !!sitios[id].fuera_de_rango, mejor: sitios[id].candidatos[0] }));
    const f = {};
    filas.forEach(x => { const k = x.mejor.franja; (f[k] ||= { franja: k, franja_en: x.mejor.franja_en, n: 0 }).n++; });
    return { filas, porFranja: Object.values(f).sort((a, b) => b.n - a.n || a.franja.localeCompare(b.franja)), fuera: filas.filter(x => x.fuera).map(x => x.id), de: filas.length };
  }

  /* Lista corta: cuántos candidatos, desde el primero, quedan a `tol` o menos del mejor puntaje. Con 2 o más, su orden no es fiable. */
  const equivalentes = (gem, tol = 0.01) => (gem.length ? gem.filter(g => g.score - gem[0].score <= tol + 1e-12).length : 0);

  /* Brecha de pendiente: el mejor candidato del sitio queda a más de `umbral` grados de la pendiente del sitio (corte provisional).
     Ahí el parecido es de forma, no de inclinación. */
  function brecha(e, umbral = 5) {
    const p = e.gemelos && e.gemelos[0] ? pendiente(e.ficha, e.gemelos[0].ficha) : null;
    return p && Math.abs(p.dif) > umbral ? p : null;
  }

  /* Hallazgos: zonas que más se repiten entre los `n` primeros candidatos de los sitios de un cruce.
     regiones = lista de sitios (cada uno con `gemelos` ordenados). Devuelve, de más a menos repetida:
     { region, lugar, lugar_en, top, primero, de, sitio } con `sitio` = el sitio donde la zona queda mejor colocada. */
  function hallazgos(regiones, n = 3) {
    const z = {};
    regiones.forEach(e => e.gemelos.slice(0, n).forEach((g, k) => {
      const x = (z[g.region] ||= { region: g.region, lugar: g.lugar, lugar_en: g.lugar_en, top: 0, primero: 0, de: regiones.length, sitio: null, _pos: n });
      x.top++; if (k === 0) x.primero++;
      if (k < x._pos) { x._pos = k; x.sitio = e.id; }
    }));
    return Object.values(z).map(({ _pos, ...x }) => x).sort((a, b) => b.top - a.top || b.primero - a.primero || a.region.localeCompare(b.region));
  }

  return { DIMS, puesto, puestoValor, tercio, forma, pendiente, uso, perfil, perfilPunto, resumenBarrido, equivalentes, brecha, hallazgos };
})();
if (typeof module !== 'undefined') module.exports = Analogia;
