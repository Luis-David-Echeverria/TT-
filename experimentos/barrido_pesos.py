"""
BARRIDO DE PESOS: la prueba clasica de si el problema es multiobjetivo.

    para cada peso w:   minimizar   w*f1_norm + (1-w)*t_evac_norm

La logica de la prueba es solida y conviene entenderla bien:

  - Si TODOS los pesos devuelven practicamente la MISMA solucion, entonces hay
    una sola solucion buena y no hay nada que negociar: el problema NO es
    multiobjetivo, y sobra montar maquinaria para varios objetivos.

  - Si los pesos devuelven soluciones DISTINTAS que se reparten a lo largo de
    una curva, entonces cada peso representa una postura distinta sobre que
    importa mas, y ninguna domina a las demas. Eso SI es multiobjetivo.

Por eso el barrido de pesos es una prueba POSITIVA valida: si sale un abanico,
la conclusion "es multiobjetivo" esta bien sacada.

LO QUE LA PRUEBA NO PUEDE VER, y conviene saberlo antes de sacar conclusiones
de mas: un barrido de pesos SOLO puede devolver puntos del casco convexo del
frente. Minimizar w*a + (1-w)*b es deslizar una recta hasta que toca el
conjunto factible, y una recta nunca toca el fondo de una hendidura. Entonces
la curva que dibuja un barrido de pesos SIEMPRE se ve convexa -- no porque el
frente lo sea, sino porque el metodo no puede devolver otra cosa.

O sea: "el barrido salio convexo" no es un hallazgo sobre el problema, es una
propiedad del metodo. Para saber si el frente TIENE hendiduras hace falta otro
metodo (epsilon-restringido, o dominancia).

LA NORMALIZACION IMPORTA Y HAY QUE DECLARARLA. Sumar metros con segundos no
significa nada, asi que cada objetivo se lleva a [0,1] con el rango de la
muestra al azar. Ese rango es una DECISION: cambiarlo cambia que solucion sale
para cada peso. Se declara aqui y se guarda con los resultados.
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import muestreo as MU         # noqa: E402
import parametros as P        # noqa: E402
from recinto import recinto_ejemplo  # noqa: E402
from frente_epsilon import _ev, _init, muta, T_MAX, serializar  # noqa: E402
from correlacion import _rects  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DESTINO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "datos", "barrido_pesos.json")


def buscar_pesos(pool, rec, semillas, rng, w, ref, mu=8, lam=24, gens=30,
                 sigma0=10.0):
    """(mu+lambda) minimizando la suma ponderada, con reglas de Deb."""
    def escalar(m):
        a = (m["acceso"] - ref["a0"]) / ref["da"]
        t = (m["t_evac"] - ref["t0"]) / ref["dt"]
        return w * a + (1 - w) * t

    def orden(z):
        return (z["viol_geo"] > 0, z["viol_geo"], escalar(z))

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
        traza.append({"g": g + 1, "acceso": round(pob[0]["acceso"], 4),
                      "t_evac": round(pob[0]["t_evac"], 3),
                      "layout": serializar(pob[0]["lay"])})
    return pob[0], traza


def main(aforo, gens, semilla):
    rec = recinto_ejemplo(h=P.H_CELDA)
    lays, _ = MU.muestra(rec, 300, semilla=semilla, modo="estricto")
    lays = [l for _, l in lays]
    # Los extremos 0 y 1 son los casos MONO-OBJETIVO puros: con w = 0 solo
    # importa el tiempo de evacuacion y con w = 1 solo la accesibilidad. Sirven
    # de referencia para todo lo demas -- dicen hasta donde llega cada funcion
    # cuando nadie le estorba, y por tanto cuanto cuesta de verdad atender a la
    # otra.
    pesos = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

    print("BARRIDO DE PESOS")
    print("  min  w·f1_norm + (1-w)·t_evac_norm,  para w de 0.1 a 0.9")
    print("  aforo %d  |  (8+24) x %d generaciones por peso" % (aforo, gens))
    t_ini = time.perf_counter()

    with ProcessPoolExecutor(initializer=_init, initargs=(aforo,)) as pool:
        base = [b for b in pool.map(_ev, lays[:120]) if b["viol_geo"] <= 0]
        a_az = np.array([b["acceso"] for b in base])
        t_az = np.array([b["t_evac"] for b in base])
        ref = {"a0": float(a_az.min()), "da": float(np.ptp(a_az)),
               "t0": float(t_az.min()), "dt": float(np.ptp(t_az))}
        print("  normalizacion (rango de %d layouts al azar):" % len(base))
        print("    acceso  [%.2f, %.2f] m     t_evac  [%.1f, %.1f] s"
              % (ref["a0"], ref["a0"] + ref["da"], ref["t0"], ref["t0"] + ref["dt"]))

        print("\n  %-7s %-14s %-14s" % ("peso w", "acceso (m)", "t_evac (s)"))
        sol = []
        for i, w in enumerate(pesos):
            m, traza = buscar_pesos(pool, rec, lays,
                                    np.random.default_rng(semilla + 200 + i),
                                    w, ref, gens=gens)
            sol.append({"w": w, "w_acceso": w, "w_tiempo": round(1 - w, 3),
                        "acceso": round(m["acceso"], 4),
                        "t_evac": round(m["t_evac"], 3),
                        "layout": serializar(m["lay"]), "traza": traza})
            print("  %-8.1f %-8.1f %-14.3f %-14.1f %s"
                  % (w, 1 - w, m["acceso"], m["t_evac"],
                     "solo tiempo" if w == 0 else
                     "solo acceso" if w == 1 else ""))

    a = np.array([s["acceso"] for s in sol])
    t = np.array([s["t_evac"] for s in sol])

    # ¿cuantas soluciones DISTINTAS salieron? es lo que decide la prueba
    distintas = []
    for i in range(len(sol)):
        if not any(abs(a[i] - a[j]) < 0.25 and abs(t[i] - t[j]) < 0.6
                   for j in distintas):
            distintas.append(i)

    print("\n" + "=" * 68)
    print("LA PRUEBA DEL PROFESOR")
    print("=" * 68)
    print("  soluciones DISTINTAS que produjo el barrido: %d de %d pesos"
          % (len(distintas), len(pesos)))
    print("  recorrido: acceso %.2f-%.2f m (%.0f %%), t_evac %.1f-%.1f s (%.0f %%)"
          % (a.min(), a.max(), 100 * (a.max() - a.min()) / a.min(),
             t.min(), t.max(), 100 * (t.max() - t.min()) / t.min()))
    if len(distintas) >= 3:
        print("\n  -> PASA. Los pesos devuelven soluciones distintas repartidas a lo")
        print("     largo de una curva: cada peso es una postura distinta sobre que")
        print("     importa mas, y ninguna domina a las demas. ES MULTIOBJETIVO.")
    else:
        print("\n  -> NO PASA: casi todos los pesos dan la misma solucion. Habria una")
        print("     sola solucion buena y no haria falta un metodo multiobjetivo.")

    # ---- contraste con el frente completo, si existe ----
    ruta_eps = os.path.join(os.path.dirname(DESTINO), "frente_epsilon.json")
    if os.path.exists(ruta_eps):
        with open(ruta_eps, encoding="utf-8") as f:
            eps = json.load(f)
        inal = [x for x in eps["frente"] if not x["alcanzable_por_pesos"]]
        print("\n" + "=" * 68)
        print("LO QUE EL BARRIDO NO PUDO VER")
        print("=" * 68)
        print("  el frente completo (epsilon-restringido) tiene %d puntos;"
              % len(eps["frente"]))
        print("  el barrido de pesos encontro %d." % len(distintas))
        if inal:
            print("\n  %-14s %-14s" % ("acceso (m)", "t_evac (s)"))
            for x in inal:
                print("  %-14.3f %-14.1f  <- ningun peso llega aqui"
                      % (x["acceso"], x["t_evac"]))
            print("\n  No son peores: son NO DOMINADAS, o sea nadie las mejora en las")
            print("  dos cosas. Simplemente estan en una hendidura del frente, y una")
            print("  recta no puede tocar el fondo de una hendidura.")
            print("\n  Por eso la curva de un barrido de pesos SIEMPRE se ve convexa:")
            print("  es una propiedad del metodo, no un hallazgo sobre el problema.")

    salida = {"aforo": aforo, "gens": gens, "semilla": semilla,
              "recinto": {"W": rec.W, "H": rec.H, "muros": _rects(rec.muros),
                          "salidas": [{"nombre": x.nombre, "lado": x.lado,
                                       "centro": x.centro, "ancho": x.ancho}
                                      for x in rec.salidas]},
              "azar": {"acceso": [round(float(x), 4) for x in a_az],
                       "t_evac": [round(float(x), 3) for x in t_az],
                       "n": len(base)},
              "cfg": {"h": P.H_CELDA, "dt": P.DT, "k_c": P.REFRESCO_CAMPO,
                      "p": P.EXP_REPARTO, "t_max": T_MAX,
                      "metodo": "suma-ponderada"},
              "normalizacion": ref, "soluciones": sol,
              "distintas": len(distintas),
              "segundos": round(time.perf_counter() - t_ini, 1)}
    with open(DESTINO, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    print("\n  guardado en datos/%s  (%.0f s)"
          % (os.path.basename(DESTINO), salida["segundos"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--aforo", type=int, default=2000)
    ap.add_argument("--gens", type=int, default=30)
    ap.add_argument("--semilla", type=int, default=0)
    a = ap.parse_args()
    main(a.aforo, a.gens, a.semilla)
