"""
Rechazar infactibles o dejarlos competir? Medido.

El optimizador actual (nucleo/optimizar.py) repara por MUESTREO POR RECHAZO:
muta hasta 60 veces hasta que la capa geometrica acepta el hijo, y si no lo
logra descarta la mutacion. La alternativa son las reglas de factibilidad de
Deb (2000): el infactible se queda en la poblacion y se ordena primero por
violacion.

El argumento teorico contra el rechazo es que dos padres infactibles pueden dar
un hijo factible, y que el camino mas corto entre dos buenas soluciones puede
pasar por territorio infactible: bloquearlo corta la exploracion. El argumento
a favor es que no gasta simulaciones en basura.

Aqui se mide cual gana con el MISMO presupuesto de evaluaciones, que es la
comparacion honesta -- el rechazo gasta computo en la capa geometrica que no
aparece como 'evaluacion', asi que tambien se reporta el tiempo de reloj.

Se mide ademas algo que el experimento del barrido ya habia insinuado: filtrar
por factibilidad induce correlacion entre objetivos que en la poblacion sin
filtrar no existe. Si eso tambien pasa DENTRO de la busqueda, el rechazo no solo
explora menos: sesga hacia donde el filtro inventa estructura.
"""
import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "nucleo"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import geometria as G         # noqa: E402
import muestreo as MU         # noqa: E402
import parametros as P        # noqa: E402
from recinto import recinto_ejemplo  # noqa: E402
from potencial import _ev, _init, muta   # noqa: E402


def buscar(pool, rec, semillas, clave, rng, modo, mu=8, lam=24, gens=40,
           sigma0=10.0, intentos=60):
    """(mu+lambda). modo='rechazo' o modo='deb'."""
    sem = list(semillas[:mu])
    pob = [{"lay": s, **m} for s, m in zip(sem, pool.map(_ev, sem))]
    orden = (lambda z: (z["viol"] > 0, z["viol"], z[clave]))
    pob.sort(key=orden)
    evals = len(pob)
    rechazadas = 0
    t_geo = 0.0

    for g in range(gens):
        sigma = sigma0 * (1.0 - 0.8 * g / max(1, gens - 1))
        hijos = []
        while len(hijos) < lam:
            padre = pob[int(rng.integers(len(pob)))]["lay"]
            h = muta(padre, rec, rng, sigma)
            if modo == "rechazo":
                t0 = time.perf_counter()
                ok = G.evaluar(rec, h, corto=True)["factible"]
                t_geo += time.perf_counter() - t0
                if not ok:
                    rechazadas += 1
                    if rechazadas % intentos == 0:   # se rinde con ese padre
                        continue
                    continue
            hijos.append(h)
        for h, m in zip(hijos, pool.map(_ev, hijos)):
            pob.append({"lay": h, **m})
        evals += lam
        pob.sort(key=orden)
        pob = pob[:mu]
    fact = [z for z in pob if z["viol"] <= 0]
    return {"mejor": (fact or pob)[0], "evals": evals,
            "rechazadas": rechazadas, "t_geo": t_geo,
            "factibles_en_pob": len(fact)}


def main(aforo, gens, repeticiones):
    rec = recinto_ejemplo(h=P.H_CELDA)
    lays, _ = MU.muestra(rec, 400, semilla=3, modo="amplio")
    lays = [l for _, l in lays]

    print("RECHAZO vs DOMINANCIA RESTRINGIDA")
    print("  mismo presupuesto de evaluaciones, %d repeticiones con semillas "
          "distintas" % repeticiones)
    print("  aforo %d, (8+24) x %d generaciones = %d evaluaciones"
          % (aforo, gens, 8 + 24 * gens))

    with ProcessPoolExecutor(initializer=_init, initargs=(aforo,)) as pool:
        for clave in ("f1", "E"):
            print("\n  objetivo: %s" % clave)
            print("  %-10s %12s %12s %12s %10s %12s"
                  % ("modo", "mejor", "peor de %d" % repeticiones, "mediana",
                     "seg", "mutaciones"))
            for modo in ("rechazo", "deb"):
                vals, segs, rech = [], [], []
                for r in range(repeticiones):
                    t0 = time.perf_counter()
                    out = buscar(pool, rec, lays, clave,
                                 np.random.default_rng(100 + r), modo, gens=gens)
                    segs.append(time.perf_counter() - t0)
                    vals.append(out["mejor"][clave])
                    rech.append(out["rechazadas"])
                v = np.array(vals)
                print("  %-10s %12.2f %12.2f %12.2f %10.0f %12s"
                      % (modo, v.min(), v.max(), np.median(v),
                         np.mean(segs),
                         "%d desechadas" % np.mean(rech) if modo == "rechazo"
                         else "0"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--aforo", type=int, default=2000)
    ap.add_argument("--gens", type=int, default=30)
    ap.add_argument("--rep", type=int, default=3)
    a = ap.parse_args()
    main(a.aforo, a.gens, a.rep)
