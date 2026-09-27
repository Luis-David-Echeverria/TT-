"""
Geometria del recinto tipo y rasterizacion a rejilla.
Todo en metros. El origen (0,0) es la esquina inferior izquierda.

Este archivo define el "caso de estudio" del boceto: un recinto rectangular
con escenario fijo, salidas fijas en el perimetro (condiciones de frontera
dictadas por PC) y sus conos de aproximacion, que son zona prohibida.
"""
import numpy as np

# --- dimensiones del recinto -------------------------------------------------
W, H = 100.0, 80.0          # ancho x fondo del recinto

# El escenario ocupa una franja preasignada al fondo. La FBS NO la toca.
FRANJA_ESCENARIO = 62.0     # y >= 62 es franja de escenario
ESCENARIO = (30.0, 68.0, 40.0, 12.0)     # (x, y, w, h) pegado al muro trasero

# Region donde vive la particion FBS
REGION_FBS = (0.0, 0.0, W, FRANJA_ESCENARIO)

# --- salidas fijas en el perimetro ------------------------------------------
# (x, y, w, h) del vano + lado. Son fuentes/sumideros de masa.
SALIDAS = [
    ("S1", (12.0, 0.0, 8.0, 1.0), "sur"),
    ("S2", (58.0, 0.0, 8.0, 1.0), "sur"),
    ("S3", (0.0, 22.0, 1.0, 8.0), "oeste"),
    ("S4", (99.0, 34.0, 1.0, 8.0), "este"),
]
# Los accesos de entrada (escenario "entrada") son un subconjunto de las salidas
ACCESOS = ["S1", "S2"]

PROF_CONO = 10.0    # profundidad del cono de aproximacion
ENSANCHE_CONO = 5.0  # cuanto se abre a cada lado


def conos_aproximacion():
    """Rectangulos (aprox. trapezoidal simplificada a rect) que deben quedar
    despejados frente a cada salida. Restriccion dura, verificable sin simular."""
    conos = []
    for nom, (x, y, w, h), lado in SALIDAS:
        if lado == "sur":
            conos.append((nom, (x - ENSANCHE_CONO, 0.0, w + 2 * ENSANCHE_CONO, PROF_CONO)))
        elif lado == "norte":
            conos.append((nom, (x - ENSANCHE_CONO, H - PROF_CONO, w + 2 * ENSANCHE_CONO, PROF_CONO)))
        elif lado == "oeste":
            conos.append((nom, (0.0, y - ENSANCHE_CONO, PROF_CONO, h + 2 * ENSANCHE_CONO)))
        else:
            conos.append((nom, (W - PROF_CONO, y - ENSANCHE_CONO, PROF_CONO, h + 2 * ENSANCHE_CONO)))
    return conos


# --- catalogo de areas de servicio ------------------------------------------
# capacidad = personas que puede atender simultaneamente sin generar cola
SERVICIOS = [
    # (id, tipo, area_m2, capacidad)
    ("B1", "banos",   90.0, 1800),
    ("B2", "banos",   90.0, 1800),
    ("B3", "banos",   90.0, 1800),
    ("C1", "comida", 120.0, 1500),
    ("C2", "comida", 120.0, 1500),
    ("C3", "comida", 120.0, 1500),
    ("D1", "bebidas", 80.0, 1600),
    ("D2", "bebidas", 80.0, 1600),
    ("D3", "bebidas", 80.0, 1600),
    ("M1", "medico",  80.0, 400),
]

# Fraccion de asistentes que demanda cada tipo de servicio en operacion normal.
DEMANDA = {"banos": 0.34, "comida": 0.26, "bebidas": 0.32, "medico": 0.08}

ASISTENTES = 14000

N_DUMMY = 20        # departamentos ficticios = area de circulacion / piso libre
AR_MAX = 4.0        # relacion de aspecto maxima de una zona de servicio
DIM_MIN = 3.5       # lado minimo de una zona (m)
ANCHO_LIBRE_MIN = 4.5   # pasillo libre normativo entre elementos (m)


class Bloque:
    __slots__ = ("bid", "tipo", "area", "cap", "es_servicio")

    def __init__(self, bid, tipo, area, cap, es_servicio):
        self.bid, self.tipo, self.area = bid, tipo, area
        self.cap, self.es_servicio = cap, es_servicio

    def __repr__(self):
        return f"<{self.bid} {self.tipo} {self.area:.0f}m2>"


def catalogo_bloques():
    """Servicios reales + departamentos ficticios que rellenan la region FBS.
    Los ficticios son la forma estandar en UA-FLP/FBS de manejar el area no
    asignada; aqui representan piso libre de circulacion."""
    bloques = [Bloque(i, t, a, c, True) for (i, t, a, c) in SERVICIOS]
    area_serv = sum(b.area for b in bloques)
    area_libre = REGION_FBS[2] * REGION_FBS[3] - area_serv
    a_dummy = area_libre / N_DUMMY
    for k in range(N_DUMMY):
        bloques.append(Bloque(f"L{k}", "circulacion", a_dummy, 0, False))
    return bloques


# --- rejilla -----------------------------------------------------------------
class Rejilla:
    """Discretizacion del recinto. h = tamano de celda en metros."""

    def __init__(self, h=2.0):
        self.h = h
        self.nx = int(round(W / h))
        self.ny = int(round(H / h))
        self.xc = (np.arange(self.nx) + 0.5) * h
        self.yc = (np.arange(self.ny) + 0.5) * h
        self.X, self.Y = np.meshgrid(self.xc, self.yc)   # shape (ny, nx)
        self.area_celda = h * h

    def mascara_rect(self, rect):
        x, y, w, hh = rect
        return (self.X >= x) & (self.X < x + w) & (self.Y >= y) & (self.Y < y + hh)

    def libre_base(self):
        """Celdas transitables ignorando los servicios: recinto menos escenario."""
        m = np.ones((self.ny, self.nx), dtype=bool)
        m &= ~self.mascara_rect(ESCENARIO)
        return m

    def mascara_salidas(self, nombres=None):
        m = np.zeros((self.ny, self.nx), dtype=bool)
        for nom, rect, lado in SALIDAS:
            if nombres is not None and nom not in nombres:
                continue
            x, y, w, hh = rect
            # engrosar el vano para que caiga al menos una celda
            m |= self.mascara_rect((x, y, max(w, self.h), max(hh, self.h)))
        return m
