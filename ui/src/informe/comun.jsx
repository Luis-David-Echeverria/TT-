/* Piezas compartidas del informe: formato, ecuaciones y estructura.
 *
 * Viven aparte porque el informe creció a varias secciones y tenerlas en un
 * solo archivo hacía imposible tocar una sin releer todo.
 */
import katex from "katex";
import "katex/dist/katex.min.css";

/* Tres decimales como máximo y sin ceros de relleno: 24.100 -> "24.1".
 * Por encima de mil los decimales son ruido, así que se separan los miles. */
export function num(v, dec = 3) {
  if (v === null || v === undefined || !isFinite(v)) return "—";
  if (Math.abs(v) >= 1000)
    return v.toLocaleString("es-MX", { maximumFractionDigits: 0 });
  return parseFloat(v.toFixed(dec)).toLocaleString("es-MX",
    { maximumFractionDigits: dec });
}

export const pct = (v, dec = 1) => (v === null || v === undefined || !isFinite(v)
  ? "—" : `${parseFloat((100 * v).toFixed(dec))} %`);

function tex(t, display) {
  try {
    return katex.renderToString(t, { displayMode: display, throwOnError: false });
  } catch { return t; }
}

/** Ecuación en bloque. */
export const Ec = ({ t }) => (
  <div className="my-3 overflow-x-auto rounded-md border border-linea bg-[#0b0f18] px-4 py-3"
       dangerouslySetInnerHTML={{ __html: tex(t, true) }} />
);

/** Ecuación dentro del texto. */
export const Ei = ({ t }) => <span dangerouslySetInnerHTML={{ __html: tex(t, false) }} />;

export const Sec = ({ n, titulo, children }) => (
  <section>
    <h2 className="mb-2 mt-8 border-b border-linea pb-1.5 text-[15px] font-semibold tracking-tight">
      <span className="mr-2 text-tenue">{n}</span>{titulo}
    </h2>
    {children}
  </section>
);

export const Sub = ({ children }) => (
  <h3 className="mb-1 mt-4 text-[12.5px] font-semibold">{children}</h3>
);

export const P = ({ children }) => (
  <p className="my-2 text-[12.5px] leading-relaxed text-[#c3ccda]">{children}</p>
);

export const Nota = ({ children, tono = "info" }) => (
  <div className={`my-3 rounded-md border-l-2 px-3 py-2 text-[12px] leading-relaxed ${
    tono === "alerta" ? "border-ambar bg-ambar/5 text-[#e3c08a]"
    : tono === "clave" ? "border-[#4C9BE8] bg-[#4C9BE8]/5 text-[#a9cdf0]"
    : "border-linea bg-panel2 text-tenue"}`}>{children}</div>
);

export const Tarjeta = ({ titulo, extra, children }) => (
  <div className="my-3 rounded-lg border border-linea bg-panel">
    <div className="flex items-center gap-2 border-b border-linea px-3 py-1.5">
      <span className="text-[11.5px] font-semibold">{titulo}</span>
      {extra && <span className="ml-auto text-[11px] text-tenue">{extra}</span>}
    </div>
    <div className="p-3">{children}</div>
  </div>
);

