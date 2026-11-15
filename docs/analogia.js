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

  return { DIMS, puesto, tercio, forma, pendiente, uso, perfil };
})();
if (typeof module !== 'undefined') module.exports = Analogia;
