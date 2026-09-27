"""
BOCETO VISUAL para la junta. No es el experimento: son dos layouts puestos a
mano (uno ingenuo, uno razonable) pasados por el MISMO modelo de fluido, con la
MISMA escala de color anclada a la densidad critica normativa.

Genera:
  salidas/01_operacion.png   comparacion lado a lado en operacion normal
  salidas/02_evacuacion.gif  la multitud drenando hacia las salidas
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

from recinto import (W, H, ESCENARIO, SALIDAS, conos_aproximacion, Rejilla, Bloque)
from modelo import V0, RHO_MAX, RHO_CRIT, weidmann, Escena
from recinto import DEMANDA

SAL = os.path.join(os.path.dirname(__file__), "..", "salidas")

COLOR_TIPO = {"banos": "#4C9BE8", "comida": "#E8A33D",
              "bebidas": "#7BC96F", "medico": "#A96BE0"}

# --- dos layouts a mano ------------------------------------------------------
# El ingenuo es el error tipico: todos los servicios juntos en la explanada
# central, y uno plantado justo enfrente de una salida.
INGENUO = {
    # una barrera casi continua entre el escenario y las salidas del sur,
    # con huecos de 4 m: justo el pasillo-astilla que la normativa prohibe
    "C1": (8, 30, 14, 10), "C2": (26, 30, 14, 10), "C3": (44, 30, 14, 10),
    "D1": (62, 30, 12, 9), "D2": (78, 30, 12, 9),
    # y tres servicios plantados sobre conos de aproximacion a salidas
    "B1": (14, 4, 10, 9), "B2": (56, 4, 10, 9), "B3": (2, 20, 8, 10),
    "D3": (34, 48, 12, 8), "M1": (54, 48, 10, 8),
}
# El razonable: repartidos por el perimetro, conos de aproximacion despejados.
BUENO = {
    "B1": (30, 2, 10, 9), "B2": (76, 2, 10, 9), "B3": (2, 44, 10, 9),
    "C1": (14, 20, 12, 10), "C2": (76, 20, 12, 10), "C3": (14, 44, 12, 10),
    "D1": (76, 44, 10, 8), "D2": (42, 4, 10, 8), "D3": (2, 4, 5, 8),
    "M1": (88, 12, 9, 9),
}
TIPO = {"B1": "banos", "B2": "banos", "B3": "banos",
        "C1": "comida", "C2": "comida", "C3": "comida",
        "D1": "bebidas", "D2": "bebidas", "D3": "bebidas", "M1": "medico"}


def bloques_de(rects):
    return [Bloque(k, TIPO[k], v[2] * v[3], 1500, True) for k, v in rects.items()]


def cmap_densidad():
    """Escala anclada a la normativa: el rojo empieza exactamente en la densidad
    critica, igual en todos los layouts. Asi el color mide algo objetivo."""
    f = RHO_CRIT / RHO_MAX
    return LinearSegmentedColormap.from_list("pc", [
        (0.00, "#0d1230"), (0.35 * f, "#1c4f8f"), (0.70 * f, "#25a3a3"),
        (f, "#f2d347"), (0.5 + 0.5 * f, "#ffd9a0"), (1.00, "#ffffff")])


def suaviza(campo, esc, sigma=1.3):
    """Solo para el render: el look continuo tipo CFD. Las metricas (p95, t95)
    se calculan SIEMPRE sobre el campo crudo, nunca sobre este."""
    c = np.where(esc.libre, campo, 0.0)
    num = ndimage.gaussian_filter(c, sigma)
    den = ndimage.gaussian_filter(esc.libre.astype(float), sigma)
    return np.where(den > 1e-6, num / np.maximum(den, 1e-6), 0.0)


def pinta_layout(ax, rects, esc, campo, titulo, cmap, vmax):
    campo = suaviza(campo, esc)
    ax.imshow(np.where(esc.libre, campo, np.nan), origin="lower",
              extent=[0, W, 0, H], cmap=cmap, vmin=0, vmax=vmax,
              interpolation="bicubic", zorder=1)
    cs = ax.contour(esc.g.X, esc.g.Y, np.where(esc.libre, campo, 0),
                    levels=[RHO_CRIT], colors="white", linewidths=1.4,
                    linestyles="--", zorder=3)
    for _, cono in conos_aproximacion():                       # conos de PC
        ax.add_patch(Rectangle(cono[:2], cono[2], cono[3], fill=False,
                               ec="white", lw=0.8, ls=":", alpha=0.55, zorder=4))
    for k, r in rects.items():                                 # zonas de servicio
        ax.add_patch(Rectangle(r[:2], r[2], r[3], fc=COLOR_TIPO[TIPO[k]],
                               ec="white", lw=1.0, alpha=0.95, zorder=5))
    ax.add_patch(Rectangle(ESCENARIO[:2], ESCENARIO[2], ESCENARIO[3],
                           fc="#2b2b3a", ec="white", lw=1.0, zorder=5))
    ax.text(ESCENARIO[0] + ESCENARIO[2] / 2, ESCENARIO[1] + ESCENARIO[3] / 2,
            "ESCENARIO", color="white", ha="center", va="center",
            fontsize=8, weight="bold", zorder=6)
    for nom, (x, y, w, h), lado in SALIDAS:                    # salidas
        ax.add_patch(Rectangle((x - 0.5, y - 0.5), max(w, 2.5) + 1, max(h, 2.5) + 1,
                               fc="#ff1f1f", ec="white", lw=0.8, zorder=7))
    ax.set_xlim(0, W); ax.set_ylim(0, H)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(titulo, fontsize=11, color="#e8e8ee", pad=8)
    return cs


def flechas_destino(ax, esc, T, paso=6):
    """Quiver de -grad T: la direccion en la que se mueve la gente. Deja claro
    que todo el mundo converge a las salidas y a ningun otro lado."""
    Tm = np.where(esc.libre & (T < 1e8), T, np.nan)
    gy, gx = np.gradient(Tm, esc.g.h)
    mag = np.hypot(gx, gy)
    ok = np.isfinite(mag) & (mag > 1e-9)
    u = np.where(ok, -gx / np.maximum(mag, 1e-9), 0.0)
    v = np.where(ok, -gy / np.maximum(mag, 1e-9), 0.0)
    sl = (slice(paso // 2, None, paso), slice(paso // 2, None, paso))
    m = ok[sl]
    ax.quiver(esc.g.X[sl][m], esc.g.Y[sl][m], u[sl][m], v[sl][m],
              color="white", alpha=0.30, scale=42, width=0.0035,
              headwidth=3.5, zorder=6)


def escena_de(rects, h=1.0):
    bl = bloques_de(rects)
    return Escena(Rejilla(h), rects, bl), bl


# --- 1) operacion normal -----------------------------------------------------
def figura_operacion():
    cmap = cmap_densidad()
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.6), facecolor="#0e0e14")
    datos = []
    for ax, (rects, nombre) in zip(axes, [(INGENUO, "Layout ingenuo"),
                                          (BUENO, "Layout repartido")]):
        esc, bl = escena_de(rects)
        dest = [(esc.tipos[t], DEMANDA[t]) for t in esc.tipos if esc.tipos[t].any()]
        rho, v, campos, p = esc.punto_fijo(dest, horizonte=200.0)
        p95 = float(np.percentile(rho[esc.libre], 95))
        datos.append((rho, p95))
        pinta_layout(ax, rects, esc, rho,
                     "%s\np95 densidad = %.2f pers/m$^2$" % (nombre, p95),
                     cmap, RHO_MAX)
    sm = plt.cm.ScalarMappable(cmap=cmap,
                               norm=plt.Normalize(vmin=0, vmax=RHO_MAX))
    cb = fig.colorbar(sm, ax=axes, fraction=0.03, pad=0.02)
    cb.set_label("densidad  [pers/m$^2$]   (--- = critica)", color="#e8e8ee")
    cb.ax.axhline(RHO_CRIT, color="white", ls="--", lw=1.4)
    cb.ax.tick_params(colors="#e8e8ee")
    fig.suptitle("Operacion normal - mismo modelo, misma escala de color",
                 color="white", fontsize=13, y=0.98)
    fig.text(0.5, 0.02, "linea blanca punteada = umbral normativo  |  "
             "punteado fino = conos de aproximacion  |  ROJO = salidas",
             ha="center", color="#9a9aa8", fontsize=8)
    out = os.path.join(SAL, "01_operacion.png")
    fig.savefig(out, dpi=140, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print("->", out, " p95:", [round(d[1], 2) for d in datos])


# --- 2) evacuacion -----------------------------------------------------------
def evacuacion(rects, h=1.0):
    """Resuelve el escenario de evacuacion. Devuelve las piezas crudas; los
    frames se arman despues sobre un reloj COMPARTIDO por los dos layouts,
    porque comparar en relojes distintos no compara nada."""
    esc, bl = escena_de(rects, h)
    rho, v, campos, p = esc.punto_fijo([(esc.salidas, 1.0)], horizonte=240.0)
    T = np.nan_to_num(campos[0], posinf=1e9, nan=1e9)
    m = esc.libre & (p > 0)
    orden = np.argsort(T[m])
    masa = p[m][orden]
    acum = np.cumsum(masa) / masa.sum()
    Torden = T[m][orden]
    t95 = float(Torden[np.searchsorted(acum, 0.95)])
    tfin = float(Torden[np.searchsorted(acum, 0.995)])
    return dict(esc=esc, rho=rho, T=T, p=p, t95=t95, tfin=tfin)


def arma_frames(d, ts):
    esc, rho, T, p = d["esc"], d["rho"], d["T"], d["p"]
    total = p.sum()
    frames = [suaviza(rho * (T > t), esc) for t in ts]
    evac = [100.0 * (1.0 - p[T > t].sum() / total) for t in ts]
    return frames, evac


def gif_evacuacion():
    cmap = cmap_densidad()
    res = {}
    for nombre, rects in (("ingenuo", INGENUO), ("bueno", BUENO)):
        res[nombre] = evacuacion(rects)
    tfin = max(res[k]["tfin"] for k in res)
    ts = list(np.linspace(0.0, tfin, 70))
    for nombre in res:
        fr, ev = arma_frames(res[nombre], ts)
        res[nombre]["frames"], res[nombre]["evac"] = fr, ev
        print("  %s: t95 = %.0f s" % (nombre, res[nombre]["t95"]))
    nmax = len(ts)

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.8), facecolor="#0e0e14")
    ims, txts = [], []
    for ax, (nombre, rects, titulo) in zip(
            axes, [("ingenuo", INGENUO, "Layout ingenuo"),
                   ("bueno", BUENO, "Layout repartido")]):
        esc = res[nombre]["esc"]
        im = ax.imshow(np.zeros_like(esc.g.X), origin="lower", extent=[0, W, 0, H],
                       cmap=cmap, vmin=0, vmax=RHO_MAX, interpolation="bicubic", zorder=1)
        for _, cono in conos_aproximacion():
            ax.add_patch(Rectangle(cono[:2], cono[2], cono[3], fill=False,
                                   ec="white", lw=0.8, ls=":", alpha=0.5, zorder=4))
        for k, r in rects.items():
            ax.add_patch(Rectangle(r[:2], r[2], r[3], fc=COLOR_TIPO[TIPO[k]],
                                   ec="white", lw=1.0, zorder=5))
        ax.add_patch(Rectangle(ESCENARIO[:2], ESCENARIO[2], ESCENARIO[3],
                               fc="#2b2b3a", ec="white", lw=1.0, zorder=5))
        for nom, (x, y, w, h), lado in SALIDAS:
            ax.add_patch(Rectangle((x - 0.5, y - 0.5), max(w, 2.5) + 1, max(h, 2.5) + 1,
                                   fc="#ff1f1f", ec="white", lw=0.8, zorder=7))
        ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_aspect("equal")
        ax.set_xticks([]); ax.set_yticks([])
        flechas_destino(ax, esc, res[nombre]["T"])
        ax.set_title(titulo, fontsize=11, color="#e8e8ee", pad=22)
        t = ax.text(0.5, 1.015, "", transform=ax.transAxes, ha="center",
                    color="#ffd9a0", fontsize=10, family="monospace")
        ims.append(im); txts.append(t)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, RHO_MAX))
    cb = fig.colorbar(sm, ax=axes, fraction=0.03, pad=0.02)
    cb.set_label("densidad  [pers/m$^2$]", color="#e8e8ee")
    cb.ax.axhline(RHO_CRIT, color="white", ls="--", lw=1.4)
    cb.ax.tick_params(colors="#e8e8ee")
    fig.suptitle("Evacuacion - 14 000 asistentes, mismas salidas, mismo reloj",
                 color="white", fontsize=13, y=0.98)

    def actualiza(f):
        for k, nombre in enumerate(("ingenuo", "bueno")):
            d = res[nombre]
            i = min(f, len(d["frames"]) - 1)
            ims[k].set_data(d["frames"][i])
            txts[k].set_text("t = %4.0f s   evacuado %5.1f %%   (t95 = %.0f s)"
                             % (ts[i], d["evac"][i], d["t95"]))
        return ims + txts

    ani = FuncAnimation(fig, actualiza, frames=nmax, interval=90, blit=False)
    out = os.path.join(SAL, "02_evacuacion.gif")
    ani.save(out, writer=PillowWriter(fps=9), dpi=72,
             savefig_kwargs={"facecolor": fig.get_facecolor()})
    plt.close(fig)
    print("->", out)


if __name__ == "__main__":
    os.makedirs(SAL, exist_ok=True)
    print("operacion normal...")
    figura_operacion()
    print("evacuacion...")
    gif_evacuacion()
