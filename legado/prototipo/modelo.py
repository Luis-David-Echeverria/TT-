"""
Modelo de flujo peatonal macroscopico + evaluacion de un layout.

Dos mitades, como en la formulacion:
  A) campo de destino  -> Eikonal |grad T| = 1/v, resuelto con FMM (scikit-fmm)
  B) acoplamiento rho<->v -> Weidmann + acumulacion de flujo + punto fijo
"""
import numpy as np
import skfmm
from scipy import ndimage

from recinto import (W, H, ESCENARIO, REGION_FBS, SALIDAS, ACCESOS,
                     conos_aproximacion, SERVICIOS, DEMANDA, ASISTENTES,
                     AR_MAX, DIM_MIN, ANCHO_LIBRE_MIN, Rejilla, catalogo_bloques)

# --- diagrama fundamental de Weidmann ---------------------------------------
V0, RHO_MAX, GAMMA = 1.34, 5.4, 1.913
RHO_JAM = 0.85 * RHO_MAX      # umbral de estancamiento (capa 1)
RHO_CRIT = 4.0                # densidad critica normativa (ancla del colormap)


def weidmann(rho):
    """v(rho): entre mas apretados, mas lento. Es la unica fisica real de multitud
    que hace que esto se parezca a un fluido."""
    r = np.clip(rho, 1e-3, RHO_MAX - 1e-3)
    return V0 * (1.0 - np.exp(-GAMMA * (1.0 / r - 1.0 / RHO_MAX)))


# --- decodificacion FBS ------------------------------------------------------
BW_MIN, BW_MAX = 6.0, 16.0   # ancho de bahia admisible (m)
AREA_BOLSA_MIN = 30.0        # m2: bolsa sellada que si importa (cabe gente)


def _reparar_bahias(grupos, areas, profundidad):
    """El ancho de una bahia es (area contenida)/profundidad, y ese ancho es lo
    que fija la relacion de aspecto de los servicios que caen dentro. Un corte
    aleatorio produce bahias de 2 m o de 40 m, y ambas degeneran las zonas.

    Reparar aqui es mas eficiente que castigarlo despues: el operador genetico
    conserva su libertad y el decode entrega siempre geometria sana.
    """
    a_min, a_max = BW_MIN * profundidad, BW_MAX * profundidad

    fus = []                                   # 1) fusionar bahias flacas
    for g in grupos:
        if fus and sum(areas[k] for k in fus[-1]) < a_min:
            fus[-1] = fus[-1] + list(g)
        else:
            fus.append(list(g))
    while len(fus) > 1 and sum(areas[k] for k in fus[-1]) < a_min:
        ult = fus.pop()
        fus[-1] = fus[-1] + ult

    fin = []                                   # 2) partir bahias gordas
    for g in fus:
        tot = sum(areas[k] for k in g)
        if tot <= a_max or len(g) == 1:
            fin.append(g)
            continue
        npart = min(len(g), int(np.ceil(tot / a_max)))
        objetivo = tot / npart
        cur, acc, hechos = [], 0.0, 0
        for idx, k in enumerate(g):
            cur.append(k)
            acc += areas[k]
            restantes = len(g) - idx - 1
            if hechos < npart - 1 and acc >= objetivo and restantes >= npart - hechos - 1:
                fin.append(cur)
                cur, acc, hechos = [], 0.0, hechos + 1
        if cur:
            fin.append(cur)
    return fin


def decode(genoma, bloques):
    """(perm, cortes, orient) -> {bid: (x,y,w,h)}. Cero traslapes por construccion."""
    perm, cortes, orient = genoma
    x0, y0, Wr, Hr = REGION_FBS
    areas = [bloques[i].area for i in perm]

    grupos, cur = [], [0]
    for k in range(len(perm) - 1):
        if cortes[k]:
            grupos.append(cur)
            cur = []
        cur.append(k + 1)
    grupos.append(cur)

    profundidad = Hr if orient == 0 else Wr
    grupos = _reparar_bahias(grupos, areas, profundidad)
    rects, cx = {}, 0.0
    for g in grupos:
        ancho_bahia = sum(areas[k] for k in g) / profundidad
        cy = 0.0
        for k in g:
            lado = areas[k] / ancho_bahia
            if orient == 0:
                rects[bloques[perm[k]].bid] = (x0 + cx, y0 + cy, ancho_bahia, lado)
            else:
                rects[bloques[perm[k]].bid] = (x0 + cy, y0 + cx, lado, ancho_bahia)
            cy += lado
        cx += ancho_bahia
    return rects


