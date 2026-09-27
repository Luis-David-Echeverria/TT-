"""
Recinto, catalogo de areas de servicio y representacion del layout.

REPRESENTACION: colocacion directa. Cada area de servicio lleva su propia
posicion y rotacion. Se eligio sobre FBS (Flexible Bay Structure, la
representacion estandar del UA-FLP) por dos razones propias de este problema:

  1. El usuario PINTA muros y elementos fijos. FBS particiona todo el recinto
     en bandas y no admite clavar un obstaculo preexistente en medio.
  2. Aqui pocas areas chicas se colocan en un espacio mayormente vacio. Eso es
     un problema de COLOCACION, no de PARTICION, que es para lo que FBS sirve.

Costo de la decision: los traslapes ya no son imposibles por construccion y hay
que verificarlos. Con areas chicas en espacio amplio es barato.
"""
from dataclasses import dataclass
import numpy as np

from parametros import H_CELDA, reg

# Las posiciones se cuantizan a esta rejilla. Dos razones:
#   1) nadie coloca un modulo sanitario al centimetro; 0.5 m es mas fino que la
#      precision con la que se replantea en obra
#   2) hace que dos layouts "iguales" sean literalmente iguales, y por tanto
#      memoizables: con posiciones en punto flotante libre, la probabilidad de
#      repetir una es practicamente nula y la cache nunca acierta
PASO_POS = reg("PASO_POS", "Δx", 0.25, "m", "calibrar",
               "Precision de replanteo en obra (criterio del proyecto)",
               "Cuantizacion de las posiciones. Tambien reduce el espacio de "
               "busqueda y habilita la memoizacion de la funcion objetivo.")


def cuantizar(v, paso=PASO_POS):
    return round(float(v) / paso) * paso


# =============================================================================
# catalogo de areas de servicio
# =============================================================================
@dataclass(frozen=True)
class TipoArea:
    clave: str
    nombre: str
    ancho: float      # m, en su orientacion base
    fondo: float      # m
    color: str

    @property
    def area(self):
        return self.ancho * self.fondo


# Dimensiones de equipo comercial tipico para eventos.
# ESTADO: catalogo -> respaldar con ficha de proveedor o pliego del evento,
# NO con literatura cientifica. Son dimensiones de producto, no constantes.
CATALOGO = [
    TipoArea("SAN", "Modulo sanitario", 8.0, 3.0, "#4C9BE8"),
    TipoArea("COM", "Carpa de comida",  5.0, 5.0, "#E8A33D"),
    TipoArea("BEB", "Barra de bebidas", 8.0, 2.5, "#7BC96F"),
    TipoArea("MED", "Primeros auxilios", 5.0, 5.0, "#A96BE0"),
]
POR_CLAVE = {t.clave: t for t in CATALOGO}


@dataclass
class Colocacion:
    """Un area de servicio puesta en el recinto."""
    tipo: str
    x: float
    y: float
    rot: int = 0      # 0 = base, 1 = girada 90 grados

    def clave(self):
        """Identidad del elemento ya cuantizada: es la llave de la memoizacion."""
        return (self.tipo, int(round(self.x / PASO_POS)),
                int(round(self.y / PASO_POS)), self.rot)

    def rect(self):
        t = POR_CLAVE[self.tipo]
        w, f = (t.ancho, t.fondo) if self.rot == 0 else (t.fondo, t.ancho)
        return (self.x, self.y, w, f)


# =============================================================================
# el recinto
# =============================================================================
@dataclass
class Salida:
    nombre: str
    lado: str         # 'N','S','E','O'
    centro: float     # coordenada a lo largo del lado, en m
    ancho: float      # m

    def ancho_util(self, capa_limite):
        """Ancho efectivo: la gente no usa la franja pegada a cada jamba."""
        return max(0.0, self.ancho - 2.0 * capa_limite)


