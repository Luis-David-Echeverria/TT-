"""
PARAMETROS DEL MODELO Y SU PROCEDENCIA.

Regla del TT: ningun numero se inventa. Cada parametro declara de donde sale y
en que estado esta. Los que no tienen fuente se marcan como tal y se ven en rojo
en la tabla del notebook, para que no se cuelen a la tesis sin querer.

ESTADOS
  medido     valor empirico publicado                       -> se cita
  derivado   se calcula de otros parametros                 -> no requiere cita propia
  normativo  lo fija un reglamento                          -> se cita articulo
  catalogo   dimension de equipo comercial                  -> se cita catalogo/proveedor
  numerico   discretizacion; sin contraparte empirica       -> requiere analisis de convergencia
  calibrar   modelado; sin contraparte empirica directa     -> requiere analisis de sensibilidad
  PENDIENTE  todavia no se verifico la fuente               -> BLOQUEA la tesis
"""
from dataclasses import dataclass, field


@dataclass
class Param:
    simbolo: str
    valor: float
    unidad: str
    estado: str
    fuente: str
    nota: str = ""

    def __float__(self):
        return float(self.valor)


REGISTRO: dict = {}


def reg(clave, simbolo, valor, unidad, estado, fuente, nota=""):
    REGISTRO[clave] = Param(simbolo, valor, unidad, estado, fuente, nota)
    return valor


# =============================================================================
# 1. DIAGRAMA FUNDAMENTAL DE PEATONES  (relacion densidad - velocidad)
# =============================================================================
# v(rho) = v0 * [ 1 - exp( -gamma * (1/rho - 1/rho_max) ) ]

V0 = reg("V0", "v₀", 1.34, "m/s", "medido",
         "Weidmann (1993), Transporttechnik der Fussgaenger, IVT/ETH Zuerich, Schriftenreihe 90",
         "Velocidad libre media de peatones en plano. VERIFICAR en el original: "
         "suele citarse de segunda mano.")

RHO_MAX = reg("RHO_MAX", "ρ_max", 5.4, "pers/m²", "medido",
              "Weidmann (1993)",
              "Densidad de atasco: la velocidad se anula. Es el limite superior fisico.")

GAMMA = reg("GAMMA", "γ", 1.913, "pers/m²", "medido",
            "Weidmann (1993)",
            "Parametro de forma de la curva.")

# -----------------------------------------------------------------------------
RHO_PERDIDA_CONTROL = reg(
    "RHO_PERDIDA_CONTROL", "ρ_c", 4.0, "pers/m²", "medido",
    "van Toll et al., SPH-enhanced crowd simulation, Computers & Graphics (2021); "
    "INRIA hal-03270915",
    "Por encima de este valor la gente PIERDE el movimiento individual y es "
    "desplazada por la presion del grupo. Es el mejor argumento para usar un "
    "modelo continuo: arriba de aqui, la decision individual que simulan los "
    "modelos de agentes es justamente lo que deja de ocurrir.")

# -----------------------------------------------------------------------------
J_ESPECIFICO = reg(
    "J_ESPECIFICO", "J_s", 1.32, "pers/(s·m)", "PENDIENTE",
    "Seyfried et al., experimentos de cuello de botella (grupo de Juelich)",
    "Flujo especifico maximo por metro de ancho util de salida. Los valores "
    "publicados varian segun el estudio y segun como se defina el ancho. "
    "VERIFICAR y citar el valor exacto con su experimento.")

CAPA_LIMITE = reg(
    "CAPA_LIMITE", "b", 0.15, "m", "PENDIENTE",
    "Seyfried et al.; efecto de borde en cuellos de botella",
    "Franja pegada a cada jamba que la gente no usa. El ancho util de una "
    "puerta es (ancho real - 2b). VERIFICAR el valor.")


# =============================================================================
# 2. NORMATIVA  (todo esto lo fija un reglamento, NO el modelo)
# =============================================================================
ANCHO_LIBRE_MIN = reg(
    "ANCHO_LIBRE_MIN", "w_min", 3.0, "m", "PENDIENTE",
    "Reglamento de Construcciones CDMX + NTC para el Proyecto Arquitectonico",
    "Ancho libre minimo de circulacion. VALOR PROVISIONAL. Hay que sacarlo del "
    "articulo y citar tabla y fecha de publicacion.")

DIST_MAX_SALIDA = reg(
    "DIST_MAX_SALIDA", "d_max", 40.0, "m", "PENDIENTE",
    "RCDF + NTC / reglamento contra incendios aplicable",
    "Distancia maxima de recorrido desde cualquier punto ocupable hasta una "
    "salida. VALOR PROVISIONAL.")

T_EVAC_MAX = reg(
    "T_EVAC_MAX", "t_lim", 600.0, "s", "PENDIENTE",
    "Programa Especial de Proteccion Civil / criterio del proyecto",
    "Tiempo maximo admisible de desalojo (10 min). VALOR PROVISIONAL. "
    "OJO con la cifra de 40 s que circula: la cota fisica es "
    "t_min = N/(J_s x ancho_util) y ninguna distribucion la baja. Para 5 000 "
    "personas en 40 s harian falta 95 m de salida util, y para 20 000 harian "
    "falta 379 m -- mas que el perimetro completo de una nave de 100x60 m. "
    "Esos 40 s no pueden ser desalojo total de un evento masivo; verificar a "
    "que se refiere exactamente la fuente.")

