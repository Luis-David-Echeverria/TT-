/* La zona ocupable, paso a paso.
 *
 * «Erosión morfológica» no le dice nada a nadie que no la haya estudiado, y
 * enseñar solo el resultado no explica de dónde sale. Aquí se ven los cuatro
 * pasos por separado, sobre el recinto real: se entiende sin saber el nombre
 * de la operación, y quien sí lo sabe reconoce la cadena.
 *
 * La idea que tiene que quedar: un hueco al que no se entra con el ancho de
 * reglamento NO es una infracción, es superficie que no se puede usar.
 */
import { useEffect, useState } from "react";
import { zonaLayout } from "../../motor";
import { num } from "../comun";

const PASOS = [
  { k: "libre", n: "1. piso libre",
    q: "Todo lo que no es muro ni módulo. Incluye recovecos donde nadie cabe." },
  { k: "erosionado", n: "2. se encoge por medio pasillo",
    q: "Se borra una franja del ancho de medio pasillo por toda la orilla. Lo que sobrevive es el esqueleto por el que SÍ se puede circular." },
  { k: "conectado", n: "3. solo lo que llega a una salida",
    q: "De ese esqueleto se conserva la parte conectada a alguna salida. Un patio cerrado se cae aquí, sin ninguna regla especial." },
  { k: "ocupable", n: "4. se vuelve a inflar",
    q: "Se devuelve la franja que se había quitado. El resultado es el piso que de verdad se puede usar." },
];

const COLOR = { libre: [70, 92, 122], erosionado: [90, 140, 200],
                conectado: [60, 170, 140], ocupable: [110, 200, 130] };

/* El catalogo no se usa aqui: la zona ocupable la calcula el worker, que ya
   lo tiene cargado. Se deja fuera para no fingir una dependencia. */
export default function DemoErosion({ recinto, layout }) {
  const [z, setZ] = useState(null);
  const [paso, setPaso] = useState(3);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!layout || !recinto) return;
    setZ(null);
    zonaLayout(layout).then(setZ).catch((e) => setErr(e.message));
  }, [layout, recinto]);

  if (!z) {
    return (
      <div className="my-3 grid h-[220px] place-items-center rounded-lg border
                      border-linea bg-panel text-[11.5px] text-tenue">
        {err || "calculando la zona ocupable…"}
      </div>
    );
  }

  const { nx, ny } = z;
  const act = z[PASOS[paso].k];
  const col = COLOR[PASOS[paso].k];
  const cuenta = (m) => { let n = 0; for (let i = 0; i < m.length; i++) if (m[i]) n++; return n; };
  const nLibre = cuenta(z.libre), nOc = cuenta(z.ocupable);
  const perdido = nLibre - nOc;

  // el mapa se dibuja como SVG de rectángulos por corrida: nítido y sin canvas
  const franjas = [];
  for (let y = 0; y < ny; y++) {
    let x = 0;
    while (x < nx) {
      if (!act[y * nx + x]) { x++; continue; }
      const x0 = x;
      while (x < nx && act[y * nx + x]) x++;
      franjas.push(<rect key={`${y}-${x0}`} x={x0} y={ny - 1 - y} width={x - x0} height={1}
                         fill={`rgb(${col[0]},${col[1]},${col[2]})`} />);
    }
  }
  const muros = [];
  for (let y = 0; y < ny; y++) {
    let x = 0;
    while (x < nx) {
      if (!z.muros[y * nx + x]) { x++; continue; }
      const x0 = x;
      while (x < nx && z.muros[y * nx + x]) x++;
      muros.push(<rect key={`m${y}-${x0}`} x={x0} y={ny - 1 - y} width={x - x0} height={1}
                       fill="#39414f" />);
    }
  }
  const sal = [];
  for (let i = 0; i < z.salidas.length; i++)
    if (z.salidas[i]) sal.push(<rect key={`s${i}`} x={i % nx} y={ny - 1 - ((i / nx) | 0)}
                                     width={1} height={1} fill="#2bff88" />);

  return (
    <div className="my-3 rounded-lg border border-linea bg-panel p-3">
      <div className="mb-2 flex flex-wrap gap-1">
        {PASOS.map((s, i) => (
          <button key={s.k} onClick={() => setPaso(i)}
            className={`rounded border px-2 py-1 text-[11px] transition-colors ${
              paso === i ? "border-[#4C9BE8] bg-[#12243a] text-[#9ecbf5]"
                : "border-linea bg-panel2 text-tenue hover:border-[#3d4757]"}`}>
            {s.n}
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded border border-linea bg-[#05070f]">
        <svg viewBox={`0 0 ${nx} ${ny}`} className="w-full" style={{ display: "block" }}
             shapeRendering="crispEdges">
          {franjas}{muros}{sal}
        </svg>
      </div>

      <p className="mt-2 text-[11.5px] leading-relaxed text-tenue">
        <b className="text-texto">{PASOS[paso].n.replace(/^\d+\.\s*/, "")}.</b>{" "}
        {PASOS[paso].q}
      </p>

      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[11px]">
        <span className="text-tenue">piso libre{" "}
          <b className="font-mono text-texto">{num(nLibre, 0)}</b> m²</span>
        <span className="text-tenue">zona ocupable{" "}
          <b className="font-mono text-texto">{num(nOc, 0)}</b> m²</span>
        <span className="text-tenue">no se puede usar{" "}
          <b className="font-mono text-ambar">{num(perdido, 0)}</b> m²
          {" "}({num(100 * perdido / Math.max(nLibre, 1), 1)} %)</span>
        <span className="ml-auto text-tenue">se encoge{" "}
          <b className="font-mono text-texto">{z.radio}</b> celda{z.radio > 1 ? "s" : ""}
          {" "}= medio pasillo</span>
      </div>

      <p className="mt-2 border-t border-linea pt-2 text-[11px] leading-relaxed text-tenue">
        Esos <b className="text-ambar">{num(perdido, 0)} m²</b> que se pierden entre
        el paso 1 y el 4 son recovecos a los que no se entra con el ancho de
        reglamento. <b className="text-texto">No se cuentan como infracción, se
        cuentan como superficie inservible</b> — y esa distinción no es cosmética:
        la primera versión los trataba como violación de seguridad y rechazaba el
        87 % de las colocaciones. Al reformularlo así, la aceptación subió al 88 %
        sin relajar ningún criterio.
      </p>
    </div>
  );
}
