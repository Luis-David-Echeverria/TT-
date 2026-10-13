"""
COSTO POR EVALUACION: cuanto tarda el ciclo del algoritmo en evaluar un layout.

Mide las tres piezas que el optimizador llama por cada candidato, en el orden
en que las llama (experimentos/potencial.py: evaluar):

    capa geometrica (G1-G6)  ->  f1 (transporte capacitado)  ->  f2 (simulacion)

y el costo por evaluacion cuando una generacion se reparte entre procesos, que
es como corre el optimizador (nucleo/optimizar.py: optimizar_par). Con eso se
dimensiona el presupuesto: cuantas evaluaciones caben en cuanto tiempo.

    py -3.12 experimentos/costo_evaluacion.py [--n 48] [--procesos 0]

Escribe datos/costo_evaluacion.json.
"""
import argparse
import json
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "nucleo"))
sys.path.insert(0, os.path.join(RAIZ, "experimentos"))

import muestreo as MU          # noqa: E402
import parametros as P         # noqa: E402
import potencial as PO         # noqa: E402
from recinto import recinto_ejemplo   # noqa: E402

AFORO = 2000


def main(n, procesos, semilla):
    rec = recinto_ejemplo(h=P.H_CELDA)
    lays = [l for _, l in MU.muestra(rec, n, semilla=semilla, modo="estricto")[0]]
    PO.evaluar(rec, lays[0], AFORO)          # primera llamada: compila el kernel (numba)

    t0 = time.perf_counter()
    ms = [PO.evaluar(rec, l, AFORO) for l in lays]
    serie = 1000 * (time.perf_counter() - t0) / len(lays)
    partes = {k: float(np.mean([m[k] for m in ms])) for k in ("ms_geo", "ms_f1", "ms_f2")}

    n_proc = procesos or max(1, (os.cpu_count() or 2))
    with ProcessPoolExecutor(max_workers=n_proc, initializer=PO._init, initargs=(AFORO,)) as pool:
        list(pool.map(PO._ev, lays[:n_proc]))                 # calentar cada proceso
        t0 = time.perf_counter()
        list(pool.map(PO._ev, lays))
        paralelo = 1000 * (time.perf_counter() - t0) / len(lays)

    total = sum(partes.values())
    print("%d layouts validos, aforo %d, %s" % (len(lays), AFORO, platform.processor() or platform.machine()))
    print("\n  pieza                 ms      %")
    for k, nombre in (("ms_geo", "capa geometrica"), ("ms_f1", "f1 acceso"), ("ms_f2", "f2 evacuacion")):
        print("  %-18s %7.1f  %5.1f" % (nombre, partes[k], 100 * partes[k] / total))
    print("  %-18s %7.1f" % ("en serie", serie))
    print("  %-18s %7.1f   (%d procesos)" % ("en paralelo", paralelo, n_proc))
    print("\n  presupuesto        tiempo")
    for evals in (2448, 10000, 25000):
        print("  %6d evaluaciones  %5.1f min" % (evals, evals * paralelo / 60000))

    salida = {"fecha": time.strftime("%Y-%m-%d"), "n": len(lays), "aforo": AFORO,
              "procesos": n_proc, "ms_por_pieza": partes, "ms_serie": serie,
              "ms_paralelo": paralelo, "maquina": platform.processor() or platform.machine()}
    with open(os.path.join(RAIZ, "datos", "costo_evaluacion.json"), "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=48)
    ap.add_argument("--procesos", type=int, default=0)
    ap.add_argument("--semilla", type=int, default=5)
    a = ap.parse_args()
    main(a.n, a.procesos, a.semilla)
