"""
Panel interactivo para explorar el modelo dentro de JupyterLab.

El modelo Python es la UNICA fuente de verdad: el panel solo dibuja lo que el
solver calcula. No hay una segunda implementacion que pueda desviarse.

Uso en el notebook:

    %matplotlib widget
    from panel import Panel
    p = Panel()
    p.mostrar()
"""
import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as W
from IPython.display import display

import parametros as P
import recinto as R
import geometria as G
import campos as C
import fluido as F
import viz as V
import optimizar as O

CONTEO = {"SAN": 3, "COM": 3, "BEB": 2, "MED": 1}


def _boton(desc, icono, estilo=""):
    return W.Button(description=desc, icon=icono, button_style=estilo,
                    layout=W.Layout(width="auto"))


class Panel:
    def __init__(self, h=1.0, aforo=6000.0, escala=18.0):
        self.rng = np.random.default_rng(0)
        self.h = h
        self.rec = R.recinto_ejemplo(h=h)
        self.layout = R.layout_factible(self.rec, self.rng, CONTEO)
        self.sim = None
        self.historia = None
        self._rechazo = ""
        self._construir(aforo, escala)

    # ------------------------------------------------------------------ UI
    def _construir(self, aforo, escala):
        est = dict(style={"description_width": "108px"},
                   layout=W.Layout(width="330px"), continuous_update=False)

        self.w_aforo = W.IntSlider(value=int(aforo), min=1000, max=25000, step=500,
                                   description="aforo [pers]", **est)
        self.w_escala = W.FloatSlider(value=escala, min=6, max=60, step=2,
                                      description="concentración [m]", **est)
        self.w_uniforme = W.Checkbox(value=False, description="repartir uniforme",
                                     indent=False)
        self.w_h = W.Dropdown(options=[("1.0 m — convergida", 1.0),
                                       ("1.5 m — intermedia", 1.5),
                                       ("2.0 m — rápida (NO convergida)", 2.0)],
                              value=self.h, description="malla",
                              style={"description_width": "108px"},
                              layout=W.Layout(width="330px"))
        self.w_gen = W.IntSlider(value=10, min=3, max=30, step=1,
                                 description="generaciones", **est)

        self.b_nuevo = _boton("Layout aleatorio", "random")
        self.b_sim = _boton("Simular", "play", "primary")
        self.b_opt = _boton("Optimizar", "bolt", "warning")

        self.w_area = W.Dropdown(options=[], description="mover área",
                                 style={"description_width": "108px"},
                                 layout=W.Layout(width="330px"))
        self.b_rot = _boton("Girar 90°", "rotate-right")

        self.w_t = W.IntSlider(value=0, min=0, max=0, step=1, description="t",
                               style={"description_width": "40px"},
                               layout=W.Layout(width="640px"),
                               continuous_update=True, readout=False)

        self.salida = W.Output()
        self.info = W.HTML()

        for b, fn in ((self.b_nuevo, self._nuevo), (self.b_sim, self._simular),
                      (self.b_opt, self._optimizar), (self.b_rot, self._girar)):
            b.on_click(fn)
        self.w_h.observe(self._cambiar_malla, names="value")
        self.w_t.observe(lambda ch: self._pintar(), names="value")
        for w in (self.w_aforo, self.w_escala, self.w_uniforme):
            w.observe(lambda ch: self._invalidar(), names="value")

        self._crear_figura()
        self._refrescar_areas()
        self._invalidar()

    def _crear_figura(self):
        plt.ioff()
        self.fig, (self.ax, self.axc) = plt.subplots(
            1, 2, figsize=(11.2, 3.9), facecolor=V.FONDO,
            gridspec_kw={"width_ratios": [2.05, 1]})
        self.fig.canvas.header_visible = False
        self.fig.canvas.footer_visible = False
        self.fig.canvas.toolbar_visible = False
        self.fig.canvas.mpl_connect("button_press_event", self._click)
        plt.ion()

    def mostrar(self):
        ctrl = W.VBox([
            W.HTML("<b style='color:#e6e1d7'>Escenario</b>"),
            self.w_aforo, self.w_escala, self.w_uniforme, self.w_h,
            W.HTML("<hr style='border-color:#272e38'>"
                   "<b style='color:#e6e1d7'>Layout</b>"),
            self.w_area, W.HBox([self.b_rot, self.b_nuevo]),
            W.HTML("<span style='color:#8b949e;font-size:11px'>"
                   "clic en el mapa = mover el área seleccionada</span>"),
            W.HTML("<hr style='border-color:#272e38'>"
                   "<b style='color:#e6e1d7'>Correr</b>"),
            self.w_gen, W.HBox([self.b_sim, self.b_opt]),
        ], layout=W.Layout(width="360px"))
        display(W.VBox([
            W.HBox([ctrl, W.VBox([self.fig.canvas, self.w_t])]),
            self.info, self.salida]))
        self._pintar()

    # ------------------------------------------------------- estado / calculo
    def _refrescar_areas(self):
        self.w_area.options = [
            ("%d · %s" % (i + 1, R.POR_CLAVE[c.tipo].nombre), i)
            for i, c in enumerate(self.layout)]
        if self.w_area.options:
            self.w_area.value = 0

    def _aforo_M0(self, rec=None, layout=None):
        rec = rec or self.rec
        layout = self.layout if layout is None else layout
        oc, _ = G.zona_ocupable(rec, layout)
        foco = None if self.w_uniforme.value else (rec.W / 2, rec.H - 2.0)
        M0 = C.distribucion_inicial(rec, oc, float(self.w_aforo.value),
                                    foco=foco, escala=self.w_escala.value)
        return oc, M0

    def _invalidar(self, *_):
        self.sim = None
        self.w_t.max = 0
        self._pintar()

    def _cambiar_malla(self, ch):
        self.h = ch["new"]
        viejo = self.layout
        self.rec = R.recinto_ejemplo(h=self.h)
        self.layout = [R.Colocacion(c.tipo, c.x, c.y, c.rot) for c in viejo]
        self._invalidar()

    def _nuevo(self, *_):
        lay = R.layout_factible(self.rec, self.rng, CONTEO)
        if lay:
            self.layout = lay
            self._refrescar_areas()
        self._invalidar()

    def _girar(self, *_):
        if self.w_area.value is None:
            return
        c = self.layout[self.w_area.value]
        prev = c.rot
        c.rot = 1 - c.rot
        if not G.evaluar(self.rec, self.layout, corto=True)["factible"]:
            c.rot = prev
            self._rechazo = "giro rechazado: no cabe"
        else:
            self._rechazo = ""
        self._invalidar()

    def _click(self, ev):
        if ev.inaxes is not self.ax or self.w_area.value is None:
            return
        c = self.layout[self.w_area.value]
        t = R.POR_CLAVE[c.tipo]
        w, f = (t.ancho, t.fondo) if c.rot == 0 else (t.fondo, t.ancho)
        px, py = c.x, c.y
        c.x = float(np.clip(ev.xdata - w / 2, 0, self.rec.W - w))
        c.y = float(np.clip(ev.ydata - f / 2, 0, self.rec.H - f))
        r = G.evaluar(self.rec, self.layout, corto=True)
        if not r["factible"]:
            c.x, c.y = px, py          # rechaza el movimiento ilegal
            motivo = next((q["nombre"] for q in r["pasos"] if q["violacion"] > 0), "?")
            self._rechazo = "movimiento rechazado por %s" % motivo
        else:
            self._rechazo = ""
        self._invalidar()

    def _simular(self, *_):
        with self.salida:
            self.salida.clear_output()
            oc, M0 = self._aforo_M0()
            self.sim = F.simular(self.rec, self.layout, float(self.w_aforo.value),
                                 dt=0.3 if self.h <= 1.0 else 0.5, t_max=1600.0,
                                 n_cuadros=45, M0=M0, guardar_campos=True)
        self.w_t.max = max(0, len(self.sim["cuadros"]) - 1)
        self.w_t.value = self.w_t.max // 3
        self._pintar()

    def _optimizar(self, *_):
        with self.salida:
            self.salida.clear_output()
            oc, M0 = self._aforo_M0()
            sem = [self.layout] + [l for l in
                   (R.layout_factible(self.rec, self.rng, CONTEO) for _ in range(5)) if l]
            print("optimizando… %d generaciones" % self.w_gen.value)
            res = O.optimizar(self.rec, sem, float(self.w_aforo.value), M0=M0,
                              mu=4, lam=8, generaciones=int(self.w_gen.value),
                              rng=self.rng, verbose=True)
            self.layout = res["mejor"]
            self.historia = res["historia"]
            print("mejor t95 = %.1f s" % res["t_mejor"])
        self._refrescar_areas()
        self._invalidar()
        self._simular()

    # ------------------------------------------------------------------ dibujo
    def _pintar(self):
        oc, M0 = self._aforo_M0()
        geo = G.evaluar(self.rec, self.layout, corto=False)

        self.ax.clear()
        if self.sim is None:
            rho = M0 / self.rec.area_celda
            titulo = "densidad inicial (t = 0)"
        else:
            i = int(self.w_t.value)
            rho = self.sim["cuadros"][i]
            titulo = "t = %.0f s   ·   evacuado %.1f %%" % (
                self.sim["t"][i], self.sim["pct"][i])
        V.mapa_densidad(self.ax, self.rec, rho, self.layout, libre=oc)
        if self.w_area.value is not None:
            V.dibujar_layout(self.ax, self.rec, self.layout,
                             resaltar={self.w_area.value})
        if self.sim is not None and self.sim["dirs"]:
            i = min(int(self.w_t.value), len(self.sim["dirs"]) - 1)
            ux, uy = self.sim["dirs"][i]
            V.flechas(self.ax, self.rec, ux, uy, self.sim["libre"],
                      paso=max(3, int(6 / self.rec.h)), alpha=0.3)
        V.estilo(self.ax, self.rec, titulo)

        self.axc.clear()
        self.axc.set_facecolor("#0f131a")
        if self.sim is not None:
            self.axc.plot(self.sim["t"], self.sim["pct"], color="#5dcaa5", lw=2)
            self.axc.axhline(95, color="white", ls="--", lw=1, alpha=.5)
            if self.sim["t95"]:
                self.axc.axvline(self.sim["t95"], color="#e0a458", ls=":", lw=1.2)
            self.axc.axvline(self.sim["t"][int(self.w_t.value)], color="white",
                             lw=1, alpha=.45)
            self.axc.set_xlabel("t [s]", fontsize=8, color=V.TINTA)
            self.axc.set_ylabel("evacuado [%]", fontsize=8, color=V.TINTA)
        elif self.historia:
            self.axc.plot(self.historia, color="#5dcaa5", lw=2, marker="o", ms=3)
            self.axc.set_xlabel("generación", fontsize=8, color=V.TINTA)
            self.axc.set_ylabel("mejor t95 [s]", fontsize=8, color=V.TINTA)
        else:
            self.axc.text(.5, .5, "pulsa Simular", ha="center", va="center",
                          color=V.TENUE, fontsize=10, transform=self.axc.transAxes)
            self.axc.set_xticks([]); self.axc.set_yticks([])
        self.axc.tick_params(colors=V.TENUE, labelsize=7)
        for s in self.axc.spines.values():
            s.set_color("#272e38")
        self.axc.grid(alpha=.12, color="white")
        self.fig.tight_layout()
        self.fig.canvas.draw_idle()
        self._info(oc, M0, geo)

    def _info(self, oc, M0, geo):
        area = float(oc.sum()) * self.rec.area_celda
        rho_m = M0[oc].mean() / self.rec.area_celda if oc.any() else 0
        rho_p = np.percentile(M0[oc], 95) / self.rec.area_celda if oc.any() else 0
        Wu = self.rec.ancho_total_salidas(P.CAPA_LIMITE)
        cota = self.w_aforo.value / (P.J_ESPECIFICO * Wu)
        ok = geo["factible"]
        fallos = [p["nombre"] for p in geo["pasos"] if p["violacion"] > 0]
        t95 = ("%.0f s" % self.sim["t95"]) if (self.sim and self.sim["t95"]) else "—"
        aviso = ("" if self.h <= 1.0 else
                 "<span style='color:#e0a458'> · malla no convergida, "
                 "los valores son indicativos</span>")
        self.info.value = (
            "<div style='font-family:ui-monospace,monospace;font-size:12px;"
            "color:#e6e1d7;background:#161b22;border:1px solid #272e38;"
            "border-radius:6px;padding:9px 12px;margin-top:6px'>"
            "capa geométrica: <b style='color:%s'>%s</b>%s &nbsp;·&nbsp; "
            "área ocupable <b>%.0f m²</b> &nbsp;·&nbsp; "
            "ρ media <b>%.2f</b> / p95 <b>%.2f</b> pers/m² &nbsp;·&nbsp; "
            "cota por puertas <b>%.0f s</b> &nbsp;·&nbsp; "
            "<b style='color:#5dcaa5'>t95 = %s</b>%s%s</div>"
            % ("#5dcaa5" if ok else "#e24b4a",
               "factible" if ok else "INFACTIBLE (%s)" % ", ".join(fallos),
               "", area, rho_m, rho_p, cota, t95, aviso,
               ("<span style='color:#e24b4a'> · %s</span>" % self._rechazo)
               if self._rechazo else ""))
