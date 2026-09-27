"""
CAPA GEOMETRICA (restriccion dura).

Se ejecuta ANTES de cualquier simulacion. Su proposito es no gastar milisegundos
de solver en layouts que ya son ilegales: si no cabe un bano, no tiene sentido
preguntarse cuanto tarda la evacuacion.

Todas las verificaciones son geometricas puras y cuestan microsegundos a
milisegundos, contra decimas de segundo que cuesta una evacuacion completa.

Cada chequeo devuelve (violacion, detalle) donde 'detalle' trae mascaras y
rectangulos para poder dibujar POR QUE fallo.

Nota sobre "dura pero medida en grado": la restriccion es dura -- ningun tiempo
de evacuacion compensa violar normativa. Pero se mide CUANTO se viola, porque un
optimizador necesita saber hacia donde moverse para salir de la region
infactible. Si solo marcara si/no, la busqueda ahi dentro seria ciega.
"""
import numpy as np
from scipy import ndimage

from parametros import ANCHO_LIBRE_MIN, DIST_MAX_SALIDA, reg

PROF_DESPEJE_SALIDA = reg(
    "PROF_DESPEJE_SALIDA", "d_s", 1.5, "× ancho", "PENDIENTE",
    "RCDF/NTC: area de descarga de salidas",
    "Profundidad que debe quedar despejada frente a una salida, como multiplo "
    "de su ancho. VALOR PROVISIONAL: verificar el criterio normativo real.")


# --- utilidades ---------------------------------------------------------------
def _inter(a, b):
    ax, ay, aw, af = a
    bx, by, bw, bf = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + af, by + bf) - max(ay, by))
    return ix * iy


def _disco(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r + 0.5


def conos_salida(rec):
    """Rectangulos frente a cada salida que deben quedar despejados."""
    conos = []
    for s in rec.salidas:
        p = PROF_DESPEJE_SALIDA * s.ancho
        a = s.centro - s.ancho / 2
        if s.lado == "S":
            conos.append((s.nombre, (a, 0.0, s.ancho, p)))
        elif s.lado == "N":
            conos.append((s.nombre, (a, rec.H - p, s.ancho, p)))
        elif s.lado == "O":
            conos.append((s.nombre, (0.0, a, p, s.ancho)))
        elif s.lado == "E":
            conos.append((s.nombre, (rec.W - p, a, p, s.ancho)))
    return conos


# --- G1: todo dentro del recinto ---------------------------------------------
def g1_dentro(rec, layout):
    v, culpables = 0.0, []
    for i, c in enumerate(layout):
        x, y, w, f = c.rect()
        fuera = (max(0.0, -x) + max(0.0, x + w - rec.W)
                 + max(0.0, -y) + max(0.0, y + f - rec.H))
        if fuera > 0:
            v += fuera
            culpables.append(i)
    return v, {"culpables": culpables}


# --- G2: no traslape entre areas de servicio ---------------------------------
def g2_traslape(rec, layout):
    v, pares = 0.0, []
    for i in range(len(layout)):
        for j in range(i + 1, len(layout)):
            a = _inter(layout[i].rect(), layout[j].rect())
            if a > 0:
                v += a
                pares.append((i, j))
    return v, {"pares": pares}


# --- G3: no encima de muros ni elementos fijos -------------------------------
def g3_muros(rec, layout):
    v, culpables = 0.0, []
    for i, c in enumerate(layout):
        m = rec.mascara_rect(c.rect()) & rec.muros
        a = float(m.sum()) * rec.area_celda
        if a > 0:
            v += a
            culpables.append(i)
    return v, {"culpables": culpables}


# --- G4: salidas y su area de descarga despejadas ----------------------------
def g4_salidas(rec, layout):
    v, culpables = 0.0, []
    conos = conos_salida(rec)
    for i, c in enumerate(layout):
        a = sum(_inter(c.rect(), cono) for _, cono in conos)
        if a > 0:
            v += a
            culpables.append(i)
    return v, {"culpables": culpables, "conos": conos}


# --- G5: zona ocupable y area inutilizada -------------------------------------
FRACCION_PERDIDA_MAX = reg(
    "FRACCION_PERDIDA_MAX", "φ_max", 0.03, "-", "calibrar",
    "Criterio de diseno del proyecto (NO es una constante fisica)",
    "Fraccion maxima del area util que un layout puede inutilizar mas alla de "
    "la huella de los propios servicios. Declararlo como criterio, no como dato.")


def zona_ocupable(rec, layout=None):
    """Piso al que la gente REALMENTE puede llegar circulando con el ancho
    normativo, partiendo de alguna salida.

    Se erosiona el piso libre por medio ancho normativo: lo que sobrevive es la
    red de circulacion por la que SI se puede transitar legalmente. Se conserva
    la parte de esa red conectada a alguna salida, y se vuelve a dilatar.

    Un recoveco detras de un puesto, al que no se entra con el ancho de
    reglamento, NO es una violacion de seguridad: es superficie que no se puede
    usar. Por eso sale de la zona ocupable en vez de contar como infraccion.
    """
    libre = rec.libre(layout)
    salidas = rec.mascara_salidas()
    r = max(1, int(round((ANCHO_LIBRE_MIN / 2) / rec.h)))
    st = _disco(r)

    erod = ndimage.binary_erosion(libre, structure=st)
    if not erod.any():
        return np.zeros_like(libre), {"erosion": erod}
    lab, _ = ndimage.label(erod)
    cerca = ndimage.binary_dilation(salidas, structure=st) & erod
    etiq = set(np.unique(lab[cerca]).tolist()) - {0}
    if not etiq:
        return np.zeros_like(libre), {"erosion": erod}
    red = np.isin(lab, list(etiq))
    ocupable = ndimage.binary_dilation(red, structure=st) & libre
    return ocupable, {"erosion": erod, "red": red}


def g5_area_util(rec, layout):
    """El layout no puede inutilizar mas de una fraccion declarada del area util,
    por encima de la huella que ocupan los propios servicios.

    Captura de un solo golpe los dos modos de falla reales:
      - amurallar una region  -> queda sin conexion -> se pierde area
      - dejar pasillos angostos -> lo que hay detras no se alcanza -> se pierde area
    """
    base, _ = zona_ocupable(rec, None)
    con, det = zona_ocupable(rec, layout)
    a_base = float(base.sum()) * rec.area_celda
    a_con = float(con.sum()) * rec.area_celda
    a_serv = sum(c.rect()[2] * c.rect()[3] for c in (layout or []))
    perdida = max(0.0, a_base - a_con - a_serv)
    tope = FRACCION_PERDIDA_MAX * a_base
    v = max(0.0, perdida - tope)
    det.update({"ocupable": con, "base": base, "perdida": perdida,
                "tope": tope, "area_util": a_con})
    return v, det


# --- G6: cada area de servicio tiene que ser ALCANZABLE ----------------------
FRENTE_MIN = reg(
    "FRENTE_MIN", "f_min", 3.0, "m", "calibrar",
    "Criterio de diseno del proyecto",
    "Metros de frente que un area de servicio debe tener sobre la zona "
    "ocupable. Sin esto, el sistema puede colocar un bano dentro de una bolsa "
    "sellada por los muros del usuario: no pisa nada, no invade conos, y como "
    "esa bolsa ya era inservible tampoco reduce el area util. Pasaba las cinco "
    "reglas anteriores siendo un area a la que nadie puede llegar.")

_CRUZ = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)


