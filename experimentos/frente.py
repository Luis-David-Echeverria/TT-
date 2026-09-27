"""
NSGA-II DE INVESTIGACION: como es el frente de verdad, cerca del optimo?

Motivo de este experimento. El barrido de 1 776 layouts AL AZAR dijo que f1 y f2
son independientes, y que t_des y E van juntas (rho +0.26 a +0.49). Pero al
optimizar un objetivo a solas aparecio otra cosa: minimizar E empeora t_des un
18 % (percentil 91). O sea, la estructura de correlacion en la NUBE ALEATORIA no
es la misma que en la FRONTERA.

Eso no es una contradiccion, es lo normal: la correlacion mide como se mueven
juntas dos metricas en la region tipica, y el frente de Pareto vive en el borde,
donde queda poquisima masa de la distribucion. Un optimizador no pasa su vida en
la region tipica -- se va al borde en las primeras generaciones. Por eso decidir
la arquitectura del algoritmo mirando solo la nube aleatoria es un error, y por
eso hace falta este experimento.

ESTO ES MEDICION, NO LA IMPLEMENTACION FINAL. Sirve para contestar: hay frente?
que tan grande? entre que objetivos? Con eso se decide que se implementa.

IMPLEMENTACION: NSGA-II (Deb et al., 2002) con dominancia restringida (Deb,
2000). Se escribe aqui en vez de usar pymoo porque el cruce tiene que
intercambiar MODULOS ENTEROS entre padres: promediar las coordenadas de dos
layouts distintos produce un layout que no se parece a ninguno de los dos y que
casi siempre tiene traslapes.
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

import muestreo as MU         # noqa: E402
import parametros as P        # noqa: E402
from recinto import Colocacion, POR_CLAVE, cuantizar, recinto_ejemplo  # noqa: E402
from potencial import _ev, _init, muta   # noqa: E402  (misma evaluacion)


# =============================================================================
# maquinaria de NSGA-II
# =============================================================================
def domina(fa, va, fb, vb):
    """Dominancia RESTRINGIDA (Deb 2000).

    Las tres reglas, en orden:
      1. factible domina a infactible, sin mirar objetivos
      2. entre dos infactibles, gana el de menor violacion
      3. entre dos factibles, la dominancia de Pareto de siempre

    Por que asi y no penalizando el objetivo con la violacion: sumar una
    penalizacion obliga a inventar un peso que mezcla metros con segundos, y ese
    peso decide el resultado. Aqui no hay peso que elegir.
    """
    if (va > 0) != (vb > 0):
        return vb > 0
    if va > 0:
        return va < vb
    return bool(np.all(fa <= fb) and np.any(fa < fb))


def ordenar_frentes(F, V):
    """Ordenamiento no dominado rapido. Devuelve lista de frentes (indices)."""
    n = len(F)
    dominados = [[] for _ in range(n)]
    cuenta = np.zeros(n, dtype=int)
    frentes = [[]]
    for i in range(n):
        for j in range(i + 1, n):
            if domina(F[i], V[i], F[j], V[j]):
                dominados[i].append(j)
                cuenta[j] += 1
            elif domina(F[j], V[j], F[i], V[i]):
                dominados[j].append(i)
                cuenta[i] += 1
    frentes[0] = [i for i in range(n) if cuenta[i] == 0]
    k = 0
    while frentes[k]:
        sig = []
        for i in frentes[k]:
            for j in dominados[i]:
                cuenta[j] -= 1
                if cuenta[j] == 0:
                    sig.append(j)
        frentes.append(sig)
        k += 1
    return frentes[:-1]


def apinamiento(F, frente):
    """Distancia de apinamiento: preserva DIVERSIDAD sobre el frente.

    Sin esto el frente colapsa a un punto: todas las soluciones no dominadas
    empatan en rango, la seleccion las trata igual y la deriva las junta. Es la
    pieza que hace que NSGA-II devuelva un abanico y no un unico compromiso.
    """
    d = np.zeros(len(frente))
    if len(frente) <= 2:
        return np.full(len(frente), np.inf)
    sub = F[frente]
    for m in range(sub.shape[1]):
        o = np.argsort(sub[:, m])
        d[o[0]] = d[o[-1]] = np.inf
        rango = sub[o[-1], m] - sub[o[0], m]
        if rango <= 0:
            continue
        for k in range(1, len(o) - 1):
            d[o[k]] += (sub[o[k + 1], m] - sub[o[k - 1], m]) / rango
    return d


def cruzar(a, b, rng):
    """Cruce uniforme por MODULO: cada area se hereda entera de un padre.

    Se hereda (x, y, rot) como bloque. Promediar coordenadas entre dos layouts
    distintos no produce un hijo intermedio -- produce uno que no se parece a
    ninguno y que casi siempre tiene traslapes.
    """
    m = rng.random(len(a)) < 0.5
    return [Colocacion(c.tipo, c.x, c.y, c.rot)
            for c in (a[i] if m[i] else b[i] for i in range(len(a)))]


def nsga2(pool, rec, semillas, objetivos, rng, pob=48, gens=50, sigma0=10.0):
    signo = np.array([1.0] * len(objetivos))

    def metricas(ms):
        return np.array([[m[k] for k in objetivos] for m in ms]) * signo

    P_ = list(semillas[:pob])
    ms = list(pool.map(_ev, P_))
    F = metricas(ms)
    V = np.array([m["viol"] for m in ms])
    hist = []

    for g in range(gens):
        sigma = sigma0 * (1.0 - 0.8 * g / max(1, gens - 1))
        frentes = ordenar_frentes(F, V)
        rango = np.empty(len(P_), dtype=int)
        dist = np.empty(len(P_))
        for r, fr in enumerate(frentes):
            rango[fr] = r
            dist[fr] = apinamiento(F, fr)

        # torneo binario: primero rango, luego apinamiento
        def torneo():
            i, j = rng.integers(len(P_), size=2)
            if rango[i] != rango[j]:
                return P_[i] if rango[i] < rango[j] else P_[j]
            return P_[i] if dist[i] > dist[j] else P_[j]

        hijos = []
        for _ in range(pob):
            h = cruzar(torneo(), torneo(), rng) if rng.random() < 0.9 else torneo()
            hijos.append(muta(h, rec, rng, sigma))
        mh = list(pool.map(_ev, hijos))

        # (mu + lambda): padres e hijos compiten juntos, nadie se pierde gratis
        P_ = P_ + hijos
        ms = ms + mh
        F = metricas(ms)
        V = np.array([m["viol"] for m in ms])

        frentes = ordenar_frentes(F, V)
        nuevos = []
        for fr in frentes:
            if len(nuevos) + len(fr) <= pob:
                nuevos += fr
                continue
            d = apinamiento(F, fr)
            orden = np.argsort(-d)
            nuevos += [fr[i] for i in orden[:pob - len(nuevos)]]
            break
        P_ = [P_[i] for i in nuevos]
        ms = [ms[i] for i in nuevos]
        F, V = metricas(ms), np.array([m["viol"] for m in ms])
        fr0 = [i for i in ordenar_frentes(F, V)[0] if V[i] <= 0]
        hist.append({"g": g, "n_frente": len(fr0),
                     "mejor": {k: float(min(m[k] for m in ms)) for k in objetivos}})
    frentes = ordenar_frentes(F, V)
    fr0 = [i for i in frentes[0] if V[i] <= 0]
    return [ms[i] for i in fr0], [P_[i] for i in fr0], hist, ms


# =============================================================================
def informe(nombre, objetivos, frente, base):
    print("\n" + "=" * 72)
    print("%s   objetivos: %s" % (nombre, " vs ".join(objetivos)))
    print("=" * 72)
    print("  soluciones no dominadas y factibles: %d" % len(frente))
    if not frente:
        print("  el frente quedo vacio")
        return
    print("\n  %-10s %12s %12s %12s %10s"
          % ("objetivo", "mejor", "peor en fr.", "mediana azar", "recorrido"))
    for k in objetivos:
        v = np.array([m[k] for m in frente])
        mz = float(np.median([b[k] for b in base]))
        rec_ = 100 * (v.max() - v.min()) / max(abs(v.min()), 1e-9)
        print("  %-10s %12.2f %12.2f %12.2f %9.1f %%"
              % (k, v.min(), v.max(), mz, rec_))
    # Metricas que NO se optimizaron. Hay que mirarlas: un frente puede estar
    # regalando en silencio algo que nadie esta vigilando, y con dos objetivos
    # el tercero no aparece en ningun lado del reporte.
    libres = [k for k in ("f1", "t95", "t_des", "E") if k not in objetivos]
    if libres:
        print()
        print("  lo que NO se optimizo, a lo largo del frente:")
        for k in libres:
            v = np.array([m[k] for m in frente])
            mz = float(np.median([b[k] for b in base]))
            print("    %-8s de %8.2f a %8.2f   mediana al azar %8.2f   "
                  "peor del frente %+.1f %%"
                  % (k, v.min(), v.max(), mz, 100 * (v.max() - mz) / mz))

    if len(objetivos) == 2:
        a = np.array([m[objetivos[0]] for m in frente])
        b_ = np.array([m[objetivos[1]] for m in frente])
        o = np.argsort(a)
        print("\n  el frente, de punta a punta:")
        paso = max(1, len(o) // 8)
        for i in o[::paso]:
            print("    %-10s %9.2f   %-10s %9.2f"
                  % (objetivos[0], a[i], objetivos[1], b_[i]))
        if len(a) > 2:
            from scipy.stats import spearmanr
            print("\n  rho SOBRE EL FRENTE: %+.3f  (en un frente real debe ser "
                  "negativo:\n  eso es lo que significa compromiso)"
                  % spearmanr(a, b_).statistic)


def main(aforo, pob, gens, semilla):
    rec = recinto_ejemplo(h=P.H_CELDA)
    lays, _ = MU.muestra(rec, max(400, pob * 3), semilla=semilla, modo="amplio")
    lays = [l for _, l in lays]
    print("NSGA-II de investigacion")
    print("  aforo %d  poblacion %d  generaciones %d  semilla %d"
          % (aforo, pob, gens, semilla))
    print("  presupuesto: %d evaluaciones por corrida" % (pob * (gens + 1)))

    with ProcessPoolExecutor(initializer=_init, initargs=(aforo,)) as pool:
        base = list(pool.map(_ev, lays[:120]))
        for objetivos, nombre in (
            (["f1", "t95"], "A. accesibilidad contra TIEMPO DE EVACUACION"),
            (["f1", "E"], "B. accesibilidad contra RIESGO DE APLASTAMIENTO"),
        ):
            t0 = time.perf_counter()
            fr, _lays, hist, _ = nsga2(pool, rec, lays,
                                       objetivos,
                                       np.random.default_rng(semilla + 3),
                                       pob=pob, gens=gens)
            informe(nombre, objetivos, fr, base)
            print("\n  %.0f s | frente por generacion: %s"
                  % (time.perf_counter() - t0,
                     " ".join(str(h["n_frente"]) for h in hist[::max(1, gens // 12)])))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--aforo", type=int, default=2000)
    ap.add_argument("--pob", type=int, default=48)
    ap.add_argument("--gens", type=int, default=50)
    ap.add_argument("--semilla", type=int, default=11)
    a = ap.parse_args()
    main(a.aforo, a.pob, a.gens, a.semilla)
