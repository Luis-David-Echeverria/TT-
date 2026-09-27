"""
EL FRENTE REAL, POR BARRIDO ε-RESTRINGIDO.

La correlacion sobre 100 layouts AL AZAR contesto una pregunta ("¿se puede
deducir una funcion de la otra?" -> no) pero no puede contestar la otra: ¿como
es el frente donde de verdad hay que elegir? Una muestra al azar nunca llega a
la frontera, se queda en la region tipica.

Este barrido llega, y sin usar el algoritmo que se va a implementar despues:

    para cada tope τ:   minimizar  f1(acceso)
                        sujeto a   t_evac ≤ τ
                                   + las restricciones geometricas

Cada τ da UN punto del frente. Barriendo τ se traza la curva entera. Es el
metodo ε-restringido (Haimes et al., 1971), y tiene una propiedad que la suma
ponderada no tiene: alcanza TODOS los puntos del frente, incluidos los de las
regiones no convexas, porque no escalariza -- restringe.

Por eso sirve de arbitro. Si el frente que sale es convexo, un barrido de pesos
bastaria y no hace falta NSGA-II. Si tiene hendiduras, el barrido de pesos se
las salta y NSGA-II queda justificado.

Se guarda tambien la trayectoria por generacion de cada τ, para poder ver como
converge cada punto del frente y no solo donde acabo.
"""
import argparse
import json
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
from correlacion import _rects  # noqa: E402  (mismos muros que ve el simulador)

# La consola de Windows viene en cp1252 y este script imprime epsilon, tau y
# acentos. Sin esto el experimento se cae por un print.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

T_MAX = 600.0
DESTINO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "datos", "frente_epsilon.json")
_W = {}


def _init(aforo):
    _W["rec"] = recinto_ejemplo(h=P.H_CELDA)
    _W["aforo"] = aforo


def _ev(layout):
    rec, aforo = _W["rec"], _W["aforo"]
    viol_geo = G.evaluar(rec, layout, corto=False)["violacion"]
    libre, _ = G.zona_ocupable(rec, layout)
    if not libre.any():
        return {"acceso": 1e6, "t_evac": T_MAX, "viol_geo": 1e6}
    acc = A.f1(rec, layout, libre)
    M0 = np.where(libre, aforo / libre.sum(), 0.0)
    r = F.simular(rec, layout, aforo, dt=P.DT, t_max=T_MAX, n_cuadros=3,
                  M0=M0, refresco=P.REFRESCO_CAMPO)
    return {"acceso": float(acc) if np.isfinite(acc) else 1e6,
            "t_evac": r["t_des"] or T_MAX, "viol_geo": float(viol_geo)}


def serializar(layout):
    """El layout en la forma que consume la interfaz."""
    return [{"tipo": c.tipo, "x": round(c.x, 3), "y": round(c.y, 3), "rot": int(c.rot)}
            for c in layout]


def muta(layout, rec, rng, sigma):
    nuevo = [Colocacion(c.tipo, c.x, c.y, c.rot) for c in layout]
    for _ in range(int(rng.integers(1, 3))):
        k = int(rng.integers(len(nuevo)))
        c = nuevo[k]
        if rng.random() < 0.20:
            c.rot = 1 - c.rot
        t = POR_CLAVE[c.tipo]
        w, f = (t.ancho, t.fondo) if c.rot == 0 else (t.fondo, t.ancho)
        if rng.random() < 0.08:
            c.x = cuantizar(rng.uniform(0, rec.W - w))
            c.y = cuantizar(rng.uniform(0, rec.H - f))
        else:
            c.x = cuantizar(np.clip(c.x + rng.normal(0, sigma), 0, rec.W - w))
            c.y = cuantizar(np.clip(c.y + rng.normal(0, sigma), 0, rec.H - f))
    return nuevo


def violacion(m, tau, objetivo):
    """Cuanto incumple. Con tau=None el tope no existe (se minimiza a secas)."""
    v = m["viol_geo"]
    if tau is not None and objetivo == "acceso":
        v += max(0.0, m["t_evac"] - tau)
    return v


