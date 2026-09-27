"""
Lectura del almacen de evaluaciones para la UI.

Sirve lo que YA se calculo; no calcula metricas nuevas. La unica excepcion es
la simulacion bajo demanda de un layout guardado, y esa se delega a la misma
maquinaria de trabajos que usa el resto de la API, para que lo que se ve
animado sea exactamente el mismo modelo que produjo los numeros de la tabla.

El recinto se reconstruye desde la tabla `casos`. Por eso la definicion del
caso incluye los muros rasterizados: sin ellos, la UI dibujaria una planta
vacia y el layout apareceria flotando sobre nada.
"""
import functools
import json
import os

import numpy as np
from fastapi import APIRouter, HTTPException
from scipy.stats import spearmanr

from . import servicio as S

import almacen as AL          # noqa: E402  (servicio ya puso nucleo en sys.path)

router = APIRouter(prefix="/api/resultados", tags=["resultados"])

# DOS OBJETIVOS, y solo dos.
#
#   f1        accesibilidad: cuanto camina la gente hasta el servicio
#   t_evac    tiempo de evacuacion, de la simulacion
#
# Se midieron otras y NO son objetivos, por una razon fisica y no de gusto: la
# densidad alta ya se castiga sola en el tiempo. Por Weidmann, donde la gente
# se apretuja camina mas lento, asi que el tiempo de evacuacion YA absorbe la
# congestion. Una metrica de densidad aparte no agrega un compromiso nuevo, es
# otra forma de mirar lo mismo. Se reportan como datos medidos, en una tabla.
METRICAS = [
    ("f1", "accesibilidad f\u2081", "m",
     "Distancia media que camina una persona hasta el modulo que la atiende, "
     "midiendo por donde se puede caminar y respetando que cada modulo atiende "
     "a un ritmo finito. Sale del problema de asignacion capacitada.",
     r"f_1=\sum_t w_t\,\bar d_t \Big/ \sum_t w_t"),
    ("t_des", "tiempo de evacuacion", "s",
     "Segundo en que el recinto queda vacio. Sale de la simulacion de fluido: "
     "es el instante en que la masa que queda adentro cae por debajo de la "
     "tolerancia de vaciado.",
     r"t_{\text{evac}}=\min\{t:\ M(t)\le \varepsilon\,M(0)\}"),
]

# Se miden y se reportan, pero no se optimizan ni se correlacionan.
DESCRIPTIVAS = [
    ("t95", "t\u2089\u2085 (95 % fuera)", "s",
     "Segundo en que ha salido el 95 % del aforo. Si queda lejos del tiempo "
     "total, es que un sector se rezago."),
    ("exposicion", "E exposicion", "m\u00b2\u00b7s",
     "Superficie por tiempo que estuvo por encima de la densidad a la que una "
     "persona pierde el movimiento propio."),
    ("rho_pico", "\u03c1 pico", "pers/m\u00b2",
     "Densidad maxima alcanzada en cualquier celda y momento."),
]
CV_MINIMO = 0.01      # por debajo de esto la metrica es constante en la practica


# =============================================================================
# utilidades
# =============================================================================
def _rects_de_mascara(m):
    """Mascara booleana -> lista minima de rectangulos por corridas de fila.

    La UI dibuja rectangulos, no rejillas. Unir las celdas contiguas de cada
    fila baja de ~80 rectangulos a 4 en el caso de ejemplo.
    """
    out = []
    ny, nx = m.shape
    for y in range(ny):
        x = 0
        while x < nx:
            if not m[y, x]:
                x += 1
                continue
            x0 = x
            while x < nx and m[y, x]:
                x += 1
            out.append({"x": x0, "y": y, "w": x - x0, "h": 1})
    # fusionar verticalmente lo que sea identico en x y ancho
    out.sort(key=lambda r: (r["x"], r["w"], r["y"]))
    fus = []
    for r in out:
        if (fus and fus[-1]["x"] == r["x"] and fus[-1]["w"] == r["w"]
                and fus[-1]["y"] + fus[-1]["h"] == r["y"]):
            fus[-1]["h"] += r["h"]
        else:
            fus.append(dict(r))
    return fus


