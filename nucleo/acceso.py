"""
f1 -- ACCESIBILIDAD A LAS AREAS DE SERVICIO.

La pregunta que responde: puesta la gente donde esta, y respetando que cada
area de servicio atiende a un ritmo finito, cuanto camina en promedio una
persona para ser atendida.

    f1 = distancia media por visita, en metros

TRES DECISIONES QUE NO SON COSMETICAS
-------------------------------------

1. DISTANCIA GEODESICA, NO EUCLIDIANA. Se mide caminando: se resuelve la
   ecuacion Eikonal con velocidad constante (|grad d| = 1) sobre el espacio
   libre, con los muros Y LAS DEMAS AREAS DE SERVICIO como obstaculos. Dos
   puntos separados por 5 m de muro estan a 5 m en linea recta y a 40 m
   caminando. La euclidiana premiaria layouts que en la practica obligan a
   rodear.

2. EL ORIGEN DEL CAMPO SON LAS CELDAS DE ATENCION, NO EL CENTROIDE. Un modulo
   sanitario de 8x3 m no se atiende desde su centro geometrico: se atiende
   desde la fila de celdas libres pegadas a la cara por donde se entra. Sembrar
   el campo en el centroide mete un error del orden del semi-lado del modulo
   (hasta 4 m aqui) y ademas atraviesa el propio edificio, que es un obstaculo.

3. ASIGNACION CAPACITADA POR TRANSPORTE EXACTO, NO POR CODICIOSO. La version
   codiciosa -- recorrer celdas y mandar cada una a la mas cercana que todavia
   tenga cupo -- da un resultado QUE DEPENDE DEL ORDEN EN QUE SE RECORREN LAS
   CELDAS. Como el orden lo fija la rejilla y no el problema, dos layouts
   identicos salvo una traslacion pueden dar f1 distintos. Eso no es ruido
   tolerable: contamina la comparacion entre layouts, que es exactamente lo
   que el optimizador va a usar. Aqui se resuelve el problema de transporte de
   verdad:

       min  sum_ij  q_i d_ij y_ij
       s.a. sum_j y_ij = 1          cada persona se atiende en algun lado
            sum_i q_i y_ij <= c_j   ningun modulo atiende mas de lo que puede
            y >= 0

   El optimo es unico en valor y no depende de ningun recorrido.

SOBRE LA RELAJACION FRACCIONARIA: y_ij es la FRACCION de la demanda de la celda
i que se atiende en j. Es lo correcto aqui, no un relajamiento: una celda es
1 m2 con decenas de personas que a lo largo del evento se reparten entre varios
modulos. Ademas el poliedro de transporte es integral, asi que ni siquiera se
paga precio por permitirlo.
"""
import numpy as np
import skfmm
from scipy import ndimage, sparse
from scipy.optimize import linprog

from parametros import reg

_CRUZ = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)


