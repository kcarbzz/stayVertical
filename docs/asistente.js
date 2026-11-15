/* Vertikal Bot: explica el resultado mostrado, en español e inglés.

   Dos capas:
   1) ENTENDER  -> decide qué se pregunta: seguridad, nombres de lugares, red neuronal pequeña (bot_nn.js)
                   y reglas de palabras clave como respaldo. Si duda, pide aclarar.
   2) RESPONDER -> arma la respuesta SOLO con los datos del contexto (ctx). Los números nunca los pone la red.

   Reglas de estilo: respuesta corta por defecto; lo demás va en "Más detalle" (botón).
   El idioma de la respuesta es el de la pregunta (si no se distingue, el de la interfaz).

   ctx = { exploratorio, origen, origenId, destino, zona, region, candidatos:[{lugar,lugar_en,region,score,corr,rank,
           categoria,pais,coord,ficha?,clima?}], gemelo, clima, viabilidad, climaMeta,
           zonasClima:[{id,nombre,nombre_en,categoria,categoria_en,pais,pais_en,continente,continente_en,lat,lon,clima}],
           sitiosPor:{luna:[{nombre,nombre_en,mejor:{lugar,lugar_en,score,corr}}], marte:[...]},
           paises:[{nombre,nombre_en}], continentes:[{nombre,nombre_en}] }
   El adaptador que construye ctx vive en app.js (contexto()). */
