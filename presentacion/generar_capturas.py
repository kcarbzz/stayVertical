"""Capturas del código real para la presentación.

Lee las líneas tal como están en el repositorio, las colorea con Pygments y las dibuja con su número de línea.
Las líneas muy largas se parten (la continuación no lleva número). Las líneas marcadas se resaltan.

  python presentacion/generar_capturas.py      → presentacion/salida/codigo_*.png
"""

import os

from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import PythonLexer
from pygments.token import Token

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "presentacion", "salida")

FONDO, FONDO_HL, NUM, TEXTO = (15, 24, 48), (36, 50, 92), (95, 110, 150), (233, 238, 251)
TITULO = (232, 177, 58)
COLORES = [
    (Token.Comment, (125, 140, 175)),
    (Token.Literal.String, (152, 214, 164)),
    (Token.Literal.Number, (247, 160, 114)),
    (Token.Keyword, (232, 177, 58)),
    (Token.Name.Builtin, (130, 190, 255)),
    (Token.Name.Function, (130, 190, 255)),
    (Token.Name.Class, (130, 190, 255)),
    (Token.Operator, (200, 210, 235)),
]

CAPTURAS = {
    # nombre: (archivo, tramos de líneas [(primera, última), ...], líneas resaltadas)
    # Entre dos tramos se dibuja «⋮» (líneas omitidas, normalmente un docstring).
    "preproceso": ("stayvertical/features.py", [(22, 32)], [25, 30, 31, 32]),
    "descriptores": ("stayvertical/features.py", [(35, 35), (41, 47), (50, 60)], [41, 42, 43, 45, 46, 47, 59, 60]),
    "ventanas": ("stayvertical/features.py", [(100, 100), (108, 129)], [109, 110, 113, 114, 115, 120, 123, 126]),
    "vector8": ("stayvertical/features.py", [(67, 67), (72, 76)], [73, 74, 75]),
    "normalizar": ("stayvertical/search.py", [(12, 18), (20, 20), (23, 23)], [14, 15, 16, 23]),
    "distancias": ("stayvertical/barrido.py", [(134, 136)], [136]),
    "sin_plano": ("stayvertical/barrido.py", [(74, 74), (76, 85), (88, 88), (90, 95)], [80, 81, 82, 83, 91, 92, 93]),
    "ncc": ("stayvertical/barrido.py", [(98, 98), (104, 121)], [104, 107, 110, 114, 115, 118]),
    "puntaje": ("stayvertical/barrido.py", [(150, 150), (164, 175)], [164, 165, 167, 168, 174], 78),
}


def color(tipo):
    for t, c in COLORES:
        if tipo in t:
            return c
    return TEXTO


def partir(tokens, ancho):
    """Parte una línea de tokens en filas de como mucho `ancho` caracteres, con sangría en la continuación."""
    filas, fila, n = [], [], 0
    sangria = 0
    texto = "".join(v for _, v in tokens)
    sangria = len(texto) - len(texto.lstrip()) + 4
    for tipo, valor in tokens:
        while valor:
            libre = ancho - n
            if len(valor) <= libre:
                fila.append((tipo, valor)); n += len(valor); valor = ""
            else:
                corte = valor[:libre]
                esp = corte.rfind(" ")
                if esp > 0:                                 # partir en un espacio si se puede
                    corte = corte[:esp + 1]
                elif n > sangria and len(valor) < ancho // 2:
                    corte = ""                              # pasar el token entero a la fila siguiente
                if corte:
                    fila.append((tipo, corte))
                filas.append(fila)
                fila, n = [(Token.Text, " " * sangria)], sangria
                valor = valor[len(corte):].lstrip(" ") if corte else valor
    filas.append(fila)
    return filas


def _fuente(negrita, tam):
    """JetBrains Mono si está instalada; si no, la DejaVu Sans Mono que trae matplotlib."""
    nombre = "JetBrainsMono-Bold.ttf" if negrita else "JetBrainsMono-Regular.ttf"
    for ruta in (f"/usr/share/fonts/truetype/jetbrains-mono/{nombre}", nombre):
        try:
            return ImageFont.truetype(ruta, tam)
        except OSError:
            pass
    import matplotlib
    alt = "DejaVuSansMono-Bold.ttf" if negrita else "DejaVuSansMono.ttf"
    return ImageFont.truetype(os.path.join(matplotlib.get_data_path(), "fonts", "ttf", alt), tam)


def tokens_por_linea(texto):
    """Colorea el archivo entero (así los docstrings de varias líneas salen bien) y lo parte por líneas."""
    lineas, actual = [], []
    for tipo, valor in lex(texto, PythonLexer()):
        partes = valor.split("\n")
        for k, parte in enumerate(partes):
            if parte:
                actual.append((tipo, parte))
            if k < len(partes) - 1:
                lineas.append(actual); actual = []
    lineas.append(actual)
    return lineas


def captura(nombre, archivo, tramos, resaltar, ancho=88, tam=30):
    with open(os.path.join(RAIZ, archivo), encoding="utf-8") as f:
        todas = tokens_por_linea(f.read())
    fuente = _fuente(False, tam)
    negrita = _fuente(True, tam)
    cw = fuente.getbbox("M")[2]
    lh = int(tam * 1.5)
    filas = []                                              # (número o None, tokens, resaltada)
    for t, (ini, fin) in enumerate(tramos):
        if t > 0:
            filas.append(("⋮", [], False))
        for num in range(ini, fin + 1):
            for m, fila in enumerate(partir(todas[num - 1], ancho)):
                filas.append((num if m == 0 else None, fila, num in resaltar))
    ini, fin = tramos[0][0], tramos[-1][1]
    usado = max(sum(len(v) for _, v in f) for _, f, _ in filas if f)
    pad, gutter, cab = 36, 5 * cw, int(tam * 2.2)
    W = pad * 2 + gutter + cw * max(usado, 40)
    H = cab + pad + lh * len(filas) + pad // 2
    img = Image.new("RGB", (W, H), FONDO)
    d = ImageDraw.Draw(img)
    for c, x in zip([(229, 72, 77), (232, 177, 58), (90, 190, 120)], range(3)):
        d.ellipse((pad + x * 30, cab // 2 - 9, pad + x * 30 + 18, cab // 2 + 9), fill=c)
    d.text((pad + 110, cab // 2), f"{archivo}  ·  líneas {ini}–{fin}", font=negrita, fill=TITULO, anchor="lm")
    y = cab + pad // 2
    for num, fila, hl in filas:
        if hl:
            d.rectangle((0, y - 4, W, y + lh - 4), fill=FONDO_HL)
        if num == "⋮":
            d.text((pad + gutter - 2 * cw, y), "⋮", font=fuente, fill=NUM, anchor="ra")
        elif num is not None:
            d.text((pad + gutter - 2 * cw, y), f"{num:>3}", font=fuente, fill=TITULO if hl else NUM, anchor="ra")
        x = pad + gutter
        for tipo, valor in fila:
            d.text((x, y), valor, font=fuente, fill=color(tipo))
            x += cw * len(valor)
        y += lh
    os.makedirs(SALIDA, exist_ok=True)
    ruta = os.path.join(SALIDA, f"codigo_{nombre}.png")
    img.save(ruta)
    print(f"{os.path.relpath(ruta, RAIZ)}  {W}×{H}")


if __name__ == "__main__":
    for n, (a, tramos, r, *ancho) in CAPTURAS.items():
        captura(n, a, tramos, r, *ancho)