def g6_alcanzable(rec, layout):
    """Un area de servicio a la que no se puede llegar no sirve para nada.

    Se mide el frente REAL sobre la zona ocupable: las celdas de la orilla del
    area que dan a piso por el que si se puede circular con el ancho normativo.
    Se usa vecindad de cruz y no de caja para contar contacto de arista, que es
    por donde se entra de verdad.
    """
    if not layout:
        return 0.0, {"culpables": [], "frentes": []}
    oc, _ = zona_ocupable(rec, layout)
    v, culpables, frentes = 0.0, [], []
    for i, c in enumerate(layout):
        m = rec.mascara_rect(c.rect())
        anillo = ndimage.binary_dilation(m, structure=_CRUZ) & ~m
        frente = float((anillo & oc).sum()) * rec.h
        frentes.append(frente)
        if frente < FRENTE_MIN:
            v += FRENTE_MIN - frente
            culpables.append(i)
    return v, {"culpables": culpables, "frentes": frentes}


# --- G7: distancia maxima de recorrido ---------------------------------------
def g7_recorrido(rec, layout, T_libre):
    """Ningun punto ocupable puede estar a mas de d_max de una salida.
    Usa el campo de tiempos a velocidad libre (T en segundos -> distancia)."""
    from parametros import V0
    libre = rec.libre(layout)
    d = np.where(np.isfinite(T_libre), T_libre * V0, np.inf)
    excede = libre & (d > DIST_MAX_SALIDA) & np.isfinite(d)
    v = float(np.maximum(d[excede] - DIST_MAX_SALIDA, 0).sum()) * 0.01 if excede.any() else 0.0
    return v, {"excede": excede, "distancia": d}


# --- orquestador --------------------------------------------------------------
ORDEN = [
    ("G1 dentro del recinto", g1_dentro),
    ("G2 sin traslape entre areas", g2_traslape),
    ("G3 sin invadir muros fijos", g3_muros),
    ("G4 salidas despejadas", g4_salidas),
    ("G5 area util conservada", g5_area_util),
    ("G6 areas alcanzables", g6_alcanzable),
]


def evaluar(rec, layout, corto=True):
    """Corre la capa geometrica en orden de costo creciente.

    corto=True detiene en el primer fallo: es lo que se quiere dentro del
    optimizador. corto=False evalua todo: es lo que se quiere para diagnosticar.
    """
    total, pasos = 0.0, []
    for nombre, fn in ORDEN:
        v, det = fn(rec, layout)
        pasos.append({"nombre": nombre, "violacion": v, "detalle": det})
        total += v
        if corto and v > 0:
            break
    return {"factible": total <= 0.0, "violacion": total, "pasos": pasos}
