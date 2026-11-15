"""Entrena el clasificador de intenciones de Vertikal Bot y lo exporta a JSON.

Red: texto -> n-gramas de caracteres hasheados (1024) -> capa oculta ReLU (48)
-> softmax (16 intenciones). Solo numpy. Pesos cuantizados a int8.

Uso:  .venv/bin/python entrenamiento/entrenar.py
"""
import json, os, random, re, sys, unicodedata
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from ejemplos import TRAIN, TEST
from ejemplos_extra import EXTRA
from ejemplos_extra2 import EXTRA2
from ejemplos_extra3 import EXTRA3
from ejemplos_extra4 import EXTRA4
from ejemplos_extra5 import EXTRA5
from ejemplos_extra6 import EXTRA6
from ejemplos_extra7 import EXTRA7
from ejemplos_extra8 import EXTRA8
from ejemplos_extra9 import EXTRA9
from ejemplos_ciegos5 import CIEGO5
from ejemplos_ciegos4 import CIEGO4
from ejemplos_ciegos3 import CIEGO3
from ejemplos_ciegos import CIEGO
from ejemplos_ciegos2 import CIEGO2

for _extra in (EXTRA, EXTRA2, EXTRA3, EXTRA4, EXTRA5, EXTRA6, EXTRA7, EXTRA8, EXTRA9):
    for _c, _i in _extra.items():
        for _l, _fr in _i.items():
            TRAIN.setdefault(_c, {}).setdefault(_l, [])
            TRAIN[_c][_l] = TRAIN[_c][_l] + _fr

DIM, OCULTAS, SEMILLA, BIGRAMAS = 1024, 48, 7, False
SEMILLAS_ENSAMBLE = (7, 11, 13)
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "docs", "bot_modelo.json")


