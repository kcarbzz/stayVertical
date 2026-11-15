"""Pone una versión nueva (?v=...) a los scripts y estilos de docs/index.html para que el navegador no use copias viejas.
Úsalo cada vez que cambies archivos de docs/:  python3 scripts/subir_version.py
"""
import os, re, time
ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "index.html")
v = time.strftime("%Y%m%d-%H%M%S")
h = open(ruta, encoding="utf-8").read()
nuevo, n = re.subn(r'((?:src|href)="(?:style\.css|i18n\.js|clima\.js|analogia\.js|polar\.js|bot_nn\.js|asistente\.js|app\.js))(?:\?v=[^"]*)?"', rf'\1?v={v}"', h)
open(ruta, "w", encoding="utf-8").write(nuevo)
print(f"versión {v} aplicada a {n} archivos en docs/index.html")
