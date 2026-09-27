"""
NSGA-II sobre la representacion FBS, con pymoo.

El genoma no es un vector real, es (permutacion, cortes, orientacion), asi que
hacen falta operadores propios: OX para la permutacion (una cruza de corte
simple produciria servicios repetidos y faltantes).
"""
import numpy as np

from pymoo.core.problem import ElementwiseProblem
from pymoo.core.sampling import Sampling
from pymoo.core.crossover import Crossover
from pymoo.core.mutation import Mutation
from pymoo.core.duplicate import ElementwiseDuplicateElimination
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize

from recinto import Rejilla, catalogo_bloques
from objetivos import evaluar

P_CORTE = 0.22


def genoma_aleatorio(rng, n, es_serv):
    """Siembra con los servicios separados en la permutacion: sube muchisimo la
    tasa de factibilidad inicial sin sesgar la busqueda."""
    serv = [i for i in range(n) if es_serv[i]]
    libres = [i for i in range(n) if not es_serv[i]]
    rng.shuffle(serv)
    rng.shuffle(libres)
    perm, si, li = [], 0, 0
    while si < len(serv) or li < len(libres):
        if li < len(libres):
            perm.append(libres[li]); li += 1
        if si < len(serv):
            perm.append(serv[si]); si += 1
    cortes = rng.random(n - 1) < P_CORTE
    if cortes.sum() < 2:
        cortes[rng.choice(n - 1, 2, replace=False)] = True
    return [perm, cortes, int(rng.integers(2))]


class MuestreoFBS(Sampling):
    def __init__(self, es_serv):
        super().__init__()
        self.es_serv = es_serv

    def _do(self, problem, n_samples, **kwargs):
        rng = np.random.default_rng()
        n = len(self.es_serv)
        X = np.full((n_samples, 1), None, dtype=object)
        for i in range(n_samples):
            X[i, 0] = genoma_aleatorio(rng, n, self.es_serv)
        return X


def ox(p1, p2, rng):
    """Order crossover: respeta que el hijo siga siendo una permutacion."""
    n = len(p1)
    a, b = sorted(rng.choice(n, 2, replace=False))
    hijo = [None] * n
    hijo[a:b + 1] = p1[a:b + 1]
    dentro = set(hijo[a:b + 1])
    resto = [g for g in p2 if g not in dentro]
    k = 0
    for i in range(n):
        if hijo[i] is None:
            hijo[i] = resto[k]; k += 1
    return hijo


class CruzaFBS(Crossover):
    def __init__(self):
        super().__init__(2, 2)

    def _do(self, problem, X, **kwargs):
        rng = np.random.default_rng()
        _, n_matings, _ = X.shape
        Y = np.full((2, n_matings, 1), None, dtype=object)
        for k in range(n_matings):
            a, b = X[0, k, 0], X[1, k, 0]
            for s, (p, q) in enumerate(((a, b), (b, a))):
                perm = ox(p[0], q[0], rng)
                mask = rng.random(len(p[1])) < 0.5          # uniforme en los cortes
                cortes = np.where(mask, p[1], q[1]).astype(bool)
                if cortes.sum() < 2:
                    cortes[rng.choice(len(cortes), 2, replace=False)] = True
                orient = p[2] if rng.random() < 0.5 else q[2]
                Y[s, k, 0] = [perm, cortes, int(orient)]
        return Y


class MutacionFBS(Mutation):
    def _do(self, problem, X, **kwargs):
        rng = np.random.default_rng()
        for i in range(len(X)):
            perm, cortes, orient = X[i, 0]
            perm = list(perm)
            cortes = cortes.copy()
            for _ in range(rng.integers(1, 4)):             # intercambiar areas
                a, b = rng.choice(len(perm), 2, replace=False)
                perm[a], perm[b] = perm[b], perm[a]
            if rng.random() < 0.5:                          # mover un area
                a, b = rng.choice(len(perm), 2, replace=False)
                perm.insert(b, perm.pop(a))
            flip = rng.random(len(cortes)) < 0.08           # bit-flip en cortes
            cortes = np.where(flip, ~cortes, cortes)
            if cortes.sum() < 2:
                cortes[rng.choice(len(cortes), 2, replace=False)] = True
            if rng.random() < 0.10:                         # voltear orientacion
                orient = 1 - orient
            X[i, 0] = [perm, cortes, int(orient)]
        return X


class SinDuplicados(ElementwiseDuplicateElimination):
    def is_equal(self, a, b):
        ga, gb = a.X[0], b.X[0]
        return (ga[0] == gb[0]) and bool(np.array_equal(ga[1], gb[1])) and ga[2] == gb[2]


class ProblemaLayout(ElementwiseProblem):
    def __init__(self, bloques, rejilla):
        super().__init__(n_var=1, n_obj=3, n_ieq_constr=1)
        self.bloques = bloques
        self.rejilla = rejilla

    def _evaluate(self, x, out, *args, **kwargs):
        r = evaluar(x[0], self.bloques, self.rejilla)
        out["F"] = r["F"]
        out["G"] = [r["G"]]          # <= 0 es factible: dominancia restringida de Deb


def correr(pop=60, gen=40, h=2.0, semilla=1, verbose=True):
    bloques = catalogo_bloques()
    es_serv = [b.es_servicio for b in bloques]
    problema = ProblemaLayout(bloques, Rejilla(h))
    alg = NSGA2(
        pop_size=pop,
        sampling=MuestreoFBS(es_serv),
        crossover=CruzaFBS(),
        mutation=MutacionFBS(),
        eliminate_duplicates=SinDuplicados(),
    )
    res = minimize(problema, alg, ("n_gen", gen), seed=semilla,
                   verbose=verbose, save_history=True)
    return res, bloques


if __name__ == "__main__":
    import time
    t0 = time.time()
    res, bloques = correr(pop=40, gen=12)
    print("tiempo %.1f s" % (time.time() - t0))
    print("soluciones en el frente:", len(res.F) if res.F is not None else 0)
    if res.F is not None:
        print(np.round(res.F, 1))