def _sep(a, b):
    """Separacion libre entre dos rectangulos (<=0 si se tocan)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    dx = max(bx - (ax + aw), ax - (bx + bw))
    dy = max(by - (ay + ah), ay - (by + bh))
    return max(dx, dy)


def _inter_area(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    return ix * iy


# --- CAPA 0: restricciones duras geometricas (microsegundos, sin simular) ----
def violaciones_geom(rects, bloques):
    """Magnitud total de violacion normativa. 0 = factible.

    Es dura (ningun objetivo la compensa) pero se mide en grado, porque NSGA-II
    necesita saber cuanto se violo para poder salirse de la region infactible.
    """
    serv = [b for b in bloques if b.es_servicio]
    v = 0.0
    for b in serv:
        x, y, w, h = rects[b.bid]
        lado_min, lado_max = min(w, h), max(w, h)
        v += max(0.0, DIM_MIN - lado_min)                        # lado minimo
        v += max(0.0, lado_max / max(lado_min, 1e-6) - AR_MAX)   # aspecto
    for i in range(len(serv)):                                   # pasillos sliver
        for j in range(i + 1, len(serv)):
            v += _viol_sep(rects[serv[i].bid], rects[serv[j].bid])
    for b in serv:                                               # conos de PC
        for _, cono in conos_aproximacion():
            v += _inter_area(rects[b.bid], cono) / 10.0
    return v


TOL_PEGADO = 0.3   # m


def _viol_sep(a, b):
    """Dos zonas pegadas son legales: forman un solo elemento (puestos en fila).
    Lo ilegal es el hueco intermedio inutil: un pasillo mas angosto que el
    normativo, por el que la gente va a intentar pasar y no cabe."""
    s = _sep(a, b)
    if s <= TOL_PEGADO or s >= ANCHO_LIBRE_MIN:
        return 0.0
    return min(s - TOL_PEGADO, ANCHO_LIBRE_MIN - s)


def _disco(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r + 0.5


# --- escena rasterizada ------------------------------------------------------
class Escena:
    def __init__(self, rejilla, rects, bloques):
        self.g = rejilla
        self.rects = rects
        obst = self.g.mascara_rect(ESCENARIO).copy()
        for b in bloques:
            if b.es_servicio:
                obst |= self.g.mascara_rect(rects[b.bid])
        self.obstaculo = obst
        self.libre = ~obst
        self.salidas = self.g.mascara_salidas() & self.libre
        self.tipos = {}
        for b in bloques:
            if b.es_servicio:
                m = self.g.mascara_rect(rects[b.bid])
                if b.tipo not in self.tipos:
                    self.tipos[b.tipo] = np.zeros_like(obst)
                self.tipos[b.tipo] |= m

    # ---- CAPA 0b: despeje normativo + conectividad (milisegundos, sin simular) --
    def violacion_despeje(self):
        """Erosiona el piso libre por medio ancho normativo: lo que queda es por
        donde SI cabe circular con el ancho de reglamento. Si una zona ocupable no
        conecta con ninguna salida a traves de ese espacio, esta sellada.

        Cubre de un golpe el ancho libre minimo y la conectividad (g1 + g7), y
        sigue siendo verificable sin simular nada."""
        r = max(1, int(round((ANCHO_LIBRE_MIN / 2) / self.g.h)))
        st = _disco(r)
        erod = ndimage.binary_erosion(self.libre, structure=st)
        if not erod.any():
            return float(self.libre.sum()) * self.g.area_celda
        lab, _ = ndimage.label(erod)
        cerca_salida = ndimage.binary_dilation(self.salidas, structure=st) & erod
        etiq = set(np.unique(lab[cerca_salida]).tolist()) - {0}
        if not etiq:
            return float(self.libre.sum()) * self.g.area_celda
        valido = np.isin(lab, list(etiq))
        alcanzable = ndimage.binary_dilation(valido, structure=st) & self.libre
        sellado = self.libre & ~alcanzable
        if not sellado.any():
            return 0.0
        # Los recovecos chicos entre puestos son inevitables y no atrapan a nadie.
        # Solo cuentan las bolsas con area suficiente para que quepa gente.
        lab2, n2 = ndimage.label(sellado)
        areas = ndimage.sum_labels(np.ones_like(lab2, float), lab2, range(1, n2 + 1))
        areas = areas * self.g.area_celda
        return float(areas[areas >= AREA_BOLSA_MIN].sum())

    # ---- mitad A: campo de destino ----
    def campo(self, destino, velocidad):
        """|grad T| = 1/v con FMM. T = tiempo de llegada al destino mas cercano."""
        alcanzable = self.libre | destino
        if not destino.any():
            return np.full(self.g.X.shape, np.inf)
        phi = np.ones(self.g.X.shape)
        phi[destino] = -1.0
        phi = np.ma.MaskedArray(phi, ~alcanzable)
        sp = np.ma.MaskedArray(np.maximum(velocidad, 1e-3), ~alcanzable)
        try:
            T = skfmm.travel_time(phi, sp, dx=self.g.h)
        except Exception:
            return np.full(self.g.X.shape, np.inf)
        return np.ma.filled(T, np.inf)

    def poblacion(self):
        """Densidad base: la gente se apila hacia el escenario, no es uniforme."""
        T = self.campo(self.g.mascara_rect(ESCENARIO), np.full(self.g.X.shape, V0))
        p = np.exp(-np.nan_to_num(T, posinf=1e6, nan=1e6) / 80.0)
        p[~self.libre] = 0.0
        s = p.sum()
        return p / s * ASISTENTES if s > 0 else p

    # ---- mitad B: acumulacion de flujo ----
    def acumular(self, T, demanda, n_buckets=90):
        """Reparte la demanda a lo largo de -grad T. Devuelve caudal por celda."""
        Q = np.where(self.libre, demanda, 0.0).astype(float)
        val = self.libre & np.isfinite(T)
        ii, jj = np.nonzero(val)
        if len(ii) == 0:
            return Q
        orden = np.argsort(-T[val])
        ii, jj = ii[orden], jj[orden]
        ny, nx = T.shape
        Tc = T[ii, jj]
        NI = np.empty((4, len(ii)), int)
        NJ = np.empty((4, len(ii)), int)
        Wt = np.zeros((4, len(ii)))
        for k, (di, dj) in enumerate(((-1, 0), (1, 0), (0, -1), (0, 1))):
            ni, nj = ii + di, jj + dj
            ok = (ni >= 0) & (ni < ny) & (nj >= 0) & (nj < nx)
            ni = np.clip(ni, 0, ny - 1)
            nj = np.clip(nj, 0, nx - 1)
            ok &= val[ni, nj]
            NI[k], NJ[k] = ni, nj
            Wt[k] = np.where(ok, np.maximum(Tc - T[ni, nj], 0.0), 0.0)
        tot = Wt.sum(0)
        tot[tot <= 0] = 1.0
        Wt /= tot
        cortes = np.linspace(0, len(ii), n_buckets + 1).astype(int)
        for b in range(n_buckets):
            s, e = cortes[b], cortes[b + 1]
            if s == e:
                continue
            q = Q[ii[s:e], jj[s:e]]
            for k in range(4):
                w = Wt[k, s:e]
                m = w > 0
                if m.any():
                    np.add.at(Q, (NI[k, s:e][m], NJ[k, s:e][m]), q[m] * w[m])
        return Q

    # ---- punto fijo: rho -> v -> T -> q -> rho ----
    def punto_fijo(self, destinos, horizonte=420.0, n_iter=4):
        """destinos: lista de (mascara, fraccion_de_demanda). Cuasi-estacionario."""
        p = self.poblacion()
        rho_base = p / self.g.area_celda
        rho = rho_base.copy()
        campos = []
        for _ in range(n_iter):
            v = weidmann(rho)
            v[~self.libre] = 1e-3
            q_tot = np.zeros_like(rho)
            campos = []
            for dest, frac in destinos:
                T = self.campo(dest, v)
                campos.append(T)
                q_tot += self.acumular(T, p * frac)
            rho_flujo = q_tot / (horizonte * np.maximum(v, 0.05) * self.g.h)
            rho = np.clip(rho_base + rho_flujo, 0.0, RHO_MAX - 1e-3)
            rho[~self.libre] = 0.0
        v = weidmann(rho)
        v[~self.libre] = 0.0
        return rho, v, campos, p
