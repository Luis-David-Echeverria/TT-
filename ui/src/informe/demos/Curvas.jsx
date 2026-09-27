/* Demostraciones interactivas del diagrama fundamental.
 *
 * El informe tiene que servirle a dos lectores a la vez: al asesor, que quiere
 * la ecuación y la fuente, y a alguien del equipo que nunca ha oído la palabra
 * Eikonal. Una curva que se puede mover con el dedo explica en tres segundos lo
 * que un párrafo no logra — y no sustituye a la ecuación, va al lado.
 *
 * Las curvas se calculan aquí con la MISMA física del modelo (crearFisica), no
 * con valores dibujados a mano: si mañana cambia un parámetro, la ilustración
 * cambia con él en vez de quedarse mintiendo.
 */
import { useMemo, useState } from "react";
import { crearFisica } from "../../modelo/fluido";
import { num } from "../comun";

const AN = 680, AL = 240, MI = 52, MD = 14, MS = 18, MB = 42;

function Ejes({ xmax, etiquetaX, children }) {
  return (
    <svg viewBox={`0 0 ${AN} ${AL}`} className="w-full">
      <line x1={MI} y1={AL - MB} x2={AN - MD} y2={AL - MB} stroke="#2b3444" />
      <line x1={MI} y1={MS} x2={MI} y2={AL - MB} stroke="#2b3444" />
      {children}
      <text x={MI} y={AL - MB + 16} fill="#7c8798" fontSize="10.5"
            textAnchor="middle" fontFamily="system-ui">0</text>
      <text x={AN - MD} y={AL - MB + 16} fill="#7c8798" fontSize="10.5"
            textAnchor="middle" fontFamily="system-ui">{xmax}</text>
      <text x={(MI + AN - MD) / 2} y={AL - 8} fill="#7c8798" fontSize="11"
            textAnchor="middle" fontFamily="system-ui">{etiquetaX}</text>
    </svg>
  );
}

/* ---------------------------------------------------------- Weidmann */
export function DemoWeidmann({ P }) {
  const fis = useMemo(() => (P?.v0 ? crearFisica(P) : null), [P]);
  const [rho, setRho] = useState(1.75);
  if (!fis) return null;
  const { rho_max } = P;
  const X = (r) => MI + (r / rho_max) * (AN - MD - MI);
  const YV = (v) => AL - MB - (v / P.v0) * (AL - MB - MS);
  const YQ = (q) => AL - MB - (q / fis.qMax) * (AL - MB - MS);

  let dv = "", dq = "";
  for (let r = 0.02; r <= rho_max; r += 0.02) {
    dv += `${dv ? "L" : "M"}${X(r).toFixed(1)} ${YV(fis.vel(r)).toFixed(1)}`;
    dq += `${dq ? "L" : "M"}${X(r).toFixed(1)} ${YQ(r * fis.vel(r)).toFixed(1)}`;
  }
  const v = fis.vel(rho), q = rho * v;

  return (
    <div className="my-3 rounded-lg border border-linea bg-panel p-3">
      <div className="mb-2 flex flex-wrap items-center gap-3 text-[11.5px]">
        <label className="flex items-center gap-2 text-tenue">
          qué tan apretada va la gente
          <input type="range" min={0.05} max={rho_max} step={0.05} value={rho}
                 onChange={(e) => setRho(+e.target.value)} className="w-32" />
        </label>
        <span className="font-mono">{num(rho, 2)} pers/m²</span>
        <span className="ml-auto font-mono text-[#6ea8d8]">v = {num(v, 2)} m/s</span>
        <span className="font-mono text-ambar">q = {num(q, 2)} pers/(m·s)</span>
      </div>

      <Ejes xmax={rho_max} etiquetaX="densidad (pers/m²) — gente por metro cuadrado">
        <line x1={X(fis.rhoCap)} y1={MS} x2={X(fis.rhoCap)} y2={AL - MB}
              stroke="#4a5563" strokeDasharray="3 4" />
        <path d={dv} fill="none" stroke="#6ea8d8" strokeWidth="2" />
        <path d={dq} fill="none" stroke="#e0a458" strokeWidth="2" />
        <line x1={X(rho)} y1={MS} x2={X(rho)} y2={AL - MB} stroke="#e8e3d9" opacity=".7" />
        <circle cx={X(rho)} cy={YV(v)} r="4.5" fill="#6ea8d8" />
        <circle cx={X(rho)} cy={YQ(q)} r="4.5" fill="#e0a458" />
        <text x={MI + 10} y={MS + 10} fill="#6ea8d8" fontSize="11" fontFamily="system-ui">
          velocidad v(ρ)
        </text>
        <text x={MI + 108} y={MS + 10} fill="#e0a458" fontSize="11" fontFamily="system-ui">
          flujo q(ρ) = ρ·v(ρ)
        </text>
        <text x={X(fis.rhoCap) + 5} y={AL - MB - 6} fill="#7c8798" fontSize="10"
              fontFamily="system-ui">ρ que da más flujo</text>
      </Ejes>

      <p className="mt-1 text-[11.5px] leading-relaxed text-tenue">
        <b className="text-texto">Más gente no significa más flujo.</b> A la
        izquierda de la línea punteada, meter más gente hace pasar más gente. A
        la derecha, la congestión destruye capacidad: van tan apretados que casi
        no avanzan. Por eso un embudo no solo frena a quien lo cruza —{" "}
        <b className="text-texto">reduce cuánta gente pasa en total</b>. Es el
        único dato empírico del modelo, y de él sale todo lo demás: el flujo
        máximo <span className="font-mono">{num(fis.qMax, 3)}</span> pers/(m·s) y
        la densidad que lo produce <span className="font-mono">{num(fis.rhoCap, 3)}</span>{" "}
        pers/m² no se ponen a mano, se derivan de esta curva.
      </p>
    </div>
  );
}