@functools.lru_cache(maxsize=8)
def _caso_ui(caso):
    """Definicion del recinto en el formato que consume la UI."""
    with AL._con() as c:
        f = c.execute("SELECT * FROM casos WHERE caso=?", (caso,)).fetchone()
    if f is None:
        return None
    d = json.loads(f["json"])
    if "muros" not in d:
        # casos guardados antes de que se incluyeran: se reconstruye del nucleo
        import recinto as R
        rec = R.recinto_ejemplo(h=d.get("h", 1.0))
        d["muros"] = _rects_de_mascara(rec.muros)
    return {
        "nombre": f["nombre"],
        "recinto": {"W": d["W"], "H": d["H"],
                    "muros": d["muros"],
                    "salidas": [{"nombre": s[0], "lado": s[1],
                                 "centro": s[2], "ancho": s[3]}
                                for s in d["salidas"]]},
        "conteo": d.get("conteo", {}),
    }


def _frente(a, b):
    """Indices no dominados minimizando las dos columnas."""
    o = np.lexsort((b, a))
    fr, mejor = [], np.inf
    for i in o:
        if b[i] < mejor - 1e-12:
            fr.append(int(i))
            mejor = b[i]
    return fr


def _ic(x, y, n=400, semilla=0):
    """Intervalo al 95 % de rho por remuestreo. Pocas repeticiones: esto es para
    mirar en pantalla, no para la tesis -- ahi esta experimentos/analisis.py."""
    rng = np.random.default_rng(semilla)
    m = len(x)
    if m < 20:
        return None, None
    r = []
    for _ in range(n):
        s = rng.integers(0, m, m)
        if len(np.unique(x[s])) < 3 or len(np.unique(y[s])) < 3:
            continue
        v = spearmanr(x[s], y[s]).statistic
        if np.isfinite(v):
            r.append(v)
    if len(r) < 50:
        return None, None
    return float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


# =============================================================================
# endpoints
# =============================================================================
@router.get("/escenarios")
def escenarios():
    """Que hay guardado: una entrada por (caso, configuracion)."""
    cfgs = AL.leer_configs()
    filas = AL.consultar()
    grupos = {}
    for f in filas:
        c = cfgs.get(f["config"])
        if c is None:
            continue
        k = (f["caso"], f["config"])
        g = grupos.setdefault(k, {"caso": f["caso"], "config": f["config"],
                                  "cfg": c, "n": 0, "factibles": 0,
                                  "sin_f1": 0, "sin_t_des": 0})
        g["n"] += 1
        g["factibles"] += int(bool(f["factible"]))
        g["sin_f1"] += int(f["f1"] is None)
        g["sin_t_des"] += int(f["t_des"] is None)

    out = []
    for g in grupos.values():
        caso = _caso_ui(g["caso"]) or {}
        c = g["cfg"]
        out.append({
            "caso": g["caso"], "config": g["config"],
            "nombre_caso": caso.get("nombre", "?"),
            "experimento": c.get("exp", "?"),
            "modo": c.get("modo_muestreo", "?"),
            "aforo": c.get("aforo"),
            "reparto": c.get("reparto_inicial"),
            "n": g["n"], "factibles": g["factibles"],
            "sin_f1": g["sin_f1"], "sin_t_des": g["sin_t_des"],
            "cfg": c,
        })
    out.sort(key=lambda r: (r["modo"], r["aforo"] or 0))
    return out


_CACHE = {}