def normalizar(s):
    """Debe ser idéntica a la de docs/bot_nn.js."""
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("%", " pct ")
    s = re.sub(r"[0-9]+", " 0 ", s)
    s = re.sub(r"[^a-z ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fnv(texto):
    h = 2166136261
    for b in texto.encode("ascii"):
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def caracteristicas(texto):
    """Devuelve {indice: valor}, L2-normalizado."""
    s = normalizar(texto)
    cont = {}
    p = " " + s + " "
    for n in (2, 3, 4):
        for i in range(len(p) - n + 1):
            k = fnv(p[i:i + n]) % DIM
            cont[k] = cont.get(k, 0) + 1
    ws = s.split()
    for w in ws:
        k = fnv("w:" + w) % DIM
        cont[k] = cont.get(k, 0) + 1
    if BIGRAMAS:
        for a, b in zip(ws, ws[1:]):
            k = fnv("b:" + a + "_" + b) % DIM
            cont[k] = cont.get(k, 0) + 1
    norma = sum(v * v for v in cont.values()) ** 0.5 or 1.0
    return {k: v / norma for k, v in cont.items()}


def matriz(textos):
    X = np.zeros((len(textos), DIM), dtype=np.float32)
    for i, t in enumerate(textos):
        for k, v in caracteristicas(t).items():
            X[i, k] = v
    return X


PREFIJOS = ["oye ", "por favor ", "una duda ", "bot ", "hey ", "please ", "quick question ", "una pregunta "]


def variantes(texto, rng, n=5):
    """Genera versiones con erratas y muletillas, para que no dependa de frases exactas."""
    out = [texto]
    for _ in range(n):
        t = texto
        r = rng.random()
        if r < 0.3 and len(t) > 4:
            i = rng.randrange(len(t)); t = t[:i] + t[i + 1:]
        elif r < 0.55 and len(t) > 4:
            i = rng.randrange(len(t) - 1); t = t[:i] + t[i + 1] + t[i] + t[i + 2:]
        elif r < 0.7:
            i = rng.randrange(len(t)); t = t[:i] + t[i] + t[i:]
        if rng.random() < 0.4:
            t = rng.choice(PREFIJOS) + t
        if rng.random() < 0.3:
            t = t + "?"
        out.append(t)
    return out


def preparar(conjunto, aumentar, rng):
    clases = list(conjunto.keys())
    textos, etiquetas = [], []
    for c, idiomas in conjunto.items():
        for lista in idiomas.values():
            for t in lista:
                for v in (variantes(t, rng) if aumentar else [t]):
                    textos.append(v); etiquetas.append(clases.index(c))
    return textos, np.array(etiquetas), clases


def softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def entrenar(X, y, k, epocas=80, lr=0.01, l2=1e-4, dropout=0.2, lote=64):
    rng = np.random.default_rng(SEMILLA)
    W1 = rng.normal(0, 0.1, (DIM, OCULTAS)).astype(np.float32); b1 = np.zeros(OCULTAS, np.float32)
    W2 = rng.normal(0, 0.1, (OCULTAS, k)).astype(np.float32);  b2 = np.zeros(k, np.float32)
    P = [W1, b1, W2, b2]; m = [np.zeros_like(p) for p in P]; v = [np.zeros_like(p) for p in P]
    t = 0
    for ep in range(epocas):
        orden = rng.permutation(len(X))
        for i in range(0, len(X), lote):
            idx = orden[i:i + lote]; xb, yb = X[idx], y[idx]
            h = np.maximum(xb @ P[0] + P[1], 0)
            mascara = (rng.random(h.shape) > dropout) / (1 - dropout)
            hd = h * mascara
            p = softmax(hd @ P[2] + P[3])
            g = p.copy(); g[np.arange(len(yb)), yb] -= 1; g /= len(yb)
            gW2 = hd.T @ g + l2 * P[2]; gb2 = g.sum(0)
            gh = (g @ P[2].T) * mascara * (h > 0)
            gW1 = xb.T @ gh + l2 * P[0]; gb1 = gh.sum(0)
            t += 1
            for j, gr in enumerate((gW1, gb1, gW2, gb2)):
                m[j] = 0.9 * m[j] + 0.1 * gr; v[j] = 0.999 * v[j] + 0.001 * gr * gr
                P[j] -= lr * (m[j] / (1 - 0.9 ** t)) / (np.sqrt(v[j] / (1 - 0.999 ** t)) + 1e-8)
    return P


def predecir_ens(Pqs, X):
    return np.mean([predecir(Pq, X) for Pq in Pqs], axis=0)


def predecir(P, X):
    return softmax(np.maximum(X @ P[0] + P[1], 0) @ P[2] + P[3])


def cuantizar(a):
    escala = float(np.abs(a).max() / 127) or 1.0
    q = np.clip(np.round(a / escala), -127, 127).astype(np.int8)
    return q, escala


def configurar(dim, ocultas, bigramas, semilla):
    global DIM, OCULTAS, BIGRAMAS, SEMILLA
    DIM, OCULTAS, BIGRAMAS, SEMILLA = dim, ocultas, bigramas, semilla


def experimento():
    """Compara configuraciones SOLO con los conjuntos de desarrollo (prueba y ciego 1). No toca CIEGO2."""
    print("config                      desarrollo (prueba+ciego1), media de 3 semillas")
    for nombre, dim, oc, bi in (("base 1024/48", 1024, 48, False), ("+bigramas 1024/48", 1024, 48, True),
                                ("2048/64", 2048, 64, False), ("+bigramas 2048/64", 2048, 64, True),
                                ("+bigramas 2048/96", 2048, 96, True)):
        accs = []
        for sem in (7, 11, 13):
            configurar(dim, oc, bi, sem)
            rng = random.Random(sem)
            textos, y, clases = preparar(TRAIN, True, rng)
            P = entrenar(matriz(textos), y, len(clases))
            dev = {c: {l: TEST[c][l] + CIEGO[c][l] for l in TEST[c]} for c in TEST}
            tt, ty, _ = preparar(dev, False, rng)
            accs.append(float((predecir(P, matriz(tt)).argmax(1) == ty).mean()))
        print(f"{nombre:<26} {np.mean(accs):.1%}  ({', '.join(f'{a:.1%}' for a in accs)})")


def main(final=False, ciego3=False, ciego4=False, ciego5=False):
    # Conjunto de SEMILLAS_ENSAMBLE redes (semillas fijas, sin elegir las mejores): promediar baja la varianza entre entrenamientos.
    Qs, Pqs = [], []
    for sem in SEMILLAS_ENSAMBLE:
        configurar(DIM, OCULTAS, BIGRAMAS, sem)
        r = random.Random(sem)
        textos, y, clases = preparar(TRAIN, True, r)
        P = entrenar(matriz(textos), y, len(clases))
        Q = [cuantizar(p) for p in P]
        Qs.append(Q); Pqs.append([q.astype(np.float32) * e for q, e in Q])
    rng = random.Random(SEMILLA)
    textos, y, clases = preparar(TRAIN, True, rng)   # mismo orden que la semilla principal (solo para métricas y vocabulario)
    # Se evalúa el conjunto YA cuantizado: es el que usará la web.

    tt, ty, _ = preparar(TEST, False, rng)
    pred = predecir_ens(Pqs, matriz(tt)).argmax(axis=1)
    acc = float((pred == ty).mean())
    entr = float((predecir_ens(Pqs, matriz([t for t in textos[::6]])).argmax(1) == y[::6]).mean())
    print(f"entrenamiento: {len(textos)} frases | precisión (muestra de entrenamiento): {entr:.1%}")
    print(f"PRUEBA (frases nuevas): {len(tt)} | precisión: {acc:.1%}")
    for c in range(len(clases)):
        s = ty == c
        print(f"  {clases[c]:<10} {float((pred[s] == c).mean()):.0%}  ({int(s.sum())})")
    fallos = [(tt[i], clases[ty[i]], clases[pred[i]]) for i in range(len(tt)) if pred[i] != ty[i]]
    for f in fallos: print("  falla:", f)

    # Conjunto ciego: se mide una sola vez con el modelo final.
    bt, by, _ = preparar(CIEGO, False, rng)
    pb = predecir_ens(Pqs, matriz(bt))
    print(f"CIEGO (frases nuevas, no usadas para ajustar nada): {len(bt)} | precisión: {float((pb.argmax(1) == by).mean()):.1%}")
    for u in (0.0, 0.4, 0.5, 0.6, 0.7):
        for nombre, P_, Y_ in (("prueba", predecir_ens(Pqs, matriz(tt)), ty), ("ciego", pb, by)):
            conf = P_.max(1); ok = P_.argmax(1) == Y_; usado = conf >= u
            print(f"  umbral {u:.1f} {nombre:<6}: responde {usado.mean():.0%}, acierta {float(ok[usado].mean()) if usado.any() else 0:.0%} de lo que responde")

    if ciego5:
        b5t, b5y, c5 = preparar(CIEGO5, False, rng)
        p5 = predecir_ens(Pqs, matriz(b5t))
        ok5 = np.array([clases[p5[i].argmax()] == c5[b5y[i]] for i in range(len(b5t))])
        print(f"CIEGO 5 (sitios y zonas, {len(b5t)} frases, evaluadas UNA vez): precisión {float(ok5.mean()):.1%}")
        for k, nombre in enumerate(c5): print(f"  {nombre:<8} {float(ok5[b5y == k].mean()):.0%}")
        for i in range(len(b5t)):
            if not ok5[i]: print("  falla:", (b5t[i], c5[b5y[i]], clases[p5[i].argmax()]))
    if ciego4:
        b4t, b4y, c4 = preparar(CIEGO4, False, rng)
        p4 = predecir_ens(Pqs, matriz(b4t))
        ok4 = np.array([clases[p4[i].argmax()] == c4[b4y[i]] for i in range(len(b4t))])
        print(f"CIEGO 4 (acerca del bot, {len(b4t)} frases, evaluadas UNA vez): precisión {float(ok4.mean()):.1%}")
        for i in range(len(b4t)):
            if not ok4[i]: print("  falla:", (b4t[i], c4[b4y[i]], clases[p4[i].argmax()]))
    if ciego3:
        # CIEGO 3: solo clima y viabilidad (las intenciones nuevas)
        b3t, b3y, c3 = preparar(CIEGO3, False, rng)
        p3 = predecir_ens(Pqs, matriz(b3t)); idx = {c: i for i, c in enumerate(clases)}
        ok3 = np.array([clases[p3[i].argmax()] == c3[b3y[i]] for i in range(len(b3t))])
        print(f"CIEGO 3 (clima y viabilidad, {len(b3t)} frases, evaluadas UNA vez): precisión {float(ok3.mean()):.1%}")
        for k, nombre in enumerate(c3): print(f"  {nombre:<11} {float(ok3[b3y == k].mean()):.0%}")
        for i in range(len(b3t)):
            if not ok3[i]: print("  falla:", (b3t[i], c3[b3y[i]], clases[p3[i].argmax()]))
    if final:
        b2t, b2y, _ = preparar(CIEGO2, False, rng)
        p2 = predecir_ens(Pqs, matriz(b2t))
        print(f"CIEGO 2 (160 frases escritas antes de esta tanda, evaluadas UNA vez): precisión {float((p2.argmax(1) == b2y).mean()):.1%}")
        for u in (0.0, 0.5, 0.6):
            conf = p2.max(1); ok = p2.argmax(1) == b2y; us = conf >= u
            print(f"  umbral {u:.1f}: responde {us.mean():.0%}, acierta {float(ok[us].mean()) if us.any() else 0:.0%} de lo que responde")
        for c in range(len(clases)):
            sel = b2y == c
            print(f"  {clases[c]:<10} {float((p2.argmax(1)[sel] == c).mean()):.0%}")

    vocab = sorted({w for t in textos for w in normalizar(t).split() if len(w) > 1})
    modelo = {"dim": DIM, "ocultas": OCULTAS, "intents": clases, "vocab": vocab,
              "modelos": [{"w1": {"e": Q[0][1], "q": Q[0][0].flatten().tolist()}, "b1": {"e": Q[1][1], "q": Q[1][0].tolist()},
                           "w2": {"e": Q[2][1], "q": Q[2][0].flatten().tolist()}, "b2": {"e": Q[3][1], "q": Q[3][0].tolist()}} for Q in Qs]}
    json.dump(modelo, open(SALIDA, "w"), separators=(",", ":"))
    print("modelo:", SALIDA, f"{os.path.getsize(SALIDA)/1024:.0f} KB")

    # Casos de paridad para comprobar que el JS calcula lo mismo.
    casos = ["¿Qué significa el 71% de parecido?", "hola", "Cuéntame un chiste", "what is the flat fraction?",
             "por qué se parecen Atacama y Haworth", "cómo subo mi zona", "de dónde salen los mapas",
             "texto sin relación alguna xyz", "", "  ¿¿¿???  "]
    paridad = [{"texto": t, "probs": [round(float(x), 5) for x in predecir_ens(Pqs, matriz([t]))[0]]} for t in casos]
    json.dump({"intents": clases, "casos": paridad, "prueba": TEST, "ciego2": CIEGO2},
              open(os.path.join(RAIZ, "entrenamiento", "referencia.json"), "w"), ensure_ascii=False)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--experimento", action="store_true")
    ap.add_argument("--semilla", type=int, default=SEMILLA); ap.add_argument("--dim", type=int, default=DIM); ap.add_argument("--ocultas", type=int, default=OCULTAS)
    ap.add_argument("--bigramas", action="store_true"); ap.add_argument("--ciego3", action="store_true", help="evalúa el conjunto ciego 3 (clima y viabilidad), UNA sola vez")
    ap.add_argument("--ciego4", action="store_true", help="evalúa el conjunto ciego 4 (acerca del bot), UNA sola vez")
    ap.add_argument("--ciego5", action="store_true", help="evalúa el conjunto ciego 5 (sitios y zonas), UNA sola vez")
    ap.add_argument("--final", action="store_true",
                    help="evalúa también el conjunto ciego 2 (hacerlo UNA sola vez)")
    a = ap.parse_args()
    configurar(a.dim, a.ocultas, a.bigramas, a.semilla)
    experimento() if a.experimento else main(a.final, a.ciego3, a.ciego4, a.ciego5)
