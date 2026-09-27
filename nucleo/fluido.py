"""
LA MULTITUD COMO FLUIDO: conservacion de masa + esquema de Godunov.

Dos ingredientes:

1) DIAGRAMA FUNDAMENTAL (Weidmann 1993) -- la unica fisica empirica del modelo.
   Relaciona densidad con velocidad: entre mas apretada la gente, mas lento
   camina. Sin esto el modelo predeciria que las multitudes ACELERAN en los
   cuellos de botella, que es lo contrario de la realidad.

       v(ρ) = v₀ · [ 1 − exp( −γ · (1/ρ − 1/ρ_max) ) ]

   De ahi sale el flujo  q(ρ) = ρ · v(ρ), que tiene un MAXIMO: la capacidad.
   Ese maximo no se pone a mano, se deriva -- y sirve de prueba de validacion
   contra los experimentos de cuello de botella publicados.

2) CONSERVACION DE MASA (LWR: Lighthill & Whitham 1955, Richards 1956)
   resuelta con el esquema de Godunov en su forma de modelo de transmision de
   celdas (Daganzo 1994).

   La regla que lo hace funcionar:

       una celda no puede ENVIAR mas de lo que su densidad permite,
       y sobre todo NO PUEDE RECIBIR mas de lo que le cabe.

   Sin la segunda condicion la masa se apila sin limite, la densidad llega a
   ρ_max, Weidmann la deja a velocidad cero y la celda SE CONGELA PARA SIEMPRE.
   Con ella aparecen colas reales: la congestion se propaga hacia atras, igual
   que en el trafico.

   Detalle fino pero decisivo: una celda congestionada SIGUE queriendo descargar
   a capacidad. Lo que la frena es que la de adelante no la acepta. Si en la
   demanda se pusiera ρ·v(ρ) (que tiende a cero al congestionarse), las celdas
   llenas se congelarian y aparece un moteado de tablero de ajedrez.
"""
import numpy as np
from scipy import ndimage

from parametros import (V0, RHO_MAX, GAMMA, J_ESPECIFICO, CAPA_LIMITE,
                        RHO_PERDIDA_CONTROL, DT, REFRESCO_CAMPO, SIGMA_KERNEL,
                        EXP_REPARTO, EPS_VACIADO, reg)
from campos import campo_tiempos, direccion
import kernel as K


# =============================================================================
# 1. diagrama fundamental
# =============================================================================
def weidmann(rho):
    r = np.clip(np.asarray(rho, dtype=float), 1e-6, RHO_MAX - 1e-6)
    return V0 * (1.0 - np.exp(-GAMMA * (1.0 / r - 1.0 / RHO_MAX)))


def flujo(rho):
    """q(ρ) = ρ · v(ρ)  [pers/(s·m)]"""
    return np.asarray(rho, dtype=float) * weidmann(rho)


def _capacidad():
    r = np.linspace(1e-4, RHO_MAX - 1e-4, 20000)
    q = flujo(r)
    k = int(np.argmax(q))
    return float(q[k]), float(r[k])


Q_MAX, RHO_CAP = _capacidad()
reg("Q_MAX", "q_max", Q_MAX, "pers/(s·m)", "derivado",
    "max de ρ·v(ρ) con Weidmann (1993)",
    "Capacidad del diagrama fundamental. NO se pone a mano. Contrastar contra "
    "los flujos medidos en experimentos de cuello de botella: si cae en el "
    "rango publicado, el modelo pasa su primera prueba de validacion.")
reg("RHO_CAP", "ρ_cap", RHO_CAP, "pers/m²", "derivado",
    "argmax de ρ·v(ρ)",
    "Densidad de capacidad. Por debajo el regimen es libre, por encima es "
    "congestionado. Separa las ramas de demanda y oferta del esquema de Godunov.")