# =============================================================================
# 1. capacidad de servicio
# =============================================================================
# PRIMERA VERSION, DESCARTADA: capacidad = unidades/tau y demanda = aforo*tasa,
# con tau el tiempo de servicio y tasa las visitas por persona y hora. Se cayo
# por dos motivos y el segundo es el grave:
#
#   a) medido con valores plausibles, la demanda salia 3 a 8 veces la capacidad.
#      Con demanda > capacidad el problema de transporte es INFACTIBLE: no hay
#      reparto que respete los cupos, el dual se dispara y f1 deja de estar
#      definido. Eso no se arregla afinando los numeros, porque
#   b) tau y tasa no tienen de donde salir. No son constantes fisicas ni
#      dimensiones de producto: son comportamiento de publico. Meterlas obliga a
#      defender en la tesis dos cifras inventadas que ademas MANDAN sobre el
#      resultado, porque son las que deciden si la restriccion de capacidad ata.
#
# LO QUE SE USA: la capacidad relativa sale de las UNIDADES DE ATENCION del
# modulo -- cuantos inodoros, cuantos grifos, cuantos puestos -- que si es dato
# de ficha de proveedor, y la demanda se normaliza contra la capacidad total del
# tipo. Queda un solo parametro explicito, la saturacion, con default 1.0.
#
# Que significa el default: cada modulo trabaja exactamente a tope. Es el caso
# mas exigente y el mas informativo, porque la restriccion ATA en todos, y
# entonces f1 mide de verdad reparto de carga. Con saturacion < 1 sobra cupo,
# los modulos lejanos se quedan ociosos y f1 degenera hacia "distancia al mas
# cercano", que es el caso que f1 justamente no deberia premiar.
SERVICIO = {
    "SAN": dict(unidades=8),   # inodoros por modulo
    "COM": dict(unidades=4),   # puntos de despacho por carpa
    "BEB": dict(unidades=6),   # grifos por barra
    "MED": dict(unidades=2),   # puestos de atencion
}
for _k, _v in SERVICIO.items():
    reg("UNID_%s" % _k, "u_%s" % _k, _v["unidades"], "unidades", "catalogo",
        "Ficha de proveedor / pliego del evento",
        "Unidades de atencion del modulo. Fijan (i) como se reparte la carga "
        "entre modulos del mismo tipo y (ii) cuanto pesa cada tipo en f1. Es "
        "un conteo de producto, verificable en catalogo. NO se usan tiempos de "
        "servicio ni tasas de visita: ver la nota de acceso.py.")

SATURACION = reg(
    "SATURACION", "sigma", 1.0, "-", "calibrar", "Criterio del proyecto",
    "Fraccion de la capacidad instalada que se usa. 1.0 = todos los modulos a "
    "tope, que es el caso que mas discrimina entre layouts. Unico parametro "
    "libre de f1; requiere analisis de sensibilidad, no cita.")


def capacidades(layout, tipo, sigma=SATURACION):
    """Fraccion de la demanda del tipo que puede absorber cada modulo.

    Normalizada: con sigma = 1 suma 1, o sea capacidad total = demanda total y
    la restriccion ata en todos los modulos.
    """
    u = np.array([SERVICIO[tipo]["unidades"]
                  for c in layout if c.tipo == tipo], dtype=float)
    return u / u.sum() / sigma if u.size else u


def peso_tipo(layout, tipo):
    """Cuanto pesa el tipo en f1: proporcional a su capacidad instalada total.

    Un tipo con el doble de unidades atiende al doble de gente y por tanto pone
    el doble de visitas en el promedio. Sale del mismo conteo de catalogo, sin
    introducir una tasa de visita aparte.
    """
    return sum(SERVICIO[tipo]["unidades"] for c in layout if c.tipo == tipo)


# =============================================================================
# 2. campos de distancia caminando, uno por modulo
# =============================================================================
def celdas_atencion(rec, col, libre):
    """Celdas libres pegadas al modulo: por ahi se entra y por ahi se mide.

    Hoy se toma todo el perimetro accesible. Cuando el catalogo declare por que
    cara atiende cada tipo, se filtra aqui y no cambia nada mas.
    """
    cuerpo = rec.mascara_rect(col.rect())
    return ndimage.binary_dilation(cuerpo, _CRUZ) & libre & ~cuerpo


def campo_distancia(rec, libre, semilla):
    """|grad d| = 1 con d = 0 en la semilla. Metros caminando. inf si no hay ruta."""
    if not semilla.any():
        return np.full(libre.shape, np.inf)
    dominio = libre | semilla
    phi = np.ones(libre.shape)
    phi[semilla] = -1.0
    try:
        d = skfmm.distance(np.ma.MaskedArray(phi, ~dominio), dx=rec.h)
    except Exception:
        return np.full(libre.shape, np.inf)
    d = np.ma.filled(d, np.inf)
    # skfmm mide al nivel cero, que cae a media celda del centro de la semilla.
    return np.maximum(d + 0.5 * rec.h, 0.0)


