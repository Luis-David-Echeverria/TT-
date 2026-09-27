"""
EXPORTA EL INFORME COMO SITIO ESTATICO.

Deja en sitio/ una carpeta que se publica sin backend: el informe con sus
ecuaciones, las graficas, los frentes y las nubes completas.

NO LLEVA SIMULACIONES PRECALCULADAS, Y ESO ES LO BUENO. La simulacion es
DETERMINISTA: dado el layout y las constantes, el resultado esta fijado, no hay
nada aleatorio que guardar. El navegador la calcula en ~300 ms con el mismo
modelo (ui/src/modelo/), asi que se puede abrir CUALQUIERA de los layouts en
vez de los 84 que alcanzaban a caber precalculados. El sitio paso de 36 MB a
poco mas de 2.

Lo unico que el navegador NO reproduce es E (exposicion): cuenta celdas que
cruzan un umbral de densidad y una diferencia de milesimas hace saltar el
conteo. No es objetivo del experimento -- la densidad alta ya se castiga sola
en el tiempo, porque por Weidmann ahi se camina mas lento -- asi que se muestra
el valor que midio Python, que viaja con cada punto.

El acuerdo entre los dos motores esta medido en experimentos/validar_js.py.
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "nucleo"))
sys.path.insert(0, RAIZ)

import acceso as AC          # noqa: E402
import almacen as AL         # noqa: E402
import campos as C           # noqa: E402
import fluido as F           # noqa: E402
import geometria as G        # noqa: E402
import parametros as P       # noqa: E402
import recinto as R          # noqa: E402
from api import resultados as RS   # noqa: E402
from api import servicio as S      # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SITIO = os.path.join(RAIZ, "sitio")
N_CUADROS = 30       # suficiente para leer la animacion sin inflar el sitio


def escribe(rel, obj):
    ruta = os.path.join(SITIO, rel)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    return os.path.getsize(ruta)


def main(solo_datos=False):
    t0 = time.perf_counter()
    if os.path.isdir(os.path.join(SITIO, "datos")):
        shutil.rmtree(os.path.join(SITIO, "datos"))
    peso = {"datos": 0, "detalle": 0}

    # ------------------------------------------------------------ catalogo
    peso["datos"] += escribe("datos/catalogo.json", S.catalogo())

    # ------------------------------------------------ escenarios y nubes
    esc = [e for e in RS.escenarios()
           if e["cfg"].get("f1_metodo") == "transporte-coordenadas"]
    peso["datos"] += escribe("datos/escenarios.json", esc)
    print("escenarios: %d (solo los del solver vigente)" % len(esc))

    rec = R.recinto_ejemplo(h=P.H_CELDA)

    for e in esc:
        n = RS.nube(config=e["config"])

        # El layout de cada punto va DENTRO de la nube, no en un archivo propio.
        # Con un archivo por punto salian 1 776 archivos de 4 KB: pesan poco
        # pero hacen lentisima la subida y ensucian el repositorio. Metidos en
        # la nube son 6 archivos y un solo viaje de red por escenario.
        fichas = {}
        for f in AL.consultar(config=e["config"]):
            if f["f1"] is None:
                continue
            fichas[f["llave"]] = RS.layout(f["llave"])
        una = next(iter(fichas.values()), None)
        n["recinto"] = una["recinto"] if una else None
        for punto in n["puntos"]:
            d = fichas.get(punto["llave"])
            if d:
                punto["layout"] = d["layout"]
                punto["f1_detalle"] = d["f1_detalle"]
                punto["violacion"] = d["metricas"].get("violacion")
        peso["datos"] += escribe("datos/nube/%s.json" % e["config"], n)

        print("  %-9s aforo %-5d  %d puntos" % (e["modo"], e["aforo"], n["n"]))

    # ------------------------------------------- los dos frentes trazados
    for nombre, archivo in (("frente", "frente_epsilon.json"),
                            ("pesos", "barrido_pesos.json")):
        ruta = os.path.join(RAIZ, "datos", archivo)
        if not os.path.exists(ruta):
            print("  FALTA datos/%s — corre su experimento antes" % archivo)
            continue
        with open(ruta, encoding="utf-8") as f:
            d = json.load(f)
        peso["datos"] += escribe("datos/%s.json" % nombre, d)

        # Cada solucion de los barridos recibe una llave y su ficha, para que
        # se pueda abrir desde las tablas. La animacion la calcula el navegador.
        puntos = d.get("frente") or d.get("soluciones") or []
        for i, x in enumerate(puntos):
            lay = [R.Colocacion(c["tipo"], c["x"], c["y"], c["rot"])
                   for c in x["layout"]]
            llave = "%s-%d" % (nombre, i)
            x["llave"] = llave
            cfg = d.get("cfg", {})
            cfg = dict(cfg, aforo=d.get("aforo"))
            ge = G.evaluar(rec, lay, corto=False)
            peso["datos"] += escribe("datos/layout/%s.json" % llave, {
                "llave": llave, "recinto": d["recinto"], "layout": x["layout"],
                "cfg": cfg, "modo": nombre, "semilla": d.get("semilla"),
                "i": i, "factible": ge["factible"],
                "metricas": {"f1": x["acceso"], "t_des": x["t_evac"],
                             "violacion": ge["violacion"]},
                "f1_detalle": {},
            })
        escribe("datos/%s.json" % nombre, d)   # reescribe con las llaves
        print("  %s: %d soluciones" % (nombre, len(puntos)))

    escribe("datos/indice.json", {
        "generado": time.strftime("%Y-%m-%d %H:%M"),
        "calculo": "en el navegador",
    })

    # ------------------------------------------------------ compilar la UI
    if not solo_datos:
        print("\ncompilando la interfaz en modo estatico…")
        env = dict(os.environ, VITE_ESTATICO="1")
        r = subprocess.run(["npm", "run", "build:sitio"], cwd=os.path.join(RAIZ, "ui"),
                           env=env, shell=True, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout[-2000:])
            print(r.stderr[-2000:])
            raise SystemExit("falló la compilación")
        print("  listo")

    # ------------------------------------------------ archivos de hosting
    # .nojekyll: GitHub Pages pasa el sitio por Jekyll, que ignora las carpetas
    # que empiezan con guion bajo y a veces reescribe rutas. Este archivo lo
    # desactiva. En otros hostings no estorba.
    pathlib.Path(os.path.join(SITIO, ".nojekyll")).write_text("", encoding="utf-8")

    # Cache: el bundle lleva hash en el nombre, asi que puede cachearse para
    # siempre. Los datos NO llevan hash, asi que se revalidan; sin esto, al
    # regenerar el informe la gente seguiria viendo los numeros viejos.
    with open(os.path.join(SITIO, "_headers"), "w", encoding="utf-8") as f:
        f.write("/assets/*\n"
                "  Cache-Control: public, max-age=31536000, immutable\n"
                "\n"
                "/datos/*\n"
                "  Cache-Control: public, max-age=0, must-revalidate\n")

    with open(os.path.join(SITIO, "netlify.toml"), "w", encoding="utf-8") as f:
        f.write('[build]\n  publish = "."\n\n'
                '[[headers]]\n  for = "/assets/*"\n'
                '  [headers.values]\n'
                '    Cache-Control = "public, max-age=31536000, immutable"\n\n'
                '[[headers]]\n  for = "/datos/*"\n'
                '  [headers.values]\n'
                '    Cache-Control = "public, max-age=0, must-revalidate"\n')

    # titulo propio: el del simulador no describe lo que es esto
    idx = os.path.join(SITIO, "index.html")
    if os.path.exists(idx):
        h = pathlib.Path(idx).read_text(encoding="utf-8")
        h = re.sub(r"<title>.*?</title>",
                   "<title>¿Es multiobjetivo? — acceso vs evacuación</title>", h)
        if "<meta name=\"description\"" not in h:
            h = h.replace("</title>",
                          "</title>\n<meta name=\"description\" content=\"Informe del "
                          "experimento: accesibilidad a las áreas de servicio contra tiempo "
                          "de evacuación en eventos masivos. TT, ESCOM-IPN.\">")
        pathlib.Path(idx).write_text(h, encoding="utf-8")

    with open(os.path.join(SITIO, "LEEME.md"), "w", encoding="utf-8") as f:
        f.write(
            "# Informe publicado\n\n"
            "Sitio estatico. No necesita servidor ni instalar nada.\n\n"
            "- **Verlo aqui:** `py -3.12 -m http.server 8080` dentro de esta carpeta,\n"
            "  y abrir http://localhost:8080\n"
            "- **Publicarlo:** subir esta carpeta tal cual a GitHub Pages, Netlify,\n"
            "  Vercel o Cloudflare Pages. No hay paso de compilacion.\n\n"
            "No abras `index.html` con doble clic: el navegador bloquea la lectura\n"
            "de los JSON con el protocolo `file://`. Hace falta servirlo por HTTP,\n"
            "aunque sea el servidor de una linea de arriba.\n\n"
            "Se regenera con:\n\n"
            "    py -3.12 experimentos/exportar_sitio.py\n")

    total = 0
    for base, _, archivos in os.walk(SITIO):
        for a in archivos:
            total += os.path.getsize(os.path.join(base, a))
    print("\n" + "=" * 60)
    print("SITIO LISTO en  sitio/")
    print("  datos del informe   %6.1f MB en %d archivos"
          % (peso["datos"] / 1e6, sum(len(a) for _, _, a in os.walk(SITIO))))
    print("  TOTAL               %6.1f MB" % (total / 1e6))
    print("  animaciones: las calcula el navegador, ~300 ms por layout")
    print("  %.0f s" % (time.perf_counter() - t0))
    print("\n  Verlo aquí:   cd sitio && py -3.12 -m http.server 8080")
    print("  Publicarlo:   arrastra la carpeta sitio/ a app.netlify.com/drop")
    print("                (lo más rápido: da un link al instante, sin cuenta)")
    print("                o súbela a GitHub Pages / Vercel / Cloudflare Pages.")
    print("\n  OJO: no sirve abrir index.html con doble clic — el navegador")
    print("  bloquea leer los JSON por file://. Tiene que ir por HTTP.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-datos", action="store_true",
                    help="no recompila la interfaz")
    a = ap.parse_args()
    main(a.solo_datos)
