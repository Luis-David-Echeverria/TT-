"""
API del simulador de layout.

Contrato estable, internos libres. Los endpoints hablan de ESCENARIOS; el
solver, el esquema numerico y las funciones objetivo pueden cambiar por dentro
sin tocar la UI.

Lanzar:
    py -3.12 -m uvicorn api.main:app --reload --port 8000
    (o doble clic en servir.bat)

Documentacion automatica en  http://localhost:8000/docs
"""
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import esquemas as E
from . import servicio as S
from .resultados import router as router_resultados

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(RAIZ, "web")

app = FastAPI(title="TT — simulador de layout para eventos masivos",
              version="0.1",
              description="Modelo continuo de multitud (Eikonal + FMM + Weidmann + "
                          "Godunov/CTM) expuesto como servicio.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


# --- metadatos ---------------------------------------------------------------
@app.get("/api/catalogo", tags=["metadatos"])
def get_catalogo():
    """Catalogo de areas, paleta y TODOS los parametros con su procedencia.

    La UI toma de aqui la paleta y los umbrales para no tener su propia copia:
    si los duplicara, las dos podrian desviarse.
    """
    return S.catalogo()


# --- capa geometrica ---------------------------------------------------------
@app.post("/api/geometria", response_model=E.RespGeometria, tags=["capa 0"])
def post_geometria(pet: E.PeticionGeometria):
    """Restricciones duras. Microsegundos a milisegundos, SIN simular.

    Si un layout no pasa por aqui, no tiene sentido preguntarse cuanto tarda la
    evacuacion. Devuelve que regla fallo y que areas son culpables.
    """
    return S.geometria(pet)


@app.post("/api/aforo", response_model=E.RespAforo, tags=["capa 0"])
def post_aforo(pet: E.PeticionAforo):
    """Area util (via FMM desde las salidas) y aforo de diseno.

    Incluye la cota por capacidad de puertas: si el tiempo de evacuacion se le
    pega, el recinto esta saturado en las salidas y el layout ya no manda.
    """
    return S.aforo(pet)


@app.post("/api/campo", response_model=E.RespCampo, tags=["campos"])
def post_campo(pet: E.PeticionCampo):
    """Campo de tiempos de llegada a las salidas, isocronas y direccion (-grad T)."""
    return S.campo(pet)


@app.post("/api/proponer", response_model=E.RespProponer, tags=["capa 0"])
def post_proponer(pet: E.PeticionProponer):
    """Acomoda al azar las areas pedidas respetando las reglas duras.

    El usuario dice CUANTAS areas de cada tipo quiere; donde van lo decide el
    sistema. Es el punto de partida contra el que se compara la optimizacion.
    """
    return S.proponer(pet)


# --- trabajos asincronos -----------------------------------------------------
@app.post("/api/trabajos", response_model=E.EstadoTrabajo, tags=["trabajos"])
def post_trabajo(pet: E.PeticionTrabajo):
    """Lanza una simulacion o una optimizacion y devuelve un id.

    Asincrono a proposito: una optimizacion no cabe en un request HTTP, y el
    cliente no puede quedarse colgado minutos.
    """
    tid = S.lanzar(pet)
    return S.estado(tid)


@app.get("/api/trabajos/{tid}", response_model=E.EstadoTrabajo, tags=["trabajos"])
def get_trabajo(tid: str):
    st = S.estado(tid)
    if st is None:
        raise HTTPException(404, "no existe ese trabajo")
    return st


@app.get("/api/trabajos", tags=["trabajos"])
def list_trabajos():
    return [{k: v for k, v in t.items() if k != "resultado"}
            for t in S.TRABAJOS.values()]


# --- resultados guardados ----------------------------------------------------
app.include_router(router_resultados)


# --- UI ----------------------------------------------------------------------
if os.path.isdir(WEB):
    app.mount("/estatico", StaticFiles(directory=WEB), name="estatico")

    @app.get("/", include_in_schema=False)
    def raiz():
        return FileResponse(os.path.join(WEB, "index.html"))