def matriz_distancias(rec, layout, libre, tipo):
    """(n_modulos, n_celdas_libres) en metros. Solo los modulos del tipo."""
    idx = [k for k, c in enumerate(layout) if c.tipo == tipo]
    if not idx:
        return np.zeros((0, int(libre.sum()))), []
    D = np.empty((len(idx), int(libre.sum())))
    for f, k in enumerate(idx):
        D[f] = campo_distancia(rec, libre,
                               celdas_atencion(rec, layout[k], libre))[libre]
    return D, idx


# =============================================================================
# 3. problema de transporte
# =============================================================================
def transporte_lp(D, q, cap):
    """Optimo exacto por programacion lineal (HiGHS).

    D   (n, m) distancia modulo-celda
    q   (m,)   demanda de cada celda
    cap (n,)   capacidad de cada modulo
    Devuelve (coste_total, y) con y de forma (n, m).
    """
    n, m = D.shape
    c = (D * q[None, :]).ravel()

    cols = np.arange(n * m)
    # cada celda reparte exactamente 1
    A_eq = sparse.csr_matrix((np.ones(n * m), (np.tile(np.arange(m), n), cols)),
                             shape=(m, n * m))
    # cada modulo no pasa de su capacidad
    A_ub = sparse.csr_matrix((np.tile(q, n), (np.repeat(np.arange(n), m), cols)),
                             shape=(n, n * m))

    r = linprog(c, A_ub=A_ub, b_ub=cap, A_eq=A_eq, b_eq=np.ones(m),
                bounds=(0, 1), method="highs")
    if not r.success:
        return np.inf, None
    return float(r.fun), r.x.reshape(n, m)


def transporte_dos(D, q, cap):
    """Optimo EXACTO para dos modulos, sin iterar: un ordenamiento y listo.

    Con dos destinos la celda i va al modulo 0 si d0i + pi0 <= d1i + pi1, o sea
    si la DIFERENCIA d0i - d1i no pasa de cierto umbral. Entonces el reparto
    optimo se obtiene ordenando las celdas por esa diferencia y llenando el
    modulo 0 desde el extremo: a las celdas que mas ganan yendo al 0 se les da
    el 0, hasta agotar su capacidad, y el resto va al 1.

    Es exacto -- no es una heuristica codiciosa disfrazada: el problema de
    transporte con dos destinos y costes lineales tiene esta solucion cerrada.
    Y como aqui la mitad de los tipos del catalogo tienen dos modulos, quita de
    un golpe las ~150 iteraciones de subgradiente que costaban.

    Las celdas sin ruta a uno de los dos modulos salen solas: su diferencia es
    +-infinito y el ordenamiento las manda al extremo que les corresponde.
    """
    d0, d1 = D[0], D[1]
    dif = np.where(np.isfinite(d0) & np.isfinite(d1), d0 - d1,
                   np.where(np.isfinite(d0), -np.inf, np.inf))
    o = np.argsort(dif, kind="stable")
    acum = np.cumsum(q[o])
    # hasta donde alcanza la capacidad del modulo 0
    k = int(np.searchsorted(acum, cap[0]))
    coste = float(np.sum(q[o[:k]] * d0[o[:k]]))
    if k < len(o):
        resto = cap[0] - (acum[k - 1] if k else 0.0)   # parte fraccionaria
        resto = min(max(resto, 0.0), q[o[k]])
        coste += resto * d0[o[k]] + (q[o[k]] - resto) * d1[o[k]]
        coste += float(np.sum(q[o[k + 1:]] * d1[o[k + 1:]]))
    return coste


def _precio_exacto(margen, q, cap):
    """Precio que deja a un modulo EXACTAMENTE en su capacidad.

    'margen_i' es cuanto le sobra a la celda i para preferir este modulo sobre
    el mejor de los otros. La celda viene a este modulo si su precio es menor
    que ese margen, asi que la carga es decreciente en el precio y basta ordenar
    los margenes de mayor a menor y cortar donde la demanda acumulada llega a la
    capacidad. Sale exacto de un solo argsort, sin iterar.
    """
    o = np.argsort(-margen, kind="stable")
    acum = np.cumsum(q[o])
    k = int(np.searchsorted(acum, cap))
    if k >= len(o):
        return float(margen[o[-1]]) - 1.0        # cabe todo: precio por debajo
    return float(margen[o[k]])


