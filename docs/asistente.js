/* Vertikal Bot: explica el resultado mostrado, en español e inglés.

   Dos capas:
   1) ENTENDER  -> decide qué se pregunta: nombres de lugares, red neuronal pequeña (bot_nn.js)
                   y reglas de palabras clave como respaldo. Si duda, pide aclarar.
   2) RESPONDER -> arma la respuesta SOLO con los datos del contexto (ctx). Los números nunca
                   los pone la red: salen de los datos.

   ctx = { exploratorio, origen, destino, zona, region: {nombre,nombre_en,ficha,revision,n_evaluados,res},
           candidatos: [{lugar,lugar_en,score,corr,rank,ficha?}], gemelo }
   El adaptador que construye ctx vive en app.js (contexto()): si cambia el esquema del JSON,
   solo hay que tocar ese adaptador. */
const Asistente = (() => {
  const en = () => I18N.lang === 'en';
  const S = (es, e) => (en() ? e : es);
  const nom = o => I18N.nm(o);
  const nomC = g => I18N.nm({ nombre: g.lugar, nombre_en: g.lugar_en });
  const f1 = n => I18N.num(n);
  const UMBRAL = 0.6, UMBRAL_DUDA = 0.4;
  const norm = t => BotNN.normalizar(t);

  const sc = x => I18N.num(Number(Number(x).toFixed(3)));
  const cr = x => I18N.num(Number(Number(x).toFixed(2)));
  const numeros = f => (f ? S(`pendiente media ${f1(f.pendiente_media)}°, rugosidad ${f1(f.rugosidad_m)} m`, `mean slope ${f1(f.pendiente_media)}°, roughness ${f1(f.rugosidad_m)} m`) : '');
  const detalle = g => S(`puntaje ${sc(g.score)} (menor es mejor), correlación de forma ${cr(g.corr)}`, `score ${sc(g.score)} (lower is better), shape correlation ${cr(g.corr)}`);
  function comparar(a, b) {
    const dp = f1(Number(Math.abs(a.pendiente_media - b.pendiente_media).toFixed(1))), dr = f1(Number(Math.abs(a.rugosidad_m - b.rugosidad_m).toFixed(1)));
    return S(`pendiente media ${f1(a.pendiente_media)}° vs ${f1(b.pendiente_media)}° (dif. ${dp}°), rugosidad ${f1(a.rugosidad_m)} m vs ${f1(b.rugosidad_m)} m (dif. ${dr} m).`,
             `mean slope ${f1(a.pendiente_media)}° vs ${f1(b.pendiente_media)}° (diff. ${dp}°), roughness ${f1(a.rugosidad_m)} m vs ${f1(b.rugosidad_m)} m (diff. ${dr} m).`);
  }
  const aviso = c => (c.exploratorio ? S('\n\nRecuerda: son resultados exploratorios (la Tierra son zonas elegidas por el equipo, no un barrido global).', '\n\nRemember: these are exploratory results (Earth is a set of zones chosen by the team, not a global sweep).') : '');
  const alertaRev = c => (c.region && c.region.revision ? S('\nEl equipo marcó este sitio como revisión prioritaria: su mejor coincidencia tiene correlación de forma baja.', '\nThe team flagged this site for priority review: its best match has a low shape correlation.') : '');
  const alertaCorr = g => (g && g.corr < 0.6 ? S('\nOjo: la correlación de forma es baja, así que la coincidencia es débil.', '\nNote: the shape correlation is low, so the match is weak.') : '');
  const lugar = g => nomC(g);

  /* ---------- seguridad: violencia / odio contra grupos de personas ----------
     Regla determinista (no depende de la red): violencia + grupo de personas, u odio + grupo. */
  const VIOLENCIA = /(^| )(matar|mata|matarlos|matarlas|matemos|asesinar|asesinemos|exterminar|exterminemos|linchar|fusilar|ahorcar|violar|disparar|masacrar|genocidio|kill|murder|exterminate|lynch|shoot|rape|massacre|genocide|burn them|hurt)( |$)|(^| )(eliminar|quemar|golpear|burn|beat|attack|hang)( a)?( los| las| all| the)?( |$)/;
  const ODIO = /(^| )(odio|odiamos|odiar|detesto|hate|hates)( |$)/;
  const GRUPOS = /(^| )(judio|judios|judia|judias|musulman|musulmanes|negro|negros|negra|negras|gitano|gitanos|gay|gays|homosexual|homosexuales|lesbiana|lesbianas|trans|transexual|transexuales|mujer|mujeres|inmigrante|inmigrantes|migrante|migrantes|indigena|indigenas|cristiano|cristianos|catolico|catolicos|arabe|arabes|asiatico|asiaticos|latino|latinos|extranjero|extranjeros|refugiado|refugiados|ninos|ninas|jew|jews|jewish|muslim|muslims|gypsy|gypsies|lesbians|women|immigrants|migrants|refugees|christians|catholics|arabs|asians|foreigners|children|kids|blacks|black people)( |$)/;
  const INCITACION = /(^| )(debemos|deberiamos|hay que|vamos a|quiero|queremos|matemos|exterminemos|que mueran|muerte a|we should|we must|lets|let us|i want to|should we|we need to|death to|they should die)( |$)/;
  function seguridad(t) {
    if (!GRUPOS.test(t) || !(VIOLENCIA.test(t) || ODIO.test(t))) return null;
    return INCITACION.test(t) ? 'incitacion' : 'sensible';
  }
  const textoSeguridad = tipo => (tipo === 'incitacion'
    ? S('No voy a ayudar con eso: es un llamado a la violencia contra un grupo de personas. Solo puedo hablar de los resultados de terreno y clima de esta página.',
        'I will not help with that: it is a call for violence against a group of people. I can only talk about the terrain and climate results on this page.')
    : S('Ese tema queda fuera de lo que puedo tratar aquí. Solo explico los resultados de terreno y clima de esta página.',
        'That topic is outside what I can address here. I only explain the terrain and climate results on this page.'));

  /* ---------- puerta de tema: sin ningún término del dominio, la pregunta es "fuera de tema" ---------- */
  const DOMINIO = new RegExp('(^| )(' + ['terren', 'parec', 'similar', 'semej', 'asemej', 'compar', 'diferen', 'difier', 'igual', 'coinci', 'gemel', 'resultado', 'candidat', 'lugar', 'zona', 'region', 'sitio',
    'mapa', 'puntaje', 'score', 'correl', 'referenc', 'numero', 'pendient', 'rugos', 'llan', 'plan', 'inclin', 'curvatur', 'aptitud', 'aterriz', 'limit', 'confi', 'fiab', 'fiar', 'sesgo', 'error', 'precis',
    'subir', 'archivo', 'dato', 'muestra', 'real', 'fuente', 'imagen', 'nasa', 'luna', 'marte', 'tierra', 'crater', 'volcan', 'desierto', 'clima', 'temperat', 'lluvi', 'llov', 'viento', 'helada', 'calor', 'frio',
    'humed', 'presion', 'solar', 'base', 'viab', 'habit', 'semaforo', 'factor', 'mejor', 'primero', 'lista', 'resumen', 'conclus', 'pantalla', 'tarjeta', 'porcentaje', 'cuantos', 'cuantas', 'cuales', 'otros', 'demas',
    'todos', 'algoritm', 'sistema', 'empar', 'junta', 'compart', 'comun', 'aparec', 'bot', 'vertikal', 'ia', 'red neuronal', 'modelo', 'servidor', 'internet', 'idioma', 'ayuda', 'funcion', 'usas', 'eres', 'tecnolog',
    'terrain', 'alike', 'differ', 'match', 'twin', 'result', 'place', 'site', 'candidate', 'reference', 'correlation', 'share', 'resembl', 'pair', 'algorithm', 'list', 'appear', 'common', 'slope', 'rough', 'flat',
    'curvature', 'suitab', 'land', 'limit', 'reliab', 'trust', 'bias', 'accura', 'precise', 'upload', 'file', 'tif', 'sample', 'source', 'image', 'moon', 'mars', 'earth', 'crater', 'volcan', 'desert', 'climate',
    'weather', 'rain', 'wind', 'frost', 'freez', 'snow', 'hot', 'cold', 'humid', 'pressure', 'viab', 'habitable', 'traffic', 'best', 'first', 'top', 'summary', 'screen', 'card', 'percent', 'how many', 'which', 'others',
    'rest', 'all ', 'model', 'server', 'neural', 'language', 'chatgpt', 'help', 'work', 'you use', 'are you', 'technolog', 'map', 'score', 'data', 'number', 'degree', 'meter', 'pais', 'country', 'continente', 'continent', 'lower', 'better', 'sum', 'red', 'green', 'amber', 'rojo', 'verde', 'ambar', 'menor'].join('|') + ')');
  const EXENTAS = new Set(['saludo', 'gracias', 'acerca', 'otro']);
  /* Distancia de edición <= 1 entre a y b (tolera una errata). */
  const casi = (a, b) => {
    if (Math.abs(a.length - b.length) > 1) return false;
    let i = 0; while (i < a.length && i < b.length && a[i] === b[i]) i++;
    if (i === a.length || i === b.length) return Math.abs(a.length - b.length) <= 1;
    return a.slice(i + 1) === b.slice(i + 1) || a.slice(i + 1) === b.slice(i) || a.slice(i) === b.slice(i + 1);
  };
  const RAICES = DOMINIO.source.replace(/^\(\^\| \)\(/, '').replace(/\)$/, '').split('|').filter(s => s.length >= 5 && !s.includes(' '));
  const casiDominio = t => t.split(' ').some(w => w.length >= 5 && RAICES.some(r => w.length >= r.length - 1 && casi(w.slice(0, r.length), r)));
  /* Puerta ESTRECHA: solo preguntas que empiezan con "por qué / why" y no traen ningún término del dominio (p. ej. "por qué el cielo es azul").
     Una puerta general bloqueaba preguntas legítimas con palabras no previstas, así que se limitó a este patrón. */
  const sinDominio = t => /^(por que|porque|why|how come)( |$)/.test(t) && t.split(' ').filter(Boolean).length >= 3 && !DOMINIO.test(t) && !casiDominio(t);

  /* ---------- clima y viabilidad ---------- */
  const SEM = { verde: ['verde', 'green'], ambar: ['ámbar', 'amber'], rojo: ['rojo', 'red'] };
  const semTxt = s => SEM[s][en() ? 1 : 0];
  const nomF = f => (en() && f.nombre_en) || f.nombre;
  const valF = f => `${f1(f.valor)} ${f.unidad}`;
  const lis = fs => fs.map(f => `${nomF(f)} (${valF(f)})`).join(', ');
  const val = (cl, id) => { const f = cl.factores.find(x => x.id === id); return f ? f.valor : null; };
  const metaTxt = c => (c.climaMeta ? S(`${c.climaMeta.fuente}, ${c.climaMeta.periodo}; celdas de ~55 km`, `${c.climaMeta.fuente}, ${c.climaMeta.periodo}; ~55 km cells`) : 'NASA POWER');
  const sinClima = () => S('El clima solo está disponible para las zonas de la Tierra. Elige un candidato terrestre (o activa la capa de clima en el mapa de la derecha) y te lo cuento.',
                           'Climate is only available for Earth zones. Pick an Earth candidate (or turn on the climate layer on the right-hand map) and I will tell you.');
  const nomZona = cl => nom({ nombre: cl.nombre, nombre_en: cl.nombre_en });
  function textoClima(cl, c, q) {
    const g = id => val(cl, id);
    let t = S(`Clima de ${nomZona(cl)} (${metaTxt(c)}): temperatura media ${f1(g('t_media_c'))} °C (extremos de ${f1(g('t_min_ext_c'))} a ${f1(g('t_max_ext_c'))} °C); lluvia ${f1(g('lluvia_anual_mm'))} mm al año en ${f1(g('dias_lluvia_anio'))} días; ${f1(g('dias_helada_anio'))} días de helada y ${f1(g('dias_calor_35_anio'))} días de 35 °C o más al año; viento medio ${f1(g('viento_10m_ms'))} m/s; radiación solar ${f1(g('solar_kwh_m2_dia'))} kWh/m²/día; presión ${f1(g('presion_kpa'))} kPa.`,
              `Climate of ${nomZona(cl)} (${metaTxt(c)}): mean temperature ${f1(g('t_media_c'))} °C (extremes from ${f1(g('t_min_ext_c'))} to ${f1(g('t_max_ext_c'))} °C); rainfall ${f1(g('lluvia_anual_mm'))} mm per year over ${f1(g('dias_lluvia_anio'))} days; ${f1(g('dias_helada_anio'))} frost days and ${f1(g('dias_calor_35_anio'))} days at 35 °C or more per year; mean wind ${f1(g('viento_10m_ms'))} m/s; solar radiation ${f1(g('solar_kwh_m2_dia'))} kWh/m²/day; pressure ${f1(g('presion_kpa'))} kPa.`);
    if (q && /pronost|hoy|manana|forecast|today|tomorrow|tiempo hace|weather/.test(norm(q)))
      t += S('\n\nNo tengo pronósticos: solo promedios de varios años, no el tiempo de hoy ni de mañana.', '\n\nI have no forecasts: only multi-year averages, not today’s or tomorrow’s weather.');
    return t;
  }
  function textoViab(cl, c) {
    const dif = cl.factores.filter(f => f.estado === 'dificil'), at = cl.factores.filter(f => f.estado === 'atencion');
    const r = cl.res;
    let t = S(`${nomZona(cl)}: semáforo ${semTxt(cl.sem)} (provisional): ${r.ok} factores favorables, ${r.atencion} en atención y ${r.dificil} difíciles.`,
              `${nomZona(cl)}: traffic light ${semTxt(cl.sem)} (provisional): ${r.ok} favorable factors, ${r.atencion} caution and ${r.dificil} difficult.`);
    if (dif.length) t += S(`\nDifíciles: ${lis(dif)}.`, `\nDifficult: ${lis(dif)}.`);
    if (at.length) t += S(`\nEn atención: ${lis(at)}.`, `\nCaution: ${lis(at)}.`);
    const v = c.viabilidad || [];
    if (v.length > 1) {
      const n = s => v.filter(x => x.sem === s).length, mejor = v.find(x => x.sem === 'verde');
      t += S(`\n\nDe los ${v.length} candidatos visibles: ${n('verde')} en verde, ${n('ambar')} en ámbar y ${n('rojo')} en rojo.`, `\n\nOf the ${v.length} visible candidates: ${n('verde')} green, ${n('ambar')} amber and ${n('rojo')} red.`);
      if (mejor) t += S(` El mejor candidato en verde es ${nomC(mejor)}.`, ` The best green candidate is ${nomC(mejor)}.`);
    }
    return t + S('\n\nEs una guía provisional: los umbrales no son normas de ingeniería, el clima es un promedio de una celda de ~55 km y no se consideran sismicidad, acceso, agua, permisos ni riesgos locales.',
                 '\n\nThis is a provisional guide: thresholds are not engineering standards, the climate is an average over a ~55 km cell, and seismicity, access, water, permits and local hazards are not considered.');
  }

  /* ---------- capa 2: respuestas ---------- */
  const R = {
    saludo: () => S('Puedo explicarte qué significan los números, comparar el sitio de referencia con cada zona terrestre candidata, decirte cuál se parece más y cuáles son los límites del resultado. Prueba con los botones de abajo.',
                    'I can explain what the numbers mean, compare the reference site with each candidate Earth zone, tell you which one looks most alike and what the limits of the result are. Try the buttons below.'),
    parecido: c => S('El puntaje va de 0 a 1 y menor es más parecido. Promedia dos cosas: qué tan cerca están los 8 números de relieve (pendiente, curvatura y rugosidad) y qué tan parecida es la forma del terreno (correlación del relieve sin su inclinación general, probando 4 rotaciones). No es un porcentaje de identidad geológica.',
                     'The score goes from 0 to 1 and lower means more alike. It averages two things: how close the 8 relief numbers (slope, curvature and roughness) are, and how similar the terrain shape is (correlation of the relief without its overall tilt, trying 4 rotations). It is not a percentage of geological identity.')
      + (c.gemelo ? S(`\n\nEn esta lista, el mejor es ${lugar(c.gemelo)}: ${detalle(c.gemelo)}.`, `\n\nIn this list, the best is ${lugar(c.gemelo)}: ${detalle(c.gemelo)}.`) : ''),
    porque: c => {
      if (!(c.region && c.gemelo)) return S('Elige un resultado en la lista y te comparo sus números con el de referencia.', 'Pick a result from the list and I will compare its numbers with the reference.');
      const g = c.gemelo;
      return S(`${lugar(g)} frente a ${nom(c.region)}: ${detalle(g)}.`, `${lugar(g)} versus ${nom(c.region)}: ${detalle(g)}.`)
        + (g.ficha && c.region.ficha ? S('\nNúmeros: ', '\nNumbers: ') + comparar(c.region.ficha, g.ficha)
                                    : S('\nPara este candidato el equipo no entregó pendiente ni rugosidad: solo puntaje y correlación.', '\nFor this candidate the team did not provide slope or roughness: only score and correlation.'))
        + alertaCorr(g) + aviso(c);
    },
    llana: () => S('En los datos actuales no se calcula la fracción llana. Se usan 8 números: pendiente (media, desviación y percentil 90), curvatura (media y percentil 90) y rugosidad (mediana, percentil 90 y desviación). Las tarjetas muestran la pendiente media y la rugosidad.',
                   'The flat fraction is not computed in the current data. 8 numbers are used: slope (mean, deviation and 90th percentile), curvature (mean and 90th percentile) and roughness (median, 90th percentile and deviation). The cards show mean slope and roughness.'),
    pendiente: () => S('La pendiente media es la inclinación promedio del terreno, en grados. Se calcula igual en los tres cuerpos y a la misma escala (80 m en la Luna, 200 m en Marte y la Tierra remuestreada), para que sean comparables.',
                       'Mean slope is the average tilt of the terrain, in degrees. It is computed the same way on all three bodies and at the same scale (80 m for the Moon, 200 m for Mars with Earth resampled), so they are comparable.'),
    rugosidad: () => S('La rugosidad mide cuánto se desvía el terreno de un plano local (en metros). Valores altos indican terreno quebrado a pequeña escala.',
                       'Roughness measures how much the terrain departs from a local plane (in meters). High values mean broken terrain at small scale.'),
    aptitud: c => S('Este análisis no evalúa si un sitio es apto para aterrizar: solo mide qué tan parecido es su relieve al de zonas de la Tierra. Para hablar de aptitud habría que añadir iluminación, hielo en sombra, visibilidad de la Tierra y criterios de misión, que no están en estos datos.',
                     'This analysis does not assess whether a site is suitable for landing: it only measures how similar its relief is to Earth zones. Talking about suitability would need lighting, shadowed ice, Earth visibility and mission criteria, which are not in this data.')
      + (c.clima ? S(`\n\nPara una base en la Tierra, el clima sí está evaluado: ${textoViab(c.clima, c)}`, `\n\nFor a base on Earth, climate is assessed: ${textoViab(c.clima, c)}`) : ''),
    limites: () => S('Límites: (1) La Tierra son 49 zonas de unos 13 km elegidas por el equipo, no un barrido global. (2) Cada sitio lunar o marciano es una ventana de ~3 km, no el cráter completo. (3) El puntaje no es un porcentaje de identidad geológica: mezcla, a partes iguales, la posición física del parche (no su distancia) y la forma, sobre los 500 mejores preseleccionados. Si se cambia ese peso, el ganador puede cambiar, y entre el primero y el segundo suele haber diferencias mínimas. (4) Luna a 80 m y Marte a 200 m (con la Tierra remuestreada). (5) El DEM terrestre incluye árboles y edificios. (6) En algunos sitios las cifras absolutas no coinciden bien aunque la forma sí, por eso hay revisiones prioritarias.',
                     'Limits: (1) Earth is 49 zones of about 13 km chosen by the team, not a global sweep. (2) Each Moon or Mars site is a ~3 km window, not the whole crater. (3) The score is not a percentage of geological identity: it mixes, in equal parts, the patch’s physical rank (not its distance) and the shape, over the 500 best preselected. If that weight changes, the winner can change, and the gap between first and second is often tiny. (4) Moon at 80 m and Mars at 200 m (with Earth resampled). (5) The Earth elevation model includes trees and buildings. (6) At some sites the absolute numbers do not match well even if the shape does, hence the priority reviews.'),
    subir: () => S('Para subir tu zona necesitas un GeoTIFF de alturas con sistema de coordenadas en metros, indicando el cuerpo, con resolución mejor que ~120 m, al menos 3×3 km y al menos 85% de píxeles válidos. Estos criterios son provisionales. Esta función aún no está disponible.',
                   'To upload your area you need an elevation GeoTIFF with a coordinate system in meters, the body stated, resolution better than ~120 m, at least 3×3 km and at least 85% valid pixels. These criteria are provisional. This feature is not available yet.'),
    muestra: c => S('No son datos de muestra: son resultados del análisis del equipo con modelos de elevación reales (Copernicus GLO-30 vía Planetary Computer para la Tierra, NASA LOLA para la Luna y USGS HRSC/MOLA para Marte). Son exploratorios: puntos de referencia, no polígonos completos.',
                    'This is not sample data: these are the team’s analysis results using real elevation models (Copernicus GLO-30 via Planetary Computer for Earth, NASA LOLA for the Moon and USGS HRSC/MOLA for Mars). They are exploratory: reference points, not full polygons.'),
    mejor: c => {
      const l = c.candidatos || [];
      if (!l.length) return S('No hay candidatos en la región elegida. Prueba con otra.', 'There are no candidates in the selected region. Try another one.');
      const g = l[0], seg = l[1];
      return S(`El mejor es ${lugar(g)} (posición #${g.rank}): ${detalle(g)}${g.ficha ? `; ${numeros(g.ficha)}` : ''}.`, `The best one is ${lugar(g)} (rank #${g.rank}): ${detalle(g)}${g.ficha ? `; ${numeros(g.ficha)}` : ''}.`)
        + (seg ? S(`\nLe sigue ${lugar(seg)} con puntaje ${sc(seg.score)}.`, `\nNext is ${lugar(seg)} with score ${sc(seg.score)}.`) : '') + alertaCorr(g) + alertaRev(c) + aviso(c);
    },
    lista: c => {
      const l = c.candidatos || [];
      if (!l.length) return S('No hay candidatos en la región elegida. Prueba con otra.', 'There are no candidates in the selected region. Try another one.');
      const top = l.slice(0, 10).map((g, i) => `${i + 1}. ${lugar(g)} — ${S('puntaje', 'score')} ${sc(g.score)}, ${S('corr.', 'corr.')} ${cr(g.corr)}`).join('\n');
      return S(`Hay ${l.length} zona${l.length === 1 ? '' : 's'} terrestre${l.length === 1 ? '' : 's'} candidata${l.length === 1 ? '' : 's'}${c.zona ? ` en ${c.zona}` : ''} (mejor parche de cada una, ordenadas por puntaje):\n`,
               `There ${l.length === 1 ? 'is 1 candidate Earth zone' : `are ${l.length} candidate Earth zones`}${c.zona ? ` in ${c.zona}` : ''} (best patch of each, ordered by score):\n`)
        + top + (l.length > 10 ? S(`\n… y ${l.length - 10} más.`, `\n… and ${l.length - 10} more.`) : '') + aviso(c);
    },
    resumen: c => {
      if (!c.region) return S('Elige una región de referencia y te resumo el resultado.', 'Pick a reference region and I will summarize the result.');
      const l = c.candidatos || [];
      let t = S(`Referencia: ${nom(c.region)} (${c.origen}): ${numeros(c.region.ficha)}${c.region.n_evaluados ? `; se evaluaron ${c.region.n_evaluados} parches terrestres a ${c.region.res || ''} m` : ''}.`,
                `Reference: ${nom(c.region)} (${c.origen}): ${numeros(c.region.ficha)}${c.region.n_evaluados ? `; ${c.region.n_evaluados} Earth patches were evaluated at ${c.region.res || ''} m` : ''}.`) + alertaRev(c);
      if (!l.length) return t + S(`\nNo hay candidatos en ${c.destino}${c.zona ? ' · ' + c.zona : ''} con esta región.`, `\nNo candidates in ${c.destino}${c.zona ? ' · ' + c.zona : ''} for this region.`);
      const mn = Math.min(...l.map(g => g.score)), mx = Math.max(...l.map(g => g.score));
      return t + S(`\nEn ${c.destino}${c.zona ? ' · ' + c.zona : ''} hay ${l.length} zona${l.length === 1 ? '' : 's'} candidata${l.length === 1 ? '' : 's'}, con puntajes de ${sc(mn)} a ${sc(mx)} (menor es mejor). La mejor: ${lugar(l[0])} (${detalle(l[0])}).`,
                   `\nIn ${c.destino}${c.zona ? ' · ' + c.zona : ''} there ${l.length === 1 ? 'is 1 candidate zone' : `are ${l.length} candidate zones`}, with scores from ${sc(mn)} to ${sc(mx)} (lower is better). The best: ${lugar(l[0])} (${detalle(l[0])}).`) + alertaCorr(l[0]) + aviso(c);
    },
    fuentes: () => S('Elevación: Tierra, Copernicus GLO-30 (Microsoft Planetary Computer); Luna, NASA LOLA a 80 m; Marte, mosaico USGS HRSC/MOLA a 200 m. Mapas: Tierra, OpenStreetMap; Luna, LRO WAC de la NASA (GSFC/ASU); Marte, Viking MDIM 2.1 (NASA/JPL-Caltech, USGS). Fronteras: Natural Earth (dominio público).',
                     'Elevation: Earth, Copernicus GLO-30 (Microsoft Planetary Computer); Moon, NASA LOLA at 80 m; Mars, USGS HRSC/MOLA blend at 200 m. Maps: Earth, OpenStreetMap; Moon, NASA LRO WAC (GSFC/ASU); Mars, Viking MDIM 2.1 (NASA/JPL-Caltech, USGS). Borders: Natural Earth (public domain).'),
    clima: (c, q) => (c.clima ? textoClima(c.clima, c, q) : sinClima()),
    viabilidad: c => (c.clima ? textoViab(c.clima, c) : S('La viabilidad climática de una base solo se evalúa para zonas de la Tierra. Elige un candidato terrestre y te la resumo.', 'Climate viability for a base is only assessed for Earth zones. Pick an Earth candidate and I will summarize it.')),
    acerca: () => S('Soy Vertikal Bot. Para entender tus preguntas uso una red neuronal pequeña (unos 190 KB) que corre en tu navegador: no es un modelo de lenguaje generativo y no envía tus preguntas a ningún servidor ni usa servicios externos de IA. Las respuestas se arman con los datos que ves en pantalla; la red solo decide de qué tema hablas, y las cifras salen de los datos, nunca de la red. Puedo equivocarme con frases nuevas: si dudo, te ofrezco temas.',
                     'I am Vertikal Bot. To understand your questions I use a small neural network (about 190 KB) that runs in your browser: it is not a generative language model, it does not send your questions to any server and it uses no external AI services. Answers are built from the data you see on screen; the network only decides which topic you are asking about, and the numbers come from the data, never from the network. I can be wrong with new phrasings: when in doubt, I offer topics.'),
    gracias: () => S('¡De nada! Si quieres, pregúntame por el mejor candidato o por los límites del resultado.', 'You are welcome! If you like, ask me about the best candidate or the limits of the result.'),
    otro: () => S('Eso queda fuera de lo que sé explicar. Me enfoco en este resultado: qué significan los números, cuál es el mejor candidato y qué límites tiene.', 'That is outside what I can explain. I focus on this result: what the numbers mean, which candidate is best and what its limits are.'),
  };
  const PREGUNTAS = {
    parecido: ['¿Qué significa el parecido?', 'What does the match mean?'], porque: ['¿Por qué se parecen?', 'Why do they look alike?'],
    limites: ['¿Qué no considera?', 'What is not considered?'], llana: ['¿Qué es la fracción llana?', 'What is the flat fraction?'],
    subir: ['¿Cómo subo mi zona?', 'How do I upload my area?'], mejor: ['¿Cuál es el mejor?', 'Which is the best?'],
    lista: ['¿Qué candidatos hay?', 'What candidates are there?'], resumen: ['Dame un resumen', 'Give me a summary'],
    pendiente: ['¿Qué es la pendiente?', 'What is slope?'], rugosidad: ['¿Qué es la rugosidad?', 'What is roughness?'],
    aptitud: ['¿Qué es la aptitud?', 'What is suitability?'], acerca: ['¿Usas inteligencia artificial?', 'Do you use AI?'], clima: ['¿Qué clima tiene?', 'What is the climate like?'], viabilidad: ['¿Es viable una base ahí?', 'Is a base viable there?'], muestra: ['¿Son datos reales?', 'Is this real data?'], fuentes: ['¿De dónde salen los mapas?', 'Where do the maps come from?'],
  };
  const preguntaDe = i => (PREGUNTAS[i] ? PREGUNTAS[i][en() ? 1 : 0] : null);
  const rapidas = () => ['parecido', 'porque', 'mejor', 'viabilidad', 'limites'].map(preguntaDe);

  /* ---------- capa 1: entender ---------- */
  const KW = {
    saludo: ['hola', 'buenas', 'ayuda', 'que puedes', 'como funciona', 'como se usa', 'hello', 'hi ', 'help', 'what can you', 'how does it work', 'how is this used'],
    parecido: ['parecido', 'porcentaje', 'similitud', 'score', 'match', 'similarity', 'percent'],
    porque: ['por que', 'se parece', 'compar', 'diferen', 'why', 'alike', 'differ'],
    llana: ['llan', 'flat', 'plano', 'plana'], pendiente: ['pendiente', 'slope', 'inclinacion', 'tilt'], rugosidad: ['rugos', 'rough'],
    aptitud: ['aptitud', 'aterriz', 'suitab', 'land'], limites: ['limit', 'no considera', 'confi', 'fiable', 'fiar', 'de fiar', 'sesgo', 'bosque', 'consider', 'reliab', 'bias', 'forest', 'error', 'preciso', 'precise', 'accura', 'exact', 'incertidumbre', 'uncertain', 'debilidad', 'weakness', 'caveat', 'trust', 'rely', 'dependable', 'fallo', 'flaw'],
    subir: ['subir', 'archivo', 'mi zona', 'criterio', 'formato', 'upload', 'file', 'my area', 'criteria', 'format'],
    muestra: ['real', 'muestra', 'ejemplo', 'falso', 'inventad', 'simulacion', 'prototipo', 'verdader', 'sample', 'example', 'fake', 'demo', 'made up', 'simulation', 'prototype', 'fictitious', 'ficticio'],
    mejor: ['mejor', 'primero', 'principal', 'top', 'best', 'first', 'mas parecido', 'closest', 'ganador', 'gana', 'lidera', 'encabeza', 'winner', 'wins', 'leads', 'numero uno', 'number one', 'ideal'],
    lista: ['lista', 'listado', 'cuantos', 'todos', 'candidatos', 'demas', 'otros', 'enumera', 'list', 'how many', 'all', 'candidates', 'others', 'the rest'],
    resumen: ['resumen', 'resume', 'resultado', 'que veo', 'sintesis', 'conclusion', 'idea principal', 'lo principal', 'summary', 'summar', 'sum up', 'result', 'what am i', 'main idea', 'main thing'],
    acerca: ['inteligencia artificial', 'red neuronal', 'redes neuronales', 'usas ia', 'eres ia', 'es ia', 'ia ', 'ai ', 'chatgpt', 'neural', 'language model', 'modelo de lenguaje', 'como funcionas', 'how do you work', 'artificial intell', 'what model', 'que modelo'],
    clima: ['clima', 'temperatur', 'lluvi', 'llover', 'llueve', 'viento', 'ventoso', 'helada', 'hiela', 'nieva', 'humedad', 'presion atmos', 'pronost', 'weather', 'climate', 'rain', 'wind', 'frost', 'freez', 'snow', 'humidity', 'forecast'],
    viabilidad: ['viab', 'habitab', 'semaforo', 'construir', 'instalar', 'levantar', 'vivir', 'campamento', 'feasib', 'traffic light', 'build', 'habitable', 'settle', 'inhabit', 'live in', 'camp'],
    fuentes: ['mapa', 'fuente', 'de donde', 'source', 'frontera', 'border'], gracias: ['gracias', 'agradez', 'agradecid', 'amable', 'thanks', 'thank', 'grateful', 'thankful'],
  };
  function porReglas(t) {
    const p = ' ' + t + ' '; let mejor = null, mx = 0;
    for (const [i, kws] of Object.entries(KW)) { const n = kws.filter(k => p.includes(' ' + k)).length; if (n > mx) { mx = n; mejor = i; } }
    return mejor;
  }
  const GENERICAS = new Set(['sierra', 'valle', 'gran', 'grand', 'river', 'kings', 'canon', 'canyon', 'crater', 'caldera', 'monte', 'mount', 'montanas', 'mountains', 'grandes', 'llanuras', 'great', 'plains', 'cordillera', 'desierto', 'desert', 'borde', 'valle', 'valley', 'isla', 'island', 'marte', 'mars', 'luna', 'moon', 'tierra', 'earth', 'cerca', 'near', 'cima', 'summit', 'delta', 'pico', 'peak', 'plateau', 'meseta', 'llanura', 'plain', 'sitio', 'discovered', 'site', 'region']);
  function palabras(o) { return new Set([...norm(o.nombre || o.lugar || '').split(' '), ...norm(o.nombre_en || o.lugar_en || '').split(' ')].filter(w => w.length >= 4 && !GENERICAS.has(w))); }
  function porNombre(t, c) {
    const p = ' ' + t + ' ';
    const cands = (c.candidatos || []).map(g => ({ g, w: palabras(g) }));
    for (const x of cands) for (const w of x.w) {
      if (!p.includes(' ' + w + ' ') && !p.includes(' ' + w)) continue;
      if (cands.filter(y => y.w.has(w)).length === 1) return { tipo: 'candidato', g: x.g };
    }
    if (c.region) for (const w of palabras(c.region)) if (p.includes(' ' + w)) return { tipo: 'region' };
    return null;
  }

  /* "el segundo", "el último", "número 3", "candidate 2"... -> candidato por posición. */
  function porOrdinal(texto, c) {
    const l = c.candidatos || [];
    if (!l.length) return null;
    const t = texto.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    const num = t.match(/(?:numero|number|candidato|candidate|lugar|place|#)\s*(\d+)/);
    let i = null;
    if (num) i = +num[1] - 1;
    else if (/\b(segundo|second)\b/.test(t)) i = 1;
    else if (/\b(tercero|tercer|third)\b/.test(t)) i = 2;
    else if (/\b(ultimo|last)\b/.test(t)) i = l.length - 1;
    if (i === null) return null;
    return i >= 0 && i < l.length ? { tipo: 'candidato', g: l[i] } : { tipo: 'fueraRango', n: l.length };
  }

  const PALABRAS_CLIMA = /clima|temperatur|llov|lluvi|viento|helada|hiela|nieva|calor|frio|humed|presion|solar|viab|habit|construir|base|semaforo|vivir|climate|weather|temperature|rain|wind|frost|freez|snow|cold|hot|humid|pressure|feasib|build|settle|live/;
  function porZonaClima(t, c) {
    const zs = (c.zonasClima || []).map(z => ({ z, w: palabras(z) }));
    for (const x of zs) for (const w of x.w) {
      if (!(' ' + t + ' ').includes(' ' + w)) continue;
      if (zs.filter(y => y.w.has(w)).length === 1) return x.z;
    }
    return null;
  }

  function entender0(texto, c) {
    const t = norm(texto);
    if (!t) return { tipo: 'nada' };
    const nombre = porOrdinal(texto, c) || porNombre(t, c);
    if (nombre) return nombre;
    const reglas = porReglas(t);
    // Si casi ninguna palabra es conocida, la red no es fiable: solo valen las reglas.
    const nn = BotNN.fraccionConocida(texto) >= 0.34 ? BotNN.clasificar(texto) : null;
    if (!nn) return reglas ? { tipo: 'intent', intent: reglas, via: 'reglas' } : { tipo: 'nada' };
    const [[i1, p1], [i2]] = nn;
    if (p1 >= UMBRAL) return { tipo: 'intent', intent: i1, p: p1, via: 'red' };
    if (p1 >= UMBRAL_DUDA) {
      if (reglas && (reglas === i1 || reglas === i2)) return { tipo: 'intent', intent: reglas, p: p1, via: 'red+reglas' };
      return { tipo: 'duda', opciones: [i1, i2].filter(x => x !== 'otro') };
    }
    return reglas ? { tipo: 'intent', intent: reglas, via: 'reglas' } : { tipo: 'nada' };
  }

  /* La puerta de tema solo corrige a 'otro' los "por qué" sin ninguna palabra del dominio. */
  function entender(texto, c) {
    const u = entender0(texto, c), t = norm(texto);
    if ((u.tipo === 'intent' && !EXENTAS.has(u.intent)) || u.tipo === 'duda') {
      if (sinDominio(t)) return { tipo: 'intent', intent: 'otro', via: 'puerta' };
    }
    return u;
  }

  /* ---------- API ---------- */
  function responder(texto, c) {
    // Pregunta de clima/viabilidad que nombra una de las 50 zonas: se responde sobre ESA zona.
    const tn = norm(texto);
    const seg = seguridad(tn);
    if (seg) return { texto: textoSeguridad(seg) };
    if (PALABRAS_CLIMA.test(tn)) {
      const z = porZonaClima(tn, c);
      if (z && z.clima) return { texto: /viab|habit|construir|base|semaforo|vivir|feasib|build|settle|live/.test(tn) ? textoViab(z.clima, c) : textoClima(z.clima, c, texto) };
    }
    const u = entender(texto, c);
    if (u.tipo === 'candidato' && u.g.clima && /clima|temperatur|llov|lluvi|viento|helada|calor|frio|humed|presion|solar|viab|habit|construir|base|semaforo|climate|weather|temperature|rain|wind|frost|cold|hot|humid|pressure|feasib|build|settle/.test(norm(texto))) {
      const viab = /viab|habit|construir|base|semaforo|feasib|build|settle/.test(norm(texto));
      return { texto: viab ? textoViab(u.g.clima, c) : textoClima(u.g.clima, c, texto) };
    }
    if (u.tipo === 'candidato') {
      const g = u.g;
      return { texto: S(`${nomC(g)} (posición #${g.rank}): ${detalle(g)}. `, `${nomC(g)} (rank #${g.rank}): ${detalle(g)}. `)
        + (g.ficha && c.region && c.region.ficha ? S(`Frente a ${nom(c.region)}: `, `Versus ${nom(c.region)}: `) + comparar(c.region.ficha, g.ficha) : g.ficha ? numeros(g.ficha) + '.' : '') + alertaCorr(g) + aviso(c) };
    }
    if (u.tipo === 'fueraRango') return { texto: S(`Solo hay ${u.n} candidato${u.n === 1 ? '' : 's'} en esta región. Pídeme uno del 1 al ${u.n}.`, `There ${u.n === 1 ? 'is only 1 candidate' : `are only ${u.n} candidates`} in this region. Ask me about one from 1 to ${u.n}.`) };
    if (u.tipo === 'region') return { texto: S(`${nom(c.region)} (${c.origen}): ${numeros(c.region.ficha)}.`, `${nom(c.region)} (${c.origen}): ${numeros(c.region.ficha)}.`) + alertaRev(c) + aviso(c) };
    if (u.tipo === 'duda') {
      const op = u.opciones.map(preguntaDe).filter(Boolean);
      return { texto: S('No estoy seguro de haber entendido. ¿Quisiste preguntar por alguno de estos temas?', 'I am not sure I understood. Did you mean one of these topics?'), sugerencias: op };
    }
    if (u.tipo === 'intent' && R[u.intent]) {
      const r = { texto: R[u.intent](c, texto) };
      if (u.intent === 'otro') r.sugerencias = rapidas();
      return r;
    }
    return { texto: S('No tengo una respuesta para eso. Puedo explicar el parecido, la pendiente, la rugosidad, los límites, el mejor candidato o cómo subir tu zona.',
                      'I do not have an answer for that. I can explain the match, slope, roughness, the limits, the best candidate or how to upload your area.'), sugerencias: rapidas() };
  }
  return { responder, rapidas, entender };
})();
if (typeof module !== 'undefined') module.exports = Asistente;
