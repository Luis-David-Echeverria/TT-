"""
Generacion de layouts para experimentar.

DOS MODOS, Y LA DIFERENCIA IMPORTA PARA LEER LA MATRIZ DE CORRELACION:

  amplio    solo lo ESTRUCTURAL -- que el modulo quepa en el recinto, que no se
            encime con otro, que no este encima de un muro -- mas la condicion
            de que se pueda llegar a el. Nada mas.

  estricto  la capa geometrica completa, incluidos los criterios de diseno
            (conos de salida despejados, area util conservada).

Por que hacen falta los dos: filtrar con la capa completa ANTES de medir la
correlacion sesga la muestra hacia la region que el propio criterio de diseno
considera buena, y entonces la correlacion que salga describe ese criterio en
vez de describir el problema. El modo amplio da la nube sin recortar. El modo
estricto dice como cambia la respuesta cuando solo se miran layouts que un
responsable de proteccion civil aceptaria. Si las dos matrices coinciden, la
conclusion es robusta; si no coinciden, eso mismo es un resultado.

Por que 'amplio' conserva la condicion de alcanzable: un modulo dentro de una
bolsa cerrada tiene f1 = infinito. No es un layout malo, es un layout sin valor
de f1, y meterlo en una correlacion de rangos con infinitos no significa nada.
Se excluye por indefinicion, no por calidad.
"""
import numpy as np

from geometria import g1_dentro, g2_traslape, g3_muros, g6_alcanzable, evaluar
from recinto import POR_CLAVE, Colocacion, cuantizar

CONTEO = {"SAN": 3, "COM": 3, "BEB": 2, "MED": 1}

# solo estructura: el modulo existe fisicamente donde se le puso
ESTRUCTURAL = [g1_dentro, g2_traslape, g3_muros]


def violacion_amplia(rec, layout, con_alcance=True):
    v = 0.0
    for fn in ESTRUCTURAL:
        v += fn(rec, layout)[0]
        if v > 0:
            return v
    if con_alcance:
        v += g6_alcanzable(rec, layout)[0]
    return v


def _propone(rec, rng, clave):
    t = POR_CLAVE[clave]
    rot = int(rng.integers(2))
    w, f = (t.ancho, t.fondo) if rot == 0 else (t.fondo, t.ancho)
    return Colocacion(clave,
                      cuantizar(rng.uniform(0, rec.W - w)),
                      cuantizar(rng.uniform(0, rec.H - f)), rot)


def generar(rec, rng, conteo=None, modo="amplio", intentos=3000):
    """Un layout, colocando modulo por modulo con rechazo.

    El rechazo es incremental: se acepta cada modulo si el layout parcial sigue
    valido. Es mucho mas barato que muestrear el layout completo y rechazarlo
    entero, y NO sesga el resultado respecto a eso ultimo mientras la condicion
    sea monotona -- agregar un modulo nunca arregla una violacion previa.

    OJO para cuando toque el algoritmo: esto es un GENERADOR de poblacion
    inicial, no un operador de variacion. Dentro del optimizador el rechazo
    esta mal: dos padres infactibles pueden dar un hijo factible, y filtrar
    mata esa exploracion. Ahi los infactibles se quedan y se ordenan por
    dominancia restringida.
    """
    conteo = conteo or CONTEO
    claves = [k for k, n in conteo.items() for _ in range(n)]
    rng.shuffle(claves)          # que el orden de colocacion no favorezca a un tipo
    lay = []
    for clave in claves:
        for _ in range(intentos):
            c = _propone(rec, rng, clave)
            if modo == "estricto":
                ok = evaluar(rec, lay + [c], corto=True)["factible"]
            else:
                ok = violacion_amplia(rec, lay + [c], con_alcance=False) <= 0
            if ok:
                lay.append(c)
                break
        else:
            return None
    # la condicion de alcanzable se revisa sobre el layout COMPLETO: un modulo
    # puede quedar encerrado por otro que se coloco despues
    if modo != "estricto" and g6_alcanzable(rec, lay)[0] > 0:
        return None
    return lay


def muestra(rec, n, semilla=0, conteo=None, modo="amplio", intentos=3000):
    """n layouts independientes y reproducibles.

    Cada layout toma su propio flujo de numeros al azar via SeedSequence.spawn,
    no posiciones sucesivas de un solo flujo. Asi el layout k es el mismo aunque
    se cambie n, se reanude el barrido o se corra en paralelo en otro orden.
    """
    hijos = np.random.SeedSequence(semilla).spawn(n)
    out, fallos = [], 0
    for i, s in enumerate(hijos):
        lay = generar(rec, np.random.default_rng(s), conteo, modo, intentos)
        if lay is None:
            fallos += 1
            continue
        out.append((i, lay))
    return out, fallos