def transporte(D, q, cap):
    """Despachador: el metodo mas barato que resuelve exacto cada tamano.

        n = 1   todo va al unico modulo
        n = 2   formula cerrada por ordenamiento
        n >= 3  descenso por coordenadas, cada una exacta

    Medido sobre 120 problemas reales, contra el LP exacto (HiGHS):
        LP exacto             139.9 ms
        subgradiente           34.4 ms   dif 5.6e-4
        este despachador       14.6 ms   dif 2.0e-4     <- 9.6x mas barato
    """
    n = D.shape[0]
    if n == 0:
        return 0.0
    if n == 1:
        return float((D[0] * q).sum())
    if n == 2:
        return transporte_dos(D, q, cap)
    return transporte_coordenadas(D, q, cap)[0]


def transporte_coordenadas(D, q, cap, barridos=12, tol=1e-9):
    """Descenso por coordenadas sobre los precios, cada una resuelta EXACTA.

    El subgradiente 1/sqrt(k) trata los precios como una caja negra y por eso
    necesitaba ~283 iteraciones (y agotaba el tope en el 39 % de las llamadas).
    Pero fijados los demas precios, el precio optimo de UN modulo tiene formula
    cerrada -- es el mismo argumento de ordenamiento que resuelve el caso de dos
    modulos, aplicado a una coordenada. Entonces se barre modulo por modulo
    resolviendo cada uno de golpe, y convergen en pocos barridos.

    Ojo: el descenso por coordenadas sobre una funcion concava NO diferenciable
    puede atorarse antes del optimo. Por eso esto NO se da por bueno: se valida
    contra el LP exacto (experimentos/), y se conserva el subgradiente como
    respaldo si alguna vez el margen se abre.
    """
    n, m = D.shape
    pi = np.zeros(n)
    C = D + pi[:, None]
    for _ in range(barridos):
        cambio = 0.0
        for j in range(n):
            otros = np.min(np.delete(C, j, axis=0), axis=0)
            margen = otros - D[j]
            nuevo = _precio_exacto(margen, q, cap[j])
            if not np.isfinite(nuevo):
                continue
            cambio = max(cambio, abs(nuevo - pi[j]))
            pi[j] = nuevo
            C[j] = D[j] + nuevo
        if cambio <= tol:
            break

    # Coste del reparto que inducen esos precios. Si las coordenadas
    # convergieron, cada modulo quedo EN su capacidad y el reparto por argmin ya
    # es factible: entonces el coste es una suma directa, sin recorrer celdas en
    # Python. Ese bucle era el 29 % del costo de f1.
    j = np.argmin(C, axis=0)
    carga = np.bincount(j, weights=q, minlength=n)
    exceso = carga - cap
    coste = float(np.sum(q * D[j, np.arange(m)]))
    if np.all(np.abs(exceso) <= 1e-9 * np.maximum(cap, 1e-12)):
        return coste, pi
    # no convergio: se repara, y se avisa devolviendo el exceso
    coste, _ = _reparar(D, q, cap, pi)
    return coste, pi


