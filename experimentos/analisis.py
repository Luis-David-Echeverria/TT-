"""
ANALISIS DEL BARRIDO: hay conflicto entre f1 y f2?

De esto depende la arquitectura del resto del TT:

  correlacion POSITIVA y fuerte  los objetivos van de la mano. Mejorar uno
                                 mejora el otro. Un multiobjetivo sobra: basta
                                 optimizar uno y reportar el otro.
  correlacion NEGATIVA           hay conflicto real. No existe un layout que
                                 sea el mejor en los dos, hay un frente de
                                 Pareto, y NSGA-II se justifica solo.
  correlacion CERCA DE CERO      son casi independientes. Tambien justifica el
                                 multiobjetivo, pero por otra razon: optimizar
                                 uno deja al otro al azar.

SE USA SPEARMAN Y NO PEARSON. A un optimizador por dominancia solo le importa
el ORDEN entre soluciones, no la distancia entre sus valores. Pearson mediria
si la relacion es una recta, que es una pregunta que aqui no le sirve a nadie.

Y SE REPORTA INTERVALO, NO SOLO EL PUNTO. Con n layouts el error tipico de rho
es ~1/sqrt(n-1): con n=300 eso es 0.058, asi que un rho de 0.09 NO es
'correlacion debil positiva', es cero con ruido. Confundir las dos cosas es
como se concluye que no hay conflicto cuando lo que pasa es que no se midio con
suficientes layouts.
"""
import json
import os
import sys

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "nucleo"))
import almacen as AL          # noqa: E402

METRICAS = [("f1", "f1 acceso (m)"), ("t_des", "t desalojo (s)"),
            ("t95", "t 95% (s)"), ("exposicion", "E exposicion (m2s)"),
            ("rho_pico", "rho pico (p/m2)")]


def bootstrap_rho(x, y, n=2000, semilla=0):
    """Intervalo al 95 % por remuestreo. Sin supuestos de normalidad, que con
    rangos y n moderado no se sostienen."""
    rng = np.random.default_rng(semilla)
    m = len(x)
    r = np.empty(n)
    for k in range(n):
        s = rng.integers(0, m, m)
        if len(np.unique(x[s])) < 3 or len(np.unique(y[s])) < 3:
            r[k] = np.nan
            continue
        r[k] = spearmanr(x[s], y[s]).statistic
    r = r[np.isfinite(r)]
    return float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


def frente_pareto(a, b):
    """Indices no dominados minimizando ambos."""
    o = np.lexsort((b, a))
    fr, mejor = [], np.inf
    for i in o:
        if b[i] < mejor - 1e-12:
            fr.append(i)
            mejor = b[i]
    return np.array(fr)


def cargar():
    """Filas agrupadas por (modo, aforo), leyendo el aforo de la tabla configs.

    Si faltan configs -- porque una corrida vieja se guardo antes de que esa
    tabla existiera -- se reconstruyen desde correlacion.configuracion(), que
    es la unica fuente de verdad de como se arma la configuracion.
    """
    import correlacion as CO
    for modo in ("amplio", "estricto"):
        for aforo in (2000, 3000, 4000):
            AL.registrar_config(CO.configuracion(aforo, modo))
    cfgs = AL.leer_configs()

    grupos = {}
    for f in AL.consultar():
        if f["f1"] is None:
            continue
        c = cfgs.get(f["config"])
        if c is None:
            continue
        grupos.setdefault((c["modo_muestreo"], int(c["aforo"])), []).append(f)
    return grupos, cfgs


