"""
Almacen de evaluaciones: no volver a calcular lo ya calculado.

Cada evaluacion se guarda con una LLAVE que es el hash de las tres cosas que
determinan el resultado:

    caso    el recinto ya rasterizado (muros, salidas, dimensiones)
    layout  la mascara de obstaculos de las areas colocadas
    config  numerica + escenario + parametros fisicos

La llave es la mascara rasterizada y no las coordenadas. Dos layouts que
difieren en menos de una celda ocupan las mismas celdas, dan exactamente el
mismo resultado, y son el MISMO caso aunque sus coordenadas no coincidan.

SQLite y no CSV: se consulta sin cargar todo en memoria, soporta escritura
concurrente desde varios procesos, y es un solo archivo que se puede versionar
o mandar por correo. La exportacion a CSV se hace aparte, para las figuras.
"""
import hashlib
import json
import os
import sqlite3
import time

import numpy as np

RUTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "datos", "evaluaciones.db")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS evaluaciones (
    llave        TEXT PRIMARY KEY,
    caso         TEXT NOT NULL,
    config       TEXT NOT NULL,
    layout_json  TEXT NOT NULL,
    modo         TEXT,
    semilla      INTEGER,
    factible     INTEGER,
    violacion    REAL,
    f1           REAL,
    t_des        REAL,
    t95          REAL,
    exposicion   REAL,
    rho_pico     REAL,
    conservacion REAL,
    ms           REAL,
    fecha        REAL,
    extra        TEXT
);
CREATE INDEX IF NOT EXISTS idx_caso ON evaluaciones(caso);
CREATE INDEX IF NOT EXISTS idx_caso_cfg ON evaluaciones(caso, config);

CREATE TABLE IF NOT EXISTS casos (
    caso   TEXT PRIMARY KEY,
    nombre TEXT,
    json   TEXT NOT NULL,
    fecha  REAL
);

