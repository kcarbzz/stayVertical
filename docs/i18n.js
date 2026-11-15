/* Idiomas de Stay Vertical: español (es) e inglés (en). */
const I18N = (() => {
  const D = {
    es: {
      aviso: 'Resultados exploratorios', avisoTitulo: 'Tierra: 49 zonas elegidas por el equipo (~13 km cada una), no un barrido global. Los sitios de la Luna y Marte son ventanas de ~3 km, no polígonos completos. El puntaje no es un porcentaje de identidad geológica.',
      cargando: 'Cargando…', cargandoDatos: 'Cargando datos…', preparando: 'Preparando los mapas…', listo: 'Listo',
      errorDatos: 'No se pudieron cargar los datos. Recarga la página.',
      hRef: 'Terreno de referencia', hDest: 'Dónde buscar parecidos',
      'modo.region': 'Región conocida', 'modo.subir': 'Subir mi zona',
      buscar: 'Buscar región…', buscarRef: 'Buscar región de referencia', buscarDest: 'Buscar región de destino',
      migasRef: 'Región de referencia', migasDest: 'Región elegida',
      'c.tierra': 'Tierra', 'c.luna': 'Luna', 'c.marte': 'Marte',
      todo: c => `Todo ${c}`,
      continente: 'Continente', sinCoincidencias: 'Sin coincidencias',
      subirTitulo: 'Subir mi zona', proximamente: 'próximamente',
      subirTexto: 'Necesitará un GeoTIFF de alturas con coordenadas en metros, cuerpo indicado, resolución mejor que ~120 m, al menos 3 × 3 km y 85% de píxeles válidos (criterios provisionales).',
      subirPronto: 'Subir tu zona estará disponible pronto. Mientras tanto, prueba una región conocida.',
      sinDatos: 'Aún no hay cálculos para este cruce. Los disponibles son Luna → Tierra y Marte → Tierra.', ningun: 'Ningún candidato en esta región. Prueba con otra.',
      referencia: c => `Referencia · ${c}`, notaPais: 'Muestra: usa los números del continente.',
      pendiente: 'Pendiente', rugosidad: 'Rugosidad', puntaje: 'Puntaje', correlacion: 'Correlación', parecido: 'Puntaje',
      revisar: 'Revisión prioritaria', verComparacion: 'Ver comparación', verTop5: 'Ver los 5 mejores', cerrarVisor: 'Cerrar',
      evaluados: (n, r) => `${n} parches evaluados · ${r} m`, difs: (p, r) => `Dif. con la referencia: ${p}° · ${r} m`, empate: n => `${n} zonas a ≤0,01 del mejor: el orden entre ellas es poco fiable.`, posicion: 'Posición', menorMejor: 'menor es mejor',
      bot: 'Vertikal Bot', botDesc: 'Explica lo que ves. Una red neuronal pequeña, que corre en tu navegador, entiende la pregunta; las cifras salen de los datos mostrados. No usa IA externa.',
      cerrar: 'Cerrar', pregunta: 'Pregunta…', enviar: 'Enviar',
      saludo: '¡Hola! Soy Vertikal Bot. Elige un cruce y te explico el resultado.',
      idioma: 'Idioma',
      capaClima: 'Capa de clima', sinCapa: 'Sin capa', capaViab: 'Viabilidad (semáforo provisional)', soloViables: 'Ocultar zonas con factores difíciles',
      verClima: 'Clima y viabilidad', factores: 'Factores climáticos', mesAMes: 'Mes a mes', tempMensual: 'Temperatura media (°C)', lluviaMensual: 'Lluvia (mm)',
      meses: 'E,F,M,A,M,J,J,A,S,O,N,D', 'est.ok': 'Favorable', 'est.atencion': 'Atención', 'est.dificil': 'Difícil', 'est.sin': 'Sin dato',
      'sem.verde': 'Semáforo: verde', 'sem.ambar': 'Semáforo: ámbar', 'sem.rojo': 'Semáforo: rojo',
      resumenFactores: (o, a, d) => `${o} favorables · ${a} en atención · ${d} difíciles`,
      climaTarj: (tt, ll) => `${tt} °C · ${ll} mm/año`, ocultas: n => `${n} zona${n === 1 ? '' : 's'} oculta${n === 1 ? '' : 's'} por factores difíciles.`,
      leyViab: 'Semáforo global (provisional)', leyVerde: 'Sin factores difíciles y pocos en atención', leyAmbar: '1–2 difíciles o varios en atención', leyRojo: '3 o más factores difíciles',
      pieClima: (f, p, r) => `Fuente: ${f}, ${p}. Resolución: ${r}.`,
      avisoUmbrales: 'Semáforo y umbrales provisionales: no son normas de ingeniería. El clima es un promedio de una celda de ~55 km, no el microclima del sitio. No incluye sismicidad, acceso, agua, permisos ni riesgos locales.',
    },
    en: {
      aviso: 'Exploratory results', avisoTitulo: 'Earth: 49 zones chosen by the team (~13 km each), not a global sweep. Moon and Mars sites are ~3 km windows, not full polygons. The score is not a percentage of geological identity.',
      cargando: 'Loading…', cargandoDatos: 'Loading data…', preparando: 'Preparing the maps…', listo: 'Ready',
      errorDatos: 'Could not load the data. Reload the page.',
      hRef: 'Reference terrain', hDest: 'Where to look for matches',
      'modo.region': 'Known region', 'modo.subir': 'Upload my area',
      buscar: 'Search region…', buscarRef: 'Search reference region', buscarDest: 'Search target region',
      migasRef: 'Reference region', migasDest: 'Selected region',
      'c.tierra': 'Earth', 'c.luna': 'Moon', 'c.marte': 'Mars',
      todo: c => `All of ${c}`,
      continente: 'Continent', sinCoincidencias: 'No matches',
      subirTitulo: 'Upload my area', proximamente: 'coming soon',
      subirTexto: 'It will need an elevation GeoTIFF with coordinates in meters, the body stated, resolution better than ~120 m, at least 3 × 3 km and 85% valid pixels (provisional criteria).',
      subirPronto: 'Uploading your area will be available soon. Meanwhile, try a known region.',
      sinDatos: 'There are no calculations for this pairing yet. Available: Moon → Earth and Mars → Earth.', ningun: 'No candidate in this region. Try another one.',
      referencia: c => `Reference · ${c}`, notaPais: 'Sample: uses the continent’s numbers.',
      pendiente: 'Slope', rugosidad: 'Roughness', puntaje: 'Score', correlacion: 'Correlation', parecido: 'Score',
      revisar: 'Priority review', verComparacion: 'View comparison', verTop5: 'View the top 5', cerrarVisor: 'Close',
      evaluados: (n, r) => `${n} patches evaluated · ${r} m`, difs: (p, r) => `Diff. from reference: ${p}° · ${r} m`, empate: n => `${n} zones within 0.01 of the best: their order is not reliable.`, posicion: 'Rank', menorMejor: 'lower is better',
      bot: 'Vertikal Bot', botDesc: 'Explains what you see. A small neural network running in your browser understands the question; the numbers come from the data shown. It does not use external AI.',
      cerrar: 'Close', pregunta: 'Ask…', enviar: 'Send',
      saludo: 'Hi! I’m Vertikal Bot. Pick a pairing and I’ll explain the result.',
      idioma: 'Language',
      capaClima: 'Climate layer', sinCapa: 'No layer', capaViab: 'Viability (provisional traffic light)', soloViables: 'Hide zones with difficult factors',
      verClima: 'Climate and viability', factores: 'Climate factors', mesAMes: 'Month by month', tempMensual: 'Mean temperature (°C)', lluviaMensual: 'Rainfall (mm)',
      meses: 'J,F,M,A,M,J,J,A,S,O,N,D', 'est.ok': 'Favorable', 'est.atencion': 'Caution', 'est.dificil': 'Difficult', 'est.sin': 'No data',
      'sem.verde': 'Traffic light: green', 'sem.ambar': 'Traffic light: amber', 'sem.rojo': 'Traffic light: red',
      resumenFactores: (o, a, d) => `${o} favorable · ${a} caution · ${d} difficult`,
      climaTarj: (tt, ll) => `${tt} °C · ${ll} mm/yr`, ocultas: n => `${n} zone${n === 1 ? '' : 's'} hidden because of difficult factors.`,
      leyViab: 'Overall traffic light (provisional)', leyVerde: 'No difficult factors and few cautions', leyAmbar: '1–2 difficult or several cautions', leyRojo: '3 or more difficult factors',
      pieClima: (f, p, r) => `Source: ${f}, ${p}. Resolution: ${r}.`,
      avisoUmbrales: 'Traffic light and thresholds are provisional: they are not engineering standards. Climate is an average over a ~55 km cell, not the site’s microclimate. Seismicity, access, water, permits and local hazards are not included.',
    },
  };
  let lang = 'es';
  try { const g = localStorage.getItem('sv-lang') || (navigator.language || 'es').slice(0, 2); if (D[g]) lang = g; } catch (e) { /* sin almacenamiento */ }
  const api = {
    get lang() { return lang; },
    set(l) { if (!D[l]) return; lang = l; try { localStorage.setItem('sv-lang', l); } catch (e) { /* ignorar */ } document.documentElement.lang = l; },
    t(k, ...a) { const v = D[lang][k] ?? D.es[k] ?? k; return typeof v === 'function' ? v(...a) : v; },
    /* nombre según idioma: objeto con `nombre` y `nombre_en` */
    nm(o) { return (lang === 'en' && o.nombre_en) || o.nombre; },
    alt(o) { return (lang === 'en' ? o.nombre : o.nombre_en) || ''; },
    num(n) { return Number(n).toLocaleString(lang === 'en' ? 'en-US' : 'es-ES'); },
    aplicar() {
      document.documentElement.lang = lang;
      document.querySelectorAll('[data-i18n]').forEach(e => { e.textContent = api.t(e.dataset.i18n); });
      document.querySelectorAll('[data-i18n-ph]').forEach(e => { e.placeholder = api.t(e.dataset.i18nPh); });
      document.querySelectorAll('[data-i18n-title]').forEach(e => { e.title = api.t(e.dataset.i18nTitle); });
      document.querySelectorAll('[data-i18n-aria]').forEach(e => { e.setAttribute('aria-label', api.t(e.dataset.i18nAria)); });
    },
  };
  document.documentElement.lang = lang;
  return api;
})();
