"""Demostración en vivo para Inteligencia Artificial 2.

Usa el código y el modelo reales del proyecto, sin reentrenar nada (salvo `curvas`, que reentrena UNA red para
registrar la pérdida por época) y sin internet.

  bot      Vertikal Bot paso a paso: texto → n-gramas con hashing → capa oculta → softmax (3 redes) → decisión.
           La decisión del bot completo (red + reglas + umbrales + guardas) sale de docs/asistente.js vía Node.
  evaluar  Las 160 frases del conjunto ciego 2, que la red no vio: exactitud, matriz de confusión,
           exactitud por intención y el compromiso entre responder y acertar según el umbral.
  curvas   Reentrena una sola red (semilla 7) con el mismo bucle del proyecto y registra pérdida y exactitud por época.
  motor    El motor de similitud como sistema de recuperación: recuperar por distancia en 8 rasgos, reordenar
           por correlación de forma y sensibilidad del ganador al peso del puntaje (8 sitios lunares).

Uso (desde la raíz del repositorio):

  python presentacion/ia2/demo_ia.py bot
  python presentacion/ia2/demo_ia.py bot "¿de dónde salen los mapas?" "es buen lugar para vivir"
  python presentacion/ia2/demo_ia.py evaluar
  python presentacion/ia2/demo_ia.py curvas
  python presentacion/ia2/demo_ia.py motor

Añade --mostrar para abrir cada figura en una ventana. Las figuras quedan en presentacion/ia2/salida/.
Requiere numpy y matplotlib (y scipy y tifffile para `motor`); Node.js es opcional (para la decisión del bot completo).
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, "salida")
sys.path.insert(0, os.path.join(RAIZ, "entrenamiento"))
sys.path.insert(0, RAIZ)

import matplotlib                                                      # noqa: E402
if "--mostrar" not in sys.argv:
    matplotlib.use("Agg")
import logging                                                         # noqa: E402
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
import matplotlib.pyplot as plt                                        # noqa: E402

import entrenar as E                                                   # noqa: E402  (entrenamiento/entrenar.py)

NAVY, GOLD, BLUE, MUTED, LIGHT, RED, GREEN = "#16203A", "#E8B13A", "#2F6DB5", "#4A5470", "#B7C2E0", "#E5484D", "#3A9D5D"
plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
    "font.size": 11, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlecolor": NAVY,
    "axes.edgecolor": LIGHT, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
})
UMBRAL, UMBRAL_DUDA = 0.6, 0.4                     # los mismos de docs/asistente.js
FRASES_DEMO = [
    "¿Qué significa la pendiente?",                # confianza alta: responde la red
    "¿Qué tan inclinado es el sitio?",             # confianza media: pide aclarar
    "¿Es buen lugar para vivir?",                  # confianza media + reglas: decide el sistema híbrido
    "¿Qué tan empinado es el terreno?",            # un error real de la red
    "asdkj qwe zxcv",                              # palabras desconocidas: la red no se usa
]


# ----------------------------------------------------------------------------- utilidades

def titulo(n, texto):
    print(f"\n\033[1;33m{n}\033[0m  {texto}")


def guardar(fig, nombre, mostrar):
    os.makedirs(SALIDA, exist_ok=True)
    ruta = os.path.join(SALIDA, nombre)
    fig.savefig(ruta, dpi=200, bbox_inches="tight")
    print(f"   figura → {os.path.relpath(ruta, RAIZ)}")
    if mostrar:
        plt.show()
    plt.close(fig)


def cargar_modelo():
    """El modelo que usa la web (docs/bot_modelo.json): 3 redes con pesos int8, descuantizados aquí."""
    m = json.load(open(os.path.join(RAIZ, "docs", "bot_modelo.json")))
    D, H, K = m["dim"], m["ocultas"], len(m["intents"])
    deq = lambda o, forma=None: (np.array(o["q"], np.float32) * o["e"]).reshape(forma or (-1,))
    redes = [[deq(r["w1"], (D, H)), deq(r["b1"]), deq(r["w2"], (H, K)), deq(r["b2"])] for r in m["modelos"]]
    return m, redes


def decision_bot_completo(frases):
    """Pasa las frases por docs/asistente.js (el bot de la web). None si no hay Node."""
    if not shutil.which("node"):
        return None
    r = subprocess.run(["node", os.path.join(AQUI, "bot_decision.js"), *frases], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else None


# ----------------------------------------------------------------------------- bot

def bot(frases, mostrar):
    m, redes = cargar_modelo()
    intents = m["intents"]
    vocab = set(m["vocab"])
    print(f"Modelo: {len(redes)} redes · {m['dim']} entradas → {m['ocultas']} ReLU → {len(intents)} intenciones "
          f"(softmax) · pesos int8 · vocabulario de {len(vocab)} palabras")
    completo = decision_bot_completo(frases) or [None] * len(frases)
    resumen = []
    for k, frase in enumerate(frases):
        print("\n" + "─" * 78 + f"\n\033[1mFrase {k + 1}: «{frase}»\033[0m")

        titulo("PASO 1", "Normalizar: minúsculas, sin acentos, números → 0, solo letras")
        s = E.normalizar(frase)
        print(f"   «{frase}» → «{s}»")

        titulo("PASO 2", f"N-gramas de 2 a 4 letras y palabras → hash FNV-1a → {m['dim']} casillas, norma L2")
        p = " " + s + " "
        grams = [p[i:i + n] for n in (2, 3, 4) for i in range(len(p) - n + 1)]
        palabras = s.split()
        print(f"   {len(grams)} n-gramas + {len(palabras)} palabras; ejemplos:")
        for g in (grams[:3] + [grams[len(grams) // 2]] + ["w:" + w for w in palabras[:2]]):
            print(f"     {repr(g):<12} fnv = {E.fnv(g):>10}  → casilla {E.fnv(g) % m['dim']:>4}")
        f = E.caracteristicas(frase)
        x = np.zeros(m["dim"], np.float32)
        for i, v in f.items():
            x[i] = v
        print(f"   vector: {len(f)} casillas distintas de cero de {m['dim']} ({len(f) / m['dim']:.1%}), "
              f"‖x‖ = {np.linalg.norm(x):.3f}")
        conocidas = [w for w in palabras if len(w) > 1]
        frac = (sum(w in vocab for w in conocidas) / len(conocidas)) if conocidas else 0.0
        print(f"   palabras conocidas del entrenamiento: {frac:.0%}" + ("  → la red NO se usa (guarda < 34 %)" if frac < 0.34 else ""))

        titulo("PASO 3", "Capa oculta: h = ReLU(x·W1 + b1), 48 neuronas, en cada una de las 3 redes")
        hs, ps = [], []
        for j, (W1, b1, W2, b2) in enumerate(redes):
            h = np.maximum(x @ W1 + b1, 0)
            z = h @ W2 + b2
            pr = np.exp(z - z.max()); pr /= pr.sum()
            hs.append(h); ps.append(pr)
            top = np.argsort(pr)[::-1][:2]
            print(f"   red {j + 1}: {int((h > 0).sum()):>2}/48 neuronas activas → {intents[top[0]]} {pr[top[0]]:.2f}, "
                  f"{intents[top[1]]} {pr[top[1]]:.2f}")

        titulo("PASO 4", "Softmax y conjunto: se promedian las probabilidades de las 3 redes")
        prom = np.mean(ps, axis=0)
        orden = np.argsort(prom)[::-1]
        for i in orden[:3]:
            print(f"   {intents[i]:<11} {prom[i]:.3f}  " + "█" * int(round(prom[i] * 40)))
        p1 = float(prom[orden[0]])

        titulo("PASO 5", f"Decisión con umbrales: ≥ {UMBRAL} responde · {UMBRAL_DUDA} a {UMBRAL} pide aclarar · < {UMBRAL_DUDA} reglas o «no sé»")
        if frac < 0.34:
            solo_red = "la red no se usa (palabras desconocidas) → reglas o «no sé»"
        elif p1 >= UMBRAL:
            solo_red = f"responde «{intents[orden[0]]}»"
        elif p1 >= UMBRAL_DUDA:
            solo_red = f"pide aclarar: «{intents[orden[0]]}» o «{intents[orden[1]]}»"
        else:
            solo_red = "confianza baja → reglas de palabras clave o «no sé»"
        print(f"   con solo los umbrales: {solo_red}")
        c = completo[k]
        if c:
            d = c["decision"]
            via = f" (vía {d['via']})" if d.get("via") else ""
            qué = {"intent": f"responde «{d.get('intent')}»{via}", "duda": f"pide aclarar entre {d.get('opciones')}",
                   "nada": "no entiende y ofrece temas"}.get(d["tipo"], d["tipo"])
            print(f"   bot completo (docs/asistente.js): {qué}")
            print(f"   respuesta: {c['respuesta']}")
        resumen.append({"frase": frase, "p1": p1, "i1": intents[orden[0]], "frac": frac, "completo": c,
                        "x": x, "f": f, "grams": grams, "hs": hs, "ps": ps, "prom": prom})

    figuras_bot(resumen, intents, mostrar)
    return resumen


def figuras_bot(res, intents, mostrar):
    r0 = res[0]
    # --- Paso 2: el vector disperso
    fig, ax = plt.subplots(1, 2, figsize=(14, 4.2), gridspec_kw={"width_ratios": [0.9, 2]})
    ejemplos = r0["grams"][:4] + r0["grams"][len(r0["grams"]) // 2:len(r0["grams"]) // 2 + 2] + ["w:" + w for w in E.normalizar(r0["frase"]).split()[:3]]
    ax[0].axis("off")
    ax[0].set_title(f"«{E.normalizar(r0['frase'])}»: n-grama → casilla")
    for i, g in enumerate(ejemplos):
        ax[0].text(0.02, 0.9 - i * 0.1, repr(g), fontsize=12, family="monospace", color=NAVY, transform=ax[0].transAxes)
        ax[0].text(0.45, 0.9 - i * 0.1, "→", fontsize=12, color=MUTED, transform=ax[0].transAxes)
        ax[0].text(0.58, 0.9 - i * 0.1, f"casilla {E.fnv(g) % 1024}", fontsize=12, family="monospace",
                   color=GOLD if g.startswith("w:") else BLUE, transform=ax[0].transAxes)
    nz = np.nonzero(r0["x"])[0]
    ax[1].vlines(nz, 0, r0["x"][nz], color=BLUE, lw=1.6)
    ax[1].plot(nz, r0["x"][nz], "o", color=BLUE, ms=3)
    ax[1].set_xlim(-5, 1029); ax[1].set_ylim(0, r0["x"].max() * 1.15)
    ax[1].set_xlabel("casilla (0 a 1023)"); ax[1].set_ylabel("valor (norma L2 = 1)")
    ax[1].set_title(f"Vector de entrada: {len(nz)} de 1024 casillas distintas de cero")
    ax[1].spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    guardar(fig, "bot_paso2_vector.png", mostrar)

    # Para la capa oculta y el softmax se usa, si la hay, una frase de confianza media: ahí se ve el conjunto de 3 redes.
    r0 = next((r for r in res if UMBRAL_DUDA <= r["p1"] < UMBRAL and r["frac"] >= 0.34), res[0])

    # --- Paso 3: capa oculta de las 3 redes
    fig, ax = plt.subplots(figsize=(14, 2.6))
    Hm = np.vstack(r0["hs"])
    im = ax.imshow(Hm, aspect="auto", cmap="YlOrBr")
    ax.set_yticks(range(3)); ax.set_yticklabels([f"red {i + 1} ({int((h > 0).sum())} activas)" for i, h in enumerate(r0["hs"])])
    ax.set_xticks(range(0, 48, 4)); ax.set_xlabel("neurona oculta (48 por red); blanco = 0 tras la ReLU")
    ax.set_title(f"«{r0['frase']}» · capa oculta: h = ReLU(x · W1 + b1)")
    plt.colorbar(im, ax=ax, fraction=0.02, pad=0.01)
    fig.tight_layout()
    guardar(fig, "bot_paso3_oculta.png", mostrar)

    # --- Paso 4: softmax por red y promedio
    fig, ax = plt.subplots(figsize=(13, 4.6))
    orden = np.argsort(r0["prom"])[::-1][:8]
    yy = np.arange(len(orden))
    ax.barh(yy, r0["prom"][orden], color=[GOLD] + [LIGHT] * (len(orden) - 1), height=0.6, label="promedio de las 3 redes")
    for j, (pr, mk) in enumerate(zip(r0["ps"], ("o", "s", "^"))):
        ax.plot(pr[orden], yy, mk, color=NAVY, ms=6, mfc="none", mew=1.5, label=f"red {j + 1}")
    ax.axvline(UMBRAL, color=GREEN, ls="--", lw=1.5); ax.axvline(UMBRAL_DUDA, color=RED, ls="--", lw=1.5)
    ax.text(UMBRAL, len(orden) - 0.4, f" responde ≥ {UMBRAL}", color=GREEN, fontsize=10)
    ax.text(UMBRAL_DUDA, len(orden) - 0.4, f" duda ≥ {UMBRAL_DUDA}", color=RED, fontsize=10, ha="right")
    ax.set_yticks(yy); ax.set_yticklabels([intents[i] for i in orden]); ax.invert_yaxis()
    ax.set_xlim(0, 1.02); ax.set_xlabel("probabilidad (softmax)")
    ax.set_title(f"«{r0['frase']}» → 8 intenciones más probables de 21")
    ax.legend(frameon=False, loc="lower right", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    guardar(fig, "bot_paso4_softmax.png", mostrar)

    # --- Paso 5: decisión de cada frase sobre las bandas de umbral
    fig, ax = plt.subplots(figsize=(13, 0.75 * len(res) + 1.4))
    ax.axvspan(0, UMBRAL_DUDA, color="#FBE3E4"); ax.axvspan(UMBRAL_DUDA, UMBRAL, color="#FDF1D6"); ax.axvspan(UMBRAL, 1, color="#E2F2E7")
    for x0, t in ((UMBRAL_DUDA / 2, "reglas o «no sé»"), ((UMBRAL + UMBRAL_DUDA) / 2, "pide aclarar"), ((1 + UMBRAL) / 2, "responde")):
        ax.text(x0, -0.75, t, ha="center", va="center", fontsize=11, color=MUTED, fontweight="bold")
    for i, r in enumerate(res):
        guarda = r["frac"] < 0.34
        ax.plot(r["p1"], i, "o", ms=11, color=MUTED if guarda else NAVY)
        c = r["completo"]
        d = c["decision"] if c else {}
        fin = {"intent": f"→ {d.get('intent')} ({d.get('via')})", "duda": f"→ ¿{' o '.join(d.get('opciones', []))}?",
               "nada": "→ no entiende"}.get(d.get("tipo"), "")
        if guarda:
            fin = "→ guarda: palabras desconocidas, la red no se usa"
        ax.text(0.005, i, f"«{r['frase']}»", va="center", fontsize=11, color=NAVY)
        ax.text(min(r["p1"] + 0.02, 0.62) if r["p1"] < 0.6 else r["p1"] - 0.02, i + 0.32,
                f"{r['i1']} {r['p1']:.2f}  {fin}", fontsize=10, color=NAVY, ha="left" if r["p1"] < 0.6 else "right")
    ax.set_ylim(len(res) - 0.4, -1.2); ax.set_xlim(0, 1)
    ax.set_yticks([]); ax.set_xlabel("probabilidad de la intención más probable (promedio de 3 redes)")
    ax.set_title("Decisión: la misma red, tres conductas según la confianza")
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    fig.tight_layout()
    guardar(fig, "bot_paso5_decision.png", mostrar)


# ----------------------------------------------------------------------------- evaluar

def evaluar(mostrar):
    m, redes = cargar_modelo()
    rng = random.Random(7)
    textos, y, clases = E.preparar(E.CIEGO2, False, rng)
    titulo("EVALUAR", f"Conjunto ciego 2: {len(textos)} frases nuevas, 10 por intención ({len(clases)} intenciones)")
    t = time.perf_counter()
    P = E.predecir_ens(redes, E.matriz(textos))
    print(f"   predicción de las {len(textos)} frases en {1000 * (time.perf_counter() - t):.0f} ms")
    pred = P.argmax(1)
    acc = float((pred == y).mean())
    print(f"   exactitud de la red sola (top-1): {int((pred == y).sum())}/{len(y)} = {acc:.1%}")
    por = {c: float((pred[y == i] == i).mean()) for i, c in enumerate(clases)}
    for c, a in sorted(por.items(), key=lambda kv: kv[1]):
        print(f"     {c:<10} {a:.0%}")
    print("   compromiso responder / acertar según el umbral:")
    conf = P.max(1)
    umbrales = np.linspace(0, 0.95, 20)
    cobertura, precision = [], []
    for u in umbrales:
        us = conf >= u
        cobertura.append(float(us.mean())); precision.append(float((pred[us] == y[us]).mean()) if us.any() else np.nan)
    for u in (0.0, 0.4, 0.6, 0.8):
        us = conf >= u
        print(f"     umbral {u:.1f}: responde {us.mean():.0%}, acierta {float((pred[us] == y[us]).mean()):.0%} de lo que responde")
    if shutil.which("node"):
        print("   bot completo (node tests/evaluar_ciego2.js):")
        out = subprocess.run(["node", os.path.join(RAIZ, "tests", "evaluar_ciego2.js")], capture_output=True, text=True).stdout
        for linea in out.splitlines()[1:5]:
            print("    " + linea)

    # Matriz de confusión: filas = las 16 intenciones del conjunto; columnas = esas 16 más las otras que la red llegó a predecir
    K = len(clases)
    cols = list(range(K)) + sorted({int(c) for c in pred if c >= K})
    etiquetas = [m["intents"][c] for c in cols]
    M = np.zeros((K, len(cols)), int)
    for a, b in zip(y, pred):
        M[a, cols.index(int(b))] += 1
    fig, ax = plt.subplots(figsize=(8.8, 7.2))
    im = ax.imshow(M, cmap="Blues", vmin=0, vmax=10)
    for i in range(K):
        for j in range(len(cols)):
            if M[i, j]:
                ax.text(j, i, M[i, j], ha="center", va="center", fontsize=9,
                        color="white" if M[i, j] > 5 else (RED if i != j else NAVY), fontweight="bold")
    if len(cols) > K:
        ax.axvline(K - 0.5, color=MUTED, lw=1, ls=":")
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(etiquetas, rotation=60, ha="right", fontsize=9)
    ax.set_yticks(range(K)); ax.set_yticklabels(clases, fontsize=9)
    ax.set_xlabel("intención predicha (a la derecha de la línea: intenciones que no están en este conjunto)")
    ax.set_ylabel("intención real")
    ax.set_title(f"Matriz de confusión · {int((pred == y).sum())}/{len(y)} = {acc:.1%}")
    fig.tight_layout()
    guardar(fig, "eval_matriz_confusion.png", mostrar)

    # Exactitud por intención + cobertura/precisión
    fig, ax = plt.subplots(1, 2, figsize=(14, 4.6), gridspec_kw={"width_ratios": [1.2, 1]})
    orden = sorted(clases, key=lambda c: por[c])
    ax[0].barh(orden, [por[c] for c in orden], color=[RED if por[c] < 0.7 else (GOLD if por[c] < 1 else NAVY) for c in orden])
    for i, c in enumerate(orden):
        ax[0].text(por[c] + 0.01, i, f"{por[c]:.0%}", va="center", fontsize=9, color=NAVY)
    ax[0].set_xlim(0, 1.12); ax[0].set_xlabel("exactitud (10 frases por intención)")
    ax[0].set_title("Exactitud por intención")
    ax[0].spines[["top", "right"]].set_visible(False)
    ax[1].plot(umbrales, cobertura, "-o", color=BLUE, ms=4, label="responde (cobertura)")
    ax[1].plot(umbrales, precision, "-o", color=GOLD, ms=4, label="acierta de lo que responde")
    for u, col in ((UMBRAL_DUDA, RED), (UMBRAL, GREEN)):
        ax[1].axvline(u, color=col, ls="--", lw=1.2)
    ax[1].set_ylim(0, 1.05); ax[1].set_xlabel("umbral de confianza"); ax[1].set_ylabel("fracción de las 160 frases")
    ax[1].set_title("Abstenerse cuesta cobertura y gana precisión")
    ax[1].legend(frameon=False, loc="lower left")
    ax[1].spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    guardar(fig, "eval_intencion_umbral.png", mostrar)


# ----------------------------------------------------------------------------- curvas

def entrenar_con_registro(X, y, k, Xt, yt, epocas=80, lr=0.01, l2=1e-4, dropout=0.2, lote=64):
    """El mismo bucle que entrenamiento/entrenar.py (función entrenar), más el registro de pérdida y exactitud."""
    rng = np.random.default_rng(E.SEMILLA)
    D, H = X.shape[1], E.OCULTAS
    W1 = rng.normal(0, 0.1, (D, H)).astype(np.float32); b1 = np.zeros(H, np.float32)
    W2 = rng.normal(0, 0.1, (H, k)).astype(np.float32); b2 = np.zeros(k, np.float32)
    P = [W1, b1, W2, b2]; m = [np.zeros_like(p) for p in P]; v = [np.zeros_like(p) for p in P]
    t, hist = 0, []
    perdida = lambda Xa, ya: float(-np.log(E.predecir(P, Xa)[np.arange(len(ya)), ya] + 1e-12).mean())
    exact = lambda Xa, ya: float((E.predecir(P, Xa).argmax(1) == ya).mean())
    for ep in range(epocas):
        orden = rng.permutation(len(X))
        for i in range(0, len(X), lote):
            idx = orden[i:i + lote]; xb, yb = X[idx], y[idx]
            h = np.maximum(xb @ P[0] + P[1], 0)
            mascara = (rng.random(h.shape) > dropout) / (1 - dropout)
            hd = h * mascara
            p = E.softmax(hd @ P[2] + P[3])
            g = p.copy(); g[np.arange(len(yb)), yb] -= 1; g /= len(yb)
            gW2 = hd.T @ g + l2 * P[2]; gb2 = g.sum(0)
            gh = (g @ P[2].T) * mascara * (h > 0)
            gW1 = xb.T @ gh + l2 * P[0]; gb1 = gh.sum(0)
            t += 1
            for j, gr in enumerate((gW1, gb1, gW2, gb2)):
                m[j] = 0.9 * m[j] + 0.1 * gr; v[j] = 0.999 * v[j] + 0.001 * gr * gr
                P[j] -= lr * (m[j] / (1 - 0.9 ** t)) / (np.sqrt(v[j] / (1 - 0.999 ** t)) + 1e-8)
        hist.append((ep + 1, perdida(X, y), exact(X, y), perdida(Xt, yt), exact(Xt, yt)))
        if (ep + 1) in (1, 5, 10, 20, 40, 80):
            print(f"   época {ep + 1:>2}: pérdida {hist[-1][1]:.3f} / {hist[-1][3]:.3f} · exactitud {hist[-1][2]:.1%} / {hist[-1][4]:.1%}  (entrenamiento / prueba)")
    return np.array(hist)


def curvas(mostrar):
    titulo("CURVAS", "Reentrenar UNA red (semilla 7) con el bucle del proyecto y registrar cada época")
    E.configurar(1024, 48, False, 7)
    rng = random.Random(7)
    textos, y, clases = E.preparar(E.TRAIN, True, rng)
    tt, ty, _ = E.preparar(E.TEST, False, rng)
    X, Xt = E.matriz(textos), E.matriz(tt)
    print(f"   {len(textos)} frases de entrenamiento (con aumento de datos) · {len(tt)} de prueba · {len(clases)} intenciones")
    t = time.perf_counter()
    h = entrenar_con_registro(X, y, len(clases), Xt, ty)
    print(f"   80 épocas en {time.perf_counter() - t:.1f} s")
    fig, ax = plt.subplots(1, 2, figsize=(14, 4.4))
    ax[0].plot(h[:, 0], h[:, 1], color=NAVY, lw=2, label="entrenamiento")
    ax[0].plot(h[:, 0], h[:, 3], color=GOLD, lw=2, label="prueba")
    ax[0].set_xlabel("época"); ax[0].set_ylabel("entropía cruzada"); ax[0].set_title("Pérdida")
    ax[1].plot(h[:, 0], h[:, 2], color=NAVY, lw=2, label="entrenamiento")
    ax[1].plot(h[:, 0], h[:, 4], color=GOLD, lw=2, label="prueba")
    ax[1].set_ylim(0, 1.08); ax[1].set_xlabel("época"); ax[1].set_ylabel("exactitud"); ax[1].set_title("Exactitud")
    for a in ax:
        a.legend(frameon=False); a.spines[["top", "right"]].set_visible(False)
    ax[1].annotate(f"{h[-1, 2]:.1%}", (80, h[-1, 2]), xytext=(-40, 6), textcoords="offset points", color=NAVY)
    ax[1].annotate(f"{h[-1, 4]:.1%}", (80, h[-1, 4]), xytext=(-40, -18), textcoords="offset points", color="#8A5A00")
    fig.tight_layout()
    guardar(fig, "curvas_entrenamiento.png", mostrar)


# ----------------------------------------------------------------------------- motor

def motor(mostrar):
    sys.path.insert(0, os.path.join(RAIZ, "presentacion"))
    import glob
    import tifffile
    import demo_pipeline as DP
    from stayvertical.barrido import Base, parches_de_tesela, puntuar_sitio, sitio_desde_dem

    titulo("MOTOR", "Recuperar (8 rasgos) y reordenar (forma) contra 50 imágenes de prueba de la Tierra")
    rutas = sorted(glob.glob(os.path.join(RAIZ, "data", "resultados", "tierra_*.tif")))
    imgs = [(DP.nombre_imagen(r), tifffile.imread(r).astype(float)) for r in rutas]
    X, centros, origen = [], [], []
    for k, (_, Hk) in enumerate(imgs):
        Xk, ck, _, _ = parches_de_tesela(Hk, DP.RES_M, DP.TAM, solape=0.5)
        X.append(Xk); centros.append(ck); origen += [k] * len(Xk)
    X, centros, origen = np.vstack(X), np.vstack(centros), np.array(origen)
    base = Base(X)
    T = DP.TAM

    def relieve_de(i):
        ci, cj = centros[i]
        return imgs[origen[i]][1][ci - T // 2:ci - T // 2 + T, cj - T // 2:cj - T // 2 + T]

    print(f"   base: {len(X)} ventanas (candidatos) de {len(imgs)} imágenes")
    sitios = ["haworth", "malapert", "degerlache", "nobile", "cabeus", "shackleton", "faustini", "shoemaker"]
    filas = {}
    for s in sitios:
        sitio = sitio_desde_dem(DP.cargar_sitio(s), DP.RES_M, T)
        filas[s] = puntuar_sitio(base, sitio, relieve_de, candidatos=150)

    # Recuperar vs reordenar (Malapert)
    f = filas["malapert"]
    d_rank = {r["indice"]: k for k, r in enumerate(sorted(f, key=lambda r: r["dist_fisica"]))}
    top = f[:5]
    print("   Malapert: puesto por distancia (recuperar) → puesto final (reordenar):")
    for k, r in enumerate(top, 1):
        print(f"     final #{k}: {imgs[origen[r['indice']]][0]:<14} era #{d_rank[r['indice']] + 1:>3} por distancia, r = {r['corr']:.2f}")

    # Sensibilidad al peso
    pesos = np.round(np.linspace(0, 1, 11), 2)
    ganador = {}
    for s in sitios:
        sitio = sitio_desde_dem(DP.cargar_sitio(s), DP.RES_M, T)
        for w in pesos:
            fs = puntuar_sitio(base, sitio, relieve_de, candidatos=150, peso_fisico=float(w))
            ganador[(s, w)] = (fs[0]["indice"], fs[0]["score"], fs[1]["score"] - fs[0]["score"])
    cambia = [sum(ganador[(s, w)][0] != ganador[(s, 0.5)][0] for s in sitios) for w in pesos]
    print("   ¿cambia el primero respecto al peso 0,5?")
    for w in (0.0, 0.2, 0.3, 0.7, 0.8, 1.0):
        i = list(pesos).index(w)
        print(f"     peso físico {w:.1f}: cambia en {cambia[i]} de {len(sitios)} sitios")
    brechas = [ganador[(s, 0.5)][2] for s in sitios]
    print(f"   brecha entre 1.º y 2.º con peso 0,5: mediana {np.median(brechas):.4f} (menos de 0,01 en {sum(b < 0.01 for b in brechas)} de {len(sitios)})")

    fig, ax = plt.subplots(1, 2, figsize=(14, 4.6))
    xs = [d_rank[r["indice"]] + 1 for r in f]
    ys = [r["corr"] for r in f]
    sc = ax[0].scatter(xs, ys, c=[r["score"] for r in f], cmap="viridis_r", s=22)
    for k, r in enumerate(top, 1):
        ax[0].scatter(d_rank[r["indice"]] + 1, r["corr"], s=180, facecolors="none", edgecolors=GOLD, linewidths=2)
        ax[0].annotate(f"#{k}", (d_rank[r["indice"]] + 1, r["corr"]), xytext=(6, 6), textcoords="offset points", color=NAVY, fontweight="bold")
    plt.colorbar(sc, ax=ax[0], fraction=0.046, pad=0.03).set_label("puntaje final (menor es mejor)")
    ax[0].set_xlabel("puesto por distancia en 8 rasgos (etapa 1: recuperar)")
    ax[0].set_ylabel("correlación de forma r (etapa 2)")
    ax[0].set_title("Malapert: el reordenador cambia el orden de los 150 finalistas")
    ax[0].spines[["top", "right"]].set_visible(False)
    ax[1].bar(pesos, cambia, width=0.07, color=[GOLD if w == 0.5 else NAVY for w in pesos])
    ax[1].set_xticks(pesos); ax[1].set_xticklabels([f"{w:.1f}" for w in pesos])
    ax[1].set_xlabel("peso del término físico en el puntaje (el proyecto usa 0,5)")
    ax[1].set_ylabel(f"sitios cuyo 1.º cambia (de {len(sitios)})")
    ax[1].set_ylim(0, len(sitios)); ax[1].set_title("Sensibilidad del ganador al peso")
    ax[1].text(0.5, 0.15, "referencia", ha="center", va="bottom", color="#8A5A00", fontsize=10, fontweight="bold")
    ax[1].spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    guardar(fig, "motor_reordenar_peso.png", mostrar)


# ----------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modo", choices=["bot", "evaluar", "curvas", "motor"])
    ap.add_argument("frases", nargs="*", help="frases para `bot` (por defecto, cinco de ejemplo)")
    ap.add_argument("--mostrar", action="store_true", help="abrir cada figura en una ventana")
    a = ap.parse_args()
    print("\033[1mStay Vertical · demostración de IA 2\033[0m")
    t0 = time.perf_counter()
    if a.modo == "bot":
        bot(a.frases or FRASES_DEMO, a.mostrar)
    elif a.modo == "evaluar":
        evaluar(a.mostrar)
    elif a.modo == "curvas":
        curvas(a.mostrar)
    else:
        motor(a.mostrar)
    print(f"\nTotal: {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