-- Sin esta tabla la base guarda el HASH de la configuracion pero no la
-- configuracion: dentro de un mes nadie sabria con que dt, que aforo o que k_c
-- se saco una fila, y el experimento dejaria de ser reproducible justo por
-- donde se pretendia asegurarlo.
CREATE TABLE IF NOT EXISTS configs (
    config TEXT PRIMARY KEY,
    json   TEXT NOT NULL,
    fecha  REAL
);
"""


def _con(ruta=RUTA):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    c = sqlite3.connect(ruta, timeout=30)
    c.row_factory = sqlite3.Row
    c.executescript(ESQUEMA)
    return c


def _hash(*partes):
    h = hashlib.blake2b(digest_size=12)
    for p in partes:
        h.update(p if isinstance(p, bytes) else str(p).encode())
        h.update(b"\x00")
    return h.hexdigest()


# =============================================================================
# llaves
# =============================================================================
def huella_caso(rec):
    """Identidad del recinto: dimensiones, muros rasterizados y salidas."""
    sal = sorted((s.nombre, s.lado, round(s.centro, 3), round(s.ancho, 3))
                 for s in rec.salidas)
    return _hash(rec.W, rec.H, rec.h, rec.muros.tobytes(), json.dumps(sal))


def huella_layout(rec, layout):
    """Identidad del layout PARA EL SIMULADOR: su mascara de obstaculos."""
    return _hash(rec.obstaculos(layout).tobytes())


def huella_config(cfg):
    """Identidad de la configuracion. Orden de llaves normalizado."""
    return _hash(json.dumps(cfg, sort_keys=True, default=str))


def llave(rec, layout, cfg):
    return _hash(huella_caso(rec), huella_layout(rec, layout), huella_config(cfg))


# =============================================================================
# escritura y lectura
# =============================================================================
def registrar_caso(rec, nombre, definicion, ruta=RUTA):
    with _con(ruta) as c:
        c.execute("INSERT OR REPLACE INTO casos(caso, nombre, json, fecha) "
                  "VALUES (?,?,?,?)",
                  (huella_caso(rec), nombre,
                   json.dumps(definicion, default=str), time.time()))
    return huella_caso(rec)


def registrar_config(cfg, ruta=RUTA):
    with _con(ruta) as c:
        c.execute("INSERT OR IGNORE INTO configs(config, json, fecha) "
                  "VALUES (?,?,?)",
                  (huella_config(cfg), json.dumps(cfg, sort_keys=True,
                                                  default=str), time.time()))
    return huella_config(cfg)


def leer_configs(ruta=RUTA):
    """hash -> configuracion completa. Es lo que permite leer la base sola."""
    with _con(ruta) as c:
        return {f["config"]: json.loads(f["json"])
                for f in c.execute("SELECT * FROM configs").fetchall()}


def buscar(rec, layout, cfg, ruta=RUTA):
    """Devuelve la fila si ya se evaluo esta combinacion, o None."""
    with _con(ruta) as c:
        f = c.execute("SELECT * FROM evaluaciones WHERE llave=?",
                      (llave(rec, layout, cfg),)).fetchone()
    return dict(f) if f else None


def guardar(rec, layout, cfg, metricas, modo="", semilla=None, extra=None,
            ruta=RUTA):
    k = llave(rec, layout, cfg)
    registrar_config(cfg, ruta)
    fila = (
        k, huella_caso(rec), huella_config(cfg),
        json.dumps([{"tipo": x.tipo, "x": x.x, "y": x.y, "rot": x.rot}
                    for x in layout]),
        modo, semilla,
        int(bool(metricas.get("factible", True))),
        metricas.get("violacion"), metricas.get("f1"),
        metricas.get("t_des"), metricas.get("t95"),
        metricas.get("exposicion"), metricas.get("rho_pico"),
        metricas.get("conservacion"), metricas.get("ms"),
        time.time(), json.dumps(extra or {}, default=str),
    )
    with _con(ruta) as c:
        c.execute(
            "INSERT OR REPLACE INTO evaluaciones VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", fila)
    return k


def consultar(caso=None, config=None, solo_factibles=False, limite=None,
              ruta=RUTA):
    q = "SELECT * FROM evaluaciones WHERE 1=1"
    a = []
    if caso:
        q += " AND caso=?"
        a.append(caso)
    if config:
        q += " AND config=?"
        a.append(config)
    if solo_factibles:
        q += " AND factible=1"
    q += " ORDER BY fecha"
    if limite:
        q += " LIMIT %d" % int(limite)
    with _con(ruta) as c:
        return [dict(f) for f in c.execute(q, a).fetchall()]


def resumen(ruta=RUTA):
    with _con(ruta) as c:
        n = c.execute("SELECT COUNT(*) n FROM evaluaciones").fetchone()["n"]
        casos = c.execute(
            "SELECT c.caso, c.nombre, COUNT(e.llave) n, "
            "       SUM(e.factible) factibles, SUM(e.ms)/1000.0 segundos "
            "FROM casos c LEFT JOIN evaluaciones e ON e.caso=c.caso "
            "GROUP BY c.caso ORDER BY n DESC").fetchall()
        cfgs = c.execute(
            "SELECT config, COUNT(*) n FROM evaluaciones "
            "GROUP BY config ORDER BY n DESC").fetchall()
    return {"total": n, "casos": [dict(x) for x in casos],
            "configs": [dict(x) for x in cfgs],
            "ruta": ruta,
            "tamano_mb": os.path.getsize(ruta) / 1e6 if os.path.exists(ruta) else 0.0}


def exportar_csv(destino, caso=None, config=None, ruta=RUTA):
    """CSV con una fila por layout evaluado, para las figuras."""
    import csv
    filas = consultar(caso=caso, config=config, ruta=ruta)
    if not filas:
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
    cols = [k for k in filas[0] if k != "layout_json"]
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)
    return len(filas)


# =============================================================================
# memoizacion transparente
# =============================================================================
def evaluar_con_cache(rec, layout, cfg, fn, modo="", semilla=None, ruta=RUTA,
                      forzar=False):
    """Devuelve (metricas, vino_de_cache).

    `fn()` solo se llama si la combinacion no estaba guardada. Es lo que permite
    repetir un experimento, agregarle layouts o cambiar solo las figuras sin
    volver a simular lo ya simulado.
    """
    if not forzar:
        prev = buscar(rec, layout, cfg, ruta)
        if prev is not None:
            return prev, True
    t0 = time.perf_counter()
    m = fn()
    m["ms"] = (time.perf_counter() - t0) * 1000.0
    guardar(rec, layout, cfg, m, modo=modo, semilla=semilla, ruta=ruta)
    return m, False