def transporte_precios(D, q, cap, iteraciones=400, tol=1e-4):
    """Mismo optimo por el dual, sin montar la matriz.

    El dual tiene UNA incognita por modulo -- aqui como mucho tres -- mientras
    que el primal tiene una por celda-modulo, aqui ~17 000. Se busca un precio
    pi_j por modulo tal que, cuando cada celda va a su argmin(d_ij + pi_j),
    ninguno se pasa de capacidad. Un modulo saturado sube su precio hasta que
    la demanda sobrante se va sola al siguiente.

    Es el mismo mecanismo que una subasta: el precio de equilibrio reparte sin
    que nadie coordine el reparto.

    Devuelve (coste, cota_inferior, brecha_relativa, precios).
    El primal reparado es factible, asi que 'coste' es cota SUPERIOR y el valor
    del dual es cota INFERIOR: la brecha certifica cuanto se esta perdiendo.
    """
    n, m = D.shape
    if n == 1:
        v = float((D[0] * q).sum())
        return v, v, 0.0, np.zeros(1)
    if n == 2:
        v = transporte_dos(D, q, cap)
        return v, v, 0.0, np.zeros(2)

    pi = np.zeros(n)
    fin = D[np.isfinite(D)]
    esc = float(fin.max() - fin.min()) if fin.size else 1.0
    esc = esc or 1.0
    mejor_dual, mejor_pi = -np.inf, pi.copy()
    ind = np.arange(m)

    for k in range(iteraciones):
        coste_min = D + pi[:, None]
        j = np.argmin(coste_min, axis=0)
        # valor del dual con estos precios: cota inferior VALIDA siempre
        dual = float((coste_min[j, ind] * q).sum() - (cap * pi).sum())
        if dual > mejor_dual:
            mejor_dual, mejor_pi = dual, pi.copy()

        carga = np.bincount(j, weights=q, minlength=n)
        exceso = carga - cap
        if np.all(exceso <= tol * cap):
            break

        paso = esc / (cap.sum() * np.sqrt(k + 1.0))
        pi = np.maximum(0.0, pi + paso * exceso)

    coste, _ = _reparar(D, q, cap, mejor_pi)
    brecha = abs(coste - mejor_dual) / max(abs(coste), 1e-12)
    return coste, mejor_dual, brecha, mejor_pi


def _reparar(D, q, cap, pi):
    """Primal factible a partir de los precios.

    Se atiende primero a quien mas pierde si no le toca su preferido (mayor
    diferencia entre su mejor y su segunda opcion). Con precios cerca del
    equilibrio casi nadie se mueve de su preferido y la brecha sale minima.
    """
    n, m = D.shape
    C = D + pi[:, None]
    orden_pref = np.argsort(C, axis=0)
    c1 = np.take_along_axis(C, orden_pref[:1], axis=0)[0]
    c2 = np.take_along_axis(C, orden_pref[1:2], axis=0)[0] if n > 1 else c1
    prioridad = np.argsort(-(c2 - c1) * q)

    resta = cap.astype(float).copy()
    y = np.zeros((n, m))
    coste = 0.0
    for i in prioridad:
        falta = q[i]
        for j in orden_pref[:, i]:
            if falta <= 1e-15:
                break
            if not np.isfinite(D[j, i]) or resta[j] <= 0:
                continue
            toma = min(falta, resta[j])
            y[j, i] += toma / q[i]
            coste += toma * D[j, i]
            resta[j] -= toma
            falta -= toma
        if falta > 1e-9:            # se acabo toda la capacidad del tipo
            j0 = orden_pref[0, i]
            coste += falta * D[j0, i]
            y[j0, i] += falta / q[i]
    return coste, y