const Asistente = (() => {
  let L = 'es';                                   // idioma de la respuesta en curso
  const en = () => L === 'en';
  const S = (es, e) => (en() ? e : es);
  const nom = o => (en() && o.nombre_en) || o.nombre;
  const nomC = g => (en() && g.lugar_en) || g.lugar;
  const num = n => Number(n).toLocaleString(en() ? 'en-US' : 'es-ES');
  const f1 = num;
  const sc = x => num(Number(Number(x).toFixed(3)));
  const cr = x => num(Number(Number(x).toFixed(2)));
  const UMBRAL = 0.6, UMBRAL_DUDA = 0.4;
  const norm = t => BotNN.normalizar(t);

  /* ---------- idioma de la pregunta ---------- */
  const PAL_ES = new Set(['entre', 'y', 'con', 'que', 'es', 'de', 'la', 'el', 'en', 'los', 'las', 'por', 'para', 'con', 'una', 'un', 'mas', 'como', 'cual', 'cuales', 'donde', 'esta', 'estan', 'hay', 'se', 'del', 'al', 'lo', 'mi', 'tu', 'son', 'sobre', 'tiene', 'tienen', 'sale', 'salen', 'cuantos', 'cuantas', 'quien', 'porque', 'muy', 'pero', 'tambien', 'puedo', 'puedes', 'dime', 'dame', 'zonas', 'areas', 'sitio', 'sitios']);
  const PAL_EN = new Set(['the', 'is', 'are', 'what', 'which', 'how', 'do', 'does', 'of', 'in', 'to', 'for', 'with', 'and', 'an', 'there', 'it', 'this', 'that', 'you', 'can', 'tell', 'about', 'have', 'has', 'where', 'why', 'my', 'your', 'from', 'be', 'was', 'were', 'will', 'would', 'could', 'any', 'more', 'most', 'zones', 'areas', 'site', 'sites']);
  function idiomaDe(t) {
    let a = 0, b = 0;
    for (const w of t.split(' ')) { if (PAL_ES.has(w)) a++; if (PAL_EN.has(w)) b++; }
    return a > b ? 'es' : b > a ? 'en' : null;
  }

  /* ---------- piezas de texto ---------- */
  const numeros = f => (f ? S(`pendiente media ${f1(f.pendiente_media)}°, rugosidad ${f1(f.rugosidad_m)} m`, `mean slope ${f1(f.pendiente_media)}°, roughness ${f1(f.rugosidad_m)} m`) : '');
  const detalle = g => S(`puntaje ${sc(g.score)} (menor es mejor), correlación de forma ${cr(g.corr)}`, `score ${sc(g.score)} (lower is better), shape correlation ${cr(g.corr)}`);
  const corto = g => S(`puntaje ${sc(g.score)}, correlación ${cr(g.corr)}`, `score ${sc(g.score)}, correlation ${cr(g.corr)}`);
  function comparar(a, b) {
    const dp = f1(Number(Math.abs(a.pendiente_media - b.pendiente_media).toFixed(1))), dr = f1(Number(Math.abs(a.rugosidad_m - b.rugosidad_m).toFixed(1)));
    return S(`pendiente ${f1(a.pendiente_media)}° vs ${f1(b.pendiente_media)}° (dif. ${dp}°); rugosidad ${f1(a.rugosidad_m)} vs ${f1(b.rugosidad_m)} m (dif. ${dr} m).`,
             `slope ${f1(a.pendiente_media)}° vs ${f1(b.pendiente_media)}° (diff. ${dp}°); roughness ${f1(a.rugosidad_m)} vs ${f1(b.rugosidad_m)} m (diff. ${dr} m).`);
  }
  const aviso = c => (c.exploratorio ? S('\n\nRecuerda: son resultados exploratorios (la Tierra son zonas elegidas por el equipo, no un barrido global).', '\n\nRemember: these are exploratory results (Earth is a set of zones chosen by the team, not a global sweep).') : '');
  const alertaRev = c => (c.region && c.region.revision ? S(' El equipo marcó este sitio para revisión prioritaria (correlación de forma baja).', ' The team flagged this site for priority review (low shape correlation).') : '');
  const alertaCorr = g => (g && g.corr < 0.6 ? S(' Ojo: la correlación de forma es baja, la coincidencia es débil.', ' Note: the shape correlation is low, so the match is weak.') : '');
  const sinCand = () => S('No hay candidatos en la región elegida. Prueba con otra.', 'There are no candidates in the selected region. Try another one.');

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

  /* ---------- puerta de tema (estrecha): "por qué / why" sin ningún término del dominio ---------- */
  const DOMINIO = new RegExp('(^| )(' + ['terren', 'parec', 'similar', 'semej', 'asemej', 'compar', 'diferen', 'difier', 'igual', 'coinci', 'gemel', 'resultado', 'candidat', 'lugar', 'zona', 'region', 'sitio',
    'mapa', 'puntaje', 'score', 'correl', 'referenc', 'numero', 'pendient', 'rugos', 'llan', 'plan', 'inclin', 'curvatur', 'aptitud', 'aterriz', 'limit', 'confi', 'fiab', 'fiar', 'sesgo', 'error', 'precis',
    'subir', 'archivo', 'dato', 'muestra', 'real', 'fuente', 'imagen', 'nasa', 'luna', 'marte', 'tierra', 'crater', 'volcan', 'desierto', 'clima', 'temperat', 'lluvi', 'llov', 'viento', 'helada', 'calor', 'frio',
    'humed', 'presion', 'solar', 'base', 'viab', 'habit', 'semaforo', 'factor', 'mejor', 'primero', 'lista', 'resumen', 'conclus', 'pantalla', 'tarjeta', 'porcentaje', 'cuantos', 'cuantas', 'cuales', 'otros', 'demas',
    'todos', 'algoritm', 'sistema', 'empar', 'junta', 'compart', 'comun', 'aparec', 'bot', 'vertikal', 'ia', 'red neuronal', 'modelo', 'servidor', 'internet', 'idioma', 'ayuda', 'funcion', 'usas', 'eres', 'tecnolog',
    'area', 'disponib', 'catalog', 'pais', 'continente', 'categoria',
    'terrain', 'alike', 'differ', 'match', 'twin', 'result', 'place', 'site', 'candidate', 'reference', 'correlation', 'share', 'resembl', 'pair', 'algorithm', 'list', 'appear', 'common', 'slope', 'rough', 'flat',
    'curvature', 'suitab', 'land', 'limit', 'reliab', 'trust', 'bias', 'accura', 'precise', 'upload', 'file', 'tif', 'sample', 'source', 'image', 'moon', 'mars', 'earth', 'crater', 'volcan', 'desert', 'climate',
    'weather', 'rain', 'wind', 'frost', 'freez', 'snow', 'hot', 'cold', 'humid', 'pressure', 'viab', 'habitable', 'traffic', 'best', 'first', 'top', 'summary', 'screen', 'card', 'percent', 'how many', 'which', 'others',
    'rest', 'all ', 'model', 'server', 'neural', 'language', 'chatgpt', 'help', 'work', 'you use', 'are you', 'technolog', 'map', 'data', 'number', 'degree', 'meter', 'country', 'continent', 'lower', 'better', 'sum',
    'red', 'green', 'amber', 'rojo', 'verde', 'ambar', 'menor', 'zone', 'available', 'catalog', 'categor'].join('|') + ')');
  const EXENTAS = new Set(['saludo', 'gracias', 'acerca', 'otro']);
  const casi = (a, b) => {                       // distancia de edición <= 1 (tolera una errata)
    if (Math.abs(a.length - b.length) > 1) return false;
    let i = 0; while (i < a.length && i < b.length && a[i] === b[i]) i++;
    if (i === a.length || i === b.length) return Math.abs(a.length - b.length) <= 1;
    return a.slice(i + 1) === b.slice(i + 1) || a.slice(i + 1) === b.slice(i) || a.slice(i) === b.slice(i + 1);
  };
  const RAICES = DOMINIO.source.replace(/^\(\^\| \)\(/, '').replace(/\)$/, '').split('|').filter(s => s.length >= 5 && !s.includes(' '));
  const casiDominio = t => t.split(' ').some(w => w.length >= 5 && RAICES.some(r => w.length >= r.length - 1 && casi(w.slice(0, r.length), r)));
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
  const PRONOSTICO = /pronost|hoy|manana|forecast|today|tomorrow|tiempo hace|weather/;
  function climaCorto(cl, c, q) {
    const g = id => val(cl, id);
    const t = S(`${nomZona(cl)}: ${f1(g('t_media_c'))} °C de media, ${f1(g('lluvia_anual_mm'))} mm de lluvia al año, ${f1(g('dias_helada_anio'))} días de helada y viento de ${f1(g('viento_10m_ms'))} m/s.`,
                `${nomZona(cl)}: ${f1(g('t_media_c'))} °C on average, ${f1(g('lluvia_anual_mm'))} mm of rain per year, ${f1(g('dias_helada_anio'))} frost days and wind of ${f1(g('viento_10m_ms'))} m/s.`);
    const pron = q && PRONOSTICO.test(norm(q)) ? S(' No tengo pronósticos: solo promedios de varios años, no el tiempo de hoy ni de mañana.', ' I have no forecasts: only multi-year averages, not today’s or tomorrow’s weather.') : '';
    return t + pron;
  }
  function climaLargo(cl, c) {
    const g = id => val(cl, id);
    return S(`Clima de ${nomZona(cl)} (${metaTxt(c)}): temperatura media ${f1(g('t_media_c'))} °C (extremos de ${f1(g('t_min_ext_c'))} a ${f1(g('t_max_ext_c'))} °C); lluvia ${f1(g('lluvia_anual_mm'))} mm al año en ${f1(g('dias_lluvia_anio'))} días; ${f1(g('dias_helada_anio'))} días de helada y ${f1(g('dias_calor_35_anio'))} días de 35 °C o más al año; viento medio ${f1(g('viento_10m_ms'))} m/s; radiación solar ${f1(g('solar_kwh_m2_dia'))} kWh/m²/día; presión ${f1(g('presion_kpa'))} kPa.`,
             `Climate of ${nomZona(cl)} (${metaTxt(c)}): mean temperature ${f1(g('t_media_c'))} °C (extremes from ${f1(g('t_min_ext_c'))} to ${f1(g('t_max_ext_c'))} °C); rainfall ${f1(g('lluvia_anual_mm'))} mm per year over ${f1(g('dias_lluvia_anio'))} days; ${f1(g('dias_helada_anio'))} frost days and ${f1(g('dias_calor_35_anio'))} days at 35 °C or more per year; mean wind ${f1(g('viento_10m_ms'))} m/s; solar radiation ${f1(g('solar_kwh_m2_dia'))} kWh/m²/day; pressure ${f1(g('presion_kpa'))} kPa.`);
  }
  function viabCorto(cl) {
    const dif = cl.factores.filter(f => f.estado === 'dificil'), r = cl.res;
    return S(`${nomZona(cl)}: semáforo ${semTxt(cl.sem)} (provisional), con ${r.dificil} factor${r.dificil === 1 ? '' : 'es'} difícil${r.dificil === 1 ? '' : 'es'} y ${r.atencion} en atención.`, `${nomZona(cl)}: traffic light ${semTxt(cl.sem)} (provisional), with ${r.dificil} difficult factor${r.dificil === 1 ? '' : 's'} and ${r.atencion} on caution.`)
      + (dif.length ? S(` Difíciles: ${lis(dif)}.`, ` Difficult: ${lis(dif)}.`) : '');
  }
  function viabLargo(cl, c) {
    const at = cl.factores.filter(f => f.estado === 'atencion'), r = cl.res;
    let t = S(`${r.ok} factores favorables, ${r.atencion} en atención y ${r.dificil} difíciles.`, `${r.ok} favorable factors, ${r.atencion} on caution and ${r.dificil} difficult.`);
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
  const climaResp = (cl, c, q) => ({ t: climaCorto(cl, c, q), mas: climaLargo(cl, c) });
  const viabResp = (cl, c) => ({ t: viabCorto(cl), mas: viabLargo(cl, c) });

  /* ---------- zonas del catálogo terrestre y sus datos ---------- */
  const catZ = z => (en() && z.categoria_en) || z.categoria;
  const paisZ = z => (en() && z.pais_en) || z.pais;
  const contZ = z => (en() && z.continente_en) || z.continente;
  const unir = xs => (xs.length > 1 ? xs.slice(0, -1).join(', ') + S(' y ', ' and ') + xs[xs.length - 1] : xs[0] || '');
  const coordTxt = (lat, lon) => `${num(Math.abs(Math.round(lat * 10) / 10))}° ${lat >= 0 ? 'N' : 'S'}, ${num(Math.abs(Math.round(lon * 10) / 10))}° ${lon >= 0 ? S('E', 'E') : S('O', 'W')}`;
  function destacaTxt(z, c) {
    const l = c.candidatos || [], g = l.find(x => x.region === z.id);
    if (!g) return S(`${nom(z)} no está entre los candidatos del sitio elegido, así que no puedo decir en qué destaca frente a él.`, `${nom(z)} is not among the candidates for the chosen site, so I cannot say what stands out compared to it.`);
    const orden = [...l].sort((a, b) => b.corr - a.corr), pos = orden.findIndex(x => x === g || x.region === g.region) + 1, items = [];
    if (pos <= 3) items.push(S(`su correlación de forma (${cr(g.corr)}, ${pos}.ª de ${l.length})`, `its shape correlation (${cr(g.corr)}, ${pos}${pos === 1 ? 'st' : pos === 2 ? 'nd' : 'rd'} of ${l.length})`));
    if (g.rank <= 5) items.push(S(`su puesto #${g.rank} por puntaje`, `its #${g.rank} place by score`));
    if (z.clima && z.clima.sem === 'verde') items.push(S('su clima favorable (semáforo verde)', 'its favorable climate (green traffic light)'));
    return items.length ? S(`Destaca por ${unir(items)}.`, `It stands out for ${unir(items)}.`)
                        : S(`No destaca en particular: ${corto(g)}, puesto #${g.rank}.`, `Nothing stands out in particular: ${corto(g)}, rank #${g.rank}.`);
  }
  const F_CAT = /categoria|category|tipo de|type of|clase de|kind of|que tipo|what type/, F_DONDE = /donde|where|ubicac|location|pais|country|queda|esta en|situad|located|coordenad|latitud|longitud/;
  const F_DEST = /destac|stand out|especial|notable|sobresal|highlight|caracteristic|fortaleza|strength|mejor en|best at|que tiene de/, F_VIAB = /viab|habit|construir|base|semaforo|vivir|feasib|build|settle|live/;
  const PALABRAS_CLIMA = /clima|temperatur|llov|lluvi|viento|helada|hiela|nieva|calor|frio|humed|presion|solar|climate|weather|temperature|rain|wind|frost|freez|snow|cold|hot|humid|pressure/;
  function facetas(tn) {
    const f = { cat: F_CAT.test(tn), donde: F_DONDE.test(tn), dest: F_DEST.test(tn), viab: F_VIAB.test(tn), clima: PALABRAS_CLIMA.test(tn) };
    f.alguna = f.cat || f.donde || f.dest || f.viab || f.clima;
    return f;
  }
  function respuestaZona(z, f, c, texto) {
    const partes = []; let mas;
    if (f.viab && z.clima) { const r = viabResp(z.clima, c); partes.push(r.t); mas = r.mas; }
    else if (f.clima && z.clima) { const r = climaResp(z.clima, c, texto); partes.push(r.t); mas = r.mas; }
    if (f.cat) partes.push(S(`${nom(z)} es de la categoría «${catZ(z)}».`, `${nom(z)} is in the “${catZ(z)}” category.`));
    if (f.donde) partes.push(S(`${nom(z)} está en ${paisZ(z) || 'un lugar sin país en el mapa base'} (${coordTxt(z.lat, z.lon)}).`, `${nom(z)} is in ${paisZ(z) || 'a place with no country on the base map'} (${coordTxt(z.lat, z.lon)}).`));
    if (f.dest) partes.push(destacaTxt(z, c));
    return { t: partes.join(' '), mas };
  }
  const GEN = new Set(['sierra', 'valle', 'gran', 'grand', 'river', 'kings', 'canon', 'canyon', 'crater', 'caldera', 'monte', 'mount', 'montanas', 'mountains', 'grandes', 'llanuras', 'great', 'plains', 'cordillera', 'desierto', 'desert', 'borde', 'valley', 'isla', 'island', 'marte', 'mars', 'luna', 'moon', 'tierra', 'earth', 'cerca', 'near', 'cima', 'summit', 'delta', 'pico', 'peak', 'plateau', 'meseta', 'llanura', 'plain', 'sitio', 'discovered', 'site', 'region', 'dunas', 'dunes', 'salar', 'caldera']);
  const palabras = o => new Set([...norm(o.nombre || o.lugar || '').split(' '), ...norm(o.nombre_en || o.lugar_en || '').split(' ')].filter(w => w.length >= 4 && !GEN.has(w)));
  function zonaPorNombre(tn, c) {
    const zs = (c.zonasClima || []).map(z => ({ z, w: palabras(z) })), p = ' ' + tn + ' ';
    for (const x of zs) for (const w of x.w) {
      if (!p.includes(' ' + w)) continue;
      if (zs.filter(y => y.w.has(w)).length === 1) return x.z;
    }
    return null;
  }

  /* lugar (país o continente) mencionado en la pregunta */
  const ALIAS = { 'estados unidos': ['usa', 'eeuu', 'ee uu', 'united states', 'us'], 'reino unido': ['uk', 'britain', 'england', 'inglaterra'], 'rusia': ['russia'], 'china': [], 'mexico': [] };
  function buscarLugar(tn, c) {
    const p = ' ' + tn + ' ', cand = [];
    const prueba = (obj, tipo, extra) => {
      for (const n of [norm(obj.nombre), norm(obj.nombre_en || ''), ...(extra || [])]) if (n && p.includes(' ' + n + ' ')) cand.push({ tipo, obj, n: n.length, nombreNorm: n });
    };
    for (const x of (c.paises || [])) prueba(x, 'pais', ALIAS[norm(x.nombre)]);
    for (const x of (c.continentes || [])) prueba(x, 'continente');
    return cand.sort((a, b) => b.n - a.n)[0] || null;
  }
  const CATS = [[/canon|canyon/, 'cañon|canyon'], [/desiert|desert/, 'desiert|desert'], [/volcan/, 'volcan'], [/montan|mountain/, 'montan|mountain'], [/crater|caldera/, 'crater|caldera']];
  const catPregunta = tn => { for (const [re, clave] of CATS) if (re.test(tn)) return new RegExp(clave); return null; };

  /* ---------- "match entre <sitio> y <país / continente / zona>" ---------- */
  const MATCHW = /match|parec|similar|semej|asemej|compar|coinci|entre|between|versus|(^| )vs( |$)|resembl|alike|gemel|twin/;
  function sitioPorNombre(tn, c) {
    const todos = [], p = ' ' + tn + ' ';
    for (const cuerpo of ['luna', 'marte']) for (const s of ((c.sitiosPor || {})[cuerpo] || [])) todos.push({ s, cuerpo, w: palabras(s) });
    for (const x of todos) for (const w of x.w) {
      if (!p.includes(' ' + w)) continue;
      if (todos.filter(y => y.w.has(w)).length === 1) return x;
    }
    return null;
  }
  const sitioActual = c => {
    if (!c.region || !c.sitiosPor) return null;
    const s = (c.sitiosPor[c.origenId] || []).find(x => x.nombre === c.region.nombre);
    return s ? { s, cuerpo: c.origenId } : null;
  };
  const avisoRevSitio = s => (s.revision ? S(` El equipo marcó ${nom(s)} para revisión prioritaria (correlación de forma baja).`, ` The team flagged ${nom(s)} for priority review (low shape correlation).`) : '');
  const filaMatch = (g, n) => S(`${nomC(g)}: puesto #${g.rank} de ${n}, ${corto(g)}`, `${nomC(g)}: rank #${g.rank} of ${n}, ${corto(g)}`);
  function matchEntre(tn, c) {
    const lugar = buscarLugar(tn, c), zona = zonaPorNombre(tn, c);
    if (!lugar && !zona) return null;
    const explicito = sitioPorNombre(tn, c);
    if (!explicito && !MATCHW.test(tn)) return null;   // sin sitio nombrado hace falta una palabra de comparación
    const x = explicito || sitioActual(c);
    if (!x) return null;
    const s = x.s, n = s.n_evaluados || 500, gem = s.gemelos || [], mejor = s.mejor;
    const cierre = S(` Para comparar, el mejor candidato de ${nom(s)} en todo el mundo es ${nomC(mejor)} (${sc(mejor.score)}).`, ` For comparison, the best candidate for ${nom(s)} worldwide is ${nomC(mejor)} (${sc(mejor.score)}).`);
    if (zona && !lugar) {                       // un sitio y UNA zona concreta (p. ej. Nobile y Atacama)
      const g = gem.find(y => y.region === zona.id);
      if (!g) return { t: S(`${nom(zona)} no está entre los candidatos de ${nom(s)}: ninguno de sus parches entró entre los ${n} mejores.`, `${nom(zona)} is not among the candidates for ${nom(s)}: none of its patches made it into the best ${n}.`) + cierre + avisoRevSitio(s) };
      return { t: S(`${nom(s)} ↔ ${nom(zona)}: puesto #${g.rank} de ${n}, ${corto(g)}.`, `${nom(s)} ↔ ${nom(zona)}: rank #${g.rank} of ${n}, ${corto(g)}.`) + alertaCorr(g) + cierre + avisoRevSitio(s) };
    }
    const nombreL = nom(lugar.obj);
    const catalogo = (c.zonasClima || []).filter(z => (lugar.tipo === 'pais' ? z.pais === lugar.obj.nombre : z.continente === lugar.obj.nombre));
    if (!catalogo.length) return { t: S(`No hay zonas del catálogo en ${nombreL}, así que no hay con qué comparar a ${nom(s)}.`, `There are no catalog zones in ${nombreL}, so there is nothing to compare ${nom(s)} with.`) };
    const enLugar = gem.filter(g => (lugar.tipo === 'pais' ? g.pais === lugar.obj.nombre : g.continente === lugar.obj.nombre)).sort((a, b) => a.rank - b.rank);
    if (!enLugar.length) return { t: S(`Ninguna zona de ${nombreL} (${unir(catalogo.map(nom))}) entra entre los candidatos de ${nom(s)}.`, `No zone in ${nombreL} (${unir(catalogo.map(nom))}) is among the candidates for ${nom(s)}.`) + cierre + avisoRevSitio(s) };
    const top = enLugar[0];
    return { t: S(`${nom(s)} ↔ ${nombreL}: la mejor coincidencia es ${filaMatch(top, n)}.`, `${nom(s)} ↔ ${nombreL}: the best match is ${filaMatch(top, n)}.`) + alertaCorr(top)
              + (enLugar.length > 1 ? S(` También: ${enLugar.slice(1, 3).map(g => filaMatch(g, n)).join('; ')}.`, ` Also: ${enLugar.slice(1, 3).map(g => filaMatch(g, n)).join('; ')}.`) : '')
              + (catalogo.length > enLugar.length ? S(` Las otras zonas de ${nombreL} no entran entre los candidatos.`, ` The other zones in ${nombreL} are not among the candidates.`) : '') + cierre + avisoRevSitio(s),
             mas: S(`El «puesto» es la posición del mejor parche de esa zona entre los ${n} evaluados (1 = el más parecido). Cuanto más alto el número, más débil la coincidencia.`, `The “rank” is the position of that zone’s best patch among the ${n} evaluated (1 = the most alike). The higher the number, the weaker the match.`) };
  }

  /* ---------- capa 2: respuestas (cada una: texto corto + "mas" opcional) ---------- */
  const R = {
    saludo: () => S('Puedo explicarte los números, comparar el sitio con cada zona terrestre, decirte cuál se parece más y qué límites tiene. Usa los botones o pregúntame.',
                    'I can explain the numbers, compare the site with each Earth zone, tell you which one looks most alike and what the limits are. Use the buttons or just ask.'),
    parecido: c => ({
      t: S('El puntaje va de 0 a 1 y menor es más parecido: combina qué tan cerca están los 8 números de relieve y qué tan parecida es la forma. No es un porcentaje.',
           'The score goes from 0 to 1 and lower is more alike: it combines how close the 8 relief numbers are and how similar the shape is. It is not a percentage.'),
      mas: S('Detalle: promedia (a) qué tan cerca están los 8 números de relieve (pendiente, curvatura y rugosidad) y (b) qué tan parecida es la forma del terreno (correlación del relieve sin su inclinación general, probando 4 rotaciones). No es un porcentaje de identidad geológica.',
             'Detail: it averages (a) how close the 8 relief numbers (slope, curvature and roughness) are and (b) how similar the terrain shape is (correlation of the relief without its overall tilt, trying 4 rotations). It is not a percentage of geological identity.')
        + (c.gemelo ? S(`\n\nEn esta lista, el mejor es ${nomC(c.gemelo)}: ${detalle(c.gemelo)}.`, `\n\nIn this list, the best is ${nomC(c.gemelo)}: ${detalle(c.gemelo)}.`) : '') }),
    porque: c => {
      if (!(c.region && c.gemelo)) return S('Elige un resultado en la lista y te comparo sus números con el de referencia.', 'Pick a result from the list and I will compare its numbers with the reference.');
      const g = c.gemelo;
      return { t: S(`${nomC(g)} frente a ${nom(c.region)}: ${corto(g)}.`, `${nomC(g)} versus ${nom(c.region)}: ${corto(g)}.`)
        + (g.ficha && c.region.ficha ? ' ' + comparar(c.region.ficha, g.ficha) : S(' Para este candidato el equipo no entregó pendiente ni rugosidad.', ' For this candidate the team did not provide slope or roughness.')) + alertaCorr(g) };
    },
    llana: () => ({ t: S('En los datos actuales no se calcula la fracción llana; las tarjetas muestran pendiente media y rugosidad.', 'The flat fraction is not computed in the current data; the cards show mean slope and roughness.'),
      mas: S('Se usan 8 números: pendiente (media, desviación y percentil 90), curvatura (media y percentil 90) y rugosidad (mediana, percentil 90 y desviación).', '8 numbers are used: slope (mean, deviation and 90th percentile), curvature (mean and 90th percentile) and roughness (median, 90th percentile and deviation).') }),
    pendiente: () => ({ t: S('La pendiente media es la inclinación promedio del terreno, en grados.', 'Mean slope is the average tilt of the terrain, in degrees.'),
      mas: S('Se calcula igual en los tres cuerpos y a la misma escala (80 m en la Luna, 200 m en Marte y la Tierra remuestreada), para que sean comparables.', 'It is computed the same way on all three bodies and at the same scale (80 m for the Moon, 200 m for Mars with Earth resampled), so they are comparable.') }),
    rugosidad: () => S('La rugosidad mide cuánto se desvía el terreno de un plano local (en metros): valores altos indican terreno quebrado a pequeña escala.',
                       'Roughness measures how much the terrain departs from a local plane (in meters): high values mean broken terrain at small scale.'),
    aptitud: c => ({
      t: S('Este análisis no mide si un sitio es apto para aterrizar: solo qué tan parecido es su relieve al de zonas de la Tierra.', 'This analysis does not measure whether a site is suitable for landing: only how similar its relief is to Earth zones.')
        + (c.clima ? S(' Para una base en la Tierra sí hay clima: pregúntame «¿es viable una base ahí?».', ' For a base on Earth there is climate data: ask me “is a base viable there?”.') : ''),
      mas: S('Para hablar de aptitud habría que añadir iluminación, hielo en sombra, visibilidad de la Tierra y criterios de misión, que no están en estos datos.', 'Talking about suitability would need lighting, shadowed ice, Earth visibility and mission criteria, which are not in this data.') }),
    limites: () => ({
      t: S('Lo principal: la Tierra son 49 zonas elegidas por el equipo (no un barrido global), el puntaje no es un porcentaje y el ganador puede cambiar con el peso, y cada sitio es una ventana de ~3 km.',
           'The main points: Earth is 49 zones chosen by the team (not a global sweep), the score is not a percentage and the winner can change with the weight, and each site is a ~3 km window.'),
      mas: S('Detalle: (1) La Tierra son 49 zonas de unos 13 km. (2) Cada sitio lunar o marciano es una ventana de ~3 km, no el cráter completo. (3) El puntaje mezcla, a partes iguales, la posición física del parche (no su distancia) y la forma, sobre los 500 mejores preseleccionados; si cambia ese peso, el ganador puede cambiar, y entre el primero y el segundo suele haber diferencias mínimas. (4) Luna a 80 m y Marte a 200 m (con la Tierra remuestreada). (5) El DEM terrestre incluye árboles y edificios. (6) En algunos sitios las cifras absolutas no coinciden bien aunque la forma sí, por eso hay revisiones prioritarias.',
             'Detail: (1) Earth is 49 zones of about 13 km. (2) Each Moon or Mars site is a ~3 km window, not the whole crater. (3) The score mixes, in equal parts, the patch’s physical rank (not its distance) and the shape, over the 500 best preselected; if that weight changes, the winner can change, and the gap between first and second is often tiny. (4) Moon at 80 m and Mars at 200 m (with Earth resampled). (5) The Earth elevation model includes trees and buildings. (6) At some sites the absolute numbers do not match well even if the shape does, hence the priority reviews.') }),
    subir: () => S('Subir tu zona aún no está disponible. Necesitará un GeoTIFF de alturas (coordenadas en metros, ≥3×3 km, resolución mejor que ~120 m y ≥85 % de píxeles válidos; criterios provisionales).',
                   'Uploading your area is not available yet. It will need an elevation GeoTIFF (coordinates in meters, ≥3×3 km, resolution better than ~120 m and ≥85% valid pixels; provisional criteria).'),
    muestra: () => ({ t: S('No son datos de muestra: son resultados reales del equipo, pero exploratorios (puntos de referencia, no polígonos completos).', 'This is not sample data: these are the team’s real results, but exploratory (reference points, not full polygons).'),
      mas: S('Vienen de modelos de elevación reales: Copernicus GLO-30 (Planetary Computer) para la Tierra, NASA LOLA para la Luna y USGS HRSC/MOLA para Marte.', 'They come from real elevation models: Copernicus GLO-30 (Planetary Computer) for Earth, NASA LOLA for the Moon and USGS HRSC/MOLA for Mars.') }),
    mejor: c => {
      const l = c.candidatos || [];
      if (!l.length) return sinCand();
      const g = l[0], seg = l[1];
      return { t: S(`${nomC(g)} (#${g.rank}): ${corto(g)}.`, `${nomC(g)} (#${g.rank}): ${corto(g)}.`) + (seg ? S(` Le sigue ${nomC(seg)} (${sc(seg.score)}).`, ` Next: ${nomC(seg)} (${sc(seg.score)}).`) : '') + alertaCorr(g) + alertaRev(c),
               mas: S(`${nomC(g)}: ${detalle(g)}${g.ficha ? `; ${numeros(g.ficha)}` : ''}.`, `${nomC(g)}: ${detalle(g)}${g.ficha ? `; ${numeros(g.ficha)}` : ''}.`) + aviso(c) };
    },
    lista: c => {
      const l = c.candidatos || [];
      if (!l.length) return sinCand();
      const fila = (g, i) => `${i + 1}. ${nomC(g)} — ${sc(g.score)}`;
      return { t: S(`Hay ${l.length} zona${l.length === 1 ? '' : 's'} candidata${l.length === 1 ? '' : 's'}${c.zona ? ` en ${c.zona}` : ''}. Las mejores:\n`, `There ${l.length === 1 ? 'is 1 candidate zone' : `are ${l.length} candidate zones`}${c.zona ? ` in ${c.zona}` : ''}. The best ones:\n`) + l.slice(0, 5).map(fila).join('\n'),
               mas: l.length > 5 ? l.slice(5, 20).map((g, i) => fila(g, i + 5)).join('\n') + (l.length > 20 ? S(`\n… y ${l.length - 20} más.`, `\n… and ${l.length - 20} more.`) : '') : undefined };
    },
    resumen: c => {
      if (!c.region) return S('Elige una región de referencia y te resumo el resultado.', 'Pick a reference region and I will summarize the result.');
      const l = c.candidatos || [], zonaTxt = `${c.destino}${c.zona ? ' · ' + c.zona : ''}`;
      let t = S(`Referencia: ${nom(c.region)} (${c.origen}), ${numeros(c.region.ficha)}.`, `Reference: ${nom(c.region)} (${c.origen}), ${numeros(c.region.ficha)}.`) + alertaRev(c);
      if (!l.length) return { t: t + S(` No hay candidatos en ${zonaTxt}.`, ` No candidates in ${zonaTxt}.`) };
      t += S(` En ${zonaTxt}: ${l.length} zona${l.length === 1 ? '' : 's'}; la mejor es ${nomC(l[0])} (${corto(l[0])}).`, ` In ${zonaTxt}: ${l.length} zone${l.length === 1 ? '' : 's'}; the best is ${nomC(l[0])} (${corto(l[0])}).`) + alertaCorr(l[0]);
      const mn = Math.min(...l.map(g => g.score)), mx = Math.max(...l.map(g => g.score));
      return { t, mas: S(`Se evaluaron ${c.region.n_evaluados || 500} parches terrestres a ${c.region.res || ''} m; los puntajes de las zonas van de ${sc(mn)} a ${sc(mx)} (menor es mejor).`, `${c.region.n_evaluados || 500} Earth patches were evaluated at ${c.region.res || ''} m; zone scores range from ${sc(mn)} to ${sc(mx)} (lower is better).`) + aviso(c) };
    },
    fuentes: () => ({ t: S('Elevación: Copernicus GLO-30 (Tierra), NASA LOLA (Luna) y USGS HRSC/MOLA (Marte). Mapas: OpenStreetMap, NASA LRO WAC y Viking MDIM 2.1.', 'Elevation: Copernicus GLO-30 (Earth), NASA LOLA (Moon) and USGS HRSC/MOLA (Mars). Maps: OpenStreetMap, NASA LRO WAC and Viking MDIM 2.1.'),
      mas: S('Detalle: Tierra, Copernicus GLO-30 vía Microsoft Planetary Computer; Luna, NASA LOLA a 80 m; Marte, mosaico USGS HRSC/MOLA a 200 m. Mapas: Luna, LRO WAC (NASA/GSFC/ASU); Marte, Viking MDIM 2.1 (NASA/JPL-Caltech, USGS). Fronteras: Natural Earth (dominio público).', 'Detail: Earth, Copernicus GLO-30 via Microsoft Planetary Computer; Moon, NASA LOLA at 80 m; Mars, USGS HRSC/MOLA blend at 200 m. Maps: Moon, LRO WAC (NASA/GSFC/ASU); Mars, Viking MDIM 2.1 (NASA/JPL-Caltech, USGS). Borders: Natural Earth (public domain).') }),
    clima: (c, q) => (c.clima ? climaResp(c.clima, c, q) : sinClima()),
    viabilidad: c => (c.clima ? viabResp(c.clima, c) : S('La viabilidad climática de una base solo se evalúa para zonas de la Tierra. Elige un candidato terrestre y te la resumo.', 'Climate viability for a base is only assessed for Earth zones. Pick an Earth candidate and I will summarize it.')),
    acerca: () => ({ t: S('Soy Vertikal Bot: un conjunto de redes neuronales pequeñas, que corre en tu navegador, entiende tu pregunta; las respuestas y cifras salen de los datos mostrados. No envía tus preguntas a ningún servidor ni usa IA externa.',
                          'I am Vertikal Bot: a set of small neural networks, running in your browser, understands your question; answers and numbers come from the data shown. It does not send your questions to any server or use external AI.'),
      mas: S('Detalle: son 3 redes de unos 190 KB cada una (≈500 KB en total) que solo clasifican de qué tema hablas; no son modelos de lenguaje generativos y no envían tus preguntas a ningún lado. Puedo equivocarme con frases nuevas: si dudo, te ofrezco temas.',
             'Detail: 3 networks of about 190 KB each (≈500 KB in total) that only classify which topic you are asking about; they are not generative language models and do not send your questions anywhere. I can be wrong with new phrasings: when in doubt, I offer topics.') }),
    sitios: (c, q) => {
      const tn = norm(q), cuerpo = /marte|mars|marcian|martian/.test(tn) ? 'marte' : /luna|moon|lunar/.test(tn) ? 'luna' : (c.origenId === 'marte' ? 'marte' : 'luna');
      let l = [...((c.sitiosPor || {})[cuerpo] || [])];
      if (!l.length) return S('Aún no tengo la comparación entre sitios.', 'I do not have the comparison between sites yet.');
      if (/crater/.test(tn)) { const f = l.filter(s => /crater/.test(norm(s.nombre + ' ' + (s.nombre_en || '')))); if (f.length) l = f; }
      l.sort((a, b) => a.mejor.score - b.mejor.score);
      const nombreC = cuerpo === 'marte' ? S('Marte', 'Mars') : S('la Luna', 'the Moon');
      const fila = (s, i) => `${i + 1}. ${nom(s)} → ${nomC(s.mejor)} (${S('puntaje', 'score')} ${sc(s.mejor.score)}, ${S('correlación', 'correlation')} ${cr(s.mejor.corr)})`;
      const porCorr = [...l].sort((a, b) => b.mejor.corr - a.mejor.corr)[0];
      return { t: S(`Sitios de ${nombreC} con mejor coincidencia terrestre (por puntaje):\n`, `Sites on ${nombreC} with the best Earth match (by score):\n`) + l.slice(0, 3).map(fila).join('\n')
                  + S('\nOjo: el puntaje es relativo a cada sitio, así que compararlo entre sitios es solo orientativo.', '\nNote: the score is relative to each site, so comparing across sites is only indicative.'),
               mas: l.map(fila).join('\n') + S(`\n\nPor correlación de forma, el más alto es ${nom(porCorr)} (${cr(porCorr.mejor.corr)}).`, `\n\nBy shape correlation, the highest is ${nom(porCorr)} (${cr(porCorr.mejor.corr)}).`) };
    },
    zonas: (c, q) => {
      const zs = c.zonasClima || [], tn = norm(q);
      if (!zs.length) return S('Aún no tengo el catálogo de zonas terrestres.', 'I do not have the Earth zone catalog yet.');
      const lugar = buscarLugar(tn, c), cat = catPregunta(tn);
      let l = zs;
      if (lugar) l = l.filter(z => (lugar.tipo === 'pais' ? z.pais === lugar.obj.nombre : z.continente === lugar.obj.nombre));
      if (cat) l = l.filter(z => cat.test(norm(z.categoria + ' ' + (z.categoria_en || ''))));
      const donde = lugar ? nom(lugar.obj) : null, etiqueta = cat && !lugar ? S('del tipo pedido', 'of that type') : null;
      if (lugar || cat) {
        if (!l.length) return S(`No hay zonas del catálogo${donde ? ` en ${donde}` : ''}${cat ? ' de ese tipo' : ''} (son 50 zonas elegidas por el equipo).`, `There are no catalog zones${donde ? ` in ${donde}` : ''}${cat ? ' of that type' : ''} (the catalog is 50 zones chosen by the team).`);
        const nombres = l.map(nom);
        return { t: S(`${donde ? `En ${donde} hay` : 'Hay'} ${l.length} zona${l.length === 1 ? '' : 's'} del catálogo${etiqueta ? ' ' + etiqueta : ''}: ${unir(nombres.slice(0, 8))}${l.length > 8 ? S(` y ${l.length - 8} más`, ` and ${l.length - 8} more`) : ''}.`,
                      `${donde ? `In ${donde} there ${l.length === 1 ? 'is' : 'are'}` : 'There ' + (l.length === 1 ? 'is' : 'are')} ${l.length} catalog zone${l.length === 1 ? '' : 's'}${etiqueta ? ' ' + etiqueta : ''}: ${unir(nombres.slice(0, 8))}${l.length > 8 ? ` and ${l.length - 8} more` : ''}.`)
                    + (donde ? S(` Para ver sus candidatos, elige ${donde} en «Dónde buscar parecidos».`, ` To see their candidates, pick ${donde} under “Where to look for matches”.`) : ''),
                 mas: l.length > 8 ? nombres.join(', ') + '.' : undefined };
      }
      const paises = new Set(zs.map(z => z.pais).filter(Boolean)).size;
      const porCat = {}; for (const z of zs) (porCat[catZ(z)] = porCat[catZ(z)] || []).push(nom(z));
      return { t: S(`El catálogo terrestre son ${zs.length} zonas elegidas por el equipo (montañas, volcanes, desiertos, cráteres y calderas, cañones y mesetas) en ${paises} países. Pregúntame por un país, por ejemplo «¿qué zonas hay en México?».`,
                    `The Earth catalog is ${zs.length} zones chosen by the team (mountains, volcanoes, deserts, craters and calderas, canyons and plateaus) in ${paises} countries. Ask me about a country, for example “what zones are in Mexico?”.`),
               mas: Object.entries(porCat).map(([k, v]) => `${k}: ${v.join(', ')}.`).join('\n') };
    },
    gracias: () => S('¡De nada! Si quieres, pregúntame por el mejor candidato o por los límites del resultado.', 'You are welcome! If you like, ask me about the best candidate or the limits of the result.'),
    otro: () => S('Eso queda fuera de lo que sé explicar: te ayudo con los resultados de terreno y clima de esta página.', 'That is outside what I can explain: I help with the terrain and climate results on this page.'),
  };
  const PREGUNTAS = {
    parecido: ['¿Qué significa el parecido?', 'What does the match mean?'], porque: ['¿Por qué se parecen?', 'Why do they look alike?'],
    limites: ['¿Qué no considera?', 'What is not considered?'], llana: ['¿Qué es la fracción llana?', 'What is the flat fraction?'],
    subir: ['¿Cómo subo mi zona?', 'How do I upload my area?'], mejor: ['¿Cuál es el mejor?', 'Which is the best?'],
    lista: ['¿Qué candidatos hay?', 'What candidates are there?'], resumen: ['Dame un resumen', 'Give me a summary'],
    pendiente: ['¿Qué es la pendiente?', 'What is slope?'], rugosidad: ['¿Qué es la rugosidad?', 'What is roughness?'],
    aptitud: ['¿Qué es la aptitud?', 'What is suitability?'], acerca: ['¿Usas inteligencia artificial?', 'Do you use AI?'], clima: ['¿Qué clima tiene?', 'What is the climate like?'],
    viabilidad: ['¿Es viable una base ahí?', 'Is a base viable there?'], muestra: ['¿Son datos reales?', 'Is this real data?'], fuentes: ['¿De dónde salen los mapas?', 'Where do the maps come from?'],
    sitios: ['¿Qué sitio se parece más a la Tierra?', 'Which site is most like Earth?'], zonas: ['¿Qué zonas hay en la Tierra?', 'What zones are there on Earth?'],
  };
  const preguntaDe = (i, idioma) => (PREGUNTAS[i] ? PREGUNTAS[i][(idioma || L) === 'en' ? 1 : 0] : null);
  const rapidas = () => ['parecido', 'porque', 'mejor', 'viabilidad', 'limites'].map(i => preguntaDe(i, typeof I18N !== 'undefined' ? I18N.lang : 'es'));

  /* ---------- capa 1: entender ---------- */
  const KW = {
    saludo: ['hola', 'buenas', 'ayuda', 'que puedes', 'como funciona', 'como se usa', 'hello', 'hi ', 'help', 'what can you', 'how does it work', 'how is this used'],
    parecido: ['parecido', 'porcentaje', 'similitud', 'score', 'match', 'similarity', 'percent', 'puntaje'],
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
    sitios: ['que sitio', 'cual sitio', 'sitios', 'ranking', 'which site', 'which crater', 'what crater', 'sites', 'crater de marte', 'crater de la luna', 'mars crater', 'moon site'],
    zonas: ['que zonas', 'que areas', 'areas disponibles', 'zonas disponibles', 'ubicaciones', 'que ubicaciones', 'catalogo', 'que paises', 'which zones', 'what zones', 'which areas', 'what areas', 'locations', 'available', 'catalog', 'which countries'],
    fuentes: ['mapa', 'fuente', 'de donde', 'source', 'frontera', 'border'], gracias: ['gracias', 'agradez', 'agradecid', 'amable', 'thanks', 'thank', 'grateful', 'thankful'],
  };
  function porReglas(t) {
    const p = ' ' + t + ' '; let mejor = null, mx = 0;
    for (const [i, kws] of Object.entries(KW)) { const n = kws.filter(k => p.includes(' ' + k)).length; if (n > mx) { mx = n; mejor = i; } }
    return mejor;
  }
  function porNombre(t, c) {
    const p = ' ' + t + ' ';
    const cands = (c.candidatos || []).map(g => ({ g, w: palabras(g) }));
    for (const x of cands) for (const w of x.w) {
      if (!p.includes(' ' + w)) continue;
      if (cands.filter(y => y.w.has(w)).length === 1) return { tipo: 'candidato', g: x.g };
    }
    if (c.region) for (const w of palabras(c.region)) if (p.includes(' ' + w)) return { tipo: 'region' };
    return null;
  }

  /* "el segundo", "el último", "número 3", "candidate 2"... -> candidato por posición. */
  function porOrdinal(texto, c) {
    const l = c.candidatos || [];
    if (!l.length) return null;
    const t = texto.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    const num_ = t.match(/(?:numero|number|candidato|candidate|lugar|place|#)\s*(\d+)/);
    let i = null;
    if (num_) i = +num_[1] - 1;
    else if (/\b(segundo|second)\b/.test(t)) i = 1;
    else if (/\b(tercero|tercer|third)\b/.test(t)) i = 2;
    else if (/\b(ultimo|last)\b/.test(t)) i = l.length - 1;
    if (i === null) return null;
    return i >= 0 && i < l.length ? { tipo: 'candidato', g: l[i] } : { tipo: 'fueraRango', n: l.length };
  }

  /* Palabras clave inequívocas: si la red elige un tema "de plantilla" (lista, mejor, resumen…) pero la pregunta nombra
     claramente otro tema, manda la palabra clave (p. ej. "cuáles son los límites" no es una lista de candidatos). */
  const FUERTES = {
    limites: ['limit', 'limitacion'], pendiente: ['pendiente', 'slope'], rugosidad: ['rugos', 'rough'], llana: ['fraccion llana', 'llano', 'flat fraction'],
    subir: ['subir', 'upload', 'geotiff'], clima: ['clima', 'temperatur', 'lluvi', 'viento', 'helada', 'weather', 'climate'], viabilidad: ['viab', 'semaforo', 'habitab', 'traffic light'],
    acerca: ['inteligencia artificial', 'red neuronal', 'chatgpt'], fuentes: ['fuente', 'source'],
  };
  const GENERICOS = new Set(['lista', 'mejor', 'resumen', 'porque', 'sitios', 'saludo']);
  function porFuertes(t) {
    const p = ' ' + t + ' ';
    const hits = Object.entries(FUERTES).filter(([, kws]) => kws.some(k => p.includes(' ' + k)));
    return hits.length === 1 ? hits[0][0] : null;          // solo si hay un tema inequívoco
  }
  /* "qué desiertos/volcanes/cañones hay…": catálogo por tipo de zona */
  const pideZonasPorTipo = t => !!catPregunta(t) && /(^| )(hay|disponib|incluy|catalog|tienen|are there|available|include)/.test(t) && !PALABRAS_CLIMA.test(t);

  /* Preguntas sobre el catálogo terrestre: nombran un país/continente junto con zonas/sitios/lugares disponibles, o dicen "catálogo". */
  const pideZonasDeLugar = (t, c) => /(zonas|areas|sitios|lugares|ubicacion|puntos|places|sites|zones|locations|spots|available|disponib|catalog|tienen|tienes|have|incluy|analiz|existe|exist|hay|there)/.test(t)
    && !/(mejor|best|primero|first|top|ranking|ordena|rank|parecid|similar|alike)/.test(t) && !PALABRAS_CLIMA.test(t) && !!buscarLugar(t, c);

  /* La pregunta es solo un país o continente ("México", "en Perú", "Asia"): se entiende como "qué zonas hay ahí". */
  const SIN_VALOR = new Set(['en', 'de', 'del', 'la', 'el', 'las', 'los', 'in', 'of', 'the', 'a', 'por', 'sobre', 'about']);
  function soloLugar(t, c) {
    const l = buscarLugar(t, c);
    if (!l) return false;
    const propios = new Set(l.nombreNorm.split(' '));
    return t.split(' ').filter(Boolean).every(w => propios.has(w) || SIN_VALOR.has(w));
  }

  function entender0(texto, c) {
    const t = norm(texto);
    if (!t) return { tipo: 'nada' };
    const nombre = porOrdinal(texto, c) || porNombre(t, c);
    if (nombre) return nombre;
    if (pideZonasPorTipo(t) || /(^| )catalog/.test(t) || pideZonasDeLugar(t, c) || soloLugar(t, c)) return { tipo: 'intent', intent: 'zonas', via: 'reglas' };
    const reglas = porReglas(t);
    // Si casi ninguna palabra es conocida, la red no es fiable: solo valen las reglas.
    const nn = BotNN.fraccionConocida(texto) >= 0.34 ? BotNN.clasificar(texto) : null;
    if (!nn) return reglas ? { tipo: 'intent', intent: reglas, via: 'reglas' } : { tipo: 'nada' };
    const [[i1, p1], [i2]] = nn;
    const fuerte = porFuertes(t);
    if (fuerte && fuerte !== i1 && GENERICOS.has(i1)) return { tipo: 'intent', intent: fuerte, p: p1, via: 'palabra clave' };
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
  function empaquetar(r) {
    const o = typeof r === 'string' ? { t: r } : r, out = { texto: o.t };
    if (o.mas) out.sugerencias = [{ etiqueta: S('Más detalle', 'More detail'), respuesta: o.mas }];
    return out;
  }

  function responder(texto, c) {
    const tn = norm(texto);
    L = idiomaDe(tn) || (typeof I18N !== 'undefined' ? I18N.lang : 'es');
    const seg = seguridad(tn);
    if (seg) return { texto: textoSeguridad(seg) };
    const mt = matchEntre(tn, c);
    if (mt) return empaquetar(mt);
    // Una zona del catálogo nombrada con una faceta (clima, viabilidad, categoría, ubicación, "en qué destaca"): se responde sobre ESA zona.
    const z = zonaPorNombre(tn, c), f = facetas(tn);
    if (z && f.alguna) return empaquetar(respuestaZona(z, f, c, texto));
    const u = entender(texto, c);
    if (u.tipo === 'candidato') {
      const g = u.g;
      const base = S(`${nomC(g)} (#${g.rank}): ${corto(g)}.`, `${nomC(g)} (#${g.rank}): ${corto(g)}.`);
      return empaquetar({ t: base + (g.ficha && c.region && c.region.ficha ? ' ' + comparar(c.region.ficha, g.ficha) : g.ficha ? ' ' + numeros(g.ficha) + '.' : '') + alertaCorr(g), mas: g.categoria ? S(`Categoría: ${catZ({ categoria: g.categoria, categoria_en: g.categoria_en })}.`, `Category: ${catZ({ categoria: g.categoria, categoria_en: g.categoria_en })}.`) + aviso(c) : aviso(c) });
    }
    if (u.tipo === 'fueraRango') return { texto: S(`Solo hay ${u.n} candidato${u.n === 1 ? '' : 's'} en esta región. Pídeme uno del 1 al ${u.n}.`, `There ${u.n === 1 ? 'is only 1 candidate' : `are only ${u.n} candidates`} in this region. Ask me about one from 1 to ${u.n}.`) };
    if (u.tipo === 'region') return empaquetar({ t: S(`${nom(c.region)} (${c.origen}): ${numeros(c.region.ficha)}.`, `${nom(c.region)} (${c.origen}): ${numeros(c.region.ficha)}.`) + alertaRev(c), mas: aviso(c).trim() || undefined });
    if (u.tipo === 'duda') {
      const op = u.opciones.map(i => preguntaDe(i)).filter(Boolean);
      return { texto: S('No estoy seguro de haber entendido. ¿Quisiste preguntar por alguno de estos temas?', 'I am not sure I understood. Did you mean one of these topics?'), sugerencias: op };
    }
    if (u.tipo === 'intent' && R[u.intent]) return empaquetar(R[u.intent](c, texto));
    return { texto: S('No tengo una respuesta para eso. Puedo explicar el parecido, la pendiente, la rugosidad, los límites, el mejor candidato o el clima.',
                      'I do not have an answer for that. I can explain the match, slope, roughness, the limits, the best candidate or the climate.') };
  }
  return { responder, rapidas, entender, idiomaDe };
})();
if (typeof module !== 'undefined') module.exports = Asistente;
