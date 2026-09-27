"""
Puente entre la API y el nucleo del modelo.

Aqui vive TODO lo que traduce entre el contrato HTTP y las estructuras de
`nucleo/`. Si manana cambia el solver, cambia este archivo y no el contrato.
"""
import base64
import sys
import os
import threading
import uuid

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "nucleo"))

import parametros as P          # noqa: E402
import recinto as R             # noqa: E402
import geometria as G           # noqa: E402
import campos as C              # noqa: E402
import fluido as F              # noqa: E402
import optimizar as O           # noqa: E402
import viz as V                 # noqa: E402


# =============================================================================
# codificacion de campos
# =============================================================================
def cod(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")


def campo_u8(arr, mascara, vmin=None, vmax=None):
    """Cuantiza un campo escalar a uint8 para transporte.

    256 niveles sobre el rango fisico sobran para dibujar (con rho_max = 5.4 da
    una resolucion de 0.02 pers/m2). Las METRICAS nunca salen de aqui: se
    calculan en Python sobre el campo en doble precision.
    """
    v = np.asarray(arr, dtype=float)
    fin = mascara & np.isfinite(v)
    vmin = float(vmin if vmin is not None else (v[fin].min() if fin.any() else 0.0))
    vmax = float(vmax if vmax is not None else (v[fin].max() if fin.any() else 1.0))
    if vmax <= vmin:
        vmax = vmin + 1e-9
    q = np.clip((v - vmin) / (vmax - vmin), 0, 1)
    q = np.where(fin, q, 0.0)
    return {"nx": int(v.shape[1]), "ny": int(v.shape[0]), "h": 0.0,
            "vmin": vmin, "vmax": vmax,
            "datos_b64": cod((q * 255).astype(np.uint8)),
            "mascara_b64": cod(fin.astype(np.uint8))}


def dir_u8(u):
    """Direccion en [-1,1] -> uint8 centrado en 128."""
    return cod(np.clip((np.nan_to_num(u) * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8))


# =============================================================================
# construccion desde el contrato
# =============================================================================
def construir_recinto(rin, h):
    rec = R.Recinto(W=rin.W, H=rin.H, h=h,
                    salidas=[R.Salida(s.nombre, s.lado, s.centro, s.ancho)
                             for s in rin.salidas])
    for m in rin.muros:
        rec.pintar_muro((m.x, m.y, m.w, m.h))
    return rec


def construir_layout(lin):
    return [R.Colocacion(c.tipo, c.x, c.y, c.rot) for c in lin]


def _rect(t):
    return {"x": t[0], "y": t[1], "w": t[2], "h": t[3]}


# =============================================================================
# catalogo y metadatos que la UI necesita para dibujar
# =============================================================================
def catalogo():
    stops = []
    cm = V.cmap_densidad()
    for f in np.linspace(0, 1, 96):   # fino: la paleta tiene quiebres marcados
        r, g, b, _ = cm(float(f))
        stops.append({"t": round(float(f), 4),
                      "c": "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))})
    return {
        "areas": [{"clave": t.clave, "nombre": t.nombre, "ancho": t.ancho,
                   "fondo": t.fondo, "area": t.area, "color": t.color}
                  for t in R.CATALOGO],
        "paleta_densidad": stops,
        "rho_max": P.RHO_MAX,
        "rho_perdida_control": P.RHO_PERDIDA_CONTROL,
        "q_max": F.Q_MAX,
        "rho_cap": F.RHO_CAP,
        "v0": P.V0,
        "parametros": [
            {"clave": k, "simbolo": s, "valor": v, "unidad": u,
             "estado": e, "fuente": f, "nota": n}
            for (k, s, v, u, e, f, n) in P.tabla()],
        "pendientes": P.pendientes(),
    }


# =============================================================================
# operaciones sincronas (baratas)
# =============================================================================
def geometria(pet):
    rec = construir_recinto(pet.recinto, P.H_CELDA)
    lay = construir_layout(pet.layout)
    res = G.evaluar(rec, lay, corto=False)
    pasos = []
    for p in res["pasos"]:
        culp = set(p["detalle"].get("culpables", []))
        for a, b in p["detalle"].get("pares", []):
            culp |= {a, b}
        pasos.append({"nombre": p["nombre"], "violacion": p["violacion"],
                      "culpables": sorted(culp)})
    return {"factible": res["factible"], "violacion": res["violacion"],
            "pasos": pasos,
            "conos": [_rect(c) for _, c in G.conos_salida(rec)]}


def aforo(pet):
    rec = construir_recinto(pet.recinto, P.H_CELDA)
    lay = construir_layout(pet.layout)
    rho_d = pet.densidad_diseno or P.RHO_DISENO
    d = C.diagnostico_area(rec, lay if lay else None)
    a_serv = C.area_que_ocuparan(pet.conteo)
    a_neta = max(0.0, d["area_alcanzable"] - a_serv)
    Wu = rec.ancho_total_salidas(P.CAPA_LIMITE)
    af = a_neta * rho_d
    return {"area_total": d["area_total"], "area_ocupable": d["area_alcanzable"],
            "area_aislada": d["area_aislada"], "area_servicios": a_serv,
            "area_neta": a_neta, "densidad_diseno": rho_d, "aforo": af,
            "ancho_util_salidas": Wu,
            "cota_puertas_s": af / (P.J_ESPECIFICO * Wu) if Wu > 0 else float("inf")}


def campo(pet):
    rec = construir_recinto(pet.recinto, pet.numerica.h)
    lay = construir_layout(pet.layout)
    oc, _ = G.zona_ocupable(rec, lay if lay else None)
    T = C.campo_tiempos(rec, oc, rec.mascara_salidas())
    fin = oc & np.isfinite(T)
    tmax = float(T[fin].max()) if fin.any() else 0.0
    ux, uy = C.direccion(T, oc, rec.h)
    c = campo_u8(T, fin, 0.0, tmax)
    c["h"] = rec.h
    niveles = list(np.linspace(0, tmax, pet.n_isocronas + 1)[1:]) if tmax > 0 else []
    return {"tiempos": c, "isocronas": [float(x) for x in niveles],
            "dir_x_b64": dir_u8(ux), "dir_y_b64": dir_u8(uy), "t_max_s": tmax}


def proponer(pet):
    """Coloca al azar las areas pedidas, respetando la capa geometrica.

    Muestreo por rechazo: se propone una posicion, se verifica contra las reglas
    duras y se reintenta si no pasa. El usuario solo dice CUANTAS quiere; donde
    van lo decide el sistema.
    """
    rec = construir_recinto(pet.recinto, P.H_CELDA)
    rng = np.random.default_rng(pet.semilla)
    lay = R.layout_factible(rec, rng, pet.conteo)
    if lay is None:
        return {"layout": [], "intentos": 0, "logrado": False,
                "mensaje": "no caben todas las areas pedidas con las reglas "
                           "actuales: reduce la cantidad o libera muros"}
    return {"layout": [{"tipo": c.tipo, "x": round(c.x, 2), "y": round(c.y, 2),
                        "rot": c.rot} for c in lay],
            "intentos": len(lay), "logrado": True, "mensaje": ""}


# =============================================================================
# trabajos asincronos
# =============================================================================
TRABAJOS: dict = {}
_LOCK = threading.Lock()


def _nuevo(tipo):
    tid = uuid.uuid4().hex[:12]
    with _LOCK:
        TRABAJOS[tid] = {"id": tid, "tipo": tipo, "estado": "encolado",
                         "progreso": 0.0, "mensaje": "", "resultado": None}
    return tid


def _act(tid, **kw):
    with _LOCK:
        if tid in TRABAJOS:
            TRABAJOS[tid].update(kw)


def estado(tid):
    with _LOCK:
        return TRABAJOS.get(tid)


def _semillas(pet, n=2):
    """Deriva n flujos independientes de UNA sola semilla.

    SeedSequence.spawn garantiza que los flujos no se correlacionen entre si,
    cosa que no ocurre si uno simplemente usa semilla, semilla+1, semilla+2...
    Asi el experimento queda descrito por un solo numero.
    """
    return [np.random.default_rng(x)
            for x in np.random.SeedSequence(int(pet.semilla)).spawn(n)]


def _prepara(pet):
    rec = construir_recinto(pet.recinto, pet.numerica.h)
    lay = construir_layout(pet.layout)
    rng_lay, _ = _semillas(pet)
    if not lay and pet.conteo:
        # El usuario solo dijo CUANTAS areas quiere. Donde van lo decide el
        # sistema, por muestreo con rechazo contra la capa geometrica.
        lay = R.layout_factible(rec, rng_lay, pet.conteo)
        if lay is None:
            raise ValueError(
                "no caben todas las areas pedidas: reduce la cantidad, "
                "libera muros o ensancha el recinto")
    oc, _ = G.zona_ocupable(rec, lay)
    dis = pet.escenario.distribucion
    foco = None
    if dis.tipo == "concentrada":
        foco = tuple(dis.foco) if dis.foco else (rec.W / 2.0, rec.H - 2.0)
    M0 = C.distribucion_inicial(rec, oc, pet.escenario.aforo,
                                foco=foco, escala=dis.escala)
    dt = pet.numerica.dt or (0.3 if pet.numerica.h <= 1.0 else 0.5)
    return rec, lay, oc, M0, dt


def _config(pet, dt):
    """Todo lo necesario para repetir el experimento. Va en el resultado para
    que quede registrado junto con los numeros que produjo."""
    d = pet.escenario.distribucion
    return {
        "semilla": pet.semilla,
        "generaciones": pet.opciones.generaciones,
        "mu": pet.opciones.mu,
        "lam": pet.opciones.lam,
        "sigma0": pet.opciones.sigma0,
        "h": pet.numerica.h,
        "dt": dt,
        "aforo": pet.escenario.aforo,
        "distribucion": d.tipo,
        "escala": d.escala if d.tipo == "concentrada" else None,
        "conteo": dict(pet.conteo),
        "version_modelo": "0.1",
    }


def _empaqueta_sim(rec, r):
    cuadros = [campo_u8(c, r["libre"], 0.0, P.RHO_MAX)["datos_b64"] for c in r["cuadros"]]
    dirs = [{"x": dir_u8(ux), "y": dir_u8(uy)} for ux, uy in r["dirs"]]
    return {
        "nx": rec.nx, "ny": rec.ny, "h": rec.h,
        "rho_max": P.RHO_MAX,
        "mascara_b64": cod(r["libre"].astype(np.uint8)),
        "cuadros_b64": cuadros,
        "direcciones": dirs,
        "t": [float(x) for x in r["t"]],
        "pct": [float(x) for x in r["pct"]],
        "t95": r["t95"],
        "evacuado_final": r["evacuado_final"],
    }


def _correr(tid, pet):
    try:
        _act(tid, estado="corriendo", mensaje="verificando capa geometrica")
        rec, lay, oc, M0, dt = _prepara(pet)
        geo = G.evaluar(rec, lay, corto=True)
        if not geo["factible"] and not pet.simular_infactible:
            fallo = next((p["nombre"] for p in geo["pasos"] if p["violacion"] > 0), "?")
            _act(tid, estado="error",
                 mensaje="layout infactible: %s (no se simula)" % fallo)
            return

        if pet.tipo == "evacuacion":
            _act(tid, progreso=0.2, mensaje="resolviendo evacuacion")
            r = F.simular(rec, lay, pet.escenario.aforo, dt=dt,
                          t_max=pet.numerica.t_max, n_cuadros=pet.numerica.n_cuadros,
                          M0=M0, guardar_campos=True)
            _act(tid, estado="listo", progreso=1.0, mensaje="listo",
                 resultado=_empaqueta_sim(rec, r))

        elif pet.tipo == "optimizacion":
            op = pet.opciones
            gens = op.generaciones
            _, rng = _semillas(pet)
            _act(tid, progreso=0.05, mensaje="sembrando")
            sem = [lay] + [l for l in (R.layout_factible(rec, rng) for _ in range(5)) if l]

            hist = []

            def paso_gen(g, mejor):
                hist.append(mejor)
                _act(tid, progreso=0.05 + 0.85 * (g + 1) / gens,
                     mensaje="generacion %d/%d — mejor t95 = %.1f s" % (g + 1, gens, mejor))

            res = O.optimizar_par(rec, sem, pet.escenario.aforo, M0=M0,
                                  mu=op.mu, lam=op.lam, sigma0=op.sigma0,
                                  generaciones=gens, rng=rng,
                                  callback=paso_gen, dt=dt, t_max=pet.numerica.t_max)
            _act(tid, progreso=0.95, mensaje="simulando el mejor")
            r = F.simular(rec, res["mejor"], pet.escenario.aforo, dt=dt,
                          t_max=pet.numerica.t_max, n_cuadros=pet.numerica.n_cuadros,
                          M0=M0, guardar_campos=True)
            out = _empaqueta_sim(rec, r)
            out["layout"] = [{"tipo": c.tipo, "x": c.x, "y": c.y, "rot": c.rot}
                             for c in res["mejor"]]
            out["historia"] = [float(x) for x in res["historia"]]
            out["t_inicial"] = float(res["historia"][0])
            out["evaluaciones"] = res["evaluaciones"]
            _act(tid, estado="listo", progreso=1.0, mensaje="listo", resultado=out)
        elif pet.tipo == "comparacion":
            # Lo que el usuario realmente quiere ver: el layout que el sistema
            # propuso al azar, contra el que sale de optimizarlo, lado a lado y
            # con el mismo reloj.
            op = pet.opciones
            gens = op.generaciones
            _, rng = _semillas(pet)

            _act(tid, progreso=0.05, mensaje="simulando el layout inicial")
            r_ini = F.simular(rec, lay, pet.escenario.aforo, dt=dt,
                              t_max=pet.numerica.t_max,
                              n_cuadros=pet.numerica.n_cuadros, M0=M0,
                              guardar_campos=True)

            sem = [lay] + [l for l in (R.layout_factible(rec, rng) for _ in range(5)) if l]

            def paso_gen(g, mejor):
                _act(tid, progreso=0.15 + 0.70 * (g + 1) / gens,
                     mensaje="generación %d/%d — mejor t95 = %.1f s" % (g + 1, gens, mejor))

            res = O.optimizar_par(rec, sem, pet.escenario.aforo, M0=M0,
                                  mu=op.mu, lam=op.lam, sigma0=op.sigma0,
                                  generaciones=gens, rng=rng, callback=paso_gen,
                                  dt=dt, t_max=pet.numerica.t_max)

            _act(tid, progreso=0.92, mensaje="simulando el layout optimizado")
            r_opt = F.simular(rec, res["mejor"], pet.escenario.aforo, dt=dt,
                              t_max=pet.numerica.t_max,
                              n_cuadros=pet.numerica.n_cuadros, M0=M0,
                              guardar_campos=True)

            _act(tid, estado="listo", progreso=1.0, mensaje="listo", resultado={
                "inicial": {"layout": [{"tipo": c.tipo, "x": c.x, "y": c.y, "rot": c.rot}
                                       for c in lay],
                            "sim": _empaqueta_sim(rec, r_ini)},
                "optimizado": {"layout": [{"tipo": c.tipo, "x": c.x, "y": c.y, "rot": c.rot}
                                          for c in res["mejor"]],
                               "sim": _empaqueta_sim(rec, r_opt)},
                "historia": [float(x) for x in res["historia"]],
                "evaluaciones": res["evaluaciones"],
                "trabajadores": res.get("trabajadores", 1),
                "config": _config(pet, dt),
            })

        else:
            _act(tid, estado="error", mensaje="tipo de trabajo desconocido")
    except Exception as e:  # noqa: BLE001
        _act(tid, estado="error", mensaje="%s: %s" % (type(e).__name__, e))


def lanzar(pet):
    tid = _nuevo(pet.tipo)
    threading.Thread(target=_correr, args=(tid, pet), daemon=True).start()
    return tid
