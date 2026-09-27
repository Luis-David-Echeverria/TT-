"""
CAMPO DE TIEMPOS DE LLEGADA (ecuacion Eikonal) y estimacion del aforo.

La ecuacion Eikonal:

        | grad T(x) | = 1 / v(x)          con   T = 0 en las salidas

En palabras: el tiempo de llegada crece a razon de uno sobre la velocidad local.
Donde la gente va lento, el tiempo se acumula rapido. La solucion T(x) dice,
para cada punto del recinto, cuantos segundos tarda en llegar a la salida mas
cercana. Y su gradiente da la direccion de movimiento: la gente camina hacia
donde T baja mas rapido.

Se resuelve con Fast Marching Method (Sethian, 1996), que avanza un frente desde
las salidas hacia adentro, mas lento en las zonas congestionadas. Implementacion:
scikit-fmm (backend en C).

Las celdas a las que el frente NUNCA llega quedan con T = infinito: son zonas
sin ruta a ninguna salida. Detectarlas es gratis y es informacion critica.
"""
import numpy as np
import skfmm

from parametros import V0, RHO_DISENO
from recinto import POR_CLAVE


def campo_tiempos(rec, libre, destino, velocidad=None):
    """Resuelve |grad T| = 1/v con T=0 en 'destino'.

    Devuelve T en segundos. Infinito donde no se puede llegar.
    """
    if not destino.any():
        return np.full(libre.shape, np.inf)
    alcanzable = libre | destino
    if velocidad is None:
        velocidad = np.full(libre.shape, V0)

    phi = np.ones(libre.shape)
    phi[destino] = -1.0
    phi = np.ma.MaskedArray(phi, ~alcanzable)
    v = np.ma.MaskedArray(np.maximum(velocidad, 1e-3), ~alcanzable)
    try:
        T = skfmm.travel_time(phi, v, dx=rec.h)
    except Exception:
        return np.full(libre.shape, np.inf)
    return np.ma.filled(T, np.inf)


def campo_a_salidas(rec, layout=None, velocidad=None):
    return campo_tiempos(rec, rec.libre(layout), rec.mascara_salidas(), velocidad)


def direccion(T, libre, h):
    """-grad T normalizado: hacia donde se mueve la gente en cada punto."""
    Tm = np.where(libre & np.isfinite(T), T, np.nan)
    gy, gx = np.gradient(np.nan_to_num(Tm, nan=0.0), h)
    mag = np.hypot(gx, gy)
    ok = libre & np.isfinite(Tm) & (mag > 1e-9)
    return (np.where(ok, -gx / np.maximum(mag, 1e-9), 0.0),
            np.where(ok, -gy / np.maximum(mag, 1e-9), 0.0))


# =============================================================================
# aforo
# =============================================================================
def diagnostico_area(rec, layout=None):
    """Area util del recinto, separando lo que SI tiene ruta a una salida.

    Sigue el orden pedido: primero FMM sobre el recinto con sus muros fijos
    (sin areas de servicio) para saber cuanto piso es realmente utilizable, y
    de paso detectar bolsas cerradas que el usuario haya creado al pintar.
    """
    from geometria import zona_ocupable
    libre, _ = zona_ocupable(rec, layout)
    T = campo_tiempos(rec, libre, rec.mascara_salidas())
    alcanzable = libre & np.isfinite(T)
    aislado = libre & ~np.isfinite(T)

    a_libre = float(libre.sum()) * rec.area_celda
    a_alc = float(alcanzable.sum()) * rec.area_celda
    a_ais = float(aislado.sum()) * rec.area_celda
    return {"T": T, "libre": libre, "alcanzable": alcanzable, "aislado": aislado,
            "area_libre": a_libre, "area_alcanzable": a_alc, "area_aislada": a_ais,
            "area_total": rec.W * rec.H}


