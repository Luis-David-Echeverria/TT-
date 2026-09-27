import { useState, useEffect, useRef, useMemo } from "react";
import {
  Play, Pause, Shuffle, Eraser, Loader2, AlertTriangle, CheckCircle2,
  Layers, Users, Ruler, Zap, DoorOpen, Trash2, Repeat, Dices, Copy, FlaskConical,
  Boxes, Database,
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { api, correrTrabajo, construirLUT, ESTATICO } from "./api";
import Mapa from "./Mapa";
import Resultados from "./Resultados";

const RECINTO = {
  W: 100, H: 60,
  salidas: [
    { nombre: "S1", lado: "S", centro: 20, ancho: 8 },
    { nombre: "S2", lado: "S", centro: 70, ancho: 8 },
    { nombre: "O1", lado: "O", centro: 30, ancho: 6 },
    { nombre: "E1", lado: "E", centro: 35, ancho: 6 },
  ],
  muros: [{ x: 46, y: 24, w: 4, h: 4 }, { x: 0, y: 50, w: 22, h: 3 }],
};

/* ------------------------------------------------------------- primitivas UI */
const Seccion = ({ icono: I, titulo, children }) => (
  <section className="border-b border-linea px-4 py-3.5">
    <h2 className="mb-3 flex items-center gap-1.5 text-[10px] font-semibold
                   uppercase tracking-[.09em] text-tenue">
      {I && <I size={12} strokeWidth={2.2} />} {titulo}
    </h2>
    {children}
  </section>
);

const Rango = ({ etiqueta, valor, onChange, min, max, step, sufijo = "", disabled }) => (
  <div className="mb-2.5">
    <div className="mb-1 flex items-baseline justify-between">
      <span className="text-[11.5px] text-tenue">{etiqueta}</span>
      <span className="font-mono text-[11.5px] tabular-nums">
        {typeof valor === "number" ? valor.toLocaleString("es-MX") : valor}{sufijo}
      </span>
    </div>
    <input type="range" className="w-full" min={min} max={max} step={step}
           value={valor} disabled={disabled}
           onChange={(e) => onChange(+e.target.value)} />
  </div>
);

const Boton = ({ children, onClick, disabled, variante = "normal", icono: I }) => {
  const base = "flex flex-1 items-center justify-center gap-1.5 rounded-md border " +
               "px-3 py-2 text-[12px] transition disabled:cursor-not-allowed " +
               "disabled:opacity-40";
  const v = {
    normal: "border-linea bg-panel2 hover:border-[#3d4757] hover:bg-[#1c2230]",
    pri: "border-ambar bg-ambar font-semibold text-[#1a1205] hover:bg-[#eab36d]",
  }[variante];
  return (
    <button className={`${base} ${v}`} onClick={onClick} disabled={disabled}>
      {I && <I size={13} strokeWidth={2.2} />}{children}
    </button>
  );
};

const Chip = ({ etiqueta, valor, tono = "" }) => (
  <div className={`rounded-md border bg-fondo/85 px-2.5 py-1 text-[11px] backdrop-blur
                   ${tono === "ok" ? "border-[#2a5348] text-verde"
                     : tono === "mal" ? "border-[#5e2a27] text-[#f0a09b]"
                     : "border-linea"}`}>
    {etiqueta && <span className="text-tenue">{etiqueta} </span>}
    <b className="font-semibold tabular-nums">{valor}</b>
  </div>
);

/* ------------------------------------------------------------------- la app */
export default function App() {
  const [cat, setCat] = useState(null);
  const [recinto, setRecinto] = useState(RECINTO);
  const [conteo, setConteo] = useState({ SAN: 3, COM: 3, BEB: 2, MED: 1 });
  const [layout, setLayout] = useState([]);
  const [esc, setEsc] = useState({ aforo: 6000, escala: 18, uniforme: false });
  const [malla, setMalla] = useState(1);
  const [alg, setAlg] = useState({ semilla: 42, generaciones: 10, mu: 4, lam: 12 });
  const [copiado, setCopiado] = useState(false);
  const [capas, setCapas] = useState({ flechas: true, isocronas: true,
                                       conos: true, rejilla: true, suavizar: false });
  const [pintar, setPintar] = useState(false);
  const [modoSalida, setModoSalida] = useState(false);
  const [vista, setVista] = useState("densidad");
  const [pestana, setPestana] = useState("simulador");

  const [geo, setGeo] = useState(null);
  const [aforo, setAforo] = useState(null);
  const [campo, setCampo] = useState(null);
  const [comp, setComp] = useState(null);
  const [cuadro, setCuadro] = useState(0);
  const [reproduciendo, setReproduciendo] = useState(false);
  const [velocidad, setVelocidad] = useState(1);
  const [ocupado, setOcupado] = useState(false);
  const [msg, setMsg] = useState({ t: "Cargando…", c: "" });

  const temp = useRef(null);
  const lut = useMemo(() => (cat ? construirLUT(cat.paleta_densidad) : null), [cat]);

  useEffect(() => {
    api("/api/catalogo").then(setCat)
      .catch((e) => setMsg({ t: "No se pudo contactar la API: " + e.message, c: "err" }));
  }, []);

  /* El usuario define recinto, muros y salidas. Las áreas de servicio NO se
     ven hasta comparar: es el sistema quien decide dónde van. */

  useEffect(() => {
    if (!cat) return;
    clearTimeout(temp.current);
    temp.current = setTimeout(async () => {
      try {
        const [g, a] = await Promise.all([
          api("/api/geometria", { recinto, layout }),
          api("/api/aforo", { recinto, layout: [], conteo }),
        ]);
        setGeo(g); setAforo(a);
        setCampo(await api("/api/campo",
          { recinto, layout, numerica: { h: malla }, n_isocronas: 14 }));
      } catch (e) { setMsg({ t: "Error: " + e.message, c: "err" }); }
    }, 130);
  }, [cat, recinto, layout, conteo, malla]);

  useEffect(() => { setComp(null); setLayout([]); setReproduciendo(false); },
            [malla, esc.aforo, esc.escala, esc.uniforme, conteo, recinto, alg]);

  /* reproducción en bucle, velocidad ajustable */
  useEffect(() => {
    if (!reproduciendo || !comp) return;
    const n = comp.inicial.sim.cuadros_b64.length;
    let raf, previo = performance.now(), acum = 0;
    const tic = (ahora) => {
      acum += ((ahora - previo) / 1000) * 12 * velocidad;   // 12 cuadros/s a 1×
      previo = ahora;
      if (acum >= 1) {
        const saltos = Math.floor(acum);
        acum -= saltos;
        setCuadro((c) => (c + saltos) % n);                 // en bucle
      }
      raf = requestAnimationFrame(tic);
    };
    raf = requestAnimationFrame(tic);
    return () => cancelAnimationFrame(raf);
  }, [reproduciendo, velocidad, comp]);

  async function comparar() {
    const total = Object.values(conteo).reduce((a, b) => a + b, 0);
    if (!total) { setMsg({ t: "Elige cuántas áreas de servicio quieres.", c: "err" }); return; }
    setOcupado(true); setComp(null); setCuadro(0); setReproduciendo(false);
    setMsg({ t: "Simulando el acomodo inicial…", c: "ocupado" });
    try {
      const t = await correrTrabajo({
        tipo: "comparacion", recinto, layout: [], conteo,
        semilla: alg.semilla,
        escenario: {
          aforo: esc.aforo,
          distribucion: esc.uniforme ? { tipo: "uniforme" }
                                     : { tipo: "concentrada", escala: esc.escala },
        },
        numerica: { h: malla, n_cuadros: 60 },
        opciones: { generaciones: alg.generaciones, mu: alg.mu, lam: alg.lam },
      }, (x) => setMsg({ t: x.mensaje || x.estado, c: "ocupado" }));

      if (t.estado === "error") { setMsg({ t: t.mensaje, c: "err" }); return; }
      const r = t.resultado;
      setComp(r); setCuadro(0); setVista("densidad"); setReproduciendo(true);
      setLayout(r.inicial.layout);
      const a = r.inicial.sim.t95, b = r.optimizado.sim.t95;
      setMsg({
        t: `Listo — ${Math.round(a)} s → ${Math.round(b)} s (${((a - b) / a * 100).toFixed(1)} %) · ` +
           `semilla ${r.config.semilla} · ${r.evaluaciones} evaluaciones en ` +
           `${r.trabajadores} procesos.`,
        c: "ok",
      });
    } catch (e) { setMsg({ t: "Error: " + e.message, c: "err" }); }
    finally { setOcupado(false); }
  }

  /* ------------------------------------------------------- salidas y muros */
  const colocarSalida = (lado, pos) => {
    const largo = lado === "S" || lado === "N" ? recinto.W : recinto.H;
    const ancho = 8;
    const centro = Math.max(ancho / 2 + 1,
                            Math.min(largo - ancho / 2 - 1, Math.round(pos)));
    const nombre = lado + (recinto.salidas.filter((s) => s.lado === lado).length + 1);
    setRecinto((R) => ({ ...R, salidas: [...R.salidas, { nombre, lado, centro, ancho }] }));
    setComp(null);
    setMsg({ t: `Salida ${nombre} colocada en el lado ${lado}.`, c: "" });
  };

  const editarSalida = (i, campo, valor) => {
    setRecinto((R) => ({ ...R, salidas: R.salidas.map((s, k) =>
      (k === i ? { ...s, [campo]: valor } : s)) }));
    setComp(null);
  };

  const quitarSalida = (i) => {
    setRecinto((R) => ({ ...R, salidas: R.salidas.filter((_, k) => k !== i) }));
    setComp(null);
  };

  const pintarMuro = (x, y) => {
    const px = Math.floor(x), py = Math.floor(y);
    if (px < 0 || py < 0 || px >= recinto.W || py >= recinto.H) return;
    setRecinto((R) => (R.muros.some((m) => m.x === px && m.y === py)
      ? R : { ...R, muros: [...R.muros, { x: px, y: py, w: 1, h: 1 }] }));
    setComp(null);
  };

  if (!cat) return <div className="grid h-full place-items-center text-tenue">{msg.t}</div>;

  const nMax = comp ? comp.inicial.sim.cuadros_b64.length - 1 : 0;
  const curva = comp ? comp.inicial.sim.t.map((t, i) => ({
    t: Math.round(t),
    inicial: comp.inicial.sim.pct[i],
    optimizado: comp.optimizado.sim.pct[i] ?? null,
  })) : [];
  const conv = comp ? comp.historia.map((v, i) => ({ g: i, t95: v })) : [];
  const capTotal = recinto.salidas.reduce((a, s) => a + Math.max(0, s.ancho - 0.3), 0);

  const paneles = comp
    ? [{ k: "inicial", tit: "Acomodo inicial (aleatorio)", d: comp.inicial, col: "text-ambar" },
       { k: "optimizado", tit: "Acomodo optimizado", d: comp.optimizado, col: "text-verde" }]
    : [{ k: "unico", tit: "Recinto — dibuja muros y salidas, luego compara",
         d: { layout: [], sim: null } }];

  if (ESTATICO) {
    return (
      <div className="h-full overflow-hidden">
        <Resultados catalogo={cat} lut={lut} />
      </div>
    );
  }

  const barra = (
    <div className="flex shrink-0 items-center gap-1 border-b border-linea bg-fondo px-3 py-1.5">
      {[["simulador", "Simulador", Boxes], ["resultados", "Resultados", Database]]
        .map(([k, t, I]) => (
        <button key={k} onClick={() => setPestana(k)}
          className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px]
                      transition-colors ${pestana === k
            ? "bg-panel2 text-texto" : "text-tenue hover:text-texto"}`}>
          <I size={13} /> {t}
        </button>
      ))}
    </div>
  );

  if (pestana === "resultados")
    return (
      <div className="flex h-full flex-col overflow-hidden">
        {barra}
        <div className="min-h-0 flex-1 overflow-hidden">
          <Resultados catalogo={cat} lut={lut} />
        </div>
      </div>
    );

  return (
    <div className="flex h-full flex-col overflow-hidden">
    {barra}
    <div className="grid min-h-0 flex-1 grid-cols-[318px_1fr] overflow-hidden">

      <aside className="overflow-y-auto border-r border-linea bg-panel">
        <div className="border-b border-linea px-4 py-4">
          <h1 className="text-[15px] font-semibold tracking-tight">
            Distribución de áreas de servicio
          </h1>
          <p className="mt-1 text-[11.5px] leading-snug text-tenue">
            Dibuja muros, coloca salidas y elige cuántas áreas de cada tipo. El
            sistema las acomoda y compara ese acomodo contra el optimizado.
          </p>
        </div>

        <Seccion icono={Layers} titulo="Áreas de servicio">
          {cat.areas.map((a) => (
            <div key={a.clave} className="mb-2 flex items-center gap-2.5">
              <span className="h-3 w-3 shrink-0 rounded-sm" style={{ background: a.color }} />
              <span className="flex-1 truncate text-[11.5px]">{a.nombre}</span>
              <span className="font-mono text-[10px] text-tenue">{a.ancho}×{a.fondo}</span>
              <input type="number" min={0} max={12} value={conteo[a.clave] ?? 0}
                     className="w-14 text-center"
                     onChange={(e) => setConteo({ ...conteo,
                       [a.clave]: Math.max(0, Math.min(12, +e.target.value || 0)) })} />
            </div>
          ))}
          {comp && (
            <div className="mt-3"><Boton onClick={() => { setComp(null); setLayout([]);
                                   setReproduciendo(false); }} icono={Shuffle}>
              Volver al recinto vacío
            </Boton></div>
          )}
          <p className="mt-2 text-[10.5px] leading-snug text-tenue">
            Las áreas no se ven hasta comparar: el sistema decide dónde van, por
            muestreo con rechazo contra la capa geométrica. Nunca las coloca en
            zonas a las que no se pueda llegar.
          </p>
        </Seccion>

        <Seccion icono={DoorOpen} titulo="Salidas">
          {recinto.salidas.map((sa, i) => (
            <div key={i} className="mb-2 rounded-md border border-linea bg-panel2 p-2">
              <div className="mb-1.5 flex items-center gap-2">
                <span className="h-2.5 w-2.5 shrink-0 rounded-sm bg-[#2bff88]" />
                <span className="flex-1 text-[11.5px] font-medium">{sa.nombre}</span>
                <span className="font-mono text-[10px] text-tenue">
                  {(sa.ancho - 0.3).toFixed(1)} m útiles
                </span>
                <button onClick={() => quitarSalida(i)}
                        className="text-tenue transition hover:text-[#e2564f]">
                  <Trash2 size={13} />
                </button>
              </div>
              <div className="flex items-end gap-2">
                <select className="w-14 shrink-0" value={sa.lado}
                        onChange={(e) => editarSalida(i, "lado", e.target.value)}>
                  {["N", "S", "E", "O"].map((l) => <option key={l} value={l}>{l}</option>)}
                </select>
                <div className="min-w-0 flex-1">
                  <div className="flex justify-between text-[10px] text-tenue">
                    <span>posición</span><span>{sa.centro} m</span>
                  </div>
                  <input type="range" className="w-full" min={5}
                         max={(sa.lado === "S" || sa.lado === "N" ? recinto.W : recinto.H) - 5}
                         value={sa.centro}
                         onChange={(e) => editarSalida(i, "centro", +e.target.value)} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex justify-between text-[10px] text-tenue">
                    <span>ancho</span><span>{sa.ancho} m</span>
                  </div>
                  <input type="range" className="w-full" min={2} max={20} step={1}
                         value={sa.ancho}
                         onChange={(e) => editarSalida(i, "ancho", +e.target.value)} />
                </div>
              </div>
            </div>
          ))}
          <label className="mb-2 flex cursor-pointer items-center gap-2 text-[12px] text-tenue">
            <input type="checkbox" checked={modoSalida}
                   onChange={(e) => { setModoSalida(e.target.checked); setPintar(false); }} />
            colocar salida con un clic en el borde
          </label>
          <p className="text-[10.5px] leading-snug text-tenue">
            Cada puerta drena a razón de <b className="text-tinta">J_s × ancho útil</b>,
            descontando la franja pegada a cada jamba que la gente no usa. Capacidad
            total ≈ <b className="text-tinta">
              {(capTotal * cat.q_max).toFixed(1)} pers/s</b>.
          </p>
        </Seccion>

        <Seccion icono={Ruler} titulo="Muros fijos">
          <label className="mb-2 flex cursor-pointer items-center gap-2 text-[12px] text-tenue">
            <input type="checkbox" checked={pintar}
                   onChange={(e) => { setPintar(e.target.checked); setModoSalida(false); }} />
            pintar muros (clic y arrastra)
          </label>
          <Boton onClick={() => { setRecinto({ ...recinto, muros: [] }); setComp(null); }}
                 icono={Eraser}>Limpiar muros</Boton>
        </Seccion>

        <Seccion icono={Users} titulo="Escenario">
          <Rango etiqueta="aforo" valor={esc.aforo} min={1000} max={25000} step={500}
                 onChange={(v) => setEsc({ ...esc, aforo: v })} />
          <label className="mb-2 flex cursor-pointer items-center gap-2 text-[12px] text-tenue">
            <input type="checkbox" checked={esc.uniforme}
                   onChange={(e) => setEsc({ ...esc, uniforme: e.target.checked })} />
            repartir uniforme
          </label>
          <Rango etiqueta="concentración" valor={esc.escala} min={6} max={60} step={2}
                 sufijo=" m" disabled={esc.uniforme}
                 onChange={(v) => setEsc({ ...esc, escala: v })} />
          {esc.uniforme && (
            <p className="rounded-md border border-[#4a3612] bg-[#241a08] px-2.5 py-2
                          text-[10.5px] leading-snug text-ambar">
              Con reparto uniforme el layout casi no afecta el tiempo: las puertas
              saturan y siempre hay una salida cerca. No es el peor caso, es el que
              menos discrimina.
            </p>
          )}
        </Seccion>

        <Seccion icono={Zap} titulo="Correr">
          <div className="mb-2.5">
            <span className="mb-1 block text-[11.5px] text-tenue">malla</span>
            <select value={malla} onChange={(e) => setMalla(+e.target.value)}>
              <option value={1}>1.0 m — convergida</option>
              <option value={1.5}>1.5 m — intermedia</option>
              <option value={2}>2.0 m — rápida (no converge)</option>
            </select>
          </div>
          {malla > 1 && (
            <p className="mb-2.5 rounded-md border border-[#4a3612] bg-[#241a08] px-2.5 py-2
                          text-[10.5px] leading-snug text-ambar">
              A 2 m el error de discretización es del tamaño de la diferencia entre
              layouts: el orden entre ellos no se conserva.
            </p>
          )}
          <div className="mb-2.5">
            <div className="mb-1 flex items-baseline justify-between">
              <span className="text-[11.5px] text-tenue">semilla</span>
              <span className="text-[10px] text-tenue">misma semilla = mismo resultado</span>
            </div>
            <div className="flex gap-1.5">
              <input type="number" min={0} step={1} value={alg.semilla}
                     onChange={(e) => setAlg({ ...alg, semilla: Math.max(0, +e.target.value || 0) })} />
              <button title="semilla al azar"
                      onClick={() => setAlg({ ...alg, semilla: Math.floor(Math.random() * 1e6) })}
                      className="shrink-0 rounded-md border border-linea bg-panel2 px-2.5
                                 transition hover:border-[#3d4757]">
                <Dices size={14} />
              </button>
            </div>
          </div>
          <Rango etiqueta="generaciones" valor={alg.generaciones} min={1} max={60} step={1}
                 onChange={(v) => setAlg({ ...alg, generaciones: v })} />
          <Rango etiqueta="población (μ)" valor={alg.mu} min={1} max={30} step={1}
                 onChange={(v) => setAlg({ ...alg, mu: v })} />
          <Rango etiqueta="descendencia (λ)" valor={alg.lam} min={1} max={60} step={1}
                 onChange={(v) => setAlg({ ...alg, lam: v })} />
          <p className="mb-2.5 text-[10.5px] leading-snug text-tenue">
            Evaluaciones ≈ <b className="text-tinta">
              {alg.mu + alg.generaciones * alg.lam}</b>. λ por debajo del número de
            procesos deja núcleos ociosos.
          </p>
          <Boton variante="pri" onClick={comparar} disabled={ocupado || !geo?.factible}
                 icono={ocupado ? Loader2 : Play}>Comparar acomodos</Boton>
        </Seccion>

        <Seccion titulo="Vista">
          <select className="mb-2" value={vista} onChange={(e) => setVista(e.target.value)}>
            <option value="densidad">densidad de multitud</option>
            <option value="tiempos">campo de tiempos a salidas</option>
          </select>
          {[["flechas", "flechas de destino (−∇T)"],
            ["isocronas", "isócronas"], ["conos", "áreas de descarga"],
            ["rejilla", "rejilla métrica (1 m / 10 m)"],
            ["suavizar", "suavizar (solo para presentar)"]].map(([k, t]) => (
            <label key={k} className="mb-1.5 flex cursor-pointer items-center gap-2
                                      text-[12px] text-tenue">
              <input type="checkbox" checked={capas[k]}
                     onChange={(e) => setCapas({ ...capas, [k]: e.target.checked })} />
              {t}
            </label>
          ))}
          <div className="mt-3 rounded-md border border-linea bg-panel2 p-2">
            <div className="mb-1 text-[10px] uppercase tracking-wider text-tenue">
              densidad [pers/m²]
            </div>
            <div className="h-2.5 rounded-sm" style={{ background:
              `linear-gradient(90deg,${cat.paleta_densidad
                .map((s) => `${s.c} ${(s.t * 100).toFixed(1)}%`).join(",")})` }} />
            <div className="mt-1 flex justify-between font-mono text-[9.5px] text-tenue">
              <span>0</span>
              <span className="text-[#e2564f]">{cat.rho_perdida_control}</span>
              <span className="text-[#781414]">{cat.rho_max}</span>
            </div>
            <div className="mt-1 text-[9.5px] leading-snug text-tenue">
              rojo = pérdida de control individual · rojo oscuro = atasco (v = 0)
              <br />cada cuadro del mapa = <b className="text-tinta">1 m²</b>
            </div>
          </div>
        </Seccion>

        {comp?.config && (
          <Seccion icono={FlaskConical} titulo="Reproducibilidad">
            <div className="rounded-md border border-linea bg-panel2 p-2">
              <table className="w-full text-[10.5px]">
                <tbody>
                  {Object.entries(comp.config).map(([k, v]) => (
                    <tr key={k}>
                      <td className="py-[1px] pr-2 text-tenue">{k}</td>
                      <td className="py-[1px] text-right font-mono tabular-nums">
                        {v === null ? "—" : typeof v === "object"
                          ? Object.entries(v).map(([a, b]) => `${a}:${b}`).join(" ")
                          : String(v)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-2">
              <Boton icono={Copy} onClick={() => {
                navigator.clipboard.writeText(JSON.stringify(comp.config, null, 2));
                setCopiado(true); setTimeout(() => setCopiado(false), 1600);
              }}>{copiado ? "copiado" : "Copiar configuración"}</Boton>
            </div>
            <p className="mt-2 text-[10.5px] leading-snug text-tenue">
              Con estos valores el resultado se reproduce idéntico. De la semilla
              se derivan dos flujos independientes: el del acomodo inicial y el
              del optimizador.
            </p>
          </Seccion>
        )}

        <div className="px-4 py-3 text-[10.5px] text-tenue">
          <a href="/docs" target="_blank" rel="noreferrer"
             className="text-[#6cb0f0] hover:underline">API /docs</a>
          {cat.pendientes.length > 0 && (
            <span className="ml-1 text-ambar">
              · {cat.pendientes.length} parámetros sin fuente verificada
            </span>)}
        </div>
      </aside>

      <main className="flex min-w-0 flex-col overflow-hidden">
        <div className="flex shrink-0 flex-wrap gap-2 border-b border-linea bg-panel px-4 py-2.5">
          {geo && (geo.factible
            ? <Chip valor="capa geométrica: factible" tono="ok" />
            : <Chip tono="mal" valor={"INFACTIBLE · " + geo.pasos
                .filter((p) => p.violacion > 0).map((p) => p.nombre).join(" · ")} />)}
          {aforo && <>
            <Chip etiqueta="aforo" valor={Math.round(aforo.aforo).toLocaleString("es-MX")} />
            <Chip etiqueta="área ocupable" valor={Math.round(aforo.area_ocupable) + " m²"} />
            <Chip etiqueta="cota puertas" valor={Math.round(aforo.cota_puertas_s) + " s"} />
            {aforo.area_aislada > 1 &&
              <Chip etiqueta="aislada" tono="mal"
                    valor={Math.round(aforo.area_aislada) + " m²"} />}
          </>}
        </div>

        <div className={`grid min-h-0 flex-1 gap-px bg-linea
                         ${comp ? "grid-cols-2" : "grid-cols-1"}`}>
          {paneles.map(({ k, tit, d, col }) => (
            <div key={k} className="relative min-w-0 bg-lienzo">
              <Mapa catalogo={cat} recinto={recinto} layout={d.layout} geo={geo}
                    campo={campo} sim={d.sim} cuadro={cuadro} vista={vista}
                    verFlechas={capas.flechas} verIsocronas={capas.isocronas}
                    verConos={capas.conos} verRejilla={capas.rejilla}
                    suavizar={capas.suavizar} modoPintar={pintar && !comp}
                    modoSalida={modoSalida && !comp} lut={lut}
                    onPintar={pintarMuro} onColocarSalida={colocarSalida}
                    etiqueta={tit && (
                      <span className="flex items-center gap-2">
                        {tit}
                        {d.sim?.t95 && <b className={col}>t95 {Math.round(d.sim.t95)} s</b>}
                      </span>)} />
            </div>
          ))}
        </div>

        {comp && (
          <div className="shrink-0 border-t border-linea bg-panel px-4 py-3">
            <div className="mb-3 flex items-center gap-3">
              <button onClick={() => setReproduciendo((v) => !v)}
                      className="flex shrink-0 items-center gap-1.5 rounded-md border
                                 border-linea bg-panel2 px-2.5 py-1.5 text-[11.5px]
                                 transition hover:border-[#3d4757]">
                {reproduciendo ? <Pause size={13} /> : <Play size={13} />}
                {reproduciendo ? "Pausa" : "Reproducir"}
              </button>
              <div className="flex shrink-0 items-center gap-1.5 text-[11px] text-tenue">
                <Repeat size={12} />
                <input type="range" className="w-20" min={0.25} max={6} step={0.25}
                       value={velocidad} onChange={(e) => setVelocidad(+e.target.value)} />
                <span className="w-9 font-mono tabular-nums">{velocidad}×</span>
              </div>
              <input type="range" className="min-w-0 flex-1" min={0} max={nMax} value={cuadro}
                     onChange={(e) => { setReproduciendo(false); setCuadro(+e.target.value); }} />
              <span className="w-52 shrink-0 text-right font-mono text-[11.5px]
                               tabular-nums text-tenue">
                t = {Math.round(comp.inicial.sim.t[cuadro] ?? 0)} s ·{" "}
                <b className="text-ambar">{(comp.inicial.sim.pct[cuadro] ?? 0).toFixed(1)}%</b>
                {" vs "}
                <b className="text-verde">{(comp.optimizado.sim.pct[cuadro] ?? 0).toFixed(1)}%</b>
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Grafica titulo="evacuados [%]" datos={curva}>
                <Line type="monotone" dataKey="inicial" stroke="#e0a458" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="optimizado" stroke="#5dcaa5" dot={false} strokeWidth={2} />
                <ReferenceLine y={95} stroke="#ffffff40" strokeDasharray="4 4" />
              </Grafica>
              <Grafica titulo="convergencia — mejor t95 [s]" datos={conv} x="g">
                <Line type="monotone" dataKey="t95" stroke="#5dcaa5" strokeWidth={2}
                      dot={{ r: 2.5, fill: "#5dcaa5" }} />
              </Grafica>
            </div>
          </div>
        )}

        <div className={`flex shrink-0 items-center gap-2 border-t border-linea bg-panel2
                         px-4 py-2.5 text-[11.5px]
                         ${msg.c === "err" ? "text-[#f0a09b]"
                           : msg.c === "ok" ? "text-verde"
                           : msg.c === "ocupado" ? "text-ambar" : "text-tenue"}`}>
          {msg.c === "ocupado" && <Loader2 size={13} className="giro shrink-0" />}
          {msg.c === "err" && <AlertTriangle size={13} className="shrink-0" />}
          {msg.c === "ok" && <CheckCircle2 size={13} className="shrink-0" />}
          {msg.t}
        </div>
      </main>
    </div>
    </div>
  );
}

function Grafica({ titulo, datos, x = "t", children }) {
  return (
    <div>
      <div className="mb-1 text-[10px] uppercase tracking-wider text-tenue">{titulo}</div>
      <div className="h-[108px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={datos} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="#ffffff12" />
            <XAxis dataKey={x} tick={{ fill: "#8a93a3", fontSize: 10 }} stroke="#232b39" />
            <YAxis tick={{ fill: "#8a93a3", fontSize: 10 }} stroke="#232b39" />
            <Tooltip contentStyle={{ background: "#11151e", border: "1px solid #232b39",
                                     borderRadius: 6, fontSize: 11 }}
                     labelStyle={{ color: "#8a93a3" }} />
            {children}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
