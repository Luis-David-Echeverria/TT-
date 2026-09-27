/* Dispersión 3D con ejes rotables, dibujada a mano sobre canvas.
 *
 * Por qué no una librería: para esto hacen falta una proyección ortográfica y
 * una caja de ejes, unas cien líneas. Meter plotly o three.js por eso agrega
 * megabytes al paquete y una dependencia que hay que mantener, para un solo
 * gráfico.
 *
 * Proyección ortográfica y no perspectiva: en perspectiva los puntos del fondo
 * salen más chicos y se leen como "menos importantes". Aquí los tres ejes son
 * magnitudes medidas y ninguna debe verse atenuada por estar atrás.
 */
import { useEffect, useRef, useState, useCallback } from "react";

const rad = (g) => (g * Math.PI) / 180;

/* ENCUADRES: poner la camara perpendicular a un plano.
 *
 * Girar con el raton sirve para entender la forma, pero para LEER valores
 * estorba: en cualquier angulo intermedio los tres ejes salen escorzados y no
 * se sabe donde cae un punto. Estos encuadres dejan dos ejes paralelos a la
 * pantalla y aplastan el tercero, con lo que la grafica queda como una 2D
 * corriente y los valores se leen directo.
 *
 * El isometrico es el unico que muestra las tres a la vez, y su elevacion no
 * es un angulo cualquiera: con atan(1/raiz(2)) = 35.264 grados los tres ejes
 * se proyectan del mismo largo. Sin eso, una magnitud parece mayor que otra
 * solo por el angulo de camara.
 */
const ENCUADRES = [
  { k: "xy", ejes: ["x", "y"], aplana: "z", az: 0, el: 90 },
  { k: "xz", ejes: ["x", "z"], aplana: "y", az: 0, el: 0 },
  { k: "yz", ejes: ["y", "z"], aplana: "x", az: -90, el: 0 },
  { k: "iso", ejes: null, aplana: null, az: -45, el: 35.264 },
];

