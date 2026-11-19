/* Puente para la demo de IA 2: pasa frases por el bot COMPLETO de la web (docs/asistente.js:
   red + reglas + umbrales + guardas) y devuelve, en JSON, la decisión y la respuesta.
   Uso: node presentacion/ia2/bot_decision.js "frase 1" "frase 2" ... */
const fs = require('fs'), path = require('path'), raiz = path.join(__dirname, '..', '..');
global.I18N = { lang: 'es', nm: o => o.nombre, num: n => String(n) };
global.BotNN = require(path.join(raiz, 'docs', 'bot_nn.js'));
const Asistente = require(path.join(raiz, 'docs', 'asistente.js'));
BotNN.cargar(JSON.parse(fs.readFileSync(path.join(raiz, 'docs', 'bot_modelo.json'))));
const ctx = { muestra: true, origen: 'Luna', destino: 'Tierra', zona: null, region: null, candidatos: [], gemelo: null };
const salida = process.argv.slice(2).map(f => {
  const u = Asistente.entender(f, ctx);
  let r = null;
  try { r = Asistente.responder(f, ctx); } catch (e) { r = { texto: '(sin respuesta: ' + e.message + ')' }; }
  return { frase: f, conocida: BotNN.fraccionConocida(f), decision: u, respuesta: r && r.texto,
           sugerencias: r && r.sugerencias ? r.sugerencias.map(s => s.etiqueta || s) : [] };
});
console.log(JSON.stringify(salida));