/** Tabla simple: encabezados y filas ya formateadas. */
export const Tabla = ({ cols, filas, alinear = [] }) => (
  <div className="my-3 overflow-x-auto rounded-lg border border-linea bg-panel">
    <table className="w-full text-[11.5px]">
      <thead className="text-tenue">
        <tr className="border-b border-linea">
          {cols.map((c, i) => (
            <th key={i} className={`px-3 py-1.5 font-normal ${
              alinear[i] === "d" ? "text-right" : "text-left"}`}>{c}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {filas.map((f, i) => (
          <tr key={i} className="border-b border-linea/40 align-top">
            {f.map((c, j) => (
              <td key={j} className={`px-3 py-1.5 ${
                alinear[j] === "d" ? "text-right font-mono" : ""}`}>{c}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

/** Etiqueta de origen de una restricción. Distinguirlas importa: se defienden
 *  distinto, y presentar un criterio de diseño como si fuera norma es el error
 *  más fácil de señalar en una revisión. */
export const Origen = ({ tipo }) => {
  const m = {
    legal: ["#e2564f", "legal"],
    consistencia: ["#4C9BE8", "consistencia"],
    diseno: ["#9d8df1", "diseño"],
  }[tipo];
  return (
    <span className="rounded px-1.5 py-px text-[10px] font-semibold"
          style={{ background: m[0] + "22", color: m[0] }}>{m[1]}</span>
  );
};

export const ESTADOS = {
  medido: ["#2bff88", "valor empírico publicado — se cita"],
  derivado: ["#7bc96f", "se calcula de otros — sin cita propia"],
  normativo: ["#4C9BE8", "lo fija un reglamento — se cita artículo"],
  catalogo: ["#9d8df1", "equipo comercial — ficha de proveedor"],
  numerico: ["#e0a458", "discretización — análisis de convergencia"],
  calibrar: ["#e0a458", "modelado — análisis de sensibilidad"],
  PENDIENTE: ["#e2564f", "sin fuente verificada — BLOQUEA la tesis"],
};

export function colorRho(r) {
  if (r === null || r === undefined) return "transparent";
  const t = Math.min(1, Math.abs(r));
  return r < 0 ? `rgba(226,86,79,${0.12 + 0.68 * t})`
               : `rgba(76,155,232,${0.12 + 0.68 * t})`;
}

/* =========================================================================
 * VARIABLES CON SIGNIFICADO A LA MANO
 *
 * Un informe lleno de ρ, γ y k_c es ilegible para quien no lo escribió. Pero
 * quitar la notación tampoco sirve: el asesor la necesita. La salida es que
 * cada símbolo lleve su significado encima, a un cursor de distancia, y que se
 * NOTE que se puede consultar — un símbolo subrayado con puntitos invita a
 * pasar el cursor; uno normal no.
 *
 * El valor y la procedencia NO se escriben aquí: se leen del registro de
 * parámetros de Python a través del contexto. Así no pueden desviarse.
 * ========================================================================= */
import { createContext, useContext } from "react";
import { GLOSARIO } from "./glosario";

const CtxGlosario = createContext(null);

export const ProveedorGlosario = ({ catalogo, children }) => {
  const reg = {};
  for (const p of catalogo?.parametros || []) reg[p.clave] = p;
  return <CtxGlosario.Provider value={reg}>{children}</CtxGlosario.Provider>;
};

/** Datos completos de un símbolo: notación + valor y procedencia del registro. */
export function useSimbolo(k) {
  const reg = useContext(CtxGlosario) || {};
  const g = GLOSARIO[k];
  if (!g) return null;
  const p = g.clave ? reg[g.clave] : null;
  return { ...g, k, valor: p?.valor, estado: p?.estado, fuente: p?.fuente };
}

/** Variable dentro del texto: se resalta y al pasar el cursor dice qué es. */
export const V = ({ k }) => {
  const s = useSimbolo(k);
  if (!s) return <Ei t={k} />;
  return (
    <span className="group relative inline-block cursor-help">
      <span className="border-b border-dotted border-[#7c8798] text-[#9ecbf5]">
        <Ei t={s.tex} />
      </span>
      <span className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-1.5
                       w-64 -translate-x-1/2 rounded-md border border-linea bg-[#0d111a]
                       px-3 py-2 text-[11px] leading-snug opacity-0 shadow-xl
                       transition-opacity group-hover:opacity-100">
        <span className="block font-semibold text-texto">{s.nombre}</span>
        <span className="mt-0.5 block text-tenue">{s.que}</span>
        <span className="mt-1.5 block border-t border-linea pt-1 font-mono text-[10.5px]">
          {s.valor !== undefined && (
            <span className="text-[#9ecbf5]">
              {typeof s.valor === "number" ? num(s.valor) : String(s.valor)}{" "}
            </span>
          )}
          <span className="text-tenue">{s.unidad}</span>
          {s.estado && (
            <span className="ml-1.5 rounded px-1 py-px text-[9.5px]"
                  style={{ background: (ESTADOS[s.estado]?.[0] || "#666") + "22",
                           color: ESTADOS[s.estado]?.[0] || "#999" }}>
              {s.estado}
            </span>
          )}
        </span>
      </span>
    </span>
  );
};

/** Lista de símbolos bajo una ecuación: qué es cada letra que acaba de salir. */
export const Simbolos = ({ ks }) => {
  const reg = useContext(CtxGlosario) || {};
  const filas = ks.map((k) => {
    const g = GLOSARIO[k];
    if (!g) return null;
    const p = g.clave ? reg[g.clave] : null;
    return { ...g, k, valor: p?.valor, estado: p?.estado, fuente: p?.fuente };
  }).filter(Boolean);

  return (
    <table className="my-2 w-full text-[11.5px]">
      <tbody>
        {filas.map((s) => (
          <tr key={s.k} className="border-b border-linea/40 align-top">
            <td className="w-[70px] py-1 pr-2 text-[#9ecbf5]"><Ei t={s.tex} /></td>
            <td className="w-[30%] py-1 pr-3">{s.nombre}</td>
            <td className="py-1 pr-3 text-tenue">{s.que}</td>
            <td className="w-[140px] py-1 text-right font-mono text-[10.5px]">
              {s.valor !== undefined && (
                <span className="text-texto">
                  {typeof s.valor === "number" ? num(s.valor) : String(s.valor)}{" "}
                </span>
              )}
              <span className="text-tenue">{s.unidad}</span>
              {s.estado && (
                <span className="ml-1 rounded px-1 py-px text-[9.5px]"
                      style={{ background: (ESTADOS[s.estado]?.[0] || "#666") + "22",
                               color: ESTADOS[s.estado]?.[0] || "#999" }}>
                  {s.estado}
                </span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};
