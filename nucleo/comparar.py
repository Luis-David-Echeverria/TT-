"""
Comparacion visual: layout aleatorio contra layout optimizado.

Ambos se simulan con el MISMO modelo, el MISMO aforo, la MISMA distribucion
inicial y el MISMO reloj. La escala de color esta anclada al umbral fisico de
perdida de control individual, asi que el color significa lo mismo en los dos
paneles y entre corridas distintas.
"""
import os
import pickle
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

from recinto import recinto_ejemplo
import campos as C
import geometria as G
import fluido as F
import viz as V
from parametros import RHO_PERDIDA_CONTROL

SAL = os.path.join(os.path.dirname(__file__), "..", "salidas")
N_CUADROS = 55


def correr(rec, layout, aforo, foco, escala):
    oc, _ = G.zona_ocupable(rec, layout)
    M0 = C.distribucion_inicial(rec, oc, aforo, foco=foco, escala=escala)
    return F.simular(rec, layout, aforo, dt=0.3, t_max=420.0,
                     n_cuadros=N_CUADROS, M0=M0, guardar_campos=True)


def gif(rec, datos, t_max_comun, salida):
    cmap = V.cmap_densidad()
    fig, axes = plt.subplots(1, 2, figsize=(13.6, 4.9), facecolor=V.FONDO)
    ims, txts, quivs = [], [], []
    for ax, (titulo, d) in zip(axes, datos):
        im = ax.imshow(np.zeros_like(rec.X), origin="lower",
                       extent=[0, rec.W, 0, rec.H], cmap=cmap,
                       vmin=0, vmax=5.4, interpolation="bicubic", zorder=1)
        V.dibujar_muros(ax, rec)
        V.dibujar_layout(ax, rec, d["layout"])
        V.dibujar_salidas(ax, rec)
        V.estilo(ax, rec)
        ax.set_title(titulo, fontsize=11, color=V.TINTA, pad=20)
        t = ax.text(0.5, 1.02, "", transform=ax.transAxes, ha="center",
                    color="#8fe8c0", fontsize=10, family="monospace")
        paso = max(3, int(6 / rec.h))
        sl = (slice(paso // 2, None, paso), slice(paso // 2, None, paso))
        msk = d["r"]["libre"][sl]
        qv = ax.quiver(rec.X[sl][msk], rec.Y[sl][msk],
                       np.zeros(int(msk.sum())), np.zeros(int(msk.sum())),
                       color="white", alpha=0.33, scale=42, width=0.003,
                       headwidth=3.3, zorder=7)
        ims.append(im); txts.append(t); quivs.append((qv, sl, msk))

    V.barra_densidad(fig, axes, cmap)
    fig.suptitle("Evacuación — mismo aforo, misma distribución inicial, mismo reloj",
                 color="white", fontsize=13, y=0.97)
    fig.text(0.5, 0.02,
             "fondo = densidad de multitud   ·   flechas = campo de destino (−∇T)   "
             "·   verde = salidas con capacidad finita",
             ha="center", color=V.TENUE, fontsize=8)

    n = max(len(d["r"]["cuadros"]) for _, d in datos)

    def act(f):
        for k, (_, d) in enumerate(datos):
            r = d["r"]
            i = min(f, len(r["cuadros"]) - 1)
            ims[k].set_data(np.where(r["libre"], r["cuadros"][i], 0.0))
            qv, sl, msk = quivs[k]
            if i < len(r["dirs"]):
                ux, uy = r["dirs"][i]
                qv.set_UVC(ux[sl][msk], uy[sl][msk])
            txts[k].set_text("t = %4.0f s    evacuado %5.1f %%    t95 = %s"
                             % (r["t"][i], r["pct"][i],
                                "%.0f s" % r["t95"] if r["t95"] else "—"))
        return ims + txts

    ani = FuncAnimation(fig, act, frames=n, interval=110, blit=False)
    ani.save(salida, writer=PillowWriter(fps=10), dpi=80,
             savefig_kwargs={"facecolor": fig.get_facecolor()})
    plt.close(fig)


def curvas(datos, historia, salida):
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 3.9), facecolor=V.FONDO)
    ax = axes[0]
    for (titulo, d), col in zip(datos, ["#e0a458", "#5dcaa5"]):
        r = d["r"]
        ax.plot(r["t"], r["pct"], color=col, lw=2, label="%s  (t95 = %.0f s)"
                % (titulo, r["t95"] or float("nan")))
        if r["t95"]:
            ax.axvline(r["t95"], color=col, ls=":", lw=1, alpha=0.7)
    ax.axhline(95, color="white", ls="--", lw=1, alpha=0.5)
    ax.set_xlabel("tiempo [s]", color=V.TINTA, fontsize=9)
    ax.set_ylabel("evacuado [%]", color=V.TINTA, fontsize=9)
    ax.legend(fontsize=8, facecolor="#161b22", edgecolor="#272e38", labelcolor=V.TINTA)

    ax2 = axes[1]
    ax2.plot(range(len(historia)), historia, color="#5dcaa5", lw=2, marker="o", ms=3)
    ax2.set_xlabel("generación", color=V.TINTA, fontsize=9)
    ax2.set_ylabel("mejor t95 [s]", color=V.TINTA, fontsize=9)
    ax2.set_title("convergencia del optimizador", color=V.TINTA, fontsize=10)

    for a in axes:
        a.set_facecolor("#0f131a")
        a.tick_params(colors=V.TENUE, labelsize=8)
        for s in a.spines.values():
            s.set_color("#272e38")
        a.grid(alpha=0.12, color="white")
    fig.tight_layout()
    fig.savefig(salida, dpi=140, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def main():
    os.makedirs(SAL, exist_ok=True)
    with open(os.path.join(SAL, "comparacion.pkl"), "rb") as f:
        g = pickle.load(f)

    rec = recinto_ejemplo(h=1.0)          # resolucion fina para el render
    datos = []
    for titulo, clave in (("Layout aleatorio (factible)", "aleatorio"),
                          ("Layout optimizado", "optimizado")):
        r = correr(rec, g[clave], g["aforo"], g["foco"], g["escala"])
        datos.append((titulo, {"layout": g[clave], "r": r}))
        print("  %-28s t95 = %s s   evacuado final %.1f %%"
              % (titulo, "%.0f" % r["t95"] if r["t95"] else "—", r["evacuado_final"]))

    t_max = max(d["r"]["t"][-1] for _, d in datos)
    gif(rec, datos, t_max, os.path.join(SAL, "evacuacion.gif"))
    print("->", os.path.join(SAL, "evacuacion.gif"))
    curvas(datos, g["historia"], os.path.join(SAL, "curvas.png"))
    print("->", os.path.join(SAL, "curvas.png"))


if __name__ == "__main__":
    main()
