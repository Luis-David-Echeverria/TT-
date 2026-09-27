"""
Transporte real de la multitud: modelo de transmision de celdas (CTM).

Es el esquema de Godunov para la ley de conservacion LWR aplicada a peatones.
La idea clave, y la razon por la que un esquema ingenuo se atora:

  una celda no puede ENVIAR mas de lo que su densidad y velocidad permiten,
  y sobre todo, una celda no puede RECIBIR mas de lo que le cabe.

Sin la segunda condicion la masa se apila sin limite en los canales, la
densidad se dispara, Weidmann la deja a velocidad cero y se congela para
siempre. Con ella aparecen colas de verdad: la congestion se propaga hacia
atras, que es como se comporta una multitud real.

Las salidas tienen capacidad finita. Eso produce fila en la puerta, que es el
mecanismo que domina el tiempo de evacuacion real.
"""
import numpy as np
from scipy import ndimage

from modelo import RHO_MAX, weidmann


def _capacidad():
    """Capacidad del diagrama fundamental y la densidad a la que ocurre.
    Por debajo de RHO_CAP el flujo crece con la densidad (regimen libre);
    por encima decrece (regimen congestionado)."""
    r = np.linspace(1e-3, RHO_MAX - 1e-3, 4000)
    q = r * weidmann(r)
    k = int(np.argmax(q))
    return float(q[k]), float(r[k])


Q_MAX, RHO_CAP = _capacidad()


def demanda(rho):
    """Lo que una celda QUIERE mandar rio abajo. Una celda congestionada sigue
    queriendo descargar a capacidad: si aqui pusieras rho*v(rho) las celdas
    llenas se congelarian y aparece un moteado de tablero de ajedrez."""
    return np.where(rho <= RHO_CAP, rho * weidmann(rho), Q_MAX)


def oferta(rho):
    """Lo que una celda PUEDE aceptar. En regimen libre acepta hasta capacidad;
    congestionada, solo lo que su propio flujo permite evacuar."""
    return np.where(rho >= RHO_CAP, rho * weidmann(rho), Q_MAX)


def pesos_direccion(T, libre):
    """Reparto del flujo hacia los vecinos cuesta abajo, y los pares de rebanadas
    (origen, destino) para moverlo sin bucles de Python."""
    ny, nx = T.shape
    val = libre & np.isfinite(T)
    Ws, idx = [], []
    for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        so = (slice(max(0, -di), ny - max(0, di)), slice(max(0, -dj), nx - max(0, dj)))
        sd = (slice(max(0, di), ny - max(0, -di)), slice(max(0, dj), nx - max(0, -dj)))
        Tn = np.full_like(T, np.inf)
        Tn[so] = T[sd]
        vecino_ok = np.zeros_like(libre)
        vecino_ok[so] = val[sd]
        ok = val & vecino_ok & np.isfinite(Tn)
        Ws.append(np.where(ok, np.maximum(T - Tn, 0.0), 0.0))
        idx.append((so, sd))
    Wt = np.stack(Ws)
    tot = Wt.sum(0)
    tot[tot <= 0] = 1.0
    return Wt / tot, idx


# Coeficiente de dispersion peatonal [m2/s]. NO es un truco de render: entra en
# la ecuacion, o sea afecta densidad, velocidad y por lo tanto a las funciones
# objetivo. Representa que la gente no sigue exactamente la trayectoria optima
# (heterogeneidad de velocidad deseada y de eleccion de ruta). Es un parametro
# a calibrar, no una constante universal.
D_DISPERSION = 0.55

# Escala a la que la gente "lee" la congestion: nadie decide su ruta por lo que
# pasa en el metro cuadrado de al lado, sino por como se ve la zona.
SIGMA_POTENCIAL = 3.5
MEZCLA_DIR = 0.35        # inercia al replanear la ruta


def difundir(M, idx, esc, dt, h):
    """Difusion en forma de flujo: conserva la masa exactamente y no cruza
    obstaculos, porque solo intercambia entre pares de celdas libres."""
    k = D_DISPERSION * dt / (h * h)
    if k <= 0:
        return M
    k = min(k, 0.2)                      # estabilidad del esquema explicito
    delta = np.zeros_like(M)
    for so, sd in idx[:2] + idx[2:]:     # los 4 pares (cada eje, ambos sentidos)
        libre_par = esc.libre[so] & esc.libre[sd]
        f = np.where(libre_par, k * 0.5 * (M[so] - M[sd]), 0.0)
        delta[sd] += f
        delta[so] -= f
    return M + delta


def suavizar_libre(campo, esc, sigma):
    """Suavizado que respeta obstaculos: promedia solo entre celdas libres."""
    c = np.where(esc.libre, campo, 0.0)
    num = ndimage.gaussian_filter(c, sigma)
    den = ndimage.gaussian_filter(esc.libre.astype(float), sigma)
    out = np.where(den > 1e-6, num / np.maximum(den, 1e-6), 0.0)
    return np.where(esc.libre, out, 0.0)


def direccion(T, esc, h):
    """Direccion de movimiento: -grad T normalizado. Es hacia donde apunta la
    gente en cada punto. Se rellenan las celdas pegadas a muros promediando las
    vecinas validas, para que las flechas no se apaguen contra los obstaculos."""
    Tm = np.where(esc.libre & (T < 1e8), T, np.nan)
    gy, gx = np.gradient(np.nan_to_num(Tm, nan=0.0), h)
    val = esc.libre & np.isfinite(Tm)
    val &= ndimage.binary_erosion(val, np.ones((3, 3)))
    den = ndimage.gaussian_filter(val.astype(float), 2.0)
    for g in (gx, gy):
        rel = ndimage.gaussian_filter(np.where(val, g, 0.0), 2.0)
        g[...] = np.where(val, g, np.where(den > 1e-6, rel / np.maximum(den, 1e-6), 0.0))
    mag = np.hypot(gx, gy)
    return (np.where(mag > 1e-9, -gx / np.maximum(mag, 1e-9), 0.0),
            np.where(mag > 1e-9, -gy / np.maximum(mag, 1e-9), 0.0))