def area_que_ocuparan(catalogo_conteo):
    """Area que van a robar las areas de servicio, antes de colocarlas.
    Sirve para estimar el aforo sin haber decidido todavia el layout."""
    return sum(POR_CLAVE[k].area * n for k, n in catalogo_conteo.items())


def estimar_aforo(rec, catalogo_conteo, rho_diseno=RHO_DISENO):
    """aforo = (area con ruta a salida - area que ocupan los servicios) x densidad

    Se usa la densidad de diseno y no el factor normativo m2/persona porque
    conecta directo con el regimen fisico que simula el modelo. El factor
    normativo debe usarse como CONTRASTE del resultado, no como entrada.
    """
    d = diagnostico_area(rec, layout=None)
    a_serv = area_que_ocuparan(catalogo_conteo)
    a_neta = max(0.0, d["area_alcanzable"] - a_serv)
    return {"aforo": a_neta * rho_diseno, "area_neta": a_neta,
            "area_servicios": a_serv, **d}


# =============================================================================
# isocronas (para dibujar)
# =============================================================================
def niveles_isocronas(T, n=12):
    finito = T[np.isfinite(T)]
    if finito.size == 0:
        return []
    return list(np.linspace(finito.min(), finito.max(), n + 2)[1:-1])


# =============================================================================
# distribucion inicial de la multitud
# =============================================================================
def distribucion_inicial(rec, ocupable, aforo, foco=None, escala=None):
    """Como esta repartida la gente al momento de iniciar la evacuacion.

    ES UNA DECISION DE MODELADO CRITICA, no un detalle. Medido en este trabajo:

      - Con el aforo repartido UNIFORME, el layout es casi irrelevante para el
        tiempo de evacuacion (< 1 % de diferencia entre un layout disperso y una
        barrera deliberada). Con todo el mundo repartido, siempre hay una salida
        cerca y el tiempo lo fija la capacidad de las puertas.
      - Con la multitud CONCENTRADA frente al escenario -- la situacion real de
        un concierto -- la diferencia sube a 5-15 %, porque toda la masa tiene
        que cruzar la misma region para alcanzar las salidas.

    O sea: el supuesto "uniforme" NO es el peor caso, es el que menos
    discrimina. Usarlo haria parecer que el layout no importa.

    foco:   (x, y) del punto de atraccion (tipicamente el escenario).
            None -> reparto uniforme.
    escala: longitud de decaimiento en metros. Es un DATO DEL EVENTO (que tan
            apretado se pone el publico hacia el frente), no una constante
            universal: debe venir de aforos medidos de eventos comparables.
    """
    from parametros import RHO_MAX
    if foco is None:
        n = int(ocupable.sum())
        return np.where(ocupable, aforo / max(n, 1), 0.0)

    m_max = (RHO_MAX - 1e-3) * rec.area_celda
    cap_total = m_max * int(ocupable.sum())
    if aforo > cap_total:
        raise ValueError(
            "El aforo (%.0f) no cabe ni a densidad de atasco en %.0f m2 "
            "(cabrian %.0f). Baja el aforo o la densidad de diseno."
            % (aforo, ocupable.sum() * rec.area_celda, cap_total))

    d = np.hypot(rec.X - foco[0], rec.Y - foco[1])
    w = np.where(ocupable, np.exp(-d / float(escala)), 0.0)
    M = w / w.sum() * aforo

    # Saturacion: nadie puede estar por encima de la densidad de atasco. Lo que
    # no cabe adelante se recorre hacia atras, que es lo que pasa de verdad.
    for _ in range(200):
        exceso = np.maximum(M - m_max, 0.0)
        tot = float(exceso.sum())
        if tot < 1e-9:
            break
        M = np.minimum(M, m_max)
        hueco = np.where(ocupable, np.maximum(m_max - M, 0.0), 0.0)
        if hueco.sum() <= 1e-12:
            break
        M = M + hueco / hueco.sum() * tot
    return np.minimum(M, m_max)