RHO_DISENO = reg(
    "RHO_DISENO", "ρ_d", 3.5, "pers/m²", "calibrar",
    "Acotado por RHO_PERDIDA_CONTROL como techo fisico",
    "Densidad de diseno para calcular el aforo: aforo = area util x ρ_d. "
    "Se usa esta via en vez del factor normativo m²/persona porque conecta "
    "directamente con el regimen fisico que modela el simulador. El factor "
    "normativo debe usarse como CONTRASTE, no como entrada.")


# =============================================================================
# 3. CATALOGO DE EQUIPO  (dimensiones comerciales)
# =============================================================================
# Se declaran en recinto.py. Estado 'catalogo': hay que respaldarlas con fichas
# de proveedor o con el pliego del evento, no con literatura cientifica.


# =============================================================================
# 4. DISCRETIZACION Y ESQUEMA NUMERICO
# =============================================================================
H_CELDA = reg("H_CELDA", "h", 1.0, "m", "numerico", "-",
              "Lado de celda. Requiere estudio de convergencia: verificar que "
              "t_evac se estabiliza al refinar.")

DT = reg("DT", "Δt", 0.3, "s", "numerico", "-",
         "Paso de tiempo. Cota CFL: dt <= h/v0 = 0.746 s. MEDIDO: dt=1.0 s la "
         "viola y el orden entre layouts cae a 0.798. Y subir dt NO acelera: lo "
         "caro es resolver el campo, no dar pasos, asi que emparejar el "
         "refresco con el paso (k_c=1) sale mas caro que dt chico con k_c alto.")

REFRESCO_CAMPO = reg(
    "REFRESCO_CAMPO", "k_c", 8, "pasos", "numerico", "-",
    "Cada cuantos pasos se re-resuelve el campo acoplado (con dt=0.3 -> cada "
    "2.4 s). MEDIDO sobre 14 layouts con la configuracion final (p=3, reparto "
    "uniforme), correlacion de rangos contra k_c=2: "
    "k_c=4 -> 0.982/0.982 (8.2 s); k_c=6 -> 0.945/0.960 (5.8 s); "
    "k_c=8 -> 0.941/0.960 (4.7 s); k_c=10 -> 0.920/0.952; "
    "k_c=12 -> 0.843/0.952; k_c=15 -> 0.807/0.925. "
    "Se elige 8: mismo orden que 6 y 19 % mas barato. "
    "Lo que se valida es el ORDEN entre layouts, no el valor: el valor converge "
    "mucho antes que el orden, y medirlo sobre un solo layout lleva a elegir "
    "k_c demasiado grande.")

EXP_REPARTO = reg(
    "EXP_REPARTO", "p", 3.0, "-", "calibrar", "-",
    "Exponente del reparto de flujo entre vecinos cuesta abajo en 2D. Godunov "
    "resuelve por cara, en una dimension; en la rejilla una celda puede tener "
    "varios vecinos cuesta abajo y hay que repartir. Es el UNICO parametro del "
    "modelo sin respaldo empirico. Con p=1 los frentes se ensanchan por "
    "difusion; con p alto reaparece el sesgo de rejilla. "
    "MEDIDO (orden entre 12 layouts, contra p=1): p=2 -> t_des 0.544, E 0.937; "
    "p=4 -> t_des 0.373, E 0.573. El orden de t_des es FRAGIL a p; el de E "
    "aguanta mucho mejor. Es el unico parametro del modelo sin respaldo "
    "empirico, asi que la sensibilidad hay que reportarla sobre E, que es la "
    "candidata a objetivo de riesgo.")

EPS_VACIADO = reg(
    "EPS_VACIADO", "eps", 0.005, "-", "numerico", "-",
    "Tolerancia de vaciado para el tiempo de desalojo. Existe solo porque la "
    "masa decae asintoticamente y el 100 % exacto nunca se alcanza.")

SIGMA_KERNEL = reg(
    "SIGMA_KERNEL", "σ_k", 2.0, "celdas", "calibrar",
    "Treuille, Cooper & Popovic (2006), Continuum Crowds, ACM TOG 25(3)",
    "Ancho del nucleo con que se estima la densidad continua a partir de la "
    "masa discreta. En Continuum Crowds la densidad se obtiene por splatting "
    "con nucleo; en SPH es el smoothing kernel. NO es un filtro cosmetico: es "
    "parte del estimador de densidad, y por eso entra en el modelo. "
    "Requiere analisis de sensibilidad.")


# =============================================================================
# utilidades para el notebook
# =============================================================================
ORDEN_ESTADO = {"PENDIENTE": 0, "calibrar": 1, "normativo": 2,
                "catalogo": 3, "numerico": 4, "medido": 5, "derivado": 6}


def tabla(filtro=None):
    """Filas (clave, simbolo, valor, unidad, estado, fuente, nota) ordenadas
    por urgencia: lo PENDIENTE primero."""
    items = sorted(REGISTRO.items(),
                   key=lambda kv: (ORDEN_ESTADO.get(kv[1].estado, 9), kv[0]))
    return [(k, p.simbolo, p.valor, p.unidad, p.estado, p.fuente, p.nota)
            for k, p in items if filtro is None or p.estado == filtro]


def pendientes():
    return [k for k, p in REGISTRO.items() if p.estado == "PENDIENTE"]
