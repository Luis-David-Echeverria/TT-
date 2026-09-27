"""
EL EXPERIMENTO: 100 layouts factibles al azar, tiempo de evacuacion contra
accesibilidad.

    accesibilidad          f1, por asignacion capacitada (transporte exacto)
    tiempo de evacuacion   t_des, de la simulacion de fluido

Es todo. No se optimiza nada: se mira si las dos medidas se relacionan, para
saber si el problema es candidato a multiobjetivo y con eso justificar (o no)
usar NSGA-II mas adelante.

Los layouts son FACTIBLES: pasan la capa geometrica completa. Es la poblacion
sobre la que de verdad trabajaria la herramienta.
"""
import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy.stats import spearmanr, pearsonr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "nucleo"))

import acceso as A            # noqa: E402
import fluido as F            # noqa: E402
import geometria as G         # noqa: E402
import muestreo as MU         # noqa: E402
import parametros as P        # noqa: E402
from recinto import recinto_ejemplo  # noqa: E402

T_MAX = 600.0
_W = {}


def _init(aforo):
    _W["rec"] = recinto_ejemplo(h=P.H_CELDA)
    _W["aforo"] = aforo


def _ev(layout):
    rec, aforo = _W["rec"], _W["aforo"]
    libre, _ = G.zona_ocupable(rec, layout)
    acc = A.f1(rec, layout, libre)
    M0 = np.where(libre, aforo / libre.sum(), 0.0)
    r = F.simular(rec, layout, aforo, dt=P.DT, t_max=T_MAX, n_cuadros=3,
                  M0=M0, refresco=P.REFRESCO_CAMPO)
    return {"acceso": float(acc), "t_evac": r["t_des"] or T_MAX}


def frente_pareto(a, b):
    """Indices no dominados minimizando las dos columnas."""
    o = np.lexsort((b, a))
    fr, mejor = [], np.inf
    for i in o:
        if b[i] < mejor - 1e-12:
            fr.append(int(i))
            mejor = b[i]
    return np.array(fr)


def bootstrap(x, y, n=4000, semilla=0):
    rng = np.random.default_rng(semilla)
    m = len(x)
    r = [spearmanr(x[s], y[s]).statistic
         for s in (rng.integers(0, m, m) for _ in range(n))]
    r = np.array([v for v in r if np.isfinite(v)])
    return float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


