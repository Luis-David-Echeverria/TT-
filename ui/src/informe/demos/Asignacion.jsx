/* Qué hace la capacidad en f₁, visto en el mapa.
 *
 * Es el concepto que más cuesta explicar con palabras y el que se entiende
 * solo al verlo: sin capacidad, las fronteras entre módulos son el Voronoi
 * geodésico — cada quien al más cercano — y un módulo puede quedar recibiendo
 * el triple de lo que atiende. Con capacidad, las fronteras SE DESPLAZAN hasta
 * que nadie se satura, y la distancia media sube. Ese aumento no es un defecto:
 * es lo que cuesta repartir la carga de forma que se pueda cumplir.
 */
import { useEffect, useState } from "react";
import Mapa from "../../Mapa";
import { accesoLayout } from "../../motor";
import { num, pct } from "../comun";

const SIN_CAPACIDAD = 0.001;   // σ chico => capacidades enormes => nadie satura

export default function DemoAsignacion({ catalogo, lut, recinto, layout }) {
  const [conCap, setConCap] = useState(null);
  const [sinCap, setSinCap] = useState(null);
  const [modo, setModo] = useState("cap");
  const [tipo, setTipo] = useState("SAN");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!layout || !recinto) return;
    setConCap(null); setSinCap(null);
    accesoLayout(layout).then(setConCap).catch((e) => setErr(e.message));
    accesoLayout(layout, SIN_CAPACIDAD).then(setSinCap).catch(() => {});
  }, [layout, recinto]);

  const act = modo === "cap" ? conCap : sinCap;
  const otro = modo === "cap" ? sinCap : conCap;
  const d = act?.tipos?.[tipo];
  const satura = sinCap?.tipos?.[tipo]
    ? Math.max(...sinCap.tipos[tipo].carga.map((c, i) => c / sinCap.tipos[tipo].capacidad[i] / SIN_CAPACIDAD))
    : 0;

  return (
    <div className="my-3 rounded-lg border border-linea bg-panel p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <div className="flex rounded-md border border-linea bg-panel2 p-0.5">
          {[["cap", "con capacidad"], ["near", "al más cercano"]].map(([k, t]) => (
            <button key={k} onClick={() => setModo(k)}
              className={`rounded px-2.5 py-1 text-[11px] transition-colors ${
                modo === k ? "bg-[#12243a] text-[#9ecbf5]" : "text-tenue hover:text-texto"}`}>
              {t}
            </button>
          ))}
        </div>
        <span className="text-[11px] text-tenue">tipo</span>
        {(catalogo?.areas || []).map((a) => (
          <button key={a.clave} onClick={() => setTipo(a.clave)}
            disabled={!act?.tipos?.[a.clave]}
            className={`rounded border px-1.5 py-0.5 text-[10.5px] disabled:opacity-30 ${
              tipo === a.clave ? "border-[#4C9BE8] text-[#9ecbf5]"
                : "border-linea text-tenue hover:border-[#3d4757]"}`}>
            <span className="mr-1 inline-block h-2 w-2 rounded-sm align-middle"
                  style={{ background: a.color }} />
            {a.clave}
          </button>
        ))}
        {act && (
          <span className="ml-auto font-mono text-[11px]">
            distancia media {num(d?.d_media)} m
          </span>
        )}
      </div>

      <div className="h-[250px] overflow-hidden rounded border border-linea">
        {act ? (
          <Mapa catalogo={catalogo} recinto={recinto} layout={layout}
                vista="acceso" acceso={act} tipoAcceso={tipo} lut={lut}
                etiqueta={modo === "cap" ? "reparto que respeta la capacidad"
                                         : "cada quien al más cercano"} />
        ) : (
          <div className="grid h-full place-items-center text-[11.5px] text-tenue">
            {err || "calculando el reparto…"}
          </div>
        )}
      </div>

      {d && (
        <table className="mt-2 w-full text-[11px]">
          <thead className="text-tenue">
            <tr className="border-b border-linea">
              <th className="py-1 text-left font-normal">módulo</th>
              <th className="py-1 text-right font-normal">le toca</th>
              <th className="py-1 text-right font-normal">puede atender</th>
              <th className="py-1 pl-3 text-left font-normal"></th>
            </tr>
          </thead>
          <tbody>
            {d.modulos.map((m, i) => {
              const cap = modo === "cap" ? d.capacidad[i] : d.capacidad[i] * SIN_CAPACIDAD;
              const uso = d.carga[i] / cap;
              return (
                <tr key={i} className="border-b border-linea/30">
                  <td className="py-1">#{m}</td>
                  <td className="py-1 text-right font-mono">{pct(d.carga[i])}</td>
                  <td className="py-1 text-right font-mono text-tenue">{pct(cap)}</td>
                  <td className="py-1 pl-3">
                    <span className={`font-mono text-[10.5px] ${
                      uso > 1.02 ? "text-rojo" : "text-verde"}`}>
                      {uso > 1.02 ? `${num(uso, 1)}× de lo que puede` : "dentro de su capacidad"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <p className="mt-2 text-[11.5px] leading-relaxed text-tenue">
        {modo === "near" ? (
          <>
            <b className="text-texto">Estas son las zonas del módulo más cercano</b>
            {satura > 1.05 && (
              <> — y uno de ellos recibe <b className="text-rojo">
              {num(satura, 1)} veces</b> lo que puede atender</>)}
            . La distancia media sale más baja, pero es una cuenta imposible: ese
            módulo tendría una cola que no baja nunca. Cambia arriba para ver el
            reparto que sí se puede cumplir.
          </>
        ) : (
          <>
            <b className="text-texto">Las fronteras ya no son las del más cercano.</b>{" "}
            Un módulo saturado le cede celdas a su vecino aunque quede más lejos, y
            por eso la distancia media sube
            {otro && <> de <span className="font-mono">{num(otro.tipos?.[tipo]?.d_media)}</span> a{" "}
            <span className="font-mono">{num(d?.d_media)}</span> m</>}.{" "}
            <b className="text-texto">Ese aumento es el costo real de repartir la
            carga</b>, y es justo lo que una fórmula de «distancia al más cercano»
            esconde.
          </>
        )}
      </p>
    </div>
  );
}