@router.get("/nube")
def nube(config: str, solo_factibles: bool = False):
    """Todos los puntos de un escenario, mas su analisis.

    Devuelve de una vez la nube, los frentes de Pareto, la matriz de rangos y la
    dispersion de cada metrica. Son la misma lectura de la base: partirlo en
    cuatro endpoints obligaria a la UI a mantenerlos sincronizados.

    Se memoriza porque los intervalos por remuestreo cuestan ~1 s y el usuario
    va a cambiar de escenario y volver. La llave incluye cuantas filas habia, de
    modo que si el barrido crece la respuesta se recalcula sola.
    """
    filas = [f for f in AL.consultar(config=config)
             if not solo_factibles or f["factible"]]
    ck = (config, solo_factibles, len(filas))
    if ck in _CACHE:
        return _CACHE[ck]
    if not filas:
        raise HTTPException(404, "no hay evaluaciones para esa configuracion")
    cfg = AL.leer_configs().get(config, {})

    puntos = []
    for f in filas:
        e = json.loads(f["extra"] or "{}")
        puntos.append({
            "llave": f["llave"], "i": e.get("i"),
            "f1": f["f1"], "t_des": f["t_des"], "t95": f["t95"],
            "exposicion": f["exposicion"], "rho_pico": f["rho_pico"],
            "factible": bool(f["factible"]), "violacion": f["violacion"],
            "ms": f["ms"],
            # el layout viaja con el punto: sin el, el motor del navegador no
            # podria abrir mas que los layouts que alguien precalculo
            "layout": json.loads(f["layout_json"]),
            "f1_detalle": e.get("f1_detalle", {}),
        })

    todas = METRICAS + [(k, n, u, e, "") for k, n, u, e in DESCRIPTIVAS]
    col = {m[0]: np.array([p[m[0]] if p[m[0]] is not None else np.nan
                           for p in puntos], dtype=float) for m in todas}
    validos = {k: np.isfinite(v) for k, v in col.items()}

    # --- dispersion: primero, porque decide que se puede correlacionar ---
    disp = []
    for k, nom, uni, expl, tex in todas:
        v = col[k][validos[k]]
        if v.size == 0:
            disp.append({"clave": k, "nombre": nom, "unidad": uni, "n": 0})
            continue
        cv = float(v.std() / abs(v.mean())) if v.mean() else 0.0
        disp.append({"clave": k, "nombre": nom, "unidad": uni, "n": int(v.size),
                     "media": float(v.mean()), "desv": float(v.std()),
                     "cv": cv, "min": float(v.min()), "max": float(v.max()),
                     "informa": bool(cv >= CV_MINIMO)})

    # la matriz de correlacion es SOLO entre objetivos: meter las
    # descriptivas daria correlaciones altas que no significan nada, porque
    # miden lo mismo que el tiempo por otra via
    objetivos = [m[0] for m in METRICAS]
    usables = [k for k in objetivos if any(d["clave"] == k and d.get("informa")
                                           for d in disp)]

    # --- matriz de rangos ---
    rho = [[None] * len(usables) for _ in usables]
    ics = [[None] * len(usables) for _ in usables]
    for a in range(len(usables)):
        for b in range(len(usables)):
            ka, kb = usables[a], usables[b]
            ok = validos[ka] & validos[kb]
            if a == b:
                rho[a][b] = 1.0
                continue
            if ok.sum() < 20:
                continue
            r = spearmanr(col[ka][ok], col[kb][ok]).statistic
            rho[a][b] = None if not np.isfinite(r) else float(r)
            if a < b:
                lo, hi = _ic(col[ka][ok], col[kb][ok])
                ics[a][b] = ics[b][a] = (None if lo is None else [lo, hi])

    # --- frentes de Pareto ---
    frentes = {}
    if "f1" in usables:
        for k in ("t_des",):
            if k not in usables:
                continue
            ok = validos["f1"] & validos[k]
            idx = np.where(ok)[0]
            fr = _frente(col["f1"][ok], col[k][ok])
            frentes[k] = {
                "llaves": [puntos[int(idx[i])]["llave"] for i in fr],
                # con dos objetivos independientes el numero esperado de no
                # dominados es el numero armonico; se manda para que la UI pueda
                # decir si el frente es mayor que el del puro azar
                "esperado_si_independientes":
                    float(np.sum(1.0 / np.arange(1, int(ok.sum()) + 1)))
                    if ok.sum() else 0.0,
            }

    caso = _caso_ui(filas[0]["caso"]) if filas else None
    r = {"config": config, "cfg": cfg, "n": len(puntos),
         "recinto": caso["recinto"] if caso else None,
         "puntos": puntos, "dispersion": disp,
         "metricas": [{"clave": k, "nombre": n, "unidad": u,
                       "explicacion": e, "tex": t}
                      for k, n, u, e, t in METRICAS],
         "descriptivas": [{"clave": k, "nombre": n, "unidad": u,
                           "explicacion": e}
                          for k, n, u, e in DESCRIPTIVAS],
         "usables": usables, "rho": rho, "ic": ics, "frentes": frentes,
         "cv_minimo": CV_MINIMO}
    _CACHE[ck] = r
    return r


@router.get("/layout/{llave}")
def layout(llave: str):
    """Un layout guardado, con su recinto y sus metricas, listo para dibujar."""
    with AL._con() as c:
        f = c.execute("SELECT * FROM evaluaciones WHERE llave=?",
                      (llave,)).fetchone()
    if f is None:
        raise HTTPException(404, "no existe esa evaluacion")
    f = dict(f)
    caso = _caso_ui(f["caso"])
    if caso is None:
        raise HTTPException(404, "el caso de esa evaluacion no esta registrado")
    extra = json.loads(f["extra"] or "{}")
    return {
        "llave": llave,
        "recinto": caso["recinto"],
        "nombre_caso": caso["nombre"],
        "layout": json.loads(f["layout_json"]),
        "cfg": AL.leer_configs().get(f["config"], {}),
        "modo": f["modo"], "semilla": f["semilla"], "i": extra.get("i"),
        "metricas": {k: f[k] for k in ("f1", "t_des", "t95", "exposicion",
                                       "rho_pico", "conservacion", "ms",
                                       "violacion")},
        "factible": bool(f["factible"]),
        "f1_detalle": extra.get("f1_detalle", {}),
    }


