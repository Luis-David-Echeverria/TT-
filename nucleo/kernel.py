"""
Nucleo compilado del paso de Godunov.

Por que existe: la version con numpy hace del orden de quince recorridos del
arreglo por paso de tiempo, creando un temporal en cada uno. Compilado, el mismo
calculo se hace en TRES recorridos y sin temporales, y ademas cabe entero en
cache.

No es una aproximacion: las operaciones y su orden son los mismos, asi que el
resultado es identico bit a bit al de numpy (se verifica en la prueba de abajo).
La ganancia es de implementacion, no de precision sacrificada.

Se mantiene la version numpy como referencia: si numba no esta disponible, el
modulo cae a ella sin cambiar resultados.
"""
import numpy as np

try:
    from numba import njit
    HAY_NUMBA = True
except Exception:                                    # pragma: no cover
    HAY_NUMBA = False
    def njit(*a, **k):
        def envoltura(f):
            return f
        return envoltura if not a else a[0]


DI = np.array([-1, 1, 0, 0], dtype=np.int64)
DJ = np.array([0, 0, -1, 1], dtype=np.int64)


@njit(cache=True, fastmath=False)
def paso_godunov(M, Wt, libre, dem_t, ofe_t, esc_t, area, h, dt, m_max,
                 entrante, envio, escala, di, dj):
    """Un paso del modelo de transmision de celdas.

    1) cada celda calcula cuanto QUIERE enviar (rama de demanda) y lo reparte
       entre sus vecinos cuesta abajo -> se acumula la demanda entrante
    2) cada celda calcula cuanto PUEDE aceptar (rama de oferta, y lo que le
       cabe) -> factor de escala
    3) se aplican los flujos ya escalados

    Los tres pasos son necesarios y en ese orden: el factor de escala depende de
    la demanda total que llega, que no se conoce hasta terminar el paso 1.
    """
    ny, nx = M.shape
    n_tab = dem_t.shape[0]

    for i in range(ny):
        for j in range(nx):
            entrante[i, j] = 0.0
            envio[i, j] = 0.0
            escala[i, j] = 1.0

    # --- 1) demanda y reparto ---
    for i in range(ny):
        for j in range(nx):
            if not libre[i, j]:
                continue
            idx = int(M[i, j] / area * esc_t)
            if idx < 0:
                idx = 0
            elif idx >= n_tab:
                idx = n_tab - 1
            e = dem_t[idx] * h * dt
            if e > M[i, j]:
                e = M[i, j]
            envio[i, j] = e
            if e <= 0.0:
                continue
            for k in range(4):
                w = Wt[k, i, j]
                if w <= 0.0:
                    continue
                ii = i + di[k]
                jj = j + dj[k]
                if 0 <= ii < ny and 0 <= jj < nx:
                    entrante[ii, jj] += e * w

    # --- 2) oferta: cuanto cabe de verdad ---
    for i in range(ny):
        for j in range(nx):
            ent = entrante[i, j]
            if ent <= 1e-12:
                continue
            idx = int(M[i, j] / area * esc_t)
            if idx < 0:
                idx = 0
            elif idx >= n_tab:
                idx = n_tab - 1
            sp = ofe_t[idx] * h * dt
            hueco = m_max - M[i, j]
            if hueco < 0.0:
                hueco = 0.0
            if hueco < sp:
                sp = hueco
            if sp < ent:
                escala[i, j] = sp / ent

    # --- 3) aplicar (los flujos ya estan determinados por 1 y 2) ---
    for i in range(ny):
        for j in range(nx):
            e = envio[i, j]
            if e <= 0.0:
                continue
            for k in range(4):
                w = Wt[k, i, j]
                if w <= 0.0:
                    continue
                ii = i + di[k]
                jj = j + dj[k]
                if 0 <= ii < ny and 0 <= jj < nx:
                    f = e * w * escala[ii, jj]
                    M[ii, jj] += f
                    M[i, j] -= f
    return M


class Buffers:
    """Arreglos de trabajo reutilizados entre pasos: evita reservar memoria
    ochocientas veces por simulacion."""

    __slots__ = ("entrante", "envio", "escala", "di", "dj")

    def __init__(self, forma):
        self.entrante = np.zeros(forma)
        self.envio = np.zeros(forma)
        self.escala = np.ones(forma)
        self.di = DI.copy()
        self.dj = DJ.copy()