def analizar(filas, etiqueta):
    d = {k: np.array([f[k] for f in filas], dtype=float)
         for k, _ in METRICAS}
    # los que llegaron al tope de tiempo no tienen t_des: se excluyen y se avisa
    tope = ~np.isfinite(d["t_des"])
    n = len(filas)
    print("\n" + "=" * 74)
    print(etiqueta + "   n = %d layouts" % n)
    if tope.any():
        print("  AVISO: %d layouts no desalojaron en el tope de tiempo" % tope.sum())
    ok = ~tope
    for k in d:
        d[k] = d[k][ok]
    n = int(ok.sum())
    if n < 20:
        print("  muy pocos layouts, se omite")
        return None

    # --- 1. varianza: si una metrica no varia, no hay nada que correlacionar
    print("\n  [1] dispersion de cada metrica")
    print("      %-22s %10s %10s %10s %8s" % ("", "media", "desv", "CV", "rango"))
    usables = []
    for k, nom in METRICAS:
        v = d[k]
        cv = v.std() / abs(v.mean()) if v.mean() else 0.0
        print("      %-22s %10.2f %10.3f %9.2f%% %8.2f"
              % (nom, v.mean(), v.std(), 100 * cv, v.max() - v.min()))
        if cv >= 0.01:
            usables.append(k)
        else:
            print("      %-22s   ^ CV < 1%%: constante en la practica, no informa"
                  % "")
    # --- 2. matriz de Spearman
    print("\n  [2] correlacion de rangos (Spearman), con intervalo al 95 %")
    print("      %-14s %-14s %8s %-18s %s"
          % ("", "", "rho", "IC 95%", "lectura"))
    res = {}
    for i, a in enumerate(usables):
        for b in usables[i + 1:]:
            rho = spearmanr(d[a], d[b]).statistic
            lo, hi = bootstrap_rho(d[a], d[b])
            if lo <= 0 <= hi:
                lect = "SIN conflicto detectable (IC cruza 0)"
            elif rho < -0.3:
                lect = "CONFLICTO"
            elif rho < 0:
                lect = "conflicto debil"
            elif rho > 0.7:
                lect = "van juntos: uno sobra"
            else:
                lect = "van juntos, parcialmente"
            print("      %-14s %-14s %8.3f [%6.3f, %6.3f]  %s"
                  % (a, b, rho, lo, hi, lect))
            res["%s~%s" % (a, b)] = (rho, lo, hi)

    # --- 3. la misma matriz en la region buena
    print("\n  [3] solo el mejor 25 %% por f1 (es donde vive el optimizador)")
    corte = np.percentile(d["f1"], 25)
    s = d["f1"] <= corte
    if s.sum() >= 20:
        for b in usables:
            if b == "f1":
                continue
            rho = spearmanr(d["f1"][s], d[b][s]).statistic
            lo, hi = bootstrap_rho(d["f1"][s], d[b][s])
            print("      f1 ~ %-12s %8.3f [%6.3f, %6.3f]   n=%d"
                  % (b, rho, lo, hi, s.sum()))
    else:
        print("      muy pocos (%d)" % s.sum())

    # --- 4. frente de Pareto
    print("\n  [4] frente de Pareto (minimizando ambos)")
    for b in ("t_des", "exposicion"):
        if b not in usables or "f1" not in usables:
            continue
        fr = frente_pareto(d["f1"], d[b])
        rf1 = d["f1"][fr].max() - d["f1"][fr].min()
        rb = d[b][fr].max() - d[b][fr].min()
        print("      f1 vs %-12s %3d no dominados (%.1f%%)   "
              "recorre f1 %.1f m y %s %.0f"
              % (b, len(fr), 100 * len(fr) / n, rf1, b, rb))
        if len(fr) <= 3:
            print("                          ^ frente casi puntual: "
                  "el conflicto no da para un frente")
    return res


def veredicto(res):
    """Que arquitectura queda justificada por lo medido."""
    print("\n" + "=" * 74)
    print("VEREDICTO")
    print("=" * 74)
    print("%-28s %-10s %-20s %s"
          % ("escenario", "rho", "IC 95%", "f1 vs t_des"))
    conflicto = indep = juntos = 0
    for etiq, r in sorted(res.items()):
        if not r:
            continue
        for par in ("f1~t_des", "f1~exposicion"):
            if par not in r:
                continue
            rho, lo, hi = r[par]
            if lo <= 0 <= hi:
                que = "independientes"
                indep += 1
            elif rho < 0:
                que = "EN CONFLICTO"
                conflicto += 1
            else:
                que = "van juntos"
                juntos += 1
            print("%-28s %-10.3f [%6.3f,%6.3f]  %-14s %s"
                  % (etiq, rho, lo, hi, par, que))
    print()
    if conflicto or indep:
        print("  Hay al menos un escenario donde f1 no se puede deducir de f2.")
        print("  -> el problema ES multiobjetivo y NSGA-II se justifica.")
    else:
        print("  f1 y f2 van juntas en todos los escenarios medidos.")
        print("  -> optimizar una basta; el multiobjetivo no se justifica AUN.")
    print("  (conflicto: %d, independientes: %d, van juntos: %d)"
          % (conflicto, indep, juntos))


if __name__ == "__main__":
    grupos, cfgs = cargar()
    print("BARRIDO: %d evaluaciones en %d escenarios"
          % (sum(len(v) for v in grupos.values()), len(grupos)))
    una = next(iter(cfgs.values()))
    print("  h=%.1f m  dt=%.2f s  k_c=%d  p=%.1f  t_max=%.0f s  sigma=%.1f"
          % (una["h"], una["dt"], una["k_c"], una["p"], una["t_max"],
             una["f1_sigma"]))

    res = {}
    for (modo, aforo), filas in sorted(grupos.items()):
        etiqueta = "modo=%-9s aforo=%d" % (modo, aforo)
        res[etiqueta] = analizar(filas, etiqueta)
    veredicto(res)