class Recinto:
    def __init__(self, W=100.0, H=60.0, h=H_CELDA, salidas=None):
        self.W, self.H, self.h = float(W), float(H), float(h)
        self.nx = int(round(W / h))
        self.ny = int(round(H / h))
        self.xc = (np.arange(self.nx) + 0.5) * h
        self.yc = (np.arange(self.ny) + 0.5) * h
        self.X, self.Y = np.meshgrid(self.xc, self.yc)
        self.area_celda = h * h
        self.muros = np.zeros((self.ny, self.nx), dtype=bool)   # lo que pinta el usuario
        self.salidas = list(salidas) if salidas else []

    # ---- geometria basica ----
    def mascara_rect(self, rect):
        x, y, w, f = rect
        return (self.X >= x) & (self.X < x + w) & (self.Y >= y) & (self.Y < y + f)

    def pintar_muro(self, rect, valor=True):
        self.muros[self.mascara_rect(rect)] = valor

    def mascara_salidas(self):
        """Celdas de salida, sobre el perimetro."""
        m = np.zeros((self.ny, self.nx), dtype=bool)
        for s in self.salidas:
            a, b = s.centro - s.ancho / 2, s.centro + s.ancho / 2
            if s.lado == "S":
                m |= (self.X >= a) & (self.X < b) & (self.Y < self.h)
            elif s.lado == "N":
                m |= (self.X >= a) & (self.X < b) & (self.Y >= self.H - self.h)
            elif s.lado == "O":
                m |= (self.Y >= a) & (self.Y < b) & (self.X < self.h)
            elif s.lado == "E":
                m |= (self.Y >= a) & (self.Y < b) & (self.X >= self.W - self.h)
        return m

    def ancho_total_salidas(self, capa_limite):
        return sum(s.ancho_util(capa_limite) for s in self.salidas)

    # ---- obstaculos ----
    def obstaculos(self, layout=None):
        """Muros pintados + areas de servicio colocadas."""
        obst = self.muros.copy()
        if layout:
            for c in layout:
                obst |= self.mascara_rect(c.rect())
        obst &= ~self.mascara_salidas()          # una salida nunca es obstaculo
        return obst

    def libre(self, layout=None):
        return ~self.obstaculos(layout)


# =============================================================================
# instancia de ejemplo
# =============================================================================
def recinto_ejemplo(h=H_CELDA):
    """Nave rectangular con cuatro salidas y dos elementos fijos de obra.

    Los elementos fijos son el caso que motivo abandonar FBS: una columna en
    medio del recinto no encaja en una particion por bandas.
    """
    r = Recinto(W=100.0, H=60.0, h=h, salidas=[
        Salida("S1", "S", 20.0, 8.0),
        Salida("S2", "S", 70.0, 8.0),
        Salida("O1", "O", 30.0, 6.0),
        Salida("E1", "E", 35.0, 6.0),
    ])
    # elementos fijos de construccion (lo que el usuario "pinta")
    r.pintar_muro((46.0, 24.0, 4.0, 4.0))      # columna central
    r.pintar_muro((0.0, 50.0, 22.0, 3.0))      # muro / barra fija al fondo
    return r


def layout_aleatorio(rec, rng, n_por_tipo=None):
    """Coloca areas al azar dentro del recinto. NO garantiza factibilidad:
    de eso se encarga la capa geometrica."""
    if n_por_tipo is None:
        n_por_tipo = {"SAN": 3, "COM": 3, "BEB": 2, "MED": 1}
    lay = []
    for clave, n in n_por_tipo.items():
        t = POR_CLAVE[clave]
        for _ in range(n):
            rot = int(rng.integers(2))
            w, f = (t.ancho, t.fondo) if rot == 0 else (t.fondo, t.ancho)
            lay.append(Colocacion(
                clave,
                float(rng.uniform(0, rec.W - w)),
                float(rng.uniform(0, rec.H - f)),
                rot))
    return lay


def layout_factible(rec, rng, n_por_tipo=None, intentos=4000):
    """Muestreo por rechazo: propone colocaciones al azar hasta que la capa
    geometrica las acepta. Sirve como semilla y como 'layout aleatorio' de
    referencia contra el que comparar al optimizado."""
    from geometria import evaluar
    if n_por_tipo is None:
        n_por_tipo = {"SAN": 3, "COM": 3, "BEB": 2, "MED": 1}
    claves = [k for k, n in n_por_tipo.items() for _ in range(n)]
    lay = []
    for clave in claves:
        t = POR_CLAVE[clave]
        puesto = False
        for _ in range(intentos):
            rot = int(rng.integers(2))
            w, f = (t.ancho, t.fondo) if rot == 0 else (t.fondo, t.ancho)
            c = Colocacion(clave,
                           cuantizar(rng.uniform(0, rec.W - w)),
                           cuantizar(rng.uniform(0, rec.H - f)), rot)
            if evaluar(rec, lay + [c], corto=True)["factible"]:
                lay.append(c)
                puesto = True
                break
        if not puesto:
            return None
    return lay