export default function Grafica3D({
  series, ejes, alto = 380, azimutInicial = -38, elevacionInicial = 22,
  onPunto, resaltado,
}) {
  /* Los nombres de eje son largos ("f₁ acceso (m)"): los botones usan la
     version corta si se la pasan. */
  const corto = (e) => ejes.corto?.[e] ?? ejes[e];
  const ref = useRef(null);
  const [vista, setVista] = useState({ az: azimutInicial, el: elevacionInicial, z: 1 });
  const arrastre = useRef(null);
  const proyectados = useRef([]);

  const dibujar = useCallback(() => {
    const cv = ref.current;
    if (!cv || !series?.length) return;
    const caja = cv.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    cv.width = Math.max(1, Math.round(caja.width * dpr));
    cv.height = Math.max(1, Math.round(alto * dpr));
    const ctx = cv.getContext("2d");
    ctx.clearRect(0, 0, cv.width, cv.height);

    /* ---- rango de los datos ---- */
    const todos = series.flatMap((s) => s.puntos);
    if (!todos.length) return;
    const lim = {};
    for (const k of ["x", "y", "z"]) {
      const v = todos.map((p) => p[k]);
      let a = Math.min(...v), b = Math.max(...v);
      if (b - a < 1e-9) { a -= 0.5; b += 0.5; }
      lim[k] = [a, b];
    }
    const nor = (p) => ({
      x: (p.x - lim.x[0]) / (lim.x[1] - lim.x[0]) - 0.5,
      y: (p.y - lim.y[0]) / (lim.y[1] - lim.y[0]) - 0.5,
      z: (p.z - lim.z[0]) / (lim.z[1] - lim.z[0]) - 0.5,
    });

    /* ---- proyección ortográfica ---- */
    const ca = Math.cos(rad(vista.az)), sa = Math.sin(rad(vista.az));
    const ce = Math.cos(rad(vista.el)), se = Math.sin(rad(vista.el));
    const esc = Math.min(cv.width, cv.height) * 0.62 * vista.z;
    const cx = cv.width / 2, cy = cv.height / 2 + cv.height * 0.04;
    const proy = (p) => {
      const n = nor(p);
      const X = n.x * ca - n.y * sa;
      const Y = n.x * sa + n.y * ca;
      return { sx: cx + X * esc, sy: cy - (n.z * ce - Y * se) * esc,
               prof: Y * ce + n.z * se };
    };

    /* ---- caja de ejes ---- */
    const V = {};
    for (const i of [0, 1]) for (const j of [0, 1]) for (const k of [0, 1]) {
      V[`${i}${j}${k}`] = proy({ x: lim.x[i], y: lim.y[j], z: lim.z[k] });
    }
    const arista = (a, b, fuerte) => {
      ctx.strokeStyle = fuerte ? "rgba(140,155,175,.55)" : "rgba(90,102,120,.22)";
      ctx.lineWidth = (fuerte ? 1.1 : 0.9) * dpr;
      ctx.beginPath();
      ctx.moveTo(V[a].sx, V[a].sy);
      ctx.lineTo(V[b].sx, V[b].sy);
      ctx.stroke();
    };
    // suelo y verticales tenues
    for (const [a, b] of [["000", "100"], ["100", "110"], ["110", "010"],
                          ["010", "000"], ["001", "101"], ["101", "111"],
                          ["111", "011"], ["011", "001"], ["000", "001"],
                          ["100", "101"], ["110", "111"], ["010", "011"]]) {
      arista(a, b, false);
    }
    // los tres ejes que nacen del origen visual, marcados
    arista("000", "100", true);
    arista("000", "010", true);
    arista("000", "001", true);

    /* ---- marcas y rótulos ---- */
    ctx.font = `${10.5 * dpr}px ui-monospace, monospace`;
    ctx.fillStyle = "#7c8798";
    const rotulo = (p, txt, dx = 0, dy = 0, alin = "center") => {
      ctx.textAlign = alin;
      ctx.fillText(txt, p.sx + dx * dpr, p.sy + dy * dpr);
    };
    const fmt = (v) => (Math.abs(v) >= 1000 ? v.toFixed(0)
      : parseFloat(v.toFixed(Math.abs(v) < 10 ? 2 : 1)).toString());
    for (let t = 0; t <= 1; t += 0.5) {
      rotulo(proy({ x: lim.x[0] + t * (lim.x[1] - lim.x[0]), y: lim.y[0], z: lim.z[0] }),
             fmt(lim.x[0] + t * (lim.x[1] - lim.x[0])), 0, 14);
      rotulo(proy({ x: lim.x[0], y: lim.y[0] + t * (lim.y[1] - lim.y[0]), z: lim.z[0] }),
             fmt(lim.y[0] + t * (lim.y[1] - lim.y[0])), 10, 12, "left");
      rotulo(proy({ x: lim.x[0], y: lim.y[0], z: lim.z[0] + t * (lim.z[1] - lim.z[0]) }),
             fmt(lim.z[0] + t * (lim.z[1] - lim.z[0])), -8, 3, "right");
    }
    ctx.fillStyle = "#9fb0c6";
    ctx.font = `600 ${11 * dpr}px system-ui, sans-serif`;
    rotulo(proy({ x: (lim.x[0] + lim.x[1]) / 2, y: lim.y[0], z: lim.z[0] }),
           ejes.x, 0, 30);
    rotulo(proy({ x: lim.x[0], y: (lim.y[0] + lim.y[1]) / 2, z: lim.z[0] }),
           ejes.y, 16, 26, "left");
    rotulo(proy({ x: lim.x[0], y: lim.y[0], z: lim.z[1] }), ejes.z, -10, -10, "right");

    /* ---- series: primero las líneas, luego los puntos, de atrás a adelante ---- */
    const items = [];
    series.forEach((s, si) => {
      const pp = s.puntos.map((p) => ({ ...proy(p), dato: p, serie: si }));
      if (s.linea !== false && pp.length > 1) {
        ctx.strokeStyle = s.color + "88";
        ctx.lineWidth = 1.3 * dpr;
        ctx.beginPath();
        pp.forEach((q, i) => (i ? ctx.lineTo(q.sx, q.sy) : ctx.moveTo(q.sx, q.sy)));
        ctx.stroke();
      }
      pp.forEach((q) => items.push({ ...q, s }));
    });
    items.sort((a, b) => a.prof - b.prof);
    for (const q of items) {
      const r = (q.s.radio ?? 3) * dpr;
      ctx.beginPath();
      ctx.arc(q.sx, q.sy, r, 0, 6.2832);
      ctx.fillStyle = q.s.color;
      ctx.globalAlpha = q.s.opacidad ?? 0.95;
      ctx.fill();
      ctx.globalAlpha = 1;
      if (q.s.borde) {
        ctx.strokeStyle = q.s.borde;
        ctx.lineWidth = 1.4 * dpr;
        ctx.stroke();
      }
      if (resaltado !== undefined && q.dato.id === resaltado) {
        ctx.beginPath();
        ctx.arc(q.sx, q.sy, r + 4 * dpr, 0, 6.2832);
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2 * dpr;
        ctx.stroke();
      }
    }
    proyectados.current = items.map((q) => ({ sx: q.sx / dpr, sy: q.sy / dpr, dato: q.dato }));
  }, [series, ejes, alto, vista, resaltado]);

  useEffect(() => { dibujar(); }, [dibujar]);
  useEffect(() => {
    const f = () => dibujar();
    window.addEventListener("resize", f);
    const ro = new ResizeObserver(f);
    if (ref.current?.parentElement) ro.observe(ref.current.parentElement);
    return () => { window.removeEventListener("resize", f); ro.disconnect(); };
  }, [dibujar]);

  return (
    <div className="relative w-full" style={{ height: alto }}>
      <canvas
        ref={ref}
        className="h-full w-full cursor-grab active:cursor-grabbing"
        onPointerDown={(e) => {
          arrastre.current = { x: e.clientX, y: e.clientY, ...vista };
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          if (!arrastre.current) return;
          const a = arrastre.current;
          setVista((v) => ({
            ...v,
            az: a.az + (e.clientX - a.x) * 0.45,
            el: Math.max(-85, Math.min(85, a.el + (e.clientY - a.y) * 0.35)),
          }));
        }}
        onPointerUp={() => { arrastre.current = null; }}
        onDoubleClick={(e) => {
          // doble clic y no clic simple: con arrastre para girar, un clic suelto
          // se dispararia sin querer cada vez que se termina de girar
          if (!onPunto) return;
          const r = e.currentTarget.getBoundingClientRect();
          const mx = e.clientX - r.left, my = e.clientY - r.top;
          let mejor = null, dmin = 18;
          for (const p of proyectados.current) {
            const d = Math.hypot(p.sx - mx, p.sy - my);
            if (d < dmin) { dmin = d; mejor = p.dato; }
          }
          if (mejor) onPunto(mejor);
        }}
        onWheel={(e) => setVista((v) => ({
          ...v, z: Math.max(0.5, Math.min(2.4, v.z * (e.deltaY < 0 ? 1.1 : 0.9))),
        }))}
      />
      <div className="absolute left-2 top-2 flex flex-wrap items-center gap-1">
        <span className="mr-0.5 text-[10px] text-tenue">ver de lado:</span>
        {ENCUADRES.map((c) => (
          <button key={c.k}
            onClick={() => setVista((v) => ({ ...v, az: c.az, el: c.el }))}
            title={c.ejes
              ? `perpendicular al plano ${corto(c.ejes[0])}–${corto(c.ejes[1])}: aplasta ${corto(c.aplana)} y queda como una gráfica 2D`
              : "isométrica: los tres ejes proyectados del mismo largo"}
            className={`rounded border px-1.5 py-0.5 text-[10px] transition-colors ${
              Math.abs(vista.az - c.az) < 0.5 && Math.abs(vista.el - c.el) < 0.5
                ? "border-[#4C9BE8] bg-[#12243a] text-[#9ecbf5]"
                : "border-linea bg-panel2/85 text-tenue hover:border-[#3d4757]"}`}>
            {c.ejes ? `${corto(c.ejes[0])} · ${corto(c.ejes[1])}` : "isométrica"}
          </button>
        ))}
      </div>
      <div className="pointer-events-none absolute right-2 top-2 rounded border
                      border-linea bg-fondo/80 px-2 py-1 text-[10px] text-tenue backdrop-blur">
        arrastra para girar · rueda para acercar{onPunto ? " · doble clic en un punto" : ""}
      </div>
      <button
        onClick={() => setVista({ az: azimutInicial, el: elevacionInicial, z: 1 })}
        className="absolute bottom-2 right-2 rounded border border-linea bg-panel2
                   px-2 py-0.5 text-[10px] text-tenue hover:border-[#3d4757]">
        reencuadrar
      </button>
    </div>
  );
}