def buscar(pool, rec, semillas, rng, objetivo, tau=None,
           mu=8, lam=24, gens=30, sigma0=10.0):
    """(mu+lambda) con reglas de factibilidad de Deb. Guarda la trayectoria."""
    def orden(z):
        v = violacion(z, tau, objetivo)
        return (v > 0, v, z[objetivo])

    pob = [{"lay": s, **m} for s, m in zip(semillas[:mu], pool.map(_ev, semillas[:mu]))]
    pob.sort(key=orden)
    traza = []

    for g in range(gens):
        sigma = sigma0 * (1.0 - 0.8 * g / max(1, gens - 1))
        hijos = [muta(pob[int(rng.integers(len(pob)))]["lay"], rec, rng, sigma)
                 for _ in range(lam)]
        for h, m in zip(hijos, pool.map(_ev, hijos)):
            pob.append({"lay": h, **m})
        pob.sort(key=orden)
        pob = pob[:mu]
        mejor = pob[0]
        traza.append({"g": g + 1,
                      "acceso": round(mejor["acceso"], 4),
                      "t_evac": round(mejor["t_evac"], 3),
                      "factible": violacion(mejor, tau, objetivo) <= 0,
                      "layout": serializar(mejor["lay"])})
    return pob[0], traza, mu + lam * gens


