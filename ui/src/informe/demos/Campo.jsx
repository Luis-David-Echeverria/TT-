/* El campo de la ecuación Eikonal, dibujado.
 *
 * «‖∇T‖ = 1/v» no le dice nada a nadie que no la haya visto antes. Pintada, la
 * misma ecuación se explica sola: cada punto lleva escrito cuánto falta para
 * salir, y las curvas de nivel son los frentes que van llegando. Quien sepa la
 * ecuación la reconoce; quien no, entiende el mapa igual.
 */
import { useEffect, useRef, useState } from "react";
import { campoLayout } from "../../motor";
import { colorTiempo } from "../../api";
import { num } from "../comun";

/** Pinta un campo escalar celda por celda, sin suavizar: la unidad del modelo
 *  es el metro cuadrado y suavizarla la esconde. */
function Lienzo({ d, isocronas, alto = 250 }) {
  const ref = useRef(null);
  useEffect(() => {
    const cv = ref.current;
    if (!cv || !d) return;
    const { nx, ny } = d;
    const dpr = window.devicePixelRatio || 1;
    const anc = cv.parentElement.getBoundingClientRect().width;
    const esc = Math.min(anc / nx, alto / ny);
    cv.width = Math.round(nx * esc * dpr);
    cv.height = Math.round(ny * esc * dpr);
    cv.style.width = `${nx * esc}px`;
    cv.style.height = `${ny * esc}px`;
    const ctx = cv.getContext("2d");

    const off = document.createElement("canvas");
    off.width = nx; off.height = ny;
    const img = off.getContext("2d").createImageData(nx, ny);
    for (let i = 0; i < nx * ny; i++) {
      const j = (ny - 1 - ((i / nx) | 0)) * nx + (i % nx);   // y hacia arriba
      const k = i * 4;
      let c;
      if (d.muros[j]) c = [44, 51, 62];
      else if (d.salidas[j]) c = [43, 255, 136];
      else if (!d.libre[j]) c = [74, 36, 21];
      else if (d.campo[j] === 255) c = [74, 31, 31];          // sin ruta
      else c = colorTiempo(d.campo[j]);
      img.data[k] = c[0]; img.data[k + 1] = c[1]; img.data[k + 2] = c[2];
      img.data[k + 3] = 255;
    }
    off.getContext("2d").putImageData(img, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(off, 0, 0, cv.width, cv.height);

    if (isocronas) {
      const paso = 255 / 14;
      ctx.strokeStyle = "rgba(255,255,255,.30)";
      ctx.lineWidth = Math.max(1, esc * dpr * 0.09);
      ctx.beginPath();
      for (let y = 0; y < ny; y++)
        for (let x = 0; x < nx; x++) {
          const i = y * nx + x;
          if (!d.libre[i] || d.campo[i] === 255) continue;
          const a = (d.campo[i] / paso) | 0;
          const Y = (ny - 1 - y) * esc * dpr;
          if (x + 1 < nx && d.libre[i + 1] && d.campo[i + 1] !== 255 &&
              ((d.campo[i + 1] / paso) | 0) !== a) {
            ctx.moveTo((x + 1) * esc * dpr, Y);
            ctx.lineTo((x + 1) * esc * dpr, Y + esc * dpr);
          }
          if (y + 1 < ny && d.libre[i + nx] && d.campo[i + nx] !== 255 &&
              ((d.campo[i + nx] / paso) | 0) !== a) {
            ctx.moveTo(x * esc * dpr, Y);
            ctx.lineTo((x + 1) * esc * dpr, Y);
          }
        }
      ctx.stroke();
    }

    // las semillas: de donde arranca el campo con valor cero
    ctx.fillStyle = "rgba(245,192,112,.95)";
    for (let i = 0; i < nx * ny; i++) {
      if (!d.semillas[i]) continue;
      const x = i % nx, y = (i / nx) | 0;
      ctx.fillRect(x * esc * dpr + esc * dpr * 0.2,
                   (ny - 1 - y) * esc * dpr + esc * dpr * 0.2,
                   esc * dpr * 0.6, esc * dpr * 0.6);
    }
  }, [d, isocronas, alto]);
  return <canvas ref={ref} className="mx-auto block" />;
}

/* -------------------------------------------- campo de salida (§5.1) */
export function DemoCampoSalidas({ recinto, layout }) {
  const [d, setD] = useState(null);
  const [iso, setIso] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!layout || !recinto) return;
    setD(null);
    campoLayout(layout, "salidas").then(setD).catch((e) => setErr(e.message));
  }, [layout, recinto]);

  return (
    <div className="my-3 rounded-lg border border-linea bg-panel p-3">
      <div className="mb-2 flex items-center gap-3 text-[11.5px]">
        <label className="flex items-center gap-1.5 text-tenue">
          <input type="checkbox" checked={iso} onChange={(e) => setIso(e.target.checked)} />
          curvas de nivel
        </label>
        {d && (
          <span className="ml-auto font-mono text-[11px] text-tenue">
            el punto más lejano está a {num(d.tmax, 1)} m de una salida
          </span>
        )}
      </div>
      <div className="overflow-hidden rounded border border-linea bg-[#05070f] p-1">
        {d ? <Lienzo d={d} isocronas={iso} />
           : <div className="grid h-[250px] place-items-center text-[11.5px] text-tenue">
               {err || "resolviendo el campo…"}</div>}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[10.5px] text-tenue">
        <span><b className="text-[#2bff88]">■</b> salidas</span>
        <span><b style={{ color: "rgb(16,26,54)" }}>■</b> cerca de salir</span>
        <span><b style={{ color: "rgb(240,222,112)" }}>■</b> lejos</span>
        <span><b style={{ color: "#4a2415" }}>■</b> módulo de servicio</span>
      </div>
      <p className="mt-2 text-[11.5px] leading-relaxed text-tenue">
        <b className="text-texto">Cada punto lleva escrito cuánto falta para
        salir.</b> El color es esa cuenta: oscuro cerca de una salida, claro
        lejos. Las curvas de nivel unen los puntos que están a la misma
        distancia — son los frentes que se van alejando de cada puerta, y donde
        dos se tocan está la divisoria entre salidas.
      </p>
      <p className="mt-1.5 text-[11.5px] leading-relaxed text-tenue">
        Fíjate en que el campo <b className="text-texto">rodea</b> los módulos en
        vez de atravesarlos: eso es lo que hace la ecuación, y es la diferencia
        con medir en línea recta. La dirección en que camina la gente es
        simplemente hacia donde este número baja más rápido.
      </p>
    </div>
  );
}

