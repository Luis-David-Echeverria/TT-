"""
¿El motor de JavaScript dice lo mismo que el de Python?

El informe publicado no lleva simulaciones precalculadas: las calcula el
navegador. Eso solo se sostiene si el motor del navegador coincide con el de
Python, que es la fuente de verdad. Si divergen y nadie lo comprueba, no hay
forma de saber cuál creer -- y el informe estaria mostrando numeros que no son
los que se midieron.

Las dos implementaciones NO son identicas por dentro y no tienen por que serlo:

    Eikonal     Python usa fast marching (scikit-fmm, cola de prioridad);
                JS usa barrido rapido. Misma ecuacion, mismo estencil de
                Godunov, distinto orden de recorrido.
    Godunov     mismo algoritmo, portado; Python lo compila con Numba.
    transporte  mismo descenso por coordenadas.

Lo que hay que medir no es que den el mismo numero hasta el ultimo decimal,
sino que ORDENEN IGUAL los layouts: es lo unico que usa quien lee el informe
para comparar distribuciones. Por eso el criterio es la correlacion de rangos,
y se reporta ademas la diferencia relativa para saber cuanto se desvian.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

import numpy as np
from scipy.stats import spearmanr

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "nucleo"))
sys.path.insert(0, RAIZ)

import acceso as AC          # noqa: E402
import fluido as F           # noqa: E402
import geometria as G        # noqa: E402
import muestreo as MU        # noqa: E402
import parametros as P       # noqa: E402
import recinto as R          # noqa: E402
from api import servicio as S    # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

T_MAX = 600.0


def _rects(m):
    out = []
    ny, nx = m.shape
    for y in range(ny):
        x = 0
        while x < nx:
            if not m[y, x]:
                x += 1
                continue
            x0 = x
            while x < nx and m[y, x]:
                x += 1
            out.append({"x": int(x0), "y": int(y), "w": int(x - x0), "h": 1})
    return out


def main(n, aforo):
    rec = R.recinto_ejemplo(h=P.H_CELDA)
    lays, _ = MU.muestra(rec, n, semilla=0, modo="estricto")
    lays = [l for _, l in lays]
    cat = S.catalogo()

    params = {
        "h": P.H_CELDA, "dt": P.DT, "k_c": P.REFRESCO_CAMPO, "p": P.EXP_REPARTO,
        "t_max": T_MAX, "eps": P.EPS_VACIADO, "v0": P.V0, "rho_max": P.RHO_MAX,
        "gamma": P.GAMMA, "rho_c": P.RHO_PERDIDA_CONTROL, "J_s": P.J_ESPECIFICO,
        "capa_limite": P.CAPA_LIMITE, "sigma_k": P.SIGMA_KERNEL,
        "w_min": P.ANCHO_LIBRE_MIN, "sigma": AC.SATURACION,
        "servicio": {k: {"unidades": v["unidades"]} for k, v in AC.SERVICIO.items()},
    }
    entrada = {
        "recinto": {"W": rec.W, "H": rec.H, "muros": _rects(rec.muros),
                    "salidas": [{"nombre": s.nombre, "lado": s.lado,
                                 "centro": s.centro, "ancho": s.ancho}
                                for s in rec.salidas]},
        "catalogo": {"areas": cat["areas"]},
        "P": params,
        "casos": [{"i": i, "aforo": aforo,
                   "layout": [{"tipo": c.tipo, "x": c.x, "y": c.y, "rot": c.rot}
                              for c in lay]}
                  for i, lay in enumerate(lays)],
    }

    print("VALIDACION DEL MOTOR DE JAVASCRIPT")
    print("  %d layouts, aforo %d, dt=%.1f k_c=%d p=%.1f"
          % (len(lays), aforo, P.DT, P.REFRESCO_CAMPO, P.EXP_REPARTO))

    tmp = tempfile.mkdtemp()
    fin = os.path.join(tmp, "entrada.json")
    fout = os.path.join(tmp, "salida.json")
    with open(fin, "w", encoding="utf-8") as f:
        json.dump(entrada, f)

    print("\n  corriendo el motor de JavaScript…", end="", flush=True)
    t0 = time.perf_counter()
    r = subprocess.run(["node", "validar.mjs", fin, fout],
                       cwd=os.path.join(RAIZ, "ui"), capture_output=True, text=True)
    if r.returncode != 0:
        print("\n" + (r.stderr or r.stdout)[-3000:])
        raise SystemExit("el motor de JavaScript fallo")
    t_js = time.perf_counter() - t0
    with open(fout, encoding="utf-8") as f:
        js = json.load(f)
    print(" %.0f s (%.0f ms/layout)" % (t_js, 1000 * t_js / len(lays)))

    print("  corriendo el motor de Python…", end="", flush=True)
    t0 = time.perf_counter()
    py = []
    for i, lay in enumerate(lays):
        libre, _ = G.zona_ocupable(rec, lay)
        acc = AC.f1(rec, lay, libre)
        M0 = np.where(libre, aforo / libre.sum(), 0.0)
        sim = F.simular(rec, lay, aforo, dt=P.DT, t_max=T_MAX, n_cuadros=4,
                        M0=M0, refresco=P.REFRESCO_CAMPO)
        py.append({"celdas_libres": int(libre.sum()), "f1": float(acc),
                   "t_des": sim["t_des"], "t95": sim["t95"],
                   "exposicion": sim["exposicion"], "rho_pico": sim["rho_pico"]})
    t_py = time.perf_counter() - t0
    print(" %.0f s (%.0f ms/layout)" % (t_py, 1000 * t_py / len(lays)))

    # ------------------------------------------------------------- comparar
    #
    # El criterio NO puede ser solo la correlacion de rangos. Hay metricas que
    # casi no varian entre layouts -- rho_pico se mueve un 1-3 % porque siempre
    # hay atasco frente a las puertas -- y ahi el orden lo decide el ruido, asi
    # que un rho bajo no dice que los motores discrepen.
    #
    # Lo que de verdad importa es si la diferencia ENTRE MOTORES es chica frente
    # a la diferencia ENTRE LAYOUTS. Si lo es, el navegador puede comparar
    # layouts sin cambiar las conclusiones; si no, no puede.
    print()
    print("  %-16s %9s %11s %11s %9s  %s"
          % ("metrica", "rho", "dif motores", "entre layouts", "razon", "veredicto"))
    filas = []
    for clave, nom in (("celdas_libres", "celdas libres"), ("f1", "f1 acceso"),
                       ("t_des", "t evacuacion"), ("t95", "t95"),
                       ("exposicion", "E exposicion"), ("rho_pico", "rho pico")):
        a = np.array([x[clave] if x[clave] is not None else np.nan for x in py], float)
        b = np.array([x[clave] if x[clave] is not None else np.nan for x in js], float)
        ok = np.isfinite(a) & np.isfinite(b)
        if ok.sum() < 3:
            print("  %-16s   sin datos suficientes" % nom)
            continue
        rho = spearmanr(a[ok], b[ok]).statistic if len(np.unique(a[ok])) > 2 else 1.0
        dif = float(np.abs(b[ok] - a[ok]).mean())            # entre motores
        spread = float(np.abs(a[ok] - a[ok].mean()).mean())  # entre layouts
        razon = dif / spread if spread > 1e-12 else np.inf
        # Menos de un tercio: el ruido entre motores no alcanza a cambiar el
        # orden salvo entre layouts practicamente empatados.
        bien = razon < 0.33
        filas.append((nom, bien, razon))
        print("  %-16s %9.4f %11.3f %11.3f %8.2f  %s"
              % (nom, rho, dif, spread, razon,
                 "SIRVE" if bien else "no reproducible"))

    print()
    print("  'dif motores' es la diferencia media entre JavaScript y Python.")
    print("  'entre layouts' es cuanto se separan los layouts entre si en Python.")
    print("  La razon entre las dos es lo que decide: por debajo de 0.33 el")
    print("  desacuerdo entre motores es menor que un tercio de la senal que hay")
    print("  que distinguir, y el navegador puede comparar layouts.")

    print("\n" + "=" * 70)
    clave_ok = [n for n, b, _ in filas if b]
    clave_no = [n for n, b, _ in filas if not b]
    print("  REPRODUCIBLE EN EL NAVEGADOR: " + ", ".join(clave_ok))
    if clave_no:
        print("  NO REPRODUCIBLE: " + ", ".join(clave_no))
        print()
        print("  Para esas, el informe debe mostrar el valor que calculo Python")
        print("  -- que ya viene guardado con cada layout -- y no el del navegador.")
        print("  E cuenta celdas que cruzan un umbral (rho > rho_c), asi que una")
        print("  diferencia de milesimas en la densidad hace saltar el conteo.")
    todo_ok = not clave_no
    return todo_ok


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--aforo", type=int, default=2000)
    a = ap.parse_args()
    main(a.n, a.aforo)