@router.post("/simular/{llave}")
def simular(llave: str, n_cuadros: int = 60):
    """Anima un layout guardado con los MISMOS parametros con que se midio.

    No se dejan elegir dt ni k_c: si se animara con otra discretizacion, la
    pelicula no correspoderia a los numeros de la tabla y la visualizacion
    dejaria de ser evidencia de nada.
    """
    d = layout(llave)
    cfg = d["cfg"]
    from . import esquemas as E
    pet = E.PeticionTrabajo(
        tipo="evacuacion",
        recinto=E.RecintoIn(**d["recinto"]),
        layout=[E.ColocacionIn(**c) for c in d["layout"]],
        conteo={},
        semilla=int(d["semilla"] or 0),
        escenario=E.Escenario(aforo=cfg.get("aforo", 4000),
                              distribucion=E.Distribucion(tipo="uniforme")),
        numerica=E.Numerica(h=cfg.get("h", 1.0), dt=cfg.get("dt", 0.3),
                            t_max=cfg.get("t_max", 600.0),
                            n_cuadros=n_cuadros),
        # se reproduce lo que se MIDIO. En la muestra amplia dos de cada tres
        # layouts no pasan la capa geometrica y aun asi tienen t_des medido: si
        # la animacion los rechazara, la tabla y la pelicula dirian cosas
        # distintas sobre el mismo layout.
        simular_infactible=True,
    )
    tid = S.lanzar(pet)
    return S.estado(tid)


@router.get("/csv")
def csv(config: str = None):
    """Ruta del CSV exportado, para citarlo en la tesis."""
    import os
    destino = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "datos", "export_ui.csv")
    n = AL.exportar_csv(destino, config=config)
    return {"filas": n, "ruta": destino}


# =============================================================================
# el frente real (barrido epsilon-restringido) y f1 dibujable
# =============================================================================
@router.get("/frente")
def frente_epsilon():
    """El frente trazado por barrido epsilon-restringido, con las trayectorias.

    No sale de la base sino de un JSON, porque no es una evaluacion por layout
    sino una corrida entera con su historia por generacion.
    """
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "datos", "frente_epsilon.json")
    if not os.path.exists(ruta):
        raise HTTPException(404, "todavia no se ha corrido experimentos/frente_epsilon.py")
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


@router.get("/acceso/{llave}")
def acceso(llave: str):
    """f1 ABIERTA EN CANAL: a que modulo le toca cada celda y a que distancia.

    Es lo que el numero f1 promedia. Dibujarlo importa porque ahi se ve lo que
    el promedio esconde: las regiones NO son las del modulo mas cercano. La
    capacidad deforma las fronteras, y esa deformacion es justamente lo que
    distingue esta formulacion de una de cercania simple.
    """
    import acceso as AC
    import geometria as G
    import recinto as R

    from . import esquemas as E
    d = layout(llave)
    rec = S.construir_recinto(E.RecintoIn(**d["recinto"]),
                              d["cfg"].get("h", 1.0))
    lay = [R.Colocacion(c["tipo"], c["x"], c["y"], c["rot"]) for c in d["layout"]]
    libre, _ = G.zona_ocupable(rec, lay)
    asg = AC.asignacion(rec, lay, libre, sigma=d["cfg"].get("f1_sigma", 1.0))

    salida = {"nx": rec.nx, "ny": rec.ny, "h": rec.h,
              "mascara_b64": S.cod(libre.astype(np.uint8)),
              "f1": d["metricas"].get("f1"), "tipos": {}}
    for tipo, info in asg.items():
        # a rejilla completa: 255 = celda sin dato (muro u obstaculo)
        quien = np.full((rec.ny, rec.nx), 255, dtype=np.uint8)
        quien[libre] = info["quien"].astype(np.uint8)
        dist = np.zeros((rec.ny, rec.nx))
        dist[libre] = np.where(np.isfinite(info["dist"]), info["dist"], 0.0)
        dmax = float(dist[libre].max()) if libre.any() else 1.0
        salida["tipos"][tipo] = {
            "quien_b64": S.cod(quien),
            "dist_b64": S.cod((np.clip(dist / max(dmax, 1e-9), 0, 1)
                               * 255).astype(np.uint8)),
            "dmax": dmax,
            "modulos": [int(i) for i in info["modulos"]],
            "carga": [round(float(x), 4) for x in info["carga"]],
            "capacidad": [round(float(x), 4) for x in info["capacidad"]],
            "d_media": round(float(info["d_media"]), 3),
        }
    return salida
