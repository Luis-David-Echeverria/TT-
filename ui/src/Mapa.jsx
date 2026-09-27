import { useRef, useEffect, useCallback } from "react";
import { debase64, colorTiempo, dimensiones, tipoDe, variantesColor } from "./api";

/* Los campos llegan de dos sitios: del backend en base64, o del motor que
 * corre en el navegador ya como Uint8Array. Se aceptan los dos para no tener
 * dos caminos de dibujo que puedan desviarse. */
const arr = (x) => (x instanceof Uint8Array ? x : debase64(x));

/* Dibuja lo que el backend calculó. No decide nada del modelo.
 * La única interacción es pintar muros: las áreas de servicio las coloca el
 * sistema, no el usuario. */
export default function Mapa({
  catalogo, recinto, layout, geo, campo, sim, cuadro,
  acceso, tipoAcceso,
  vista, verFlechas, verIsocronas, verConos, verRejilla, suavizar,
  modoPintar, modoSalida, lut, onPintar, onColocarSalida, etiqueta,
}) {
  const ref = useRef(null);
  const off = useRef(null);
  const pintando = useRef(false);
  const T = useRef({ s: 1, ox: 0, oy: 0, dpr: 1 });
  if (!off.current) off.current = document.createElement("canvas");

  const dibujar = useCallback(() => {
    const cv = ref.current;
    if (!cv || !catalogo || !lut) return;

    const caja = cv.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    cv.width = Math.max(1, Math.round(caja.width * dpr));
    cv.height = Math.max(1, Math.round(caja.height * dpr));
    const m = 14 * dpr;
    const s = Math.min((cv.width - 2 * m) / recinto.W, (cv.height - 2 * m) / recinto.H);
    T.current = { s, dpr, ox: (cv.width - recinto.W * s) / 2,
                  oy: (cv.height - recinto.H * s) / 2 };

    const ctx = cv.getContext("2d");
    const X = (x) => T.current.ox + x * s;
    const Y = (y) => cv.height - T.current.oy - y * s;
    ctx.fillStyle = "#05070f";
    ctx.fillRect(0, 0, cv.width, cv.height);

    const rect = (x, y, w, h, relleno, borde, grosor) => {
      if (relleno) { ctx.fillStyle = relleno; ctx.fillRect(X(x), Y(y + h), w * s, h * s); }
      if (borde) {
        ctx.strokeStyle = borde;
        ctx.lineWidth = grosor ?? Math.max(1, s * 0.05);
        ctx.strokeRect(X(x), Y(y + h), w * s, h * s);
      }
    };

    const pintarCampo = (datos, mascara, nx, ny, esTiempo) => {
      const o = off.current;
      o.width = nx; o.height = ny;
      const octx = o.getContext("2d");
      const img = octx.createImageData(nx, ny);
      for (let i = 0; i < nx * ny; i++) {
        const j = (ny - 1 - ((i / nx) | 0)) * nx + (i % nx);
        const v = datos[j], k = i * 4;
        if (mascara && !mascara[j]) {
          img.data[k] = 5; img.data[k+1] = 7; img.data[k+2] = 15; img.data[k+3] = 255;
          continue;
        }
        if (esTiempo) { const c = colorTiempo(v);
          img.data[k] = c[0]; img.data[k+1] = c[1]; img.data[k+2] = c[2]; }
        else { img.data[k] = lut[v*3]; img.data[k+1] = lut[v*3+1]; img.data[k+2] = lut[v*3+2]; }
        img.data[k+3] = 255;
      }
      octx.putImageData(img, 0, 0);
      // Por defecto SIN interpolar: la unidad fisica del modelo es la celda de
      // 1 m², y suavizar la esconde. Cada cuadrito de la pantalla es una celda
      // con su densidad, legible contra la leyenda. El suavizado queda como
      // opcion para presentaciones, no como vista de trabajo.
      ctx.imageSmoothingEnabled = !!suavizar;
      if (suavizar) ctx.imageSmoothingQuality = "high";
      ctx.drawImage(o, X(0), Y(recinto.H), recinto.W * s, recinto.H * s);
      ctx.imageSmoothingEnabled = false;
    };

    /* f1 dibujada: cada celda del color del modulo que la atiende, mas oscura
       cuanto mas lejos queda. Es el reparto que el numero f1 promedia. */
    const pintarAcceso = () => {
      const t = acceso?.tipos?.[tipoAcceso];
      if (!t) return;
      const quien = arr(t.quien ?? t.quien_b64);
      const dist = arr(t.dist ?? t.dist_b64);
      const base = tipoDe(tipoAcceso, catalogo)?.color || "#4C9BE8";
      const col = variantesColor(base, t.modulos.length);
      const nx = acceso.nx, ny = acceso.ny;
      const o = off.current;
      o.width = nx; o.height = ny;
      const octx = o.getContext("2d");
      const img = octx.createImageData(nx, ny);
      for (let i = 0; i < nx * ny; i++) {
        const j = (ny - 1 - ((i / nx) | 0)) * nx + (i % nx);
        const k = i * 4, m = quien[j];
        if (m === 255 || m >= col.length) {
          img.data[k] = 5; img.data[k+1] = 7; img.data[k+2] = 15; img.data[k+3] = 255;
          continue;
        }
        // 1.0 pegado al modulo, 0.34 en el punto mas lejano de su region
        const f = 1.0 - 0.66 * (dist[j] / 255);
        img.data[k]     = col[m][0] * f;
        img.data[k + 1] = col[m][1] * f;
        img.data[k + 2] = col[m][2] * f;
        img.data[k + 3] = 255;
      }
      octx.putImageData(img, 0, 0);
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(o, X(0), Y(recinto.H), recinto.W * s, recinto.H * s);
    };

    const pintarFlechas = (dx, dy, mascara, nx, ny, h) => {
      const paso = Math.max(2, Math.round(6 / h));
      const L = h * paso * 0.4;
      ctx.strokeStyle = "rgba(255,255,255,.32)";
      ctx.lineWidth = Math.max(0.9, s * 0.045);
      ctx.beginPath();
      for (let i = paso >> 1; i < ny; i += paso)
        for (let j = paso >> 1; j < nx; j += paso) {
          const k = i * nx + j;
          if (mascara && !mascara[k]) continue;
          const ux = (dx[k] / 255) * 2 - 1, uy = (dy[k] / 255) * 2 - 1;
          if (Math.hypot(ux, uy) < 0.25) continue;
          const cx = (j + 0.5) * h, cy = (i + 0.5) * h;
          const bx = cx + ux * L, by = cy + uy * L;
          ctx.moveTo(X(cx - ux * L), Y(cy - uy * L)); ctx.lineTo(X(bx), Y(by));
          const a = Math.atan2(uy, ux), r = L * 0.5;
          ctx.moveTo(X(bx), Y(by));
          ctx.lineTo(X(bx - r*Math.cos(a-0.5)), Y(by - r*Math.sin(a-0.5)));
          ctx.moveTo(X(bx), Y(by));
          ctx.lineTo(X(bx - r*Math.cos(a+0.5)), Y(by - r*Math.sin(a+0.5)));
        }
      ctx.stroke();
    };

    const pintarIsocronas = () => {
      if (!campo || !verIsocronas) return;
      const c = campo.tiempos;
      const d = debase64(c.datos_b64), mk = debase64(c.mascara_b64);
      const paso = 255 / Math.max(1, campo.isocronas.length);
      ctx.strokeStyle = "rgba(255,255,255,.26)";
      ctx.lineWidth = Math.max(0.6, s * 0.028);
      ctx.beginPath();
      for (let i = 0; i < c.ny; i++)
        for (let j = 0; j < c.nx; j++) {
          const k = i * c.nx + j;
          if (!mk[k]) continue;
          const a = (d[k] / paso) | 0;
          if (j+1 < c.nx && mk[k+1] && ((d[k+1]/paso)|0) !== a) {
            ctx.moveTo(X((j+1)*c.h), Y(i*c.h)); ctx.lineTo(X((j+1)*c.h), Y((i+1)*c.h)); }
          if (i+1 < c.ny && mk[k+c.nx] && ((d[k+c.nx]/paso)|0) !== a) {
            ctx.moveTo(X(j*c.h), Y((i+1)*c.h)); ctx.lineTo(X((j+1)*c.h), Y((i+1)*c.h)); }
        }
      ctx.stroke();
    };

    if (vista === "acceso" && acceso) {
      pintarAcceso();
    } else if (vista === "tiempos" && campo) {
      const c = campo.tiempos;
      pintarCampo(debase64(c.datos_b64), debase64(c.mascara_b64), c.nx, c.ny, true);
      pintarIsocronas();
      if (verFlechas) pintarFlechas(debase64(campo.dir_x_b64), debase64(campo.dir_y_b64),
                                    debase64(c.mascara_b64), c.nx, c.ny, c.h);
    } else if (sim) {
      const cu = sim.cuadros ?? sim.cuadros_b64;
      const mk = arr(sim.mascara ?? sim.mascara_b64);
      const i = Math.min(cuadro, cu.length - 1);
      pintarCampo(arr(cu[i]), mk, sim.nx, sim.ny, false);
      if (verFlechas && sim.direcciones?.[i])
        pintarFlechas(arr(sim.direcciones[i].x), arr(sim.direcciones[i].y),
                      mk, sim.nx, sim.ny, sim.h);
    } else if (campo) {
      const c = campo.tiempos;
      pintarCampo(debase64(c.datos_b64), debase64(c.mascara_b64), c.nx, c.ny, true);
      pintarIsocronas();
      if (verFlechas) pintarFlechas(debase64(campo.dir_x_b64), debase64(campo.dir_y_b64),
                                    debase64(c.mascara_b64), c.nx, c.ny, c.h);
    }

    // rejilla metrica: fina cada 1 m cuando hay espacio, marcada cada 10 m
    if (verRejilla) {
      ctx.lineWidth = 1;
      if (s > 7) {
        ctx.strokeStyle = "rgba(255,255,255,.07)";
        ctx.beginPath();
        for (let x = 1; x < recinto.W; x++) {
          ctx.moveTo(X(x) + 0.5, Y(0)); ctx.lineTo(X(x) + 0.5, Y(recinto.H));
        }
        for (let y = 1; y < recinto.H; y++) {
          ctx.moveTo(X(0), Y(y) + 0.5); ctx.lineTo(X(recinto.W), Y(y) + 0.5);
        }
        ctx.stroke();
      }
      ctx.strokeStyle = "rgba(255,255,255,.17)";
      ctx.beginPath();
      for (let x = 10; x < recinto.W; x += 10) {
        ctx.moveTo(X(x) + 0.5, Y(0)); ctx.lineTo(X(x) + 0.5, Y(recinto.H));
      }
      for (let y = 10; y < recinto.H; y += 10) {
        ctx.moveTo(X(0), Y(y) + 0.5); ctx.lineTo(X(recinto.W), Y(y) + 0.5);
      }
      ctx.stroke();
    }

    rect(0, 0, recinto.W, recinto.H, null, "#2b3444", Math.max(1, s * 0.05));

    if (verConos && geo) {
      const d = s * 0.4;
      ctx.setLineDash([d, d * 0.85]);
      for (const c of geo.conos)
        rect(c.x, c.y, c.w, c.h, null, "rgba(224,164,88,.5)", Math.max(1, s * 0.03));
      ctx.setLineDash([]);
    }

    for (const w of recinto.muros) rect(w.x, w.y, w.w, w.h, "#2c333e", "#404b5c");

    const malas = new Set();
    if (geo) for (const p of geo.pasos) for (const i of p.culpables) malas.add(i);
    layout.forEach((c, i) => {
      const [w, f] = dimensiones(c, catalogo);
      rect(c.x, c.y, w, f, tipoDe(c.tipo, catalogo).color,
           malas.has(i) ? "#e2564f" : "rgba(255,255,255,.7)",
           malas.has(i) ? Math.max(2, s * 0.1) : Math.max(1, s * 0.045));
    });

    for (const e of recinto.salidas) {
      const g = 1.8, a = e.centro - e.ancho / 2;
      const r = e.lado === "S" ? [a, -g/2, e.ancho, g]
              : e.lado === "N" ? [a, recinto.H - g/2, e.ancho, g]
              : e.lado === "O" ? [-g/2, a, g, e.ancho]
              : [recinto.W - g/2, a, g, e.ancho];
      rect(r[0], r[1], r[2], r[3], "#2bff88", "#05070f", Math.max(1, s * 0.04));
    }
  }, [catalogo, recinto, layout, geo, campo, sim, cuadro, vista,
      acceso, tipoAcceso,
      verFlechas, verIsocronas, verConos, verRejilla, suavizar, lut]);

  useEffect(() => { dibujar(); }, [dibujar]);
  useEffect(() => {
    const f = () => dibujar();
    window.addEventListener("resize", f);
    const ro = new ResizeObserver(f);
    if (ref.current?.parentElement) ro.observe(ref.current.parentElement);
    return () => { window.removeEventListener("resize", f); ro.disconnect(); };
  }, [dibujar]);

  const aMundo = (ev) => {
    const cv = ref.current, r = cv.getBoundingClientRect();
    const { s, ox, oy, dpr } = T.current;
    return [((ev.clientX - r.left) * dpr - ox) / s,
            (cv.height - (ev.clientY - r.top) * dpr - oy) / s];
  };

  return (
    <div className="relative h-full w-full">
      <canvas
        ref={ref}
        className={`absolute inset-0 h-full w-full ${modoPintar || modoSalida ? "cursor-crosshair" : ""}`}
        onPointerDown={(ev) => {
          if (modoSalida) {
            const [x, y] = aMundo(ev);
            // el lado mas cercano decide donde va la puerta
            const d = [["S", y], ["N", recinto.H - y], ["O", x], ["E", recinto.W - x]];
            d.sort((a, b) => a[1] - b[1]);
            const lado = d[0][0];
            onColocarSalida(lado, lado === "S" || lado === "N" ? x : y);
            return;
          }
          if (!modoPintar) return;
          pintando.current = true;
          ref.current.setPointerCapture(ev.pointerId);
          onPintar(...aMundo(ev));
        }}
        onPointerMove={(ev) => { if (pintando.current) onPintar(...aMundo(ev)); }}
        onPointerUp={() => { pintando.current = false; }}
        onPointerCancel={() => { pintando.current = false; }}
      />
      {etiqueta && (
        <div className="pointer-events-none absolute left-3 top-3 rounded-md border
                        border-linea bg-fondo/85 px-2.5 py-1 text-[11px] backdrop-blur">
          {etiqueta}
        </div>
      )}
    </div>
  );
}
