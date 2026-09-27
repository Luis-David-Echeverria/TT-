"""
CUANTO MARGEN HAY, Y HACE FALTA MULTIOBJETIVO DE VERDAD?

Tres preguntas que hay que contestar ANTES de elegir algoritmo, porque cada una
puede cancelar la siguiente:

  1. Cuanto cuesta una evaluacion, desglosado. Fija el presupuesto de busqueda.
  2. Cuanto mejor que el azar se puede llegar optimizando UN objetivo. Si el
     margen es del 2 %, no hay tesis que defender con metaheuristicas.
  3. Al optimizar f1 a solas, que le pasa a f2 (y al reves). Con objetivos
     independientes lo esperado es que el otro se quede donde estaba, y eso es
     exactamente lo que justifica el multiobjetivo.

La busqueda de aqui es deliberadamente simple -- (mu+lambda) con mutacion
gaussiana -- porque no se esta comparando algoritmos todavia: se esta midiendo
si el PROBLEMA tiene margen. Un algoritmo mejor solo puede mejorar estas cifras,
asi que sirven de cota inferior del margen disponible.

MANEJO DE RESTRICCIONES: reglas de factibilidad de Deb (1) factible gana a
infactible, (2) entre infactibles gana el de menor violacion, (3) entre
factibles gana el de mejor objetivo. NO se rechaza por muestreo: un infactible
puede ser padre de un factible, y filtrarlo mata esa ruta.
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
import fluido as F            # noqa: E402
import geometria as G         # noqa: E402
import muestreo as MU         # noqa: E402
import parametros as P        # noqa: E402
from recinto import Colocacion, POR_CLAVE, cuantizar, recinto_ejemplo  # noqa: E402

T_MAX = 600.0
_W = {}


# =============================================================================
# evaluacion: TODAS las metricas de un golpe
# =============================================================================
def evaluar(rec, layout, aforo):
    """f1, f2 y violacion en una sola pasada.

    Se calculan las dos aunque se optimice una: el costo extra es el de f1, que
    es la barata, y a cambio se ve gratis que le pasa al objetivo que NO se esta
    optimizando. Sin eso, medir el efecto cruzado costaria el doble.
    """
    t0 = time.perf_counter()
    viol = G.evaluar(rec, layout, corto=False)["violacion"]
    t1 = time.perf_counter()

    libre, _ = G.zona_ocupable(rec, layout)
    if not libre.any():
        return {"f1": np.inf, "t_des": T_MAX, "t95": T_MAX, "E": np.inf,
                "viol": np.inf, "ms_geo": 0, "ms_f1": 0, "ms_f2": 0}

    v1 = A.f1(rec, layout, libre)
    t2 = time.perf_counter()

    M0 = np.where(libre, aforo / libre.sum(), 0.0)
    r = F.simular(rec, layout, aforo, dt=P.DT, t_max=T_MAX, n_cuadros=3,
                  M0=M0, refresco=P.REFRESCO_CAMPO)
    t3 = time.perf_counter()

    return {"f1": float(v1) if np.isfinite(v1) else 1e6,
            "t_des": r["t_des"] or T_MAX,
            "t95": r["t95"] or T_MAX,
            "E": r["exposicion"], "viol": float(viol),
            "ms_geo": 1e3 * (t1 - t0), "ms_f1": 1e3 * (t2 - t1),
            "ms_f2": 1e3 * (t3 - t2)}


def _init(aforo):
    _W["rec"] = recinto_ejemplo(h=P.H_CELDA)
    _W["aforo"] = aforo


def _ev(layout):
    return evaluar(_W["rec"], layout, _W["aforo"])


# =============================================================================
# busqueda de un solo objetivo con reglas de factibilidad
# =============================================================================
def mejor_que(a, b, clave):
    """Reglas de Deb (2000). a domina a b?"""
    fa, fb = a["viol"] <= 0, b["viol"] <= 0
    if fa != fb:
        return fa
    if not fa:
        return a["viol"] < b["viol"]
    return a[clave] < b[clave]


def muta(layout, rec, rng, sigma):
    """Desplaza, gira o reubica. SIN rechazo: lo infactible sigue vivo."""
    nuevo = [Colocacion(c.tipo, c.x, c.y, c.rot) for c in layout]
    for _ in range(int(rng.integers(1, 3))):
        k = int(rng.integers(len(nuevo)))
        c = nuevo[k]
        if rng.random() < 0.20:
            c.rot = 1 - c.rot
        t = POR_CLAVE[c.tipo]
        w, f = (t.ancho, t.fondo) if c.rot == 0 else (t.fondo, t.ancho)
        if rng.random() < 0.08:            # salto largo: escapa de minimos locales
            c.x = cuantizar(rng.uniform(0, rec.W - w))
            c.y = cuantizar(rng.uniform(0, rec.H - f))
        else:
            c.x = cuantizar(np.clip(c.x + rng.normal(0, sigma), 0, rec.W - w))
            c.y = cuantizar(np.clip(c.y + rng.normal(0, sigma), 0, rec.H - f))
    return nuevo


def buscar(pool, rec, semillas, clave, rng, mu=8, lam=24, gens=40, sigma0=10.0):
    pob = [{"lay": s, **m} for s, m in
           zip(semillas[:mu], pool.map(_ev, semillas[:mu]))]
    pob.sort(key=lambda z: (z["viol"] > 0, z["viol"], z[clave]))
    hist = [dict(pob[0])]
    evals = len(pob)

    for g in range(gens):
        sigma = sigma0 * (1.0 - 0.8 * g / max(1, gens - 1))
        hijos = [muta(pob[int(rng.integers(len(pob)))]["lay"], rec, rng, sigma)
                 for _ in range(lam)]
        for h, m in zip(hijos, pool.map(_ev, hijos)):
            pob.append({"lay": h, **m})
        evals += lam
        pob.sort(key=lambda z: (z["viol"] > 0, z["viol"], z[clave]))
        pob = pob[:mu]
        hist.append(dict(pob[0]))
    return pob[0], hist, evals


# =============================================================================
def main(aforo, gens, semilla):
    rec = recinto_ejemplo(h=P.H_CELDA)
    rng = np.random.default_rng(semilla)
    lays, _ = MU.muestra(rec, 400, semilla=semilla, modo="amplio")
    lays = [l for _, l in lays]
    print("recinto %gx%g  aforo %d  semilla %d" % (rec.W, rec.H, aforo, semilla))

    with ProcessPoolExecutor(initializer=_init, initargs=(aforo,)) as pool:
        # ---------------------------------------------- 1. costo por evaluacion
        t0 = time.perf_counter()
        base = list(pool.map(_ev, lays[:120]))
        wall = time.perf_counter() - t0
        g_ms = np.mean([b["ms_geo"] for b in base])
        f1_ms = np.mean([b["ms_f1"] for b in base])
        f2_ms = np.mean([b["ms_f2"] for b in base])
        tot = g_ms + f1_ms + f2_ms
        print("\n[1] COSTO DE UNA EVALUACION (media de 120)")
        print("    capa geometrica  %7.1f ms  %4.1f %%" % (g_ms, 100 * g_ms / tot))
        print("    f1 acceso        %7.1f ms  %4.1f %%" % (f1_ms, 100 * f1_ms / tot))
        print("    f2 evacuacion    %7.1f ms  %4.1f %%" % (f2_ms, 100 * f2_ms / tot))
        print("    serial total     %7.1f ms" % tot)
        print("    en paralelo      %7.1f ms/layout  (%d procesos, %.0fx)"
              % (1e3 * wall / 120, os.cpu_count(), tot / (1e3 * wall / 120)))
        print("    -> con 10 000 evaluaciones: %.1f min en paralelo"
              % (10000 * wall / 120 / 60))

        # ---------------------------------------------------- 2. linea base
        fac = [b for b in base if b["viol"] <= 0]
        print("\n[2] LINEA BASE: 120 layouts al azar (%d factibles)" % len(fac))
        for k, u in (("f1", "m"), ("t_des", "s"), ("E", "m2s")):
            v = np.array([b[k] for b in base])
            print("    %-6s mediana %9.2f %-4s  mejor %9.2f   peor %9.2f"
                  % (k, np.median(v), u, v.min(), v.max()))

        # ------------------------------------ 3. optimizar cada uno a solas
        res = {}
        for clave in ("f1", "E"):
            t0 = time.perf_counter()
            mejor, hist, ev = buscar(pool, rec, lays, clave,
                                     np.random.default_rng(semilla + 7),
                                     gens=gens)
            res[clave] = (mejor, hist, ev, time.perf_counter() - t0)

    # ------------------------------------------------------------- informe
    med = {k: float(np.median([b[k] for b in base])) for k in ("f1", "t_des", "E")}
    mej = {k: float(np.min([b[k] for b in base])) for k in ("f1", "t_des", "E")}
    print("\n[3] OPTIMIZANDO UN SOLO OBJETIVO")
    print("    %-22s %12s %12s %12s" % ("", "f1 (m)", "t_des (s)", "E (m2s)"))
    print("    %-22s %12.2f %12.2f %12.0f"
          % ("mediana al azar", med["f1"], med["t_des"], med["E"]))
    print("    %-22s %12.2f %12.2f %12.0f"
          % ("mejor de 120 al azar", mej["f1"], mej["t_des"], mej["E"]))
    for clave, (m, hist, ev, seg) in res.items():
        print("    %-22s %12.2f %12.2f %12.0f   (%d evals, %.0f s)"
              % ("optimizando " + clave, m["f1"], m["t_des"], m["E"], ev, seg))

    print("\n[4] MARGEN Y EFECTO CRUZADO")
    for clave in res:
        m = res[clave][0]
        gan = 100 * (med[clave] - m[clave]) / med[clave]
        print("    optimizando %-3s -> gana %5.1f %% en %s" % (clave, gan, clave))
        for otro in ("f1", "t_des", "E"):
            if otro == clave:
                continue
            d = 100 * (med[otro] - m[otro]) / med[otro]
            pct = 100 * np.mean([b[otro] < m[otro] for b in base])
            print("        %-6s queda en %9.2f  (%+5.1f %% vs mediana, "
                  "percentil %2.0f del azar)" % (otro, m[otro], d, pct))
    print("\n    Percentil ~50 en el objetivo NO optimizado = el algoritmo lo "
          "dejo donde\n    estaba el azar. Eso es lo que predice la "
          "independencia, y es\n    exactamente el argumento a favor del "
          "multiobjetivo.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--aforo", type=int, default=2000)
    ap.add_argument("--gens", type=int, default=40)
    ap.add_argument("--semilla", type=int, default=11)
    a = ap.parse_args()
    main(a.aforo, a.gens, a.semilla)