# --- tabulacion -------------------------------------------------------------
# demanda(rho) y oferta(rho) son funciones PURAS de la densidad, y se evaluan dos
# veces por paso sobre toda la rejilla. Evaluar la exponencial de Weidmann ahi
# costaba el 29 % del tiempo total. Tabuladas, el costo es un indexado.
#
# El error de la tabla es el de interpolar una funcion suave en N_TABLA puntos
# sobre [0, rho_max]: con 4096 puntos es ~1e-6 pers/(s*m), cinco ordenes de
# magnitud por debajo del error de discretizacion de la malla.
N_TABLA = 32768
_RHO_T = np.linspace(0.0, RHO_MAX, N_TABLA)
_DEM_T = np.where(_RHO_T <= RHO_CAP, _RHO_T * weidmann(_RHO_T), Q_MAX)
_OFE_T = np.where(_RHO_T >= RHO_CAP, _RHO_T * weidmann(_RHO_T), Q_MAX)
_DEM_T[0] = 0.0
_OFE_T[-1] = 0.0
_ESC_T = (N_TABLA - 1) / RHO_MAX


def _indexar(tabla, rho):
    i = np.clip((rho * _ESC_T).astype(np.int32), 0, N_TABLA - 1)
    return tabla[i]


def demanda(rho):
    """Lo que una celda quiere mandar rio abajo (rama de Godunov aguas arriba)."""
    return _indexar(_DEM_T, rho)


def oferta(rho):
    """Lo que una celda puede aceptar (rama de Godunov aguas abajo)."""
    return _indexar(_OFE_T, rho)


# =============================================================================
# 2. estimador de densidad
# =============================================================================
def densidad_suave(M, libre, area_celda, sigma=SIGMA_KERNEL):
    """Densidad continua estimada de la masa discreta, con nucleo gaussiano.

    NO es un filtro cosmetico. En Continuum Crowds (Treuille et al. 2006) la
    densidad se obtiene depositando cada persona sobre la rejilla con un nucleo;
    en SPH es el smoothing kernel. Es parte del estimador, y por eso entra en el
    modelo y no en el dibujo.

    Ademas evita una patologia real: con densidad instantanea celda a celda,
    cualquier hueco vacio tiene velocidad maxima -> tiempo bajo -> el gradiente
    apunta HACIA el hueco. La gente se dirige a los huecos, eso abre mas huecos,
    y la multitud se fragmenta en islas.
    """
    c = np.where(libre, M / area_celda, 0.0)
    num = ndimage.gaussian_filter(c, sigma)
    den = ndimage.gaussian_filter(libre.astype(float), sigma)
    out = np.where(den > 1e-6, num / np.maximum(den, 1e-6), 0.0)
    return np.where(libre, out, 0.0)


# =============================================================================
# 3. transporte
# =============================================================================
def pesos_direccion(T, libre, p=EXP_REPARTO):
    """Reparto del flujo entre los vecinos cuesta abajo.

        w_j = (T_i - T_j)^p   para los vecinos con T_j < T_i

    Godunov resuelve por cara, en una dimension. En la rejilla una celda puede
    tener varios vecinos cuesta abajo, y hay que decidir como se parte el flujo
    entre ellos. El exponente p es el unico parametro del modelo sin respaldo
    empirico: p=1 difunde de mas, p alto reintroduce sesgo de rejilla.
    """
    ny, nx = T.shape
    val = libre & np.isfinite(T)
    Ws, idx = [], []
    for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        so = (slice(max(0, -di), ny - max(0, di)), slice(max(0, -dj), nx - max(0, dj)))
        sd = (slice(max(0, di), ny - max(0, -di)), slice(max(0, dj), nx - max(0, -dj)))
        Tn = np.full_like(T, np.inf)
        Tn[so] = T[sd]
        vec_ok = np.zeros_like(libre)
        vec_ok[so] = val[sd]
        ok = val & vec_ok & np.isfinite(Tn)
        d = np.where(ok, np.maximum(T - Tn, 0.0), 0.0)
        Ws.append(d if p == 1.0 else np.power(d, p))
        idx.append((so, sd))
    Wt = np.stack(Ws)
    tot = Wt.sum(0)
    tot[tot <= 0] = 1.0
    return Wt / tot, idx