def main(aforo, gens, n_tau, semilla):
    rec = recinto_ejemplo(h=P.H_CELDA)
    lays, _ = MU.muestra(rec, 300, semilla=semilla, modo="estricto")
    lays = [l for _, l in lays]

    print("FRENTE POR BARRIDO ε-RESTRINGIDO")
    print("  aforo %d  |  %d topes  |  (8+24) x %d generaciones cada uno"
          % (aforo, n_tau, gens))
    t_ini = time.perf_counter()
    salida = {"aforo": aforo, "gens": gens, "semilla": semilla,
              "cfg": {"h": P.H_CELDA, "dt": P.DT, "k_c": P.REFRESCO_CAMPO,
                      "p": P.EXP_REPARTO, "t_max": T_MAX,
                      "modo_muestreo": "estricto",
                      "metodo": "epsilon-restringido",
                      "objetivo": "min acceso s.a. t_evac <= tau"},
              "corridas": [], "azar": {}}

    with ProcessPoolExecutor(initializer=_init, initargs=(aforo,)) as pool:
        base = list(pool.map(_ev, lays[:120]))
        fac = [b for b in base if b["viol_geo"] <= 0]
        t_az = np.array([b["t_evac"] for b in fac])
        a_az = np.array([b["acceso"] for b in fac])
        salida["azar"] = {"n": len(fac),
                          "acceso": [round(float(x), 4) for x in a_az],
                          "t_evac": [round(float(x), 3) for x in t_az]}
        print("  referencia al azar (%d factibles): acceso %.2f-%.2f m, "
              "t_evac %.1f-%.1f s" % (len(fac), a_az.min(), a_az.max(),
                                      t_az.min(), t_az.max()))

        # el extremo rapido: hasta donde baja el tiempo si solo importa el tiempo
        print("\n  buscando el extremo de tiempo minimo…", end="", flush=True)
        m_t, traza_t, _ = buscar(pool, rec, lays, np.random.default_rng(semilla + 1),
                                 "t_evac", None, gens=gens)
        t_lo = m_t["t_evac"]
        print(" t_evac = %.1f s (acceso %.2f m)" % (t_lo, m_t["acceso"]))

        taus = np.linspace(t_lo, float(np.median(t_az)), n_tau)
        print("\n  %-6s %-10s %-12s %-12s %-10s %s"
              % ("#", "tope τ", "acceso", "t_evac", "cumple?", "seg"))
        for i, tau in enumerate(taus):
            t0 = time.perf_counter()
            m, traza, ev = buscar(pool, rec, lays,
                                  np.random.default_rng(semilla + 100 + i),
                                  "acceso", float(tau), gens=gens)
            cumple = m["viol_geo"] <= 0 and m["t_evac"] <= tau + 1e-6
            salida["corridas"].append({
                "tau": round(float(tau), 3),
                "acceso": round(m["acceso"], 4),
                "t_evac": round(m["t_evac"], 3),
                "cumple": bool(cumple),
                "evaluaciones": ev,
                "layout": serializar(m["lay"]),
                "traza": traza,
            })
            print("  %-6d %-10.1f %-12.3f %-12.1f %-10s %.0f"
                  % (i, tau, m["acceso"], m["t_evac"],
                     "si" if cumple else "NO", time.perf_counter() - t0))

    # ------------------------------------------------- el frente y su forma
    ok = [c for c in salida["corridas"] if c["cumple"]]
    a = np.array([c["acceso"] for c in ok])
    t = np.array([c["t_evac"] for c in ok])
    # quedarse solo con los no dominados: topes distintos pueden dar el mismo punto
    o = np.lexsort((t, a))
    fr, mejor = [], np.inf
    for i in o:
        if t[i] < mejor - 1e-9:
            fr.append(int(i))
            mejor = t[i]
    fr = np.array(fr)

    # Que puntos del frente minimiza ALGUNA suma ponderada. Los indices son
    # POSICIONES DENTRO DEL FRENTE, no del arreglo completo: mezclarlos hacia
    # que hasta los extremos salieran "inalcanzables", que es imposible -- el
    # extremo de cada eje siempre lo encuentra el peso 0 o el peso 1.
    af, tf = a[fr], t[fr]
    alcanz = set()
    if len(fr) >= 2:
        na = (af - af.min()) / max(float(np.ptp(af)), 1e-12)
        nt = (tf - tf.min()) / max(float(np.ptp(tf)), 1e-12)
        for w in np.linspace(0, 1, 4001):
            alcanz.add(int(np.argmin(w * na + (1 - w) * nt)))
    else:
        alcanz = set(range(len(fr)))

    salida["recinto"] = {
        "W": rec.W, "H": rec.H,
        "muros": _rects(rec.muros),
        "salidas": [{"nombre": x.nombre, "lado": x.lado,
                     "centro": x.centro, "ancho": x.ancho} for x in rec.salidas],
    }
    salida["frente"] = [{"acceso": float(af[k]), "t_evac": float(tf[k]),
                         "alcanzable_por_pesos": k in alcanz,
                         "layout": ok[fr[k]]["layout"],
                         "tau": ok[fr[k]]["tau"]}
                        for k in range(len(fr))]
    salida["convexo"] = bool(len(alcanz) == len(fr))
    salida["segundos"] = round(time.perf_counter() - t_ini, 1)

    print("\n" + "=" * 68)
    print("EL FRENTE")
    print("=" * 68)
    print("  %-14s %-14s %s" % ("acceso (m)", "t_evac (s)", "¿la alcanza un barrido de pesos?"))
    for k in range(len(fr)):
        print("  %-14.3f %-14.1f %s"
              % (af[k], tf[k], "si" if k in alcanz else "NO — inalcanzable"))
    print()
    print("  %d puntos no dominados; un barrido de pesos alcanzaria %d."
          % (len(fr), len(alcanz)))
    if salida["convexo"]:
        print("  -> FRENTE CONVEXO. Un barrido de pesos bastaria; NSGA-II no")
        print("     se justifica por este argumento.")
    else:
        print("  -> FRENTE NO CONVEXO: %d puntos son inalcanzables con CUALQUIER"
              % (len(fr) - len(alcanz)))
        print("     peso. Ahi si hace falta un metodo por dominancia.")

    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    with open(DESTINO, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    print("\n  guardado en datos/%s  (%.0f s)"
          % (os.path.basename(DESTINO), salida["segundos"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--aforo", type=int, default=2000)
    ap.add_argument("--gens", type=int, default=30)
    ap.add_argument("--topes", type=int, default=9)
    ap.add_argument("--semilla", type=int, default=0)
    a = ap.parse_args()
    main(a.aforo, a.gens, a.topes, a.semilla)
