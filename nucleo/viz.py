"""
Dibujo. La estetica de mapa de calor por densidad esta anclada a un umbral
fisico: el color caliente empieza exactamente en la densidad a la que la gente
pierde el movimiento individual. Asi el color mide algo objetivo y es comparable
entre layouts, en vez de "lo mas denso de esta corrida".
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
from scipy import ndimage

from parametros import RHO_MAX, RHO_PERDIDA_CONTROL
from recinto import POR_CLAVE

FONDO = "#0b0e14"
TINTA = "#e6e1d7"
TENUE = "#8b949e"


def cmap_densidad():
    """Escala anclada a umbrales fisicos, no al maximo de la corrida.

    El ROJO arranca exactamente en la densidad a la que la gente pierde el
    movimiento individual y pasa a ser desplazada por la presion del grupo; el
    rojo oscuro marca el atasco (rho_max, velocidad cero). Asi el color significa
    lo mismo entre layouts y entre corridas, en vez de "lo mas denso de esta vez".
    """
    f = RHO_PERDIDA_CONTROL / RHO_MAX          # donde empieza el rojo
    return LinearSegmentedColormap.from_list("dens", [
        (0.000,  "#0a0f1e"),
        (0.012,  "#162842"),
        (0.200,  "#1e6e96"),
        (0.400,  "#5fbe8c"),
        (0.600,  "#f0c850"),
        (f,      "#e24b4a"),
        (1.000,  "#781414")])


def cmap_tiempo():
    return LinearSegmentedColormap.from_list("t", [
        (0.00, "#0d163c"), (0.28, "#28598c"), (0.55, "#2da096"),
        (0.78, "#96c85a"), (1.00, "#fae86e")])


def suavizar_display(campo, libre, sigma=1.1):
    c = np.where(libre, campo, 0.0)
    num = ndimage.gaussian_filter(c, sigma)
    den = ndimage.gaussian_filter(libre.astype(float), sigma)
    return np.where(den > 1e-6, num / np.maximum(den, 1e-6), 0.0)


def estilo(ax, rec, titulo=None):
    ax.set_facecolor("#05070f")
    ax.set_xlim(0, rec.W)
    ax.set_ylim(0, rec.H)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#272e38")
    if titulo:
        ax.set_title(titulo, fontsize=10, color=TINTA, pad=8)


def dibujar_muros(ax, rec):
    ys, xs = np.nonzero(rec.muros)
    for i, j in zip(ys, xs):
        ax.add_patch(Rectangle((rec.xc[j] - rec.h / 2, rec.yc[i] - rec.h / 2),
                               rec.h, rec.h, fc="#2b323c", ec="none", zorder=5))


def dibujar_salidas(ax, rec, color="#2bff88"):
    for s in rec.salidas:
        a = s.centro - s.ancho / 2
        if s.lado == "S":
            r = (a, -0.6, s.ancho, 2.2)
        elif s.lado == "N":
            r = (a, rec.H - 1.6, s.ancho, 2.2)
        elif s.lado == "O":
            r = (-0.6, a, 2.2, s.ancho)
        else:
            r = (rec.W - 1.6, a, 2.2, s.ancho)
        ax.add_patch(Rectangle(r[:2], r[2], r[3], fc=color, ec="white",
                               lw=0.8, zorder=8))


def dibujar_layout(ax, rec, layout, alpha=1.0, resaltar=()):
    for i, c in enumerate(layout or []):
        t = POR_CLAVE[c.tipo]
        x, y, w, f = c.rect()
        ec = "#ff3b30" if i in resaltar else "white"
        lw = 2.0 if i in resaltar else 0.9
        ax.add_patch(Rectangle((x, y), w, f, fc=t.color, ec=ec, lw=lw,
                               alpha=alpha, zorder=6))


def mapa_densidad(ax, rec, rho, layout=None, libre=None, suave=True, cmap=None):
    libre = rec.libre(layout) if libre is None else libre
    campo = suavizar_display(rho, libre) if suave else rho
    im = ax.imshow(np.where(libre, campo, 0.0), origin="lower",
                   extent=[0, rec.W, 0, rec.H], cmap=cmap or cmap_densidad(),
                   vmin=0, vmax=RHO_MAX, interpolation="bicubic", zorder=1)
    dibujar_muros(ax, rec)
    dibujar_layout(ax, rec, layout)
    dibujar_salidas(ax, rec)
    estilo(ax, rec)
    return im


def mapa_tiempos(ax, rec, T, layout=None, isocronas=True, n_iso=12):
    libre = rec.libre(layout)
    fin = np.isfinite(T) & libre
    vmax = float(T[fin].max()) if fin.any() else 1.0
    campo = np.where(fin, T, np.nan)
    ax.imshow(campo, origin="lower", extent=[0, rec.W, 0, rec.H],
              cmap=cmap_tiempo(), vmin=0, vmax=vmax,
              interpolation="bilinear", zorder=1)
    # zonas sin ruta a ninguna salida
    aislado = libre & ~np.isfinite(T)
    if aislado.any():
        rgba = np.zeros(T.shape + (4,))
        rgba[..., 0] = 0.85
        rgba[..., 3] = np.where(aislado, 0.85, 0.0)
        ax.imshow(rgba, origin="lower", extent=[0, rec.W, 0, rec.H], zorder=2)
    if isocronas and fin.any():
        niveles = np.linspace(0, vmax, n_iso + 1)[1:]
        ax.contour(rec.X, rec.Y, np.where(fin, T, np.nan), levels=niveles,
                   colors="white", linewidths=0.6, alpha=0.45, zorder=3)
    dibujar_muros(ax, rec)
    dibujar_layout(ax, rec, layout)
    dibujar_salidas(ax, rec)
    estilo(ax, rec)
    return vmax


def flechas(ax, rec, ux, uy, libre, paso=5, alpha=0.4):
    sl = (slice(paso // 2, None, paso), slice(paso // 2, None, paso))
    m = libre[sl] & ((np.hypot(ux, uy)[sl]) > 1e-6)
    if not m.any():
        return None
    return ax.quiver(rec.X[sl][m], rec.Y[sl][m], ux[sl][m], uy[sl][m],
                     color="white", alpha=alpha, scale=40, width=0.003,
                     headwidth=3.4, zorder=7)


def figura(n=1, ancho=6.4, alto=4.2):
    fig, axes = plt.subplots(1, n, figsize=(ancho * n, alto), facecolor=FONDO)
    if n == 1:
        axes = [axes]
    return fig, list(np.atleast_1d(axes))


def barra_densidad(fig, axes, cmap=None):
    sm = plt.cm.ScalarMappable(cmap=cmap or cmap_densidad(),
                               norm=plt.Normalize(0, RHO_MAX))
    cb = fig.colorbar(sm, ax=axes, fraction=0.025, pad=0.015)
    cb.set_label("densidad  [pers/m²]", color=TINTA, fontsize=9)
    cb.ax.axhline(RHO_PERDIDA_CONTROL, color="white", ls="--", lw=1.3)
    cb.ax.tick_params(colors=TINTA, labelsize=8)
    cb.ax.text(1.15, RHO_PERDIDA_CONTROL, " pérdida de\n control individual",
               color="white", fontsize=7, va="center", transform=cb.ax.get_yaxis_transform())
    return cb