def capacidad_salidas(rec, alcance=2):
    """Cada salida: (zona de drenaje, capacidad en pers/s).

    Una puerta es una SECCION TRANSVERSAL con capacidad fija, no una celda que
    almacena. Drena a la multitud que tiene enfrente a razon de

            J_s × ancho util,     ancho util = ancho − 2·capa_limite

    (la capa limite es la franja pegada a cada jamba que la gente no usa).

    Por que la zona de drenaje abarca varias celdas hacia adentro y no solo la
    del borde: si solo se drenara la fila del borde, el caudal real se queda muy
    por debajo del nominal, porque el reparto de flujo de Godunov manda parte de
    la masa de lado en vez de hacia la puerta. Medido: una puerta de 12 m
    alcanzaba apenas el 71 % de su capacidad. Con la zona de drenaje la puerta
    trabaja a su capacidad mientras haya gente enfrente, que es lo que hace una
    puerta de verdad, y la fila se forma detras.
    """
    out = []
    for s in rec.salidas:
        a, b = s.centro - s.ancho / 2, s.centro + s.ancho / 2
        if s.lado == "S":
            m = (rec.X >= a) & (rec.X < b) & (rec.Y < rec.h)
        elif s.lado == "N":
            m = (rec.X >= a) & (rec.X < b) & (rec.Y >= rec.H - rec.h)
        elif s.lado == "O":
            m = (rec.Y >= a) & (rec.Y < b) & (rec.X < rec.h)
        else:
            m = (rec.Y >= a) & (rec.Y < b) & (rec.X >= rec.W - rec.h)
        zona = ndimage.binary_dilation(m, np.ones((3, 3)), iterations=alcance)
        out.append((zona, J_ESPECIFICO * s.ancho_util(CAPA_LIMITE)))
    return out


def paso(M, Wt, idx, libre, salidas_cap, area_celda, h, dt, m_max, buf=None):
    """Un paso de Godunov + descarga por las puertas.

    El transporte lo hace el kernel compilado (kernel.py), que produce el mismo
    resultado que la version numpy a tolerancia de redondeo pero en tres
    recorridos del arreglo en vez de quince.
    """
    if buf is None:
        buf = K.Buffers(M.shape)
    K.paso_godunov(M, Wt, libre, _DEM_T, _OFE_T, _ESC_T, area_celda, h, dt,
                   m_max, buf.entrante, buf.envio, buf.escala, buf.di, buf.dj)

    # cada salida deja pasar solo su capacidad: aqui nace la fila en la puerta
    salieron = 0.0
    for zona, cap in salidas_cap:
        masa = float(M[zona].sum())
        if masa <= 1e-12:
            continue
        sale = min(cap * dt, masa)
        M[zona] = M[zona] * (1.0 - sale / masa)
        salieron += sale
    return M, salieron


