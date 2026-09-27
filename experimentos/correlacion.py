"""
BARRIDO PARA LA MATRIZ DE CORRELACION ENTRE f1 Y f2.

Pregunta que contesta: acercar a la gente a los servicios (f1) y desalojar
rapido y sin aplastamientos (f2), son objetivos en conflicto? Si no lo son,
sobra el algoritmo multiobjetivo: basta optimizar uno. Si lo son, hace falta
un frente de Pareto y NSGA-II se justifica solo.

NO SE OPTIMIZA NADA AQUI. Se muestrean layouts, se miden, y se mira como se
relacionan las medidas. Si esto se hiciera con layouts ya optimizados, la
correlacion describiria al optimizador y no al problema.

EJES DEL BARRIDO
  aforo   medido antes: el layout solo separa cuando el recinto NO esta lleno.
          Con reparto uniforme y aforo de diseno, todo se clava en la cota de
          las puertas y no hay nada que correlacionar. Por eso el aforo es un
          eje, no un dato.
  modo    'amplio' es la nube sin recortar; 'estricto' solo lo que aceptaria
          un criterio de proteccion civil. Si las dos matrices coinciden, la
          conclusion aguanta.

Se guarda todo en datos/evaluaciones.db: volver a correr esto no recalcula
nada, y agregar layouts o aforos solo calcula lo que falta.
"""
import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "nucleo"))

import acceso as A            # noqa: E402
import almacen as AL          # noqa: E402
import fluido as F            # noqa: E402
import geometria as G         # noqa: E402
import muestreo as MU         # noqa: E402
import parametros as P        # noqa: E402
from recinto import recinto_ejemplo  # noqa: E402

T_MAX = 600.0                 # 10 min, tope pedido para el experimento


def configuracion(aforo, modo):
    """Todo lo que cambia el resultado. Es la llave de la cache y, a la vez,
    el registro de reproducibilidad del experimento."""
    return {
        "exp": "correlacion-f1-f2", "v": 2,
        "aforo": float(aforo), "modo_muestreo": modo,
        "reparto_inicial": "uniforme",
        "h": P.H_CELDA, "dt": P.DT, "k_c": P.REFRESCO_CAMPO,
        "p": P.EXP_REPARTO, "t_max": T_MAX, "eps": P.EPS_VACIADO,
        "v0": P.V0, "rho_max": P.RHO_MAX, "gamma": P.GAMMA,
        "rho_c": P.RHO_PERDIDA_CONTROL, "J_s": P.J_ESPECIFICO,
        "capa_limite": P.CAPA_LIMITE,
        "f1_metodo": "transporte-coordenadas", "f1_sigma": A.SATURACION,
        "w_min": P.ANCHO_LIBRE_MIN,
    }


def _rects(m):
    """Mascara booleana -> rectangulos, uniendo corridas por fila y columna."""
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
    out.sort(key=lambda r: (r["x"], r["w"], r["y"]))
    fus = []
    for r in out:
        if (fus and fus[-1]["x"] == r["x"] and fus[-1]["w"] == r["w"]
                and fus[-1]["y"] + fus[-1]["h"] == r["y"]):
            fus[-1]["h"] += r["h"]
        else:
            fus.append(dict(r))
    return fus


_REC = None


def _init():
    global _REC
    _REC = recinto_ejemplo(h=P.H_CELDA)


