"""
CONTRATOS DE LA API.

Criterio de diseno: los endpoints describen ESCENARIOS, no llamadas a funciones
concretas. Un escenario es "que recinto, que layout, cuanta gente y como
repartida, con que numerica". Asi se puede cambiar el solver, meter un objetivo
nuevo o cambiar el esquema numerico por dentro sin tocar el contrato ni la UI.

Todo lo que la UI necesita para dibujar (paleta, umbrales, catalogo) lo sirve el
backend. La UI NO reimplementa nada del modelo: si tuviera su propia copia,
las dos podrian desviarse y la visualizacion dejaria de ser evidencia.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


# --- geometria de entrada ----------------------------------------------------
class SalidaIn(BaseModel):
    nombre: str
    lado: Literal["N", "S", "E", "O"]
    centro: float = Field(gt=0, description="posicion a lo largo del lado [m]")
    ancho: float = Field(gt=0, description="ancho del vano [m]")


class RectIn(BaseModel):
    x: float
    y: float
    w: float
    h: float


class RecintoIn(BaseModel):
    W: float = Field(100.0, gt=0)
    H: float = Field(60.0, gt=0)
    salidas: list[SalidaIn] = []
    muros: list[RectIn] = Field(default_factory=list,
                                description="elementos fijos de obra")


class ColocacionIn(BaseModel):
    tipo: str = Field(description="clave del catalogo: SAN, COM, BEB, MED")
    x: float
    y: float
    rot: Literal[0, 1] = 0


# --- escenario y numerica ----------------------------------------------------
class Distribucion(BaseModel):
    """Como esta repartida la gente al iniciar la evacuacion.

    Es una decision de modelado critica, no un detalle: con 'uniforme' el layout
    deja de importar (las puertas saturan y siempre hay una salida cerca); con
    'concentrada' -- la situacion real de un concierto -- si decide.
    """
    tipo: Literal["uniforme", "concentrada"] = "concentrada"
    foco: Optional[tuple[float, float]] = None
    escala: float = Field(18.0, gt=0, description="longitud de decaimiento [m]")


class Escenario(BaseModel):
    aforo: float = Field(6000.0, gt=0)
    distribucion: Distribucion = Distribucion()


class Numerica(BaseModel):
    h: float = Field(1.0, gt=0, description="lado de celda [m]")
    dt: Optional[float] = Field(None, description="paso de tiempo [s]; None = automatico")
    t_max: float = 1600.0
    n_cuadros: int = 45


# --- peticiones --------------------------------------------------------------
class PeticionGeometria(BaseModel):
    recinto: RecintoIn
    layout: list[ColocacionIn] = []


class PeticionAforo(BaseModel):
    recinto: RecintoIn
    layout: list[ColocacionIn] = []
    conteo: dict[str, int] = {"SAN": 3, "COM": 3, "BEB": 2, "MED": 1}
    densidad_diseno: Optional[float] = None


class PeticionCampo(BaseModel):
    recinto: RecintoIn
    layout: list[ColocacionIn] = []
    numerica: Numerica = Numerica()
    n_isocronas: int = 14


class PeticionProponer(BaseModel):
    """El usuario NO coloca las areas: dice cuantas quiere de cada tipo y el
    sistema las acomoda respetando la capa geometrica."""
    recinto: RecintoIn
    conteo: dict[str, int] = {"SAN": 3, "COM": 3, "BEB": 2, "MED": 1}
    semilla: int = 0


class RespProponer(BaseModel):
    layout: list["ColocacionIn"]
    intentos: int
    logrado: bool
    mensaje: str = ""


class Opciones(BaseModel):
    """Parametros del algoritmo. Se declaran explicitos y no como dict suelto
    para que queden en la documentacion y en el registro del experimento."""
    generaciones: int = Field(10, ge=1, le=500)
    mu: int = Field(4, ge=1, le=100, description="tamano de la poblacion que sobrevive")
    lam: int = Field(12, ge=1, le=400, description="descendientes por generacion")
    sigma0: float = Field(9.0, gt=0, description="desviacion inicial de la mutacion [m]")


class PeticionTrabajo(BaseModel):
    """Un trabajo asincrono. 'tipo' selecciona que se corre; agregar un tipo
    nuevo (otra funcion objetivo, otro escenario) no rompe el contrato."""
    tipo: Literal["evacuacion", "optimizacion", "comparacion"] = "evacuacion"
    recinto: RecintoIn
    layout: list[ColocacionIn] = Field(
        default_factory=list,
        description="Si viene vacio y hay 'conteo', el sistema propone el acomodo. "
                    "Ese es el flujo normal: el usuario define recinto, muros y "
                    "salidas; DONDE van las areas lo decide el sistema.")
    conteo: dict[str, int] = Field(
        default_factory=dict,
        description="Cuantas areas de cada tipo. Se usa cuando 'layout' va vacio.")
    semilla: int = 0
    escenario: Escenario = Escenario()
    numerica: Numerica = Numerica()
    opciones: "Opciones" = Field(default_factory=lambda: Opciones())
    simular_infactible: bool = Field(
        False,
        description="Simula aunque el layout no pase la capa geometrica. La reja "
                    "existe para no gastar computo en el simulador interactivo, "
                    "pero un layout infactible SI tiene evacuacion bien definida: "
                    "violar un criterio de diseno no impide que la gente camine. "
                    "Se necesita para reproducir evaluaciones guardadas -- en la "
                    "muestra amplia dos de cada tres layouts son infactibles y sus "
                    "metricas estan medidas -- y lo va a necesitar el optimizador, "
                    "que debe rankear infactibles por dominancia restringida en "
                    "vez de descartarlos.")


# --- respuestas --------------------------------------------------------------
class PasoGeometria(BaseModel):
    nombre: str
    violacion: float
    culpables: list[int] = []


class RespGeometria(BaseModel):
    factible: bool
    violacion: float
    pasos: list[PasoGeometria]
    conos: list[RectIn]


class RespAforo(BaseModel):
    area_total: float
    area_ocupable: float
    area_aislada: float
    area_servicios: float
    area_neta: float
    densidad_diseno: float
    aforo: float
    ancho_util_salidas: float
    cota_puertas_s: float


class Campo(BaseModel):
    """Un campo escalar servido como bytes. La UI lo pinta; no lo calcula."""
    nx: int
    ny: int
    h: float
    vmin: float
    vmax: float
    datos_b64: str = Field(description="uint8, fila 0 = borde inferior")
    mascara_b64: str = Field(description="uint8: 1 = celda valida")


class RespCampo(BaseModel):
    tiempos: Campo
    isocronas: list[float]
    dir_x_b64: str
    dir_y_b64: str
    t_max_s: float


class EstadoTrabajo(BaseModel):
    id: str
    tipo: str
    estado: Literal["encolado", "corriendo", "listo", "error"]
    progreso: float = 0.0
    mensaje: str = ""
    resultado: Optional[dict] = None