/* ------------------------------ desde dónde se mide un módulo (§6.2) */
export function DemoSemillas({ recinto, layout, catalogo }) {
  const [d, setD] = useState(null);
  const [mod, setMod] = useState(0);
  const [modo, setModo] = useState("geo");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!layout || !recinto) return;
    setD(null);
    campoLayout(layout, { modulo: mod }).then(setD).catch((e) => setErr(e.message));
  }, [layout, recinto, mod]);

  /* La alternativa que se descartó: línea recta desde el centro del módulo.
     Se calcula aquí mismo porque es trivial — y porque enseñarla al lado es lo
     que deja claro por qué no sirve. */
  const dEuclid = (() => {
    if (!d || !layout?.[mod] || !catalogo) return null;
    const t = catalogo.areas.find((a) => a.clave === layout[mod].tipo);
    if (!t) return null;
    const [w, f] = layout[mod].rot === 0 ? [t.ancho, t.fondo] : [t.fondo, t.ancho];
    const cx = layout[mod].x + w / 2, cy = layout[mod].y + f / 2;
    const { nx, ny, h } = d;
    const campo = new Uint8Array(nx * ny).fill(255);
    let mx = 0;
    const dd = new Float64Array(nx * ny);
    for (let i = 0; i < nx * ny; i++) {
      if (!d.libre[i]) continue;
      const x = (i % nx + 0.5) * h, y = (((i / nx) | 0) + 0.5) * h;
      dd[i] = Math.hypot(x - cx, y - cy);
      if (dd[i] > mx) mx = dd[i];
    }
    for (let i = 0; i < nx * ny; i++)
      if (d.libre[i]) campo[i] = Math.min(254, (dd[i] / (mx || 1)) * 254) | 0;
    return { ...d, campo, tmax: mx, semillas: new Uint8Array(nx * ny) };
  })();

  const act = modo === "geo" ? d : dEuclid;
  const mods = (layout || []).map((c, i) => ({ i, tipo: c.tipo }));

  return (
    <div className="my-3 rounded-lg border border-linea bg-panel p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <div className="flex rounded-md border border-linea bg-panel2 p-0.5">
          {[["geo", "caminando, desde su borde"], ["euc", "en línea recta, desde su centro"]]
            .map(([k, t]) => (
            <button key={k} onClick={() => setModo(k)}
              className={`rounded px-2.5 py-1 text-[11px] transition-colors ${
                modo === k ? "bg-[#12243a] text-[#9ecbf5]" : "text-tenue hover:text-texto"}`}>
              {t}
            </button>
          ))}
        </div>
        <span className="text-[11px] text-tenue">módulo</span>
        <select value={mod} onChange={(e) => setMod(+e.target.value)}
          className="rounded border border-linea bg-panel2 px-1.5 py-0.5 text-[11px]">
          {mods.map((m) => (
            <option key={m.i} value={m.i}>#{m.i} · {m.tipo}</option>
          ))}
        </select>
        {act && (
          <span className="ml-auto font-mono text-[11px] text-tenue">
            más lejano: {num(act.tmax, 1)} m
          </span>
        )}
      </div>

      <div className="overflow-hidden rounded border border-linea bg-[#05070f] p-1">
        {act ? <Lienzo d={act} isocronas />
             : <div className="grid h-[250px] place-items-center text-[11.5px] text-tenue">
                 {err || "resolviendo el campo…"}</div>}
      </div>

      <p className="mt-2 text-[11.5px] leading-relaxed text-tenue">
        {modo === "geo" ? (
          <>
            Los cuadritos naranjas son las <b className="text-texto">semillas</b>:
            las celdas libres pegadas al módulo, desde donde el campo arranca en
            cero. Es ahí donde la gente llega —{" "}
            <b className="text-texto">a la barra, no al centro del puesto</b> — y
            el campo rodea el módulo en vez de atravesarlo.
          </>
        ) : (
          <>
            <b className="text-texto">Esto es lo que se descartó.</b> Los círculos
            salen del centro del módulo y atraviesan tanto el propio módulo como
            los muros: dice que un sanitario está a 20 m cuando, rodeando, está a
            60. Y no se puede arreglar midiendo geodésicamente desde el centro,
            porque <b className="text-texto">el centro cae dentro de un obstáculo</b>
            {" "}y el campo no tiene por dónde salir.
          </>
        )}
      </p>
      {modo === "geo" && d && dEuclid && (
        <p className="mt-1.5 text-[11px] text-tenue">
          El punto más lejano queda a <span className="font-mono">{num(d.tmax, 1)}</span> m
          caminando contra <span className="font-mono">{num(dEuclid.tmax, 1)}</span> m en
          línea recta. Cambia arriba para ver la diferencia.
        </p>
      )}
    </div>
  );
}
