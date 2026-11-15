/* Evaluación de extremo a extremo (red + reglas + umbrales) sobre el conjunto ciego 2. Se ejecuta UNA vez. */
const fs = require('fs'), path = require('path'), raiz = path.join(__dirname, '..');
global.I18N = { lang: 'es', nm: o => o.nombre, num: n => String(n) };
global.BotNN = require(path.join(raiz, 'docs', 'bot_nn.js'));
const Asistente = require(path.join(raiz, 'docs', 'asistente.js'));
BotNN.cargar(JSON.parse(fs.readFileSync(path.join(raiz, 'docs', 'bot_modelo.json'))));
const ref = JSON.parse(fs.readFileSync(path.join(raiz, 'entrenamiento', 'referencia.json')));
const ctx = { muestra: true, origen: 'Luna', destino: 'Tierra', zona: null, region: null, candidatos: [], gemelo: null };
let n = 0, directo = 0, aclara = 0, mal = 0, solored = 0; const fallos = [];
for (const [intent, langs] of Object.entries(ref.ciego2)) for (const frases of Object.values(langs)) for (const f of frases) {
  n++;
  const u = Asistente.entender(f, ctx), top = BotNN.clasificar(f)[0][0];
  if (top === intent) solored++;
  if (u.tipo === 'intent' && u.intent === intent) directo++;
  else if (u.tipo === 'duda' && u.opciones.includes(intent)) aclara++;
  else { mal++; fallos.push([f, intent, u.tipo === 'intent' ? u.intent : u.tipo]); }
}
console.log(`CIEGO 2, ${n} frases`);
console.log(`  solo la red (top-1):           ${solored}/${n} = ${(100 * solored / n).toFixed(1)}%`);
console.log(`  bot completo, responde bien:    ${directo}/${n} = ${(100 * directo / n).toFixed(1)}%`);
console.log(`  bot completo, pide aclarar bien (el tema correcto está entre las opciones): ${aclara}`);
console.log(`  bot completo, se equivoca o no entiende: ${mal}/${n} = ${(100 * mal / n).toFixed(1)}%`);
fallos.forEach(x => console.log('   -', JSON.stringify(x[0]), '| esperado:', x[1], '| obtuvo:', x[2]));