/* --------------------------------------------------- oferta y demanda */
export function DemoOfertaDemanda({ P }) {
  const fis = useMemo(() => (P?.v0 ? crearFisica(P) : null), [P]);
  if (!fis) return null;
  const { rho_max } = P;
  const X = (r) => MI + (r / rho_max) * (AN - MD - MI);
  const Y = (q) => AL - MB - (q / fis.qMax) * (AL - MB - MS);

  let dd = "", ds = "";
  for (let r = 0.02; r <= rho_max; r += 0.02) {
    const q = r * fis.vel(r);
    dd += `${dd ? "L" : "M"}${X(r).toFixed(1)} ${Y(r <= fis.rhoCap ? q : fis.qMax).toFixed(1)}`;
    ds += `${ds ? "L" : "M"}${X(r).toFixed(1)} ${Y(r >= fis.rhoCap ? q : fis.qMax).toFixed(1)}`;
  }

  return (
    <div className="my-3 rounded-lg border border-linea bg-panel p-3">
      <Ejes xmax={rho_max} etiquetaX="densidad de la celda (pers/m²)">
        <line x1={X(fis.rhoCap)} y1={MS} x2={X(fis.rhoCap)} y2={AL - MB}
              stroke="#4a5563" strokeDasharray="3 4" />
        <path d={dd} fill="none" stroke="#e2564f" strokeWidth="2" />
        <path d={ds} fill="none" stroke="#5dcaa5" strokeWidth="2" />
        <text x={MI + 10} y={MS + 10} fill="#e2564f" fontSize="11" fontFamily="system-ui">
          lo que quiere MANDAR — demanda D(ρ)
        </text>
        <text x={MI + 10} y={MS + 26} fill="#5dcaa5" fontSize="11" fontFamily="system-ui">
          lo que puede RECIBIR — oferta S(ρ)
        </text>
      </Ejes>
      <p className="mt-1 text-[11.5px] leading-relaxed text-tenue">
        Entre dos celdas pasa <b className="text-texto">lo menor de las dos</b>.
        Fíjate en lo que hace la curva roja pasada la línea: <b className="text-texto">
        no cae a cero</b>. Una celda atascada sigue queriendo descargar a tope —
        la gente apretujada avanza si el de adelante se movió. Lo que cae es la
        verde: la de adelante deja de aceptar. <b className="text-texto">La cola
        se forma por el que recibe, no por el que empuja</b>, que es como ocurre
        de verdad.
      </p>
      <p className="mt-1.5 text-[11px] leading-relaxed text-tenue">
        Si en vez de esto se usara ρ·v(ρ) para lo que manda, una celda llena
        tendría velocidad cero, dejaría de entregar masa y{" "}
        <b className="text-texto">se congelaría para siempre</b>, con un moteado
        de tablero de ajedrez alrededor. No es un detalle de implementación: sin
        esta separación el modelo converge a la solución equivocada.
      </p>
    </div>
  );
}
