"""
GIF del fluido de verdad: la multitud SE MUEVE.

La masa se transporta con el modelo de transmision de celdas (ver fluido.py),
que es el esquema de Godunov para la ley de conservacion LWR. No se desvanece
en su lugar: fluye, se acumula, hace cola en las puertas y sale.

Fondo   = densidad de multitud (la gente)
Rojo    = carga sobre fronteras (donde empuja contra algo que no cede)
Verde   = salidas, con capacidad finita
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
from matplotlib.animation import FuncAnimation, PillowWriter
from scipy import ndimage

from recinto import W, H, ESCENARIO, SALIDAS, conos_aproximacion
from modelo import RHO_MAX, RHO_CRIT
from demo import INGENUO, BUENO, TIPO, COLOR_TIPO, SAL, escena_de, suaviza
from demo_carga import carga_por_choque, cmap_carga, UMBRAL_CARGA
from fluido import simular

N_FRAMES = 64


def cmap_multitud():
    """Vacio = casi negro, multitud = clara, critico = blanco incandescente."""
    f = RHO_CRIT / RHO_MAX
    return LinearSegmentedColormap.from_list("mul", [
        (0.00, "#05070f"), (0.18, "#10305e"), (0.45 * f + 0.1, "#1f7f96"),
        (f, "#7fd6c2"), (0.5 + 0.5 * f, "#ffe9b0"), (1.00, "#ffffff")])


def campo_deseo(esc):
    """Direccion en linea recta a la salida mas cercana, ignorando obstaculos."""
    _, ind = ndimage.distance_transform_edt(~esc.salidas, return_indices=True)
    ex, ey = esc.g.X[ind[0], ind[1]], esc.g.Y[ind[0], ind[1]]
    ddx, ddy = ex - esc.g.X, ey - esc.g.Y
    dm = np.hypot(ddx, ddy)
    return (np.where(dm > 1e-9, ddx / np.maximum(dm, 1e-9), 0.0),
            np.where(dm > 1e-9, ddy / np.maximum(dm, 1e-9), 0.0))


def corrida(rects):
    esc, _ = escena_de(rects, 1.0)
    M0 = esc.poblacion()
    cuadros, ts, pct, dirs = simular(esc, M0, n_frames=N_FRAMES, t_max=620.0)
    dx, dy = campo_deseo(esc)
    cargas = []
    for rho in cuadros:
        m = rho * esc.g.area_celda
        cargas.append(suaviza(carga_por_choque(esc, m, dx, dy, paso=1.0), esc, 2.8))
    return dict(esc=esc, cuadros=cuadros, ts=ts, pct=pct, cargas=cargas, dirs=dirs)


def marco(ax, rects, esc, cm):
    ax.set_facecolor("#05070f")
    im = ax.imshow(np.zeros_like(esc.g.X), origin="lower", extent=[0, W, 0, H],
                   cmap=cm, vmin=0, vmax=RHO_MAX, interpolation="bicubic", zorder=1)
    imc = ax.imshow(np.zeros(esc.g.X.shape + (4,)), origin="lower",
                    extent=[0, W, 0, H], interpolation="bilinear", zorder=3)
    for _, cono in conos_aproximacion():
        ax.add_patch(Rectangle(cono[:2], cono[2], cono[3], fill=False,
                               ec="white", lw=0.7, ls=":", alpha=0.28, zorder=4))
    for k, r in rects.items():
        ax.add_patch(Rectangle(r[:2], r[2], r[3], fc=COLOR_TIPO[TIPO[k]],
                               ec="white", lw=1.0, zorder=5))
    ax.add_patch(Rectangle(ESCENARIO[:2], ESCENARIO[2], ESCENARIO[3],
                           fc="#2b2b3a", ec="white", lw=1.0, zorder=5))
    ax.text(ESCENARIO[0] + ESCENARIO[2] / 2, ESCENARIO[1] + ESCENARIO[3] / 2,
            "ESCENARIO", color="white", ha="center", va="center",
            fontsize=8, weight="bold", zorder=6)
    for nom, (x, y, w, h), lado in SALIDAS:
        ax.add_patch(Rectangle((x - 0.5, y - 0.5), max(w, 2.5) + 1, max(h, 2.5) + 1,
                               fc="#2bff88", ec="white", lw=0.9, zorder=7))
    paso = 5
    sl = (slice(paso // 2, None, paso), slice(paso // 2, None, paso))
    msk = esc.libre[sl]
    qx, qy = esc.g.X[sl][msk], esc.g.Y[sl][msk]
    qv = ax.quiver(qx, qy, np.zeros_like(qx), np.zeros_like(qy), color="white",
                   alpha=0.42, scale=38, width=0.0032, headwidth=3.4, zorder=6)
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    return im, imc, (qv, sl, msk)


def main():
    os.makedirs(SAL, exist_ok=True)
    cm, cc = cmap_multitud(), cmap_carga()
    ds = {}
    for nombre, rects in (("ingenuo", INGENUO), ("bueno", BUENO)):
        ds[nombre] = corrida(rects)
        print("  %-8s evacuado %.1f %% en %.0f s"
              % (nombre, ds[nombre]["pct"][-1], ds[nombre]["ts"][-1]))

    n = max(len(ds[k]["cuadros"]) for k in ds)
    vmax_c = max(max(x.max() for x in ds[k]["cargas"]) for k in ds)
    umb = UMBRAL_CARGA * vmax_c

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.9), facecolor="#0b0b12")
    ims, imcs, txts, quivs = [], [], [], []
    for ax, (nombre, rects, tit) in zip(axes, [
            ("ingenuo", INGENUO, "Layout ingenuo"),
            ("bueno", BUENO, "Layout repartido")]):
        im, imc, q = marco(ax, rects, ds[nombre]["esc"], cm)
        quivs.append(q)
        ax.set_title(tit, fontsize=11, color="#e8e8ee", pad=22)
        t = ax.text(0.5, 1.015, "", transform=ax.transAxes, ha="center",
                    color="#8fe8c0", fontsize=10, family="monospace")
        ims.append(im); imcs.append(imc); txts.append(t)

    s1 = plt.cm.ScalarMappable(cmap=cm, norm=plt.Normalize(0, RHO_MAX))
    cb1 = fig.colorbar(s1, ax=axes, fraction=0.022, pad=0.015)
    cb1.set_label("densidad de multitud  [pers/m$^2$]", color="#e8e8ee", fontsize=9)
    cb1.ax.axhline(RHO_CRIT, color="white", ls="--", lw=1.3)
    cb1.ax.tick_params(colors="#e8e8ee", labelsize=8)
    s2 = plt.cm.ScalarMappable(cmap=cc, norm=plt.Normalize(umb, vmax_c))
    cb2 = fig.colorbar(s2, ax=axes, fraction=0.022, pad=0.015)
    cb2.set_label("CARGA sobre fronteras", color="#ff6a4a", fontsize=9)
    cb2.ax.tick_params(colors="#e8e8ee", labelsize=8)

    fig.suptitle("Evacuacion: la multitud transportada como fluido (mismo reloj)",
                 color="white", fontsize=13, y=0.98)
    fig.text(0.5, 0.03, "flechas = campo de destino  |  la masa fluye y hace cola en las puertas  |  "
             "ROJO = empuja contra algo que no cede  |  verde = salidas (capacidad finita)",
             ha="center", color="#9a9aa8", fontsize=8)

    def act(f):
        for k, nombre in enumerate(("ingenuo", "bueno")):
            d = ds[nombre]
            i = min(f, len(d["cuadros"]) - 1)
            esc = d["esc"]
            ims[k].set_data(np.where(esc.libre, d["cuadros"][i], 0.0))
            c = d["cargas"][i]
            nn = np.clip((c - umb) / max(vmax_c - umb, 1e-9), 0.0, 1.0)
            rgba = cc(nn)
            rgba[..., 3] = np.where(esc.libre & (c >= umb),
                                    np.clip(0.4 + 0.6 * nn, 0.0, 1.0), 0.0)
            imcs[k].set_data(rgba)
            qv, sl, msk = quivs[k]
            ux, uy = d["dirs"][i]
            qv.set_UVC(ux[sl][msk], uy[sl][msk])
            txts[k].set_text("t = %4.0f s   evacuado %5.1f %%" % (d["ts"][i], d["pct"][i]))
        return ims + imcs + txts + [q[0] for q in quivs]

    ani = FuncAnimation(fig, act, frames=n, interval=110, blit=False)
    out = os.path.join(SAL, "06_fluido.gif")
    ani.save(out, writer=PillowWriter(fps=10), dpi=78,
             savefig_kwargs={"facecolor": fig.get_facecolor()})
    plt.close(fig)
    print("->", out)


if __name__ == "__main__":
    main()