def paso_ctm(M, Wt, idx, esc, dt, m_max, cap_salida):
    """Un paso de tiempo. Devuelve (M_nueva, personas_que_salieron)."""
    h = esc.g.h
    area = esc.g.area_celda
    rho = M / area

    # --- flujo de Godunov: demanda aguas arriba contra oferta aguas abajo ---
    envio = np.minimum(demanda(rho) * h * dt, M)
    envio = np.where(esc.libre, envio, 0.0)

    # --- cuanto pide entrar a cada celda ---
    quiere = [envio * Wt[k] for k in range(4)]
    entrante = np.zeros_like(M)
    for k, (so, sd) in enumerate(idx):
        entrante[sd] += quiere[k][so]

    # --- cuanto le CABE a cada celda: esta es la condicion que evita el atasco ---
    espacio = np.minimum(oferta(rho) * h * dt, np.maximum(m_max - M, 0.0))
    espacio = np.where(esc.salidas, 1e12, espacio)     # la salida siempre acepta
    escala = np.where(entrante > 1e-12,
                      np.minimum(1.0, espacio / np.maximum(entrante, 1e-12)), 1.0)

    delta = np.zeros_like(M)
    for k, (so, sd) in enumerate(idx):
        f = quiere[k][so] * escala[sd]
        delta[sd] += f
        delta[so] -= f
    M = M + delta

    M = difundir(M, idx, esc, dt, h)

    # --- las salidas dejan pasar solo su capacidad: aqui nace la fila ---
    sale = np.minimum(np.where(esc.salidas, M, 0.0), cap_salida)
    M = M - sale
    return M, float(sale.sum())


def simular(esc, M0, dt=0.5, refresco=20, t_max=1200.0, n_frames=60,
            flujo_especifico=1.3):
    """Evacuacion completa. Devuelve cuadros del campo de densidad."""
    h = esc.g.h
    area = esc.g.area_celda
    m_max = (RHO_MAX - 1e-3) * area
    cap_salida = flujo_especifico * h * dt        # personas por celda de salida y paso

    M = M0.copy()
    total = M.sum()
    fuera = 0.0
    Wt = idx = None

    cuadros, tiempos, pct, dirs = [], [], [], []
    ux = uy = None
    n_pasos = int(t_max / dt)
    guardar = max(1, n_pasos // n_frames)
    t = 0.0
    for paso in range(n_pasos):
        if paso % refresco == 0:
            # El campo de tiempos debe reflejar la congestion a ESCALA GRANDE,
            # no el ruido celda a celda. Con densidad instantanea sin suavizar,
            # cualquier hueco vacio tiene velocidad maxima -> tiempo bajo -> el
            # gradiente apunta hacia el hueco. La gente se dirige a los huecos,
            # eso abre mas huecos, y la multitud se fragmenta en islas.
            rho = suavizar_libre(M / area, esc, SIGMA_POTENCIAL)
            v = weidmann(rho)
            v[~esc.libre] = 1e-3
            T = esc.campo(esc.salidas, v)
            Tf = np.nan_to_num(T, posinf=1e9, nan=1e9)
            Wt, idx = pesos_direccion(Tf, esc.libre)
            nux, nuy = direccion(Tf, esc, h)
            if ux is None:
                ux, uy = nux, nuy
            else:
                # la gente no replanea su ruta cada medio segundo: la direccion
                # se mezcla con la anterior en vez de saltar de golpe
                ux = (1 - MEZCLA_DIR) * ux + MEZCLA_DIR * nux
                uy = (1 - MEZCLA_DIR) * uy + MEZCLA_DIR * nuy
                m = np.hypot(ux, uy)
                ux = np.where(m > 1e-9, ux / np.maximum(m, 1e-9), 0.0)
                uy = np.where(m > 1e-9, uy / np.maximum(m, 1e-9), 0.0)
        M, salieron = paso_ctm(M, Wt, idx, esc, dt, m_max, cap_salida)
        fuera += salieron
        if paso % guardar == 0:
            cuadros.append((M / area).copy())
            tiempos.append(t)
            pct.append(100.0 * fuera / total)
            dirs.append((ux.copy(), uy.copy()))
        t += dt
        if M.sum() <= 0.01 * total:
            break
    return cuadros, tiempos, pct, dirs


def tiempo_evacuacion(esc, M0, pct=95.0, dt=1.0, t_max=900.0):
    """t_pct: segundo en que ha salido el pct % de la masa.

    Este es el valor que consume f3. Sale de la simulacion CTM completa, con
    capacidad finita en las salidas, asi que incluye tanto el tiempo de recorrido
    como el de cola en la puerta -- y esos dos NO son independientes: el layout
    decide como se reparte la multitud entre salidas, y ese reparto decide las
    colas. Por eso no se pueden calcular por separado y tomar el maximo.
    """
    _, ts, p, _ = simular(esc, M0, dt=dt, t_max=t_max, n_frames=200)
    p = np.asarray(p)
    ts = np.asarray(ts)
    if not (p >= pct).any():
        # no alcanzo a evacuar en el horizonte: se penaliza extrapolando
        return t_max * (1.0 + (pct - p[-1]) / 100.0)
    return float(ts[np.argmax(p >= pct)])
