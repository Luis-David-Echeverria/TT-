"""
Las tres funciones objetivo + la capa 1 (estancamiento).

  f1  accesibilidad   -> solo geometria (velocidad libre). NO usa el fluido.
  f2  congestion      -> punto fijo del fluido, p95 de densidad, max entre escenarios
  f3  evacuacion      -> escenario dinamico
  capa 1              -> restriccion dura binaria: se atasca o no
"""
import numpy as np

from recinto import (ESCENARIO, SALIDAS, DEMANDA, ASISTENTES, Rejilla,
                     catalogo_bloques)
from modelo import (V0, RHO_MAX, RHO_JAM, weidmann, decode, violaciones_geom,
                    Escena)
from fluido import tiempo_evacuacion

FLUJO_ESPECIFICO = 1.3     # pers/(s*m) de ancho de salida -- cota de capacidad
T_COLA_REF = 300.0         # s de cola cuando una instalacion esta al 100% sobre cupo
EPS_FACTIBLE = 0.25        # tolerancia constructiva: no colocas un puesto al centimetro


def ancho_total_salidas():
    tot = 0.0
    for _, (x, y, w, h), lado in SALIDAS:
        tot += w if lado in ("sur", "norte") else h
    return tot


# --- f1: accesibilidad (velocidad libre + asignacion capacitada) -------------
def f1_accesibilidad(esc, bloques, p):
    """Tiempo medio al servicio mas cercano de cada tipo, ponderado por demanda.
    Se calcula a velocidad libre a proposito: asi f1 mide geometria pura y no
    se traslapa con f2."""
    vlib = np.full(esc.g.X.shape, V0)
    total = 0.0
    for tipo, frac in DEMANDA.items():
        insts = [b for b in bloques if b.es_servicio and b.tipo == tipo]
        if not insts:
            continue
        Ts, caps = [], []
        for b in insts:
            m = esc.g.mascara_rect(esc.rects[b.bid])
            Ts.append(esc.campo(m, vlib))
            caps.append(b.cap)
        Ts = np.stack(Ts)
        Ts = np.nan_to_num(Ts, posinf=1e5, nan=1e5)
        cercana = np.argmin(Ts, axis=0)
        Tmin = np.min(Ts, axis=0)

        # asignacion capacitada: carga por instalacion -> tiempo de cola
        dem = p * frac
        cola = np.zeros(len(insts))
        for k in range(len(insts)):
            carga = dem[(cercana == k) & esc.libre].sum()
            if caps[k] > 0:
                cola[k] = max(0.0, carga - caps[k]) / caps[k] * T_COLA_REF
        Tefec = Tmin + cola[cercana]

        w = dem * esc.libre
        if w.sum() > 0:
            total += frac * float((Tefec * w).sum() / w.sum())
    return total


# --- f2 / capa 1: escenarios de fluido --------------------------------------
def escenario_operacion(esc):
    dest = [(esc.tipos[t], DEMANDA[t]) for t in esc.tipos if esc.tipos[t].any()]
    if not dest:
        return None
    return esc.punto_fijo(dest, horizonte=420.0, n_iter=4)


def escenario_evacuacion(esc):
    if not esc.salidas.any():
        return None
    return esc.punto_fijo([(esc.salidas, 1.0)], horizonte=240.0, n_iter=4)


def f2_congestion(rhos):
    """p95 sobre celdas, MAXIMO entre escenarios: el riesgo es del peor instante."""
    return max(float(np.percentile(r[m], 95)) for r, m in rhos)


def violacion_estancamiento(rhos):
    """Capa 1. Dura y binaria en concepto, medida en grado para guiar la busqueda."""
    v = 0.0
    for r, m in rhos:
        v += float(np.maximum(r[m] - RHO_JAM, 0.0).sum()) * 0.01
    return v


# --- f3: evacuacion ----------------------------------------------------------
def f3_evacuacion(esc, p):
    """Tiempo hasta que ha salido el 95 % de la masa, con el transporte CTM.

    La version anterior era max(tiempo_geodesico, cota_por_capacidad) y estaba
    MAL: con la instancia actual la cota dominaba siempre, asi que f3 daba el
    mismo numero para todos los layouts y el optimizador corria de hecho con dos
    objetivos, no tres.
    """
    return tiempo_evacuacion(esc, p)


# --- evaluacion completa de un individuo ------------------------------------
def evaluar(genoma, bloques, rejilla, detallado=False):
    """Pipeline: decode -> capa 0 -> fluido -> capa 1 -> objetivos."""
    rects = decode(genoma, bloques)

    # CAPA 0a: geometria sobre los rectangulos. Microsegundos, sin rasterizar.
    g0 = violaciones_geom(rects, bloques)
    if g0 > EPS_FACTIBLE and not detallado:
        return dict(F=[1e5, 1e3, 1e5], G=g0, factible=False)

    esc = Escena(rejilla, rects, bloques)
    if not esc.salidas.any():
        return dict(F=[1e5, 1e3, 1e5], G=g0 + 100.0, factible=False)

    # CAPA 0b: despeje normativo + conectividad. Milisegundos, sigue sin simular.
    g0 += esc.violacion_despeje() * 0.05
    if g0 > EPS_FACTIBLE and not detallado:
        return dict(F=[1e5, 1e3, 1e5], G=g0, factible=False)

    op = escenario_operacion(esc)
    ev = escenario_evacuacion(esc)
    if op is None or ev is None:
        return dict(F=[1e5, 1e3, 1e5], G=g0 + 100.0, factible=False)

    rho_op, v_op, campos_op, p = op
    rho_ev, v_ev, campos_ev, _ = ev

    rhos = [(rho_op, esc.libre), (rho_ev, esc.libre)]
    g1 = violacion_estancamiento(rhos)

    f1 = f1_accesibilidad(esc, bloques, p)
    f2 = f2_congestion(rhos)
    f3 = f3_evacuacion(esc, p)

    gtot = max(0.0, g0 + g1 - EPS_FACTIBLE)
    r = dict(F=[f1, f2, f3], G=gtot, factible=gtot <= 0)
    if detallado:
        r.update(esc=esc, rects=rects, rho_op=rho_op, v_op=v_op, rho_ev=rho_ev,
                 v_ev=v_ev, T_ev=campos_ev[0], campos_op=campos_op, p=p, g0=g0, g1=g1)
    return r
