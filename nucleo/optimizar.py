"""
Optimizador de una sola funcion objetivo: tiempo de evacuacion.

Todavia NO es NSGA-II. El plan acordado es primero averiguar si el problema es
genuinamente multiobjetivo (barriendo pesos sobre una suma ponderada) antes de
montar un algoritmo multiobjetivo. Esta pieza resuelve el caso de un objetivo,
que es el ladrillo de ese barrido.

Estrategia evolutiva (mu + lambda) sobre colocacion directa:
  - individuo  = lista de Colocacion (x, y, rotacion por area de servicio)
  - mutacion   = desplazar un area y/o girarla
  - reparacion = por rechazo contra la capa geometrica

La capa geometrica actua como filtro duro ANTES de simular: un layout ilegal se
descarta sin gastar una sola evacuacion. Eso es lo que hace viable el ciclo.
"""
import numpy as np

from recinto import Colocacion, POR_CLAVE, cuantizar
from geometria import evaluar as evaluar_geom
from fluido import simular


def _muta(layout, rec, rng, sigma):
    """Desplaza y/o gira una o dos areas. Devuelve None si no logra ser legal."""
    for _ in range(60):
        nuevo = [Colocacion(c.tipo, c.x, c.y, c.rot) for c in layout]
        for _ in range(int(rng.integers(1, 3))):
            k = int(rng.integers(len(nuevo)))
            c = nuevo[k]
            if rng.random() < 0.22:
                c.rot = 1 - c.rot
            t = POR_CLAVE[c.tipo]
            w, f = (t.ancho, t.fondo) if c.rot == 0 else (t.fondo, t.ancho)
            c.x = cuantizar(np.clip(c.x + rng.normal(0, sigma), 0, rec.W - w))
            c.y = cuantizar(np.clip(c.y + rng.normal(0, sigma), 0, rec.H - f))
        if evaluar_geom(rec, nuevo, corto=True)["factible"]:
            return nuevo
    return None


def llave(rec, layout):
    """Identidad de un layout PARA EL SIMULADOR: la mascara de obstaculos ya
    rasterizada.

    Es la llave correcta y no las coordenadas. Dos acomodos que difieren en
    menos de una celda ocupan exactamente las mismas celdas, dan exactamente el
    mismo resultado, y por tanto son el MISMO caso aunque sus coordenadas no
    coincidan. Cuantizar las posiciones mas fino que la celda genera llaves
    distintas para casos identicos, y la cache nunca acierta (medido: 0 %).
    """
    import hashlib
    return hashlib.blake2b(rec.obstaculos(layout).tobytes(), digest_size=16).digest()


class Memo:
    """Cache de la funcion objetivo.

    En generaciones tardias la poblacion converge y las mutaciones caen una y
    otra vez sobre acomodos ya evaluados. Sin cuantizar las posiciones esto no
    serviria de nada: dos posiciones en punto flotante casi nunca coinciden.
    """

    __slots__ = ("tabla", "aciertos", "fallos")

    def __init__(self):
        self.tabla, self.aciertos, self.fallos = {}, 0, 0

    def get(self, rec, layout):
        v = self.tabla.get(llave(rec, layout))
        if v is None:
            self.fallos += 1
        else:
            self.aciertos += 1
        return v

    def set(self, rec, layout, valor):
        self.tabla[llave(rec, layout)] = valor

    @property
    def tasa(self):
        n = self.aciertos + self.fallos
        return self.aciertos / n if n else 0.0


def t_evac(rec, layout, aforo, M0=None, dt=0.5, t_max=2500.0):
    # parar_en_pct=95: el objetivo es t95, seguir simulando despues no aporta
    r = simular(rec, layout, aforo, dt=dt, t_max=t_max, n_cuadros=6, M0=M0,
                parar_en_pct=95.0)
    if r is None or r["t95"] is None:
        return t_max * 2.0
    return r["t95"]