def _medir(args):
    """Un layout: f1, f2 y factibilidad estricta. Corre en el pool."""
    i, layout, aforo = args
    rec = _REC
    t0 = time.perf_counter()

    libre, _ = G.zona_ocupable(rec, layout)
    if not libre.any():
        return i, {"factible": False, "violacion": np.inf, "f1": None}

    # --- f1: accesibilidad ---
    v1, det1 = A.f1(rec, layout, libre, por_tipo=True)

    # --- f2: evacuacion ---
    M0 = np.where(libre, aforo / libre.sum(), 0.0)
    r = F.simular(rec, layout, aforo, dt=P.DT, t_max=T_MAX, n_cuadros=4,
                  M0=M0, refresco=P.REFRESCO_CAMPO)

    # factibilidad de la capa COMPLETA: se guarda para poder mirar despues el
    # subconjunto estricto sin volver a simular
    ge = G.evaluar(rec, layout, corto=False)

    return i, {
        "f1": None if not np.isfinite(v1) else float(v1),
        "t_des": r["t_des"], "t95": r["t95"],
        "exposicion": r["exposicion"], "rho_pico": r["rho_pico"],
        "conservacion": r["conservacion"],
        "evacuado_final": r["evacuado_final"],
        "factible": ge["factible"], "violacion": ge["violacion"],
        "area_util": float(libre.sum()) * rec.area_celda,
        "tope": bool(r["t_des"] is None),
        "f1_detalle": {k: {a: round(b, 5) for a, b in v.items()
                           if isinstance(b, (int, float))}
                       for k, v in det1.items()},
        "ms": (time.perf_counter() - t0) * 1000.0,
    }


def correr(n, aforos, modos, semilla=0, procesos=None):
    rec = recinto_ejemplo(h=P.H_CELDA)
    AL.registrar_caso(rec, "nave-100x60-4salidas",
                      {"W": rec.W, "H": rec.H, "h": rec.h,
                       "salidas": [(s.nombre, s.lado, s.centro, s.ancho)
                                   for s in rec.salidas],
                       # los muros van rasterizados y no como los rects que los
                       # pintaron: es lo que de verdad vio el simulador, y es lo
                       # que la UI debe redibujar para que layout y planta
                       # correspondan
                       "muros": _rects(rec.muros),
                       "conteo": MU.CONTEO})

    for modo in modos:
        lays, fallos = MU.muestra(rec, n, semilla=semilla, modo=modo)
        print("\n=== modo %s: %d/%d layouts generados (%d fallos) ==="
              % (modo, len(lays), n, fallos))

        for aforo in aforos:
            cfg = configuracion(aforo, modo)
            pend, hechos = [], 0
            for i, lay in lays:
                if AL.buscar(rec, lay, cfg) is not None:
                    hechos += 1
                else:
                    pend.append((i, lay, aforo))

            print("  aforo %5d:  %d en cache, %d por calcular"
                  % (aforo, hechos, len(pend)), end="", flush=True)
            if not pend:
                print()
                continue

            t0 = time.perf_counter()
            with ProcessPoolExecutor(max_workers=procesos,
                                     initializer=_init) as ex:
                for k, (i, m) in enumerate(ex.map(_medir, pend, chunksize=2), 1):
                    AL.guardar(rec, dict(lays)[i], cfg, m,
                               modo=modo, semilla=semilla,
                               extra={"i": i, "f1_detalle": m.get("f1_detalle"),
                                      "tope": m.get("tope")})
                    if k % 25 == 0:
                        print(".", end="", flush=True)
            dt = time.perf_counter() - t0
            print("  %.0f s (%.2f s/layout)" % (dt, dt / len(pend)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=300)
    ap.add_argument("--aforos", type=int, nargs="+", default=[2000, 3000, 4000])
    ap.add_argument("--modos", nargs="+", default=["amplio", "estricto"])
    ap.add_argument("--semilla", type=int, default=0)
    ap.add_argument("--procesos", type=int, default=None)
    a = ap.parse_args()

    print("BARRIDO f1 vs f2")
    print("  n=%d  aforos=%s  modos=%s  semilla=%d"
          % (a.n, a.aforos, a.modos, a.semilla))
    print("  dt=%.2f  k_c=%d  p=%.1f  t_max=%.0f s  h=%.1f m"
          % (P.DT, P.REFRESCO_CAMPO, P.EXP_REPARTO, T_MAX, P.H_CELDA))
    t0 = time.perf_counter()
    correr(a.n, a.aforos, a.modos, a.semilla, a.procesos)
    print("\ntotal %.0f s" % (time.perf_counter() - t0))
    print(AL.resumen()["total"], "evaluaciones en", AL.RUTA)
