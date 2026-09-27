"""
Vista de FLUIDO (campos continuos, sin particulas) + mapa de CARGA.

La carga sale del conflicto entre dos campos de direccion:

  campo de DESEO    -> hacia donde quiere ir la gente, en linea recta,
                       ignorando obstaculos (informacion imperfecta)
  campo FACTIBLE    -> -grad T, que rodea correctamente los obstaculos
                       (informacion perfecta)

Donde el deseo apunta contra algo que no cede, la masa que venia empujando se
queda atorada. Esa masa acumulada es la carga sobre esa frontera.

No son newtons: es propulsion bloqueada. Sirve para comparar layouts entre si,
no para dimensionar una valla. Volverla fuerza requiere calibracion empirica.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
from scipy import ndimage

from recinto import W, H, ESCENARIO, SALIDAS, conos_aproximacion
from modelo import RHO_MAX, weidmann
from demo import INGENUO, BUENO, TIPO, COLOR_TIPO, SAL, escena_de, suaviza

UMBRAL_CARGA = 0.22      # fraccion del maximo global a partir de la cual es "roja"


def cmap_fluido():
    """Azul profundo -> turquesa -> blanco. Sin rojo: el rojo es de la carga."""
    return LinearSegmentedColormap.from_list("flu", [
        (0.00, "#070a1c"), (0.30, "#123a6b"), (0.58, "#1f7f96"),
        (0.80, "#63c4b4"), (1.00, "#eafaf6")])


def cmap_carga():
    return LinearSegmentedColormap.from_list("car", [
        (0.00, "#ff8c1a"), (0.45, "#ff2d1a"), (1.00, "#7d0512")])


def carga_por_choque(esc, p, dx, dy, paso=0.5):
    """Traza un rayo desde cada celda en la direccion de DESEO. Si el rayo llega
    a una salida, esa gente sale y no carga nada. Si se topa con un obstaculo o
    con el muro perimetral, deposita su masa justo delante del punto de choque.

    La suma de todas las masas que descargan en el mismo punto es la carga
    acumulada sobre esa frontera: no es el impacto de una persona, es la fila de
    gente que viene empujando detras sin poder pasar.
    """
    h = esc.g.h
    ny, nx = p.shape
    ii, jj = np.nonzero(esc.libre & (p > 0))
    x, y = esc.g.X[ii, jj].copy(), esc.g.Y[ii, jj].copy()
    ux, uy = dx[ii, jj].copy(), dy[ii, jj].copy()
    masa = p[ii, jj].copy()
    activo = np.hypot(ux, uy) > 1e-9
    carga = np.zeros_like(p)

    for _ in range(int((W + H) / (paso * h)) + 4):
        if not activo.any():
            break
        xn = x + ux * paso * h
        yn = y + uy * paso * h
        fuera = (xn < 0) | (xn >= W) | (yn < 0) | (yn >= H)
        cj = np.clip((xn / h).astype(int), 0, nx - 1)
        ci = np.clip((yn / h).astype(int), 0, ny - 1)
        llega = activo & ~fuera & esc.salidas[ci, cj]
        choca = activo & ~llega & (fuera | esc.obstaculo[ci, cj])
        if choca.any():
            lj = np.clip((x[choca] / h).astype(int), 0, nx - 1)
            li = np.clip((y[choca] / h).astype(int), 0, ny - 1)
            np.add.at(carga, (li, lj), masa[choca])
        activo &= ~(choca | llega)
        x = np.where(activo, xn, x)
        y = np.where(activo, yn, y)
    return np.where(esc.libre, carga, 0.0)


def campos(rects, h=1.0):
    esc, bl = escena_de(rects, h)
    rho, v, camp, p = esc.punto_fijo([(esc.salidas, 1.0)], horizonte=240.0)
    T = np.nan_to_num(camp[0], posinf=1e9, nan=1e9)

    # --- campo FACTIBLE: -grad T, rodea obstaculos ---
    Tm = np.where(esc.libre & (T < 1e8), T, np.nan)
    gy, gx = np.gradient(np.nan_to_num(Tm, nan=0.0), h)
    val = esc.libre & np.isfinite(Tm)
    val &= ndimage.binary_erosion(val, np.ones((3, 3)))
    num = ndimage.gaussian_filter(np.where(val, gx, 0.0), 2.0)
    nuy = ndimage.gaussian_filter(np.where(val, gy, 0.0), 2.0)
    den = ndimage.gaussian_filter(val.astype(float), 2.0)
    gx = np.where(val, gx, np.where(den > 1e-6, num / np.maximum(den, 1e-6), 0.0))
    gy = np.where(val, gy, np.where(den > 1e-6, nuy / np.maximum(den, 1e-6), 0.0))
    mag = np.hypot(gx, gy)
    fx = np.where(mag > 1e-9, -gx / np.maximum(mag, 1e-9), 0.0)
    fy = np.where(mag > 1e-9, -gy / np.maximum(mag, 1e-9), 0.0)

    # --- campo de DESEO: recta a la salida mas cercana, sin ver obstaculos ---
    dist, ind = ndimage.distance_transform_edt(~esc.salidas, return_indices=True)
    dist = dist * h
    ex, ey = esc.g.X[ind[0], ind[1]], esc.g.Y[ind[0], ind[1]]
    ddx, ddy = ex - esc.g.X, ey - esc.g.Y
    dm = np.hypot(ddx, ddy)
    dx = np.where(dm > 1e-9, ddx / np.maximum(dm, 1e-9), 0.0)
    dy = np.where(dm > 1e-9, ddy / np.maximum(dm, 1e-9), 0.0)

    # --- desalineacion: 0 si deseo y factible coinciden, 1 si son opuestos ---
    desal = np.clip((1.0 - (dx * fx + dy * fy)) / 2.0, 0.0, 1.0)

    # --- carga por choque: cada porcion de multitud avanza en linea recta
    #     hacia donde quiere ir y descarga su masa donde se topa con algo ---
    carga = carga_por_choque(esc, p, dx, dy)
    carga = suaviza(carga, esc, 2.8)

    rapidez = np.where(esc.libre, weidmann(rho), 0.0)
    return dict(esc=esc, rho=rho, rapidez=rapidez, fx=fx, fy=fy,
                carga=carga, T=T, p=p)


def panel(ax, rects, d, titulo, vmax_c, cf, cc):
    esc = d["esc"]
    ax.set_facecolor("#070a1c")
    # capa 1: el fluido (rapidez), continuo
    ax.imshow(np.where(esc.libre, suaviza(d["rapidez"], esc, 1.2), 0.0),
              origin="lower", extent=[0, W, 0, H], cmap=cf, vmin=0, vmax=1.34,
              interpolation="bicubic", zorder=1)
    # capa 2: lineas de corriente del campo factible
    try:
        ax.streamplot(esc.g.xc, esc.g.yc,
                      np.where(esc.libre, d["fx"], 0.0),
                      np.where(esc.libre, d["fy"], 0.0),
                      density=1.25, linewidth=0.55, arrowsize=0.6,
                      color="#dff3ff", zorder=3)
        for c in ax.collections:
            if hasattr(c, "set_alpha"):
                pass
    except Exception as e:
        print("   (streamplot omitido:", e, ")")
    # capa 3: la carga, SOLO por encima del umbral
    # RGBA explicito: enmascarar + bicubico hace desaparecer las regiones chicas
    umb = UMBRAL_CARGA * vmax_c
    n = np.clip((d["carga"] - umb) / max(vmax_c - umb, 1e-9), 0.0, 1.0)
    rgba = cc(n)
    rgba[..., 3] = np.where(esc.libre & (d["carga"] >= umb),
                            np.clip(0.45 + 0.55 * n, 0.0, 1.0), 0.0)
    ax.imshow(rgba, origin="lower", extent=[0, W, 0, H],
              interpolation="bilinear", zorder=4)

    for _, cono in conos_aproximacion():
        ax.add_patch(Rectangle(cono[:2], cono[2], cono[3], fill=False,
                               ec="white", lw=0.7, ls=":", alpha=0.35, zorder=5))
    for k, r in rects.items():
        ax.add_patch(Rectangle(r[:2], r[2], r[3], fc=COLOR_TIPO[TIPO[k]],
                               ec="white", lw=1.0, zorder=6))
    ax.add_patch(Rectangle(ESCENARIO[:2], ESCENARIO[2], ESCENARIO[3],
                           fc="#2b2b3a", ec="white", lw=1.0, zorder=6))
    ax.text(ESCENARIO[0] + ESCENARIO[2] / 2, ESCENARIO[1] + ESCENARIO[3] / 2,
            "ESCENARIO", color="white", ha="center", va="center",
            fontsize=8, weight="bold", zorder=7)
    for nom, (x, y, w, h), lado in SALIDAS:
        ax.add_patch(Rectangle((x - 0.5, y - 0.5), max(w, 2.5) + 1, max(h, 2.5) + 1,
                               fc="#2bff88", ec="white", lw=0.9, zorder=8))
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(titulo, fontsize=11, color="#e8e8ee", pad=8)


def main():
    os.makedirs(SAL, exist_ok=True)
    cf, cc = cmap_fluido(), cmap_carga()
    ds = {}
    for nombre, rects in (("ingenuo", INGENUO), ("bueno", BUENO)):
        ds[nombre] = campos(rects)
    vmax_c = max(d["carga"].max() for d in ds.values())   # misma escala en ambos

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.9), facecolor="#0e0e14")
    for ax, (nombre, rects, tit) in zip(axes, [
            ("ingenuo", INGENUO, "Layout ingenuo"),
            ("bueno", BUENO, "Layout repartido")]):
        d = ds[nombre]
        # el area roja crece con el numero de obstaculos, no con la gravedad:
        # la que compara bien layouts es la carga PICO sobre una frontera
        pico = float(np.where(d["esc"].libre, d["carga"], 0.0).max())
        panel(ax, rects, d, "%s\ncarga pico sobre frontera = %.0f" % (tit, pico),
              vmax_c, cf, cc)
        print("  %-8s carga pico %.0f" % (nombre, pico))

    s1 = plt.cm.ScalarMappable(cmap=cf, norm=plt.Normalize(0, 1.34))
    cb1 = fig.colorbar(s1, ax=axes, fraction=0.022, pad=0.015)
    cb1.set_label("rapidez de la multitud  [m/s]", color="#e8e8ee", fontsize=9)
    cb1.ax.tick_params(colors="#e8e8ee", labelsize=8)

    s2 = plt.cm.ScalarMappable(cmap=cc, norm=plt.Normalize(UMBRAL_CARGA * vmax_c, vmax_c))
    cb2 = fig.colorbar(s2, ax=axes, fraction=0.022, pad=0.015)
    cb2.set_label("CARGA sobre fronteras  (propulsion bloqueada)",
                  color="#ff6a4a", fontsize=9)
    cb2.ax.tick_params(colors="#e8e8ee", labelsize=8)

    fig.suptitle("Campo de fluido + carga sobre muros y zonas de servicio",
                 color="white", fontsize=13, y=0.98)
    fig.text(0.5, 0.02,
             "fondo = rapidez  |  lineas = campo factible  |  ROJO = donde la multitud "
             "empuja contra algo que no cede  |  verde = salidas",
             ha="center", color="#9a9aa8", fontsize=8)
    out = os.path.join(SAL, "04_carga.png")
    fig.savefig(out, dpi=140, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print("->", out)


if __name__ == "__main__":
    main()