def optimizar(rec, semillas, aforo, M0=None, mu=5, lam=10, generaciones=12,
              sigma0=9.0, rng=None, verbose=True, callback=None, dt=0.5,
              t_max=2500.0, memo=None):
    """(mu + lambda) minimizando el tiempo de evacuacion.

    sigma decae con las generaciones: exploracion amplia al principio, ajuste
    fino al final.
    """
    rng = rng or np.random.default_rng(0)
    # MISMO dt que usara la simulacion final: si difieren, el 'antes' y el
    # 'despues' se miden en escalas distintas y la mejora reportada es falsa.
    pob = [(ev(s), s) for s in semillas[:mu]]
    pob.sort(key=lambda z: z[0])
    historia = [pob[0][0]]
    evals = len(pob)

    for g in range(generaciones):
        sigma = sigma0 * (1.0 - 0.75 * g / max(1, generaciones - 1))
        hijos = []
        while len(hijos) < lam:
            _, padre = pob[int(rng.integers(len(pob)))]
            h = _muta(padre, rec, rng, sigma)
            if h is not None:
                hijos.append(h)
        for h in hijos:
            pob.append((ev(h), h))
            evals += 1
        pob.sort(key=lambda z: z[0])
        pob = pob[:mu]
        historia.append(pob[0][0])
        if verbose:
            print("  gen %2d  sigma %4.1f m   mejor t95 = %6.1f s" % (g + 1, sigma, pob[0][0]))
        if callback is not None:
            callback(g, pob[0][0])
    return {"mejor": pob[0][1], "t_mejor": pob[0][0], "historia": historia,
            "evaluaciones": evals, "poblacion": pob, "memo": memo,
            "tasa_cache": memo.tasa}


# =============================================================================
# evaluacion en paralelo
# =============================================================================
# Los algoritmos poblacionales son vergonzosamente paralelos: los individuos de
# una generacion no dependen entre si. Este es el mayor acelerador disponible, y
# escala con nucleos -- no con GPU (ver nota al final del archivo).
_W = {}


def _init_worker(rec, aforo, M0, dt, t_max):
    _W.update(rec=rec, aforo=aforo, M0=M0, dt=dt, t_max=t_max)


def _eval_worker(layout):
    return t_evac(_W["rec"], layout, _W["aforo"], _W["M0"],
                  dt=_W["dt"], t_max=_W["t_max"])


def optimizar_par(rec, semillas, aforo, M0=None, mu=5, lam=10, generaciones=12,
                  sigma0=9.0, rng=None, callback=None, dt=0.5, t_max=2500.0,
                  trabajadores=None, memo=None):
    """Igual que optimizar(), pero evaluando cada generacion en paralelo."""
    from concurrent.futures import ProcessPoolExecutor
    import os

    rng = rng or np.random.default_rng(0)
    memo = memo if memo is not None else Memo()
    n = trabajadores or max(1, (os.cpu_count() or 4) - 1)

    with ProcessPoolExecutor(max_workers=n, initializer=_init_worker,
                             initargs=(rec, aforo, M0, dt, t_max)) as pool:
        def evaluar_lote(lista):
            """Solo se mandan a los procesos los acomodos que la cache no tiene,
            y de esos, solo uno por cada llave repetida dentro del mismo lote."""
            pendientes, indices = [], {}
            salida = [None] * len(lista)
            for i, L in enumerate(lista):
                v = memo.get(rec, L)
                if v is not None:
                    salida[i] = v
                    continue
                k = llave(rec, L)
                if k in indices:
                    indices[k].append(i)
                else:
                    indices[k] = [i]
                    pendientes.append(L)
            if pendientes:
                for L, v in zip(pendientes, pool.map(_eval_worker, pendientes)):
                    memo.set(rec, L, v)
                    for i in indices[llave(rec, L)]:
                        salida[i] = v
            return salida

        pob = list(zip(evaluar_lote(semillas[:mu]), semillas[:mu]))
        pob.sort(key=lambda z: z[0])
        historia, evals = [pob[0][0]], len(pob)

        for g in range(generaciones):
            sigma = sigma0 * (1.0 - 0.75 * g / max(1, generaciones - 1))
            hijos = []
            while len(hijos) < lam:
                _, padre = pob[int(rng.integers(len(pob)))]
                h = _muta(padre, rec, rng, sigma)
                if h is not None:
                    hijos.append(h)
            for t, h in zip(evaluar_lote(hijos), hijos):
                pob.append((t, h))
                evals += 1
            pob.sort(key=lambda z: z[0])
            pob = pob[:mu]
            historia.append(pob[0][0])
            if callback is not None:
                callback(g, pob[0][0])

    return {"mejor": pob[0][1], "t_mejor": pob[0][0], "historia": historia,
            "evaluaciones": evals, "poblacion": pob, "trabajadores": n,
            "memo": memo, "tasa_cache": memo.tasa,
            "simulaciones": memo.fallos}