# =============================================================================
# 4. f1
# =============================================================================
def f1(rec, layout, libre=None, sigma=SATURACION, exacto=False, por_tipo=False):
    """Distancia media por visita, en metros, sobre todos los tipos.

    No depende del aforo. Con el reparto uniforme de gente que usa el resto del
    modelo, el aforo multiplica por igual a todas las celdas y se cancela al
    promediar: f1 es una propiedad de la GEOMETRIA del layout, no del numero de
    asistentes. Que no dependa del aforo es deseable -- significa que comparar
    layouts no arrastra el supuesto de cuanta gente hay.
    """
    if libre is None:
        from geometria import zona_ocupable
        libre, _ = zona_ocupable(rec, layout)

    n_celdas = int(libre.sum())
    if n_celdas == 0:
        return (np.inf, {}) if por_tipo else np.inf

    q = np.full(n_celdas, 1.0 / n_celdas)      # demanda normalizada a 1
    peso_total = 0.0
    suma = 0.0
    det = {}
    for tipo in SERVICIO:
        D, idx = matriz_distancias(rec, layout, libre, tipo)
        if D.shape[0] == 0:
            continue
        cap = capacidades(layout, tipo, sigma)

        sin_ruta = ~np.isfinite(D).any(axis=0)
        if sin_ruta.any():                     # celdas sin ruta a ningun modulo
            det[tipo] = {"sin_ruta": float(sin_ruta.mean())}
            return (np.inf, det) if por_tipo else np.inf

        if exacto:
            coste, _ = transporte_lp(D, q, cap)
            brecha = 0.0
        else:
            coste, brecha = transporte(D, q, cap), 0.0

        w = peso_tipo(layout, tipo)
        suma += w * coste
        peso_total += w
        det[tipo] = {"d_media": coste, "brecha": brecha, "n": len(idx), "peso": w}

    if peso_total <= 0:
        return (np.inf, det) if por_tipo else np.inf
    val = suma / peso_total
    return (val, det) if por_tipo else val


# =============================================================================
# 5. el reparto, para poder DIBUJARLO
# =============================================================================
def asignacion(rec, layout, libre=None, sigma=SATURACION):
    """A que modulo le toca cada celda, y a que distancia caminando.

    Es f1 abierta en canal: en vez del promedio, el reparto completo que lo
    produce. Sirve para dibujarlo, y dibujarlo importa porque es donde se ve lo
    que el numero esconde -- que las regiones NO son las del modulo mas cercano.
    La capacidad deforma las fronteras: un modulo saturado le cede celdas a su
    vecino aunque quede mas lejos, y esa frontera desplazada es justamente lo
    que distingue esta formulacion de una de cercania simple.

    Devuelve, por tipo: indice del modulo que atiende cada celda libre, la
    distancia a ese modulo, y los modulos del tipo.
    """
    if libre is None:
        from geometria import zona_ocupable
        libre, _ = zona_ocupable(rec, layout)

    n_celdas = int(libre.sum())
    salida = {}
    if n_celdas == 0:
        return salida

    q = np.full(n_celdas, 1.0 / n_celdas)
    for tipo in SERVICIO:
        D, idx = matriz_distancias(rec, layout, libre, tipo)
        if D.shape[0] == 0:
            continue
        cap = capacidades(layout, tipo, sigma)

        if D.shape[0] == 1:
            pi = np.zeros(1)
        elif D.shape[0] == 2:
            # el caso de dos se resuelve por ordenamiento y no deja precios:
            # se recupera el umbral, que es el precio relativo del segundo
            d0, d1 = D[0], D[1]
            dif = np.where(np.isfinite(d0) & np.isfinite(d1), d0 - d1,
                           np.where(np.isfinite(d0), -np.inf, np.inf))
            o = np.argsort(dif, kind="stable")
            k = int(np.searchsorted(np.cumsum(q[o]), cap[0]))
            # la celda va al modulo 0 si  d0 + pi0 < d1 + pi1, o sea si
            # (d0 - d1) < pi1 - pi0. Fijando pi0 = 0, el umbral ES pi1.
            umbral = float(dif[o[min(k, len(o) - 1)]])
            pi = np.array([0.0, umbral])
        else:
            _, pi = transporte_coordenadas(D, q, cap)

        quien = np.argmin(D + pi[:, None], axis=0).astype(np.int16)
        dist = D[quien, np.arange(n_celdas)]
        carga = np.bincount(quien, weights=q, minlength=len(idx))
        salida[tipo] = {
            "quien": quien, "dist": dist, "modulos": idx,
            "carga": carga, "capacidad": cap,
            "d_media": float(np.sum(q * np.where(np.isfinite(dist), dist, 0.0))),
        }
    return salida