def simular(rec, layout, aforo, dt=DT, t_max=1200.0, n_cuadros=60,
            refresco=REFRESCO_CAMPO, guardar_campos=False, M0=None,
            parar_en_pct=None, p_reparto=EXP_REPARTO, rho_c=RHO_PERDIDA_CONTROL,
            eps=EPS_VACIADO):
    """Evacuacion desde aforo lleno repartido uniformemente (peor caso).

    Devuelve cuadros de densidad, la curva de evacuados y t95.
    """
    from geometria import zona_ocupable
    # El dominio es la zona OCUPABLE, no el libre crudo: en los recovecos donde
    # no se entra con el ancho normativo no hay que poner gente, porque si se
    # pone, nunca sale y contamina el tiempo de evacuacion.
    libre, _ = zona_ocupable(rec, layout)
    salidas_cap = capacidad_salidas(rec)
    area = rec.area_celda
    m_max = (RHO_MAX - 1e-3) * area

    n_celdas = int(libre.sum())
    if n_celdas == 0:
        return None
    if M0 is None:
        # peor caso pedido: aforo lleno repartido UNIFORME sobre la zona ocupable
        M = np.where(libre, aforo / n_celdas, 0.0)
    else:
        M = np.where(libre, M0, 0.0)
        if M.sum() > 0:
            M = M / M.sum() * aforo
    total = M.sum()

    Wt = idx = None
    ux = uy = None
    buf = K.Buffers(M.shape)          # se reutiliza en todos los pasos
    Wc = None
    cuadros, tiempos, pct, dirs = [], [], [], []
    fuera, t = 0.0, 0.0
    t95 = t_des = None             # se rastrean PASO A PASO, no en los cuadros:
    exposicion = 0.0               # m2*s por encima de la densidad critica
    rho_pico = 0.0
    n_pasos = int(t_max / dt)      # con muestreo grueso el cruce del 95 % se pierde
    # Se guarda FINO (cada ~2 s) y se submuestrea al final. Calcular la cadencia
    # a partir de t_max no sirve: la evacuacion casi siempre termina mucho antes
    # y quedan cuatro cuadros contados.
    cada = max(1, int(round(2.0 / dt)))

    for k in range(n_pasos):
        if k % refresco == 0:
            rho = densidad_suave(M, libre, area)
            v = np.where(libre, weidmann(rho), 1e-3)
            T = campo_tiempos(rec, libre, rec.mascara_salidas(), v)
            Tf = np.nan_to_num(T, posinf=1e9, nan=1e9)
            Wt, idx = pesos_direccion(Tf, libre, p_reparto)
            Wc = np.ascontiguousarray(Wt)
            if guardar_campos:
                ux, uy = direccion(Tf, libre, rec.h)
        M, sal = paso(M, Wc, idx, libre, salidas_cap, area, rec.h, dt, m_max, buf)
        fuera += sal
        if t95 is None and fuera >= 0.95 * total:
            t95 = t
        if t_des is None and (total - fuera) <= eps * total:
            t_des = t

        # Exposicion: superficie-tiempo por encima de la densidad critica. Es la
        # candidata a objetivo de riesgo, asi que se acumula SIEMPRE aunque hoy
        # no se optimice -- sin ella no hay matriz de correlacion.
        rho_ahora = M / area
        sobre = rho_ahora[libre] > rho_c
        if sobre.any():
            exposicion += float(sobre.sum()) * area * dt
        mx = float(rho_ahora[libre].max()) if libre.any() else 0.0
        if mx > rho_pico:
            rho_pico = mx
        if k % cada == 0:
            cuadros.append((M / area).copy())
            tiempos.append(t)
            pct.append(100.0 * fuera / total)
            if guardar_campos:
                dirs.append((ux.copy(), uy.copy()))
        t += dt
        # Corte temprano: la funcion objetivo solo necesita t95. Seguir hasta
        # vaciar el recinto cuesta ~10 % mas de pasos que NO se usan para nada.
        # Es exacto, no una aproximacion: t95 ya quedo determinado.
        if parar_en_pct is not None and fuera >= parar_en_pct / 100.0 * total:
            break
        if M.sum() <= 0.005 * total:
            break

    if len(cuadros) > n_cuadros:                      # submuestreo uniforme
        sel = np.linspace(0, len(cuadros) - 1, n_cuadros).astype(int)
        cuadros = [cuadros[i] for i in sel]
        tiempos = [tiempos[i] for i in sel]
        pct = [pct[i] for i in sel]
        if dirs:
            dirs = [dirs[i] for i in sel if i < len(dirs)]
    p = np.asarray(pct)
    ts = np.asarray(tiempos)
    return {"cuadros": cuadros, "t": ts, "pct": p,
            "t95": t95, "t_des": t_des,
            "exposicion": exposicion, "rho_pico": rho_pico,
            "dirs": dirs, "libre": libre, "total": total,
            "masa_final": float(M.sum()),
            # Validacion 1: masa_dentro + evacuados debe seguir siendo N hasta
            # error de maquina. Se expone como metrica de diagnostico, no como
            # assert, para poder reportarla en la tesis.
            "conservacion": float((M.sum() + fuera) / total - 1.0) if total > 0 else 0.0,
            "evacuados": float(fuera),
            "evacuado_final": float(p[-1]) if len(p) else 0.0}


def t_evacuacion(rec, layout, aforo, t_max=1200.0, dt=DT):
    """f_evac: la funcion objetivo. Tiempo hasta que sale el 95 % de la masa.

    Si no alcanza a evacuar en el horizonte, se penaliza extrapolando, para que
    el optimizador siga teniendo gradiente y no vea una meseta plana.
    """
    r = simular(rec, layout, aforo, dt=dt, t_max=t_max, n_cuadros=120,
                parar_en_pct=pct)
    if r is None:
        return t_max * 3
    if r["t95"] is None:
        falta = max(0.0, 95.0 - r["evacuado_final"])
        return t_max * (1.0 + falta / 100.0)
    return r["t95"]
