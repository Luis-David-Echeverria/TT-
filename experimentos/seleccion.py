"""
El conflicto que aparece en modo estricto, es del problema o del filtro?

En la nube sin recortar f1 y f2 salen independientes. Al mirar solo los layouts
que pasan la capa geometrica aparece una correlacion negativa debil. Hay dos
explicaciones y llevan a conclusiones opuestas:

  (a) el filtro revela estructura real que el ruido de la nube grande tapaba
  (b) el filtro la FABRICA: condicionar sobre un criterio que se relaciona con
      los dos objetivos induce correlacion entre ellos aunque sean
      independientes -- el mismo mecanismo que hace que entre los admitidos a
      una universidad las notas y el examen de ingreso salgan correlacionados
      al reves que en la poblacion general

Se distinguen sin simular nada nuevo: la muestra amplia ya trae guardado si
cada layout pasa o no la capa completa. Si al filtrar la muestra AMPLIA aparece
la misma correlacion negativa, es (b).
"""
import os
import sys

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "nucleo"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import almacen as AL          # noqa: E402
from analisis import bootstrap_rho, frente_pareto, cargar   # noqa: E402

grupos, cfgs = cargar()

print("EFECTO DE SELECCION")
print("=" * 78)
print("%-10s %-24s %6s %9s %-18s" % ("aforo", "poblacion", "n", "rho", "IC 95%"))

for aforo in (2000, 3000, 4000):
    amp = grupos.get(("amplio", aforo), [])
    est = grupos.get(("estricto", aforo), [])
    if not amp or not est:
        continue
    print("-" * 78)
    for nombre, filas in (("amplia, sin filtrar", amp),
                          ("amplia, solo factibles", [f for f in amp if f["factible"]]),
                          ("amplia, solo INfactibles", [f for f in amp if not f["factible"]]),
                          ("generada ya factible", est)):
        x = np.array([f["f1"] for f in filas], dtype=float)
        y = np.array([f["t_des"] for f in filas], dtype=float)
        ok = np.isfinite(x) & np.isfinite(y)
        x, y = x[ok], y[ok]
        if len(x) < 20:
            print("%-10d %-24s %6d   muy pocos" % (aforo, nombre, len(x)))
            continue
        rho = spearmanr(x, y).statistic
        lo, hi = bootstrap_rho(x, y)
        marca = "" if lo <= 0 <= hi else "  <-- IC excluye 0"
        print("%-10d %-24s %6d %9.3f [%6.3f, %6.3f]%s"
              % (aforo, nombre, len(x), rho, lo, hi, marca))

# --- cuantos no dominados predice la independencia -------------------------
print()
print("TAMANO DEL FRENTE DE PARETO CONTRA LO QUE PREDICE LA INDEPENDENCIA")
print("=" * 78)
print("Con n puntos y dos objetivos INDEPENDIENTES, el numero esperado de no")
print("dominados es el numero armonico H_n = 1 + 1/2 + ... + 1/n ~ ln(n) + 0.577.")
print("Si lo observado coincide, la nube se comporta como dos objetivos sin")
print("relacion; si es mucho mayor, hay conflicto de verdad.")
print()
print("%-10s %-10s %6s %10s %10s" % ("modo", "aforo", "n", "observado", "esperado"))
for (modo, aforo), filas in sorted(grupos.items()):
    x = np.array([f["f1"] for f in filas], dtype=float)
    y = np.array([f["t_des"] for f in filas], dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    n = len(x)
    esperado = float(np.sum(1.0 / np.arange(1, n + 1)))
    print("%-10s %-10d %6d %10d %10.1f"
          % (modo, aforo, n, len(frente_pareto(x, y)), esperado))