def main(n, aforo, semilla):
    rec = recinto_ejemplo(h=P.H_CELDA)
    lays, fallos = MU.muestra(rec, n, semilla=semilla, modo="estricto")
    lays = [l for _, l in lays]

    print("=" * 70)
    print("ACCESIBILIDAD  vs  TIEMPO DE EVACUACION")
    print("=" * 70)
    print("  %d layouts factibles al azar (%d fallos de generacion)"
          % (len(lays), fallos))
    print("  recinto %gx%g m, %d salidas, aforo %d personas"
          % (rec.W, rec.H, len(rec.salidas), aforo))
    print("  h=%.1f m  dt=%.1f s  k_c=%d  p=%.1f  semilla=%d"
          % (P.H_CELDA, P.DT, P.REFRESCO_CAMPO, P.EXP_REPARTO, semilla))

    t0 = time.perf_counter()
    with ProcessPoolExecutor(initializer=_init, initargs=(aforo,)) as pool:
        res = list(pool.map(_ev, lays))
    acc = np.array([r["acceso"] for r in res])
    tev = np.array([r["t_evac"] for r in res])
    print("  %d evaluaciones en %.0f s" % (len(res), time.perf_counter() - t0))

    # ------------------------------------------------------------ 1. varian?
    print("\n[1] ¿VARIA CADA UNA?  (si una es constante, no hay nada que correlacionar)")
    print("    %-24s %9s %9s %9s %9s"
          % ("", "media", "desv", "CV", "min-max"))
    for nom, v, u in (("accesibilidad f1", acc, "m"),
                      ("tiempo de evacuacion", tev, "s")):
        print("    %-24s %9.2f %9.2f %8.1f%% %9s"
              % (nom + " [" + u + "]", v.mean(), v.std(),
                 100 * v.std() / v.mean(), "%.1f-%.1f" % (v.min(), v.max())))

    # ------------------------------------------------------- 2. correlacion
    rho = spearmanr(acc, tev).statistic
    lo, hi = bootstrap(acc, tev)
    r_p = pearsonr(acc, tev).statistic
    print("\n[2] ¿SE RELACIONAN?")
    print("    Spearman (orden)   rho = %+.3f   IC 95%% [%+.3f, %+.3f]"
          % (rho, lo, hi))
    print("    Pearson  (lineal)  r   = %+.3f" % r_p)
    print("    error tipico esperado por el tamano de muestra: +-%.3f"
          % (1 / np.sqrt(len(acc) - 1)))
    if lo <= 0 <= hi:
        print("\n    -> EL INTERVALO CRUZA CERO: no se detecta relacion.")
        print("       Las dos medidas son INDEPENDIENTES: saber que un layout")
        print("       es bueno en una NO dice nada de la otra.")
    elif rho < 0:
        print("\n    -> RELACION NEGATIVA: hay conflicto. Mejorar una empeora la otra.")
    else:
        print("\n    -> RELACION POSITIVA: van juntas.")
        if rho > 0.7:
            print("       Tan juntas que una sobra: bastaria optimizar una sola.")

    # ----------------------------------------------------------- 3. frente
    fr = frente_pareto(acc, tev)
    esperado = float(np.sum(1.0 / np.arange(1, len(acc) + 1)))
    print("\n[3] EL FRENTE DE PARETO  (minimizando las dos)")
    print("    no dominados: %d de %d" % (len(fr), len(acc)))
    print("    si fueran independientes se esperarian: %.1f" % esperado)
    print("    (es el numero armonico H_n ~ ln n + 0.577; con dos objetivos")
    print("     independientes ese es el numero esperado de no dominados)")
    print()
    print("    %-10s %-16s %-16s" % ("", "accesibilidad", "t evacuacion"))
    o = fr[np.argsort(acc[fr])]
    for i in o:
        print("    %-10s %-16.2f %-16.1f" % ("", acc[i], tev[i]))
    if len(fr) > 2:
        print("\n    rho SOBRE EL FRENTE: %+.3f" % spearmanr(acc[fr], tev[fr]).statistic)
        recorre_a = 100 * (acc[fr].max() - acc[fr].min()) / acc[fr].min()
        recorre_t = 100 * (tev[fr].max() - tev[fr].min()) / tev[fr].min()
        print("    el frente recorre %.1f %% en accesibilidad y %.1f %% en tiempo"
              % (recorre_a, recorre_t))

    # --------------------------------------------------------- 4. veredicto
    print("\n" + "=" * 70)
    print("VEREDICTO")
    print("=" * 70)
    if rho > 0.7:
        print("  NO es candidato a multiobjetivo: las dos medidas van tan juntas")
        print("  que optimizar una ya optimiza la otra.")
    elif lo <= 0 <= hi:
        print("  SI es candidato a multiobjetivo, por INDEPENDENCIA.")
        print()
        print("  No estan en conflicto, pero tampoco se puede deducir una de la")
        print("  otra: optimizar solo la accesibilidad dejaria el tiempo de")
        print("  evacuacion donde lo ponga el azar. Un metodo multiobjetivo")
        print("  (NSGA-II) queda justificado porque hay que perseguir las dos.")
        print()
        print("  OJO con el tamano del frente: si coincide con %.1f, la nube se"
              % esperado)
        print("  comporta como dos objetivos sin relacion. Que el frente sea")
        print("  chico NO invalida el multiobjetivo -- es lo que la independencia")
        print("  predice para una muestra AL AZAR.")
    else:
        print("  SI es candidato a multiobjetivo, por CONFLICTO (rho = %+.3f)." % rho)
        print("  No existe un layout que sea el mejor en las dos cosas.")

    return acc, tev, fr


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=100)
    ap.add_argument("--aforo", type=int, default=2000)
    ap.add_argument("--semilla", type=int, default=0)
    a = ap.parse_args()
    main(a.n, a.aforo, a.semilla)
