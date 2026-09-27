"""
Se puede abaratar f1 sin cambiar el ORDEN entre layouts?

f1 cuesta 327 ms, la mitad del presupuesto de una evaluacion, porque resuelve un
campo Eikonal por modulo (9 campos) para poder plantear el transporte capacitado.
Si una version mas barata ordenara los layouts igual, el presupuesto de busqueda
se duplicaria sin cambiar el resultado de la optimizacion.

Se prueban tres candidatos, de mas barato a mas caro:

  cercano_1fmm   UN solo campo multi-fuente sembrado en TODOS los modulos a la
                 vez: da la distancia al modulo mas cercano, sin capacidades.
                 Es 9 veces mas barato. Ignora por completo el reparto de carga.
  euclidiano     transporte capacitado exacto, pero con distancia en linea recta
                 en vez de caminando. Barato, y aisla cuanto aporta la geodesica.
  exacto         lo que ya esta: 9 campos geodesicos + transporte capacitado.

LO QUE SE MIDE ES LA CORRELACION DE RANGOS, no el valor. A un optimizador por
dominancia le da igual que f1 valga 17 o 34 mientras ordene igual. Un surrogado
con rho > 0.95 se puede usar DENTRO de la busqueda y dejar el exacto para el
reporte final; con rho < 0.9 estaria optimizando otro problema.
"""
import os
import sys
import time

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "nucleo"))

import acceso as A            # noqa: E402
import geometria as G         # noqa: E402
import muestreo as MU         # noqa: E402
import parametros as P        # noqa: E402
from recinto import recinto_ejemplo  # noqa: E402


def f1_cercano(rec, layout, libre):
    """Un solo campo, sembrado en el frente de TODOS los modulos a la vez."""
    semilla = np.zeros_like(libre)
    for c in layout:
        semilla |= A.celdas_atencion(rec, c, libre)
    d = A.campo_distancia(rec, libre, semilla)[libre]
    d = d[np.isfinite(d)]
    return float(d.mean()) if d.size else np.inf


def f1_euclidiano(rec, layout, libre):
    """Transporte capacitado, pero midiendo en linea recta."""
    n = int(libre.sum())
    ys, xs = np.where(libre)
    cx = (xs + 0.5) * rec.h
    cy = (ys + 0.5) * rec.h
    q = np.full(n, 1.0 / n)
    suma = peso = 0.0
    for tipo in A.SERVICIO:
        idx = [c for c in layout if c.tipo == tipo]
        if not idx:
            continue
        D = np.empty((len(idx), n))
        for k, c in enumerate(idx):
            x, y, w, f = c.rect()
            # distancia al RECTANGULO, no a su centro: un modulo de 8 m de largo
            # no se atiende desde un punto
            dx = np.maximum(np.maximum(x - cx, cx - (x + w)), 0.0)
            dy = np.maximum(np.maximum(y - cy, cy - (y + f)), 0.0)
            D[k] = np.hypot(dx, dy)
        coste, _c, _b, _p = A.transporte_precios(D, q, A.capacidades(layout, tipo))
        w_ = A.peso_tipo(layout, tipo)
        suma += w_ * coste
        peso += w_
    return suma / peso if peso else np.inf


def main(n=60):
    rec = recinto_ejemplo(h=P.H_CELDA)
    lays, _ = MU.muestra(rec, n, semilla=5, modo="amplio")
    lays = [l for _, l in lays]
    libs = [G.zona_ocupable(rec, l)[0] for l in lays]
    print("%d layouts" % len(lays))

    res, tiempos = {}, {}
    for nombre, fn in (("exacto", lambda l, b: A.f1(rec, l, b)),
                       ("cercano_1fmm", lambda l, b: f1_cercano(rec, l, b)),
                       ("euclidiano", lambda l, b: f1_euclidiano(rec, l, b))):
        t0 = time.perf_counter()
        res[nombre] = np.array([fn(l, b) for l, b in zip(lays, libs)])
        tiempos[nombre] = (time.perf_counter() - t0) / len(lays)

    ref = res["exacto"]
    print("\n%-14s %10s %10s %10s %12s %10s"
          % ("variante", "ms/layout", "vs exacto", "rho", "inversiones", "media"))
    npares = len(ref) * (len(ref) - 1) // 2
    for k in ("exacto", "cercano_1fmm", "euclidiano"):
        v = res[k]
        ok = np.isfinite(v) & np.isfinite(ref)
        rho = spearmanr(v[ok], ref[ok]).statistic
        inv = sum(1 for i in range(len(ref)) for j in range(i + 1, len(ref))
                  if ok[i] and ok[j] and (ref[i] < ref[j]) != (v[i] < v[j]))
        print("%-14s %10.1f %9.1fx %10.4f %7d/%-5d %10.2f"
              % (k, 1e3 * tiempos[k], tiempos["exacto"] / tiempos[k], rho,
                 inv, npares, np.nanmean(v[ok])))

    print("\nLECTURA")
    for k in ("cercano_1fmm", "euclidiano"):
        v = res[k]
        ok = np.isfinite(v) & np.isfinite(ref)
        rho = spearmanr(v[ok], ref[ok]).statistic
        veredicto = ("SIRVE como surrogado dentro de la busqueda" if rho > 0.95
                     else "NO sirve: ordena distinto, seria otro problema")
        print("  %-14s rho %.4f  ->  %s" % (k, rho, veredicto))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
