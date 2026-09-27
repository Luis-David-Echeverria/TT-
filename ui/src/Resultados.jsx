/* REPORTE DEL EXPERIMENTO.
 *
 * Esta pestaña no es un tablero: es un documento que el equipo debe poder leer
 * de arriba abajo y salir sabiendo qué se hizo, con qué ecuaciones, qué
 * significa cada símbolo y cómo se lee cada gráfica. Los datos están embebidos
 * en el punto del texto donde se explican, no amontonados al final.
 *
 * Igual que el resto de la interfaz, aquí NO se calcula nada del modelo. Las
 * correlaciones, los intervalos, los frentes y la tabla de parámetros vienen
 * del backend. Si la interfaz tuviera su propia copia del modelo, las dos
 * podrían desviarse y la visualización dejaría de ser evidencia.
 */
import { useEffect, useMemo, useState } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";
import {
  Database, Play, Pause, Loader2, AlertTriangle, BookOpen, Route, Users,
} from "lucide-react";

import Mapa from "./Mapa";
import { num, pct, Ec, Ei, Sec, P, Nota, Tarjeta, ESTADOS, colorRho,
         ProveedorGlosario, Simbolos, V } from "./informe/comun";
import { SecProblema, SecPreparacion, SecRestricciones } from "./informe/Metodo";
import { DemoWeidmann, DemoOfertaDemanda } from "./informe/demos/Curvas";
import DemoAsignacion from "./informe/demos/Asignacion";
import { DemoCampoSalidas, DemoSemillas } from "./informe/demos/Campo";
import Grafica3D from "./Grafica3D";
import { api, variantesColor } from "./api";
import { iniciarMotor, simularLayout, accesoLayout, parametrosDe } from "./motor";

/* ========================================================================= */
/* Una simulación llega del motor local (cuadros) o del backend
 * (cuadros_b64). Cualquier lectura del número de cuadros tiene que
 * aceptar las dos formas. */
const nCuadros = (sim) => (sim?.cuadros ?? sim?.cuadros_b64)?.length ?? 0;

export default function Resultados({ catalogo, lut }) {
  const [escenarios, setEscenarios] = useState(null);
  const [sel, setSel] = useState(null);
  const [nube, setNube] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [metricaY, setMetricaY] = useState("t_des");
  const [soloFactibles, setSoloFactibles] = useState(false);

  const [llaveSel, setLlaveSel] = useState(null);
  const [detalle, setDetalle] = useState(null);
  const [sim, setSim] = useState(null);
  const [cuadro, setCuadro] = useState(0);
  const [reproduciendo, setReproduciendo] = useState(false);
  const [velocidad, setVelocidad] = useState(1);
  const [simulando, setSimulando] = useState(false);
  const [verTodos, setVerTodos] = useState(false);
  const [err, setErr] = useState("");
  const [frente, setFrente] = useState(null);
  const [pesos, setPesos] = useState(null);
  const [directo, setDirecto] = useState(null);   // layout abierto sin llave
  const [capa, setCapa] = useState("f2");        // que se dibuja sobre el layout
  const [tipoAcc, setTipoAcc] = useState("SAN");
  const [acceso, setAcceso] = useState(null);

  useEffect(() => {
    api("/api/resultados/escenarios")
      .then((e) => {
        setEscenarios(e);
        const pref = e.find((x) => x.cfg?.f1_metodo === "transporte-coordenadas");
        if (e.length) setSel((pref || e[0]).config);
      })
      .catch((x) => setErr(x.message));
  }, []);

  useEffect(() => {
    if (!sel) return;
    setCargando(true); setNube(null);
    setLlaveSel(null); setDetalle(null); setSim(null);
    api(`/api/resultados/nube?config=${sel}&solo_factibles=${soloFactibles}`)
      .then(setNube).catch((x) => setErr(x.message)).finally(() => setCargando(false));
  }, [sel, soloFactibles]);

  useEffect(() => {
    api("/api/resultados/frente").then(setFrente).catch(() => setFrente(false));
    api("/api/resultados/pesos").then(setPesos).catch(() => setPesos(false));
  }, []);

  /* El motor se prepara con el recinto del escenario. A partir de ahí puede
     simular CUALQUIER layout en ~300 ms, así que no hace falta descargar
     películas precalculadas ni dejar puntos sin poder abrirse. */
  useEffect(() => {
    const r = nube?.recinto || detalle?.recinto;
    if (!r || !catalogo) return;
    iniciarMotor(r, catalogo).catch((e) => setErr(e.message));
  }, [nube, catalogo, detalle?.recinto]);

  useEffect(() => {
    if (!llaveSel) return;
    setSim(null); setReproduciendo(false); setAcceso(null); setCapa("f2");
    // en el informe publicado el layout viene dentro de la nube; con backend
    // se pide aparte. Se mira primero lo que ya se tiene.
    const p = nube?.puntos?.find((q) => q.llave === llaveSel);
    if (p?.layout && nube?.recinto) {
      setDetalle({
        llave: llaveSel, recinto: nube.recinto, layout: p.layout,
        i: p.i, factible: p.factible, f1_detalle: p.f1_detalle || {},
        cfg: nube.cfg,
        metricas: { f1: p.f1, t_des: p.t_des, exposicion: p.exposicion,
                    violacion: p.violacion },
      });
      return;
    }
    api(`/api/resultados/layout/${llaveSel}`).then(setDetalle).catch(() => {});
  }, [llaveSel, nube]);

  /* el reparto de f1 se pide solo cuando se va a ver: cuesta los campos
     Eikonal de todos los modulos y no hace falta para la animacion */
  useEffect(() => {
    if (capa !== "f1" || !detalle || acceso) return;
    accesoLayout(detalle.layout).then(setAcceso).catch((e) => setErr(e.message));
  }, [capa, detalle, acceso]);

  useEffect(() => {
    if (!reproduciendo || !sim) return;
    const n = nCuadros(sim);
    let raf, previo = performance.now(), acum = 0;
    const tic = (ahora) => {
      acum += ((ahora - previo) / 1000) * 12 * velocidad;
      previo = ahora;
      if (acum >= 1) { const s = Math.floor(acum); acum -= s; setCuadro((c) => (c + s) % n); }
      raf = requestAnimationFrame(tic);
    };
    raf = requestAnimationFrame(tic);
    return () => cancelAnimationFrame(raf);
  }, [reproduciendo, velocidad, sim]);

  const enFrente = useMemo(() => {
    const s = new Set();
    nube?.frentes?.[metricaY]?.llaves?.forEach((k) => s.add(k));
    return s;
  }, [nube, metricaY]);

  const datos = useMemo(() => {
    if (!nube) return [];
    return nube.puntos
      .filter((p) => p.f1 !== null && p[metricaY] !== null)
      .map((p) => ({ ...p, x: p.f1, y: p[metricaY], frente: enFrente.has(p.llave) }));
  }, [nube, metricaY, enFrente]);

  const frenteDatos = useMemo(
    () => datos.filter((d) => d.frente).sort((a, b) => a.x - b.x), [datos]);

  /* Los parámetros del modelo, para las ilustraciones: salen del registro de
     Python, no de valores escritos en la interfaz. */
  const Pmod = useMemo(() => (catalogo ? parametrosDe(catalogo) : null), [catalogo]);

  /* Un layout cualquiera de la nube sirve de ejemplo para las ilustraciones.
     Se toma el de f₁ mediana: ni el mejor ni el peor, uno típico. */
  const layoutMuestra = useMemo(() => {
    const ps = (nube?.puntos || []).filter((x) => x.layout && x.f1 != null);
    if (!ps.length) return null;
    const o = [...ps].sort((a, b) => a.f1 - b.f1);
    return o[Math.floor(o.length / 2)].layout;
  }, [nube]);

  const metaY = nube?.metricas.find((m) => m.clave === metricaY);
  const dispY = nube?.dispersion.find((d) => d.clave === metricaY);

  /* Abre un layout en el panel. Con llave se pide su ficha completa; sin
     llave -- los de las trazas por generacion -- se muestra lo que ya se tiene.
     Esos no traen animacion porque simular cada generacion de cada corrida
     habria sido precalcular miles de peliculas. */
  function abrir({ llave, recinto, layout, metricas, etiqueta }) {
    setSim(null); setAcceso(null); setCapa("f2"); setErr("");
    if (llave) { setDirecto(null); setLlaveSel(llave); return; }
    setLlaveSel(null);
    setDirecto({ recinto, layout, metricas, etiqueta, sinLlave: true });
    setDetalle({ recinto, layout, metricas, etiqueta, sinLlave: true,
                 factible: true, f1_detalle: {} });
  }

  async function simular() {
    if (!detalle) return;
    setSimulando(true); setErr("");
    try {
      const cfg = detalle.cfg || nube?.cfg || {};
      const r = await simularLayout(detalle.layout, cfg.aforo ?? 2000, {
        dt: cfg.dt, k_c: cfg.k_c, p: cfg.p, t_max: cfg.t_max, n_cuadros: 30,
      });
      setSim(r); setCuadro(0); setReproduciendo(true);
    } catch (x) { setErr(x.message); } finally { setSimulando(false); }
  }

  if (err && !escenarios)
    return <div className="grid h-full place-items-center text-rojo">{err}</div>;
  if (!escenarios)
    return <div className="grid h-full place-items-center text-tenue">Leyendo el almacén…</div>;
  if (!escenarios.length)
    return (
      <div className="grid h-full place-items-center px-8 text-center text-tenue">
        <div>
          <Database size={22} className="mx-auto mb-3 opacity-40" />
          <p className="text-[12.5px]">No hay evaluaciones guardadas todavía.</p>
          <p className="mt-2 font-mono text-[11px]">py -3.12 experimentos/correlacion.py -n 300</p>
        </div>
      </div>
    );

  const metodos = new Set(escenarios.map((e) => e.cfg?.f1_metodo));
  const marcar = metodos.size > 1;
  const corto = (m) => (m || "").replace("transporte-", "");
  const cfg = nube?.cfg || {};
  const params = catalogo?.parametros || [];
  const pend = params.filter((p) => p.estado === "PENDIENTE");

  return (
    <ProveedorGlosario catalogo={catalogo}>
    <div className="grid h-full min-h-0 grid-cols-[1fr_370px] overflow-hidden">

      {/* ============================== EL DOCUMENTO ============================== */}
      <div className="min-w-0 overflow-y-auto">
        <div className="mx-auto max-w-[820px] px-7 py-6">

          <div className="flex items-center gap-2 text-[11px] text-tenue">
            <BookOpen size={13} /> REPORTE DEL EXPERIMENTO
          </div>
          <h1 className="mt-1 text-[21px] font-semibold tracking-tight">
            ¿Acercar la gente a los servicios pelea con evacuar bien?
          </h1>
          <P>
            Este experimento no optimiza nada. Genera muchas distribuciones de
            áreas de servicio, mide cada una con dos funciones objetivo, y mira
            cómo se relacionan esas dos medidas. De la respuesta depende toda la
            arquitectura del trabajo: si una función se puede deducir de la otra,
            sobra el algoritmo multiobjetivo y basta optimizar una sola.
          </P>

          <SecProblema catalogo={catalogo} />
          <SecPreparacion cfg={cfg} catalogo={catalogo}
                          recinto={nube?.recinto} layout={layoutMuestra} />
          <SecRestricciones />

          {/* ------------------------------------------------ 4 */}
          <Sec n="4." titulo="Qué se hizo, paso a paso">
            <ol className="my-2 space-y-2 text-[12.5px] leading-relaxed text-[#c3ccda]">
              {[
                ["Rasterizar el recinto.", <>Se parte la planta en celdas cuadradas de <Ei t="h=1\ \text{m}" />. La unidad física del modelo es el metro cuadrado, y por eso el mapa se dibuja pixelado y no suavizado. Medido: a 2 m el orden entre layouts se rompe (<Ei t="\rho=0.107" />).</>],
                ["Colocar los módulos.", <>Se generan {nube ? nube.n : "~300"} layouts distintos al azar. El usuario solo dice <em>cuántos</em> módulos de cada tipo; dónde van lo decide el sistema.</>],
                ["Resolver el campo de rutas.", <>Para cada layout se resuelve la ecuación Eikonal desde las salidas: da, para cada punto, cuánto falta para salir y hacia dónde caminar (§5.1).</>],
                ["Simular el desalojo.", <>Se mueve la multitud como un medio continuo, con la velocidad cayendo al subir la densidad y conservando masa (§5.2 y §5.3).</>],
                ["Medir.", <>De cada layout salen <Ei t="f_1" /> (acceso) y las métricas de evacuación (§3).</>],
                ["Correlacionar.", <>Se mide si el ORDEN entre layouts según una función predice el orden según la otra (§10).</>],
              ].map(([t, d], i) => (
                <li key={i} className="flex gap-2.5">
                  <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center
                                   rounded-full bg-panel2 text-[10.5px] text-tenue">{i + 1}</span>
                  <span><b className="text-texto">{t}</b> {d}</span>
                </li>
              ))}
            </ol>
            <Nota tono="clave">
              Los layouts se generan <b>al azar</b>, no optimizados, y eso es
              deliberado: si se correlacionaran layouts ya optimizados, el
              resultado describiría al optimizador y no al problema.
            </Nota>
          </Sec>

          {/* ------------------------------------------------ 5 */}
          <Sec n="5." titulo="El modelo de multitud">
            <P>
              La multitud se modela como un <b>medio continuo</b>, no como agentes
              individuales. La razón no es comodidad: por encima de
              <Ei t="\ \rho_c=4\ \text{pers/m}^2" /> la gente pierde el movimiento
              propio y es desplazada por la presión del grupo (van&nbsp;Toll et
              al., 2021) — justamente la decisión individual que los modelos de
              agentes simulan es la que deja de ocurrir.
            </P>

            <h3 className="mb-1 mt-4 text-[12.5px] font-semibold">
              5.1 Hacia dónde camina la gente — ecuación Eikonal
            </h3>
            <P>
              Se resuelve el tiempo de llegada <Ei t="T(x)" /> a la salida más
              cercana, con el frente avanzando más lento donde se va más lento:
            </P>
            <Ec t={String.raw`\left\lVert \nabla T(x) \right\rVert = \frac{1}{v(x)},
                  \qquad T = 0 \ \text{ en las salidas}`} />
            <Simbolos ks={["T", "v", "h"]} />
            {layoutMuestra && nube?.recinto && (
              <DemoCampoSalidas recinto={nube.recinto} layout={layoutMuestra} />
            )}
            <P>
              Se resuelve con <b>Fast Marching Method</b> (Sethian, 1996). La
              dirección de marcha es <Ei t="-\nabla T" /> normalizado: se camina
              hacia donde <Ei t="T" /> baja más rápido. Las celdas que el frente
              nunca alcanza quedan con <Ei t="T=\infty" />: son zonas sin ruta a
              ninguna salida, y detectarlas es gratis.
            </P>

            <h3 className="mb-1 mt-4 text-[12.5px] font-semibold">
              5.2 Qué tan rápido se camina — diagrama fundamental
            </h3>
            <P>Cuanto más apretado, más lento. La relación es empírica (Weidmann, 1993):</P>
            <Ec t={String.raw`v(\rho) = v_0\left[1 - \exp\!\left(-\gamma\left(\frac{1}{\rho}
                  -\frac{1}{\rho_{\max}}\right)\right)\right]`} />
            <Simbolos ks={["v", "rho", "v0", "gamma", "rho_max"]} />
            <P>
              Con <Ei t="v_0=1.34\ \text{m/s}" />, <Ei t="\gamma=1.913" /> y
              <Ei t="\ \rho_{\max}=5.4\ \text{pers/m}^2" />, que es la densidad de
              atasco: ahí la velocidad se anula. De esta curva se derivan el flujo
              máximo <Ei t="q_{\max}=1.2249" /> y la densidad que lo produce
              <Ei t="\ \rho_{\text{opt}}=1.751" />; no son datos nuevos, salen de
              <Ei t="\ \max_\rho\, \rho\, v(\rho)" />.
            </P>

            <DemoWeidmann P={Pmod} />

            <h3 className="mb-1 mt-4 text-[12.5px] font-semibold">
              5.3 Cómo se mueve la masa — conservación y esquema de Godunov
            </h3>
            <P>La gente no aparece ni desaparece. Eso es una ley de conservación (Lighthill–Whitham–Richards):</P>
            <Ec t={String.raw`\frac{\partial \rho}{\partial t}
                  + \nabla\!\cdot\!\big(\rho\, v(\rho)\, \hat{u}\big) = 0`} />
            <P>
              Se discretiza con el <b>esquema de Godunov</b> en su forma de
              transmisión de celdas (Daganzo, 1994): entre dos celdas pasa lo menor
              entre lo que la de atrás puede <em>mandar</em> y lo que la de
              adelante puede <em>recibir</em>.
            </P>
            <Ec t={String.raw`D(\rho)=\begin{cases}\rho\,v(\rho) & \rho \le \rho_{\text{opt}}\\
                  q_{\max} & \rho > \rho_{\text{opt}}\end{cases}
                  \qquad
                  S(\rho)=\begin{cases}q_{\max} & \rho \le \rho_{\text{opt}}\\
                  \rho\,v(\rho) & \rho > \rho_{\text{opt}}\end{cases}`} />
            <Simbolos ks={["D", "S", "q_max", "rho_cap"]} />
            <P>
              Eso es lo que produce colas reales: cuando la celda de adelante se
              llena, su oferta <Ei t="S" /> cae y la de atrás no puede vaciarse
              aunque quiera. Validado: la masa se conserva con error relativo de
              <Ei t="\ 5\times10^{-15}" />.
            </P>

            <DemoOfertaDemanda P={Pmod} />
            <P>
              En 2D una celda puede tener varios vecinos cuesta abajo y hay que
              repartir el flujo entre ellos, con peso
              <Ei t="\ w_j=(T_i-T_j)^p" />. Ese exponente <Ei t="p" /> es el
              <b> único parámetro del modelo sin respaldo empírico</b>.
            </P>
            <P>El paso de tiempo debe cumplir la condición CFL o el esquema se vuelve inestable:</P>
            <Ec t={String.raw`\Delta t \;\le\; \frac{h}{v_0} = \frac{1.0}{1.34}
                  = 0.746\ \text{s}`} />
            <Simbolos ks={["dt", "h", "v0", "k_c"]} />
          </Sec>

          {/* ------------------------------------------------ 6 */}
          <Sec n="6." titulo="Las dos funciones objetivo">
            <P>
              <b>f₁</b> mide el acceso a los servicios. <b>f₂</b> no es un número
              sino una intención — «que la evacuación salga bien» — y hay que
              convertirla en algo medible. Se midieron cuatro candidatas y quedaron
              estas:
            </P>
            {nube && nube.metricas.map((m) => (
              <div key={m.clave} className="my-3 rounded-lg border border-linea bg-panel p-3">
                <div className="flex items-baseline gap-2">
                  <span className="text-[13px] font-semibold">{m.nombre}</span>
                  <span className="text-[11px] text-tenue">[{m.unidad}]</span>
                </div>
                <p className="mt-1 text-[12px] leading-relaxed text-[#c3ccda]">{m.explicacion}</p>
                <Ec t={m.tex} />
              </div>
            ))}
            <Nota tono="alerta">
              <b>Dos candidatas se retiraron, y conviene saber por qué.</b>{" "}
              <b>ρ pico</b> (la densidad máxima alcanzada) tiene un CV de 1.2 a
              3.0 %: siempre sale entre 4.8 y 5.1, porque siempre hay atasco frente
              a las puertas. No distingue un layout de otro.{" "}
              <b>t₉₅</b> (el segundo en que ha salido el 95 %) es otra lectura del
              mismo tiempo de evacuación y solo agrega una columna que interpretar.
              Los datos de las dos siguen guardados en la base; solo no se grafican.
            </Nota>

            <h3 className="mb-1 mt-4 text-[12.5px] font-semibold">
              6.1 Cómo se calcula f₁ — problema de transporte
            </h3>
            <P>
              Ingenuamente, «cada quien va al módulo más cercano». Pero un módulo
              atiende a un ritmo finito: si todos van al mismo, ese se satura.
              Entonces se resuelve el reparto óptimo como un <b>problema de
              transporte</b>, donde <Ei t="y_{ij}" /> es la fracción de la demanda
              de la celda <Ei t="i" /> que se atiende en el módulo <Ei t="j" />:
            </P>
            <Ec t={String.raw`\begin{aligned}
                  \min_{y}\quad & \sum_{i}\sum_{j} q_i\, d_{ij}\, y_{ij} \\[2pt]
                  \text{s.a.}\quad & \textstyle\sum_j y_{ij} = 1
                    && \text{cada quien se atiende en algún lado}\\
                  & \textstyle\sum_i q_i\, y_{ij} \le c_j
                    && \text{ningún módulo atiende de más}\\
                  & y_{ij} \ge 0
                  \end{aligned}`} />
            <Simbolos ks={["f1", "d_ij", "q_i", "c_j", "y_ij", "w_t", "sigma"]} />
            <P>
              <V k="d_ij" /> es la distancia <b>caminando</b> (geodésica, no en
              línea recta), sembrada en las celdas libres pegadas al módulo y no en
              su centroide — un módulo de 8×3 m no se atiende desde su centro.
              <V k="c_j" /> sale de las unidades de atención del módulo (cuántos
              inodoros, cuántos grifos).
            </P>

            <h3 className="mb-1 mt-4 text-[12.5px] font-semibold">
              6.2 Desde dónde se mide un módulo
            </h3>
            {layoutMuestra && nube?.recinto && (
              <DemoSemillas recinto={nube.recinto} layout={layoutMuestra}
                            catalogo={catalogo} />
            )}
            {layoutMuestra && nube?.recinto && (
              <DemoAsignacion catalogo={catalogo} lut={lut}
                              recinto={nube.recinto} layout={layoutMuestra} />
            )}

            <Nota>
              <b>Por qué no el codicioso.</b> Recorrer celdas mandando cada una a la
              más cercana con cupo da un resultado que <b>depende del orden en que
              se recorre la rejilla</b>. Medido: ese ruido es de 5.4 % en promedio y
              hasta 13 %, contra 2.0 % de separación real entre layouts —{" "}
              <b>2.7× la señal</b>. Ordenaría por el barrido de la rejilla, no por
              el layout. El transporte exacto no depende de ningún recorrido.
            </Nota>
          </Sec>

          {/* ------------------------------------------------ 7 */}
          <Sec n="7." titulo="Cómo se generaron los layouts">
            <P>
              Cada layout se arma colocando módulo por módulo al azar y aceptándolo
              si el layout parcial sigue siendo válido. Hay dos modos, y la
              diferencia importa para leer los resultados:
            </P>
            <div className="my-2 grid gap-2 sm:grid-cols-2">
              <div className="rounded-md border border-linea bg-panel2 p-2.5">
                <div className="text-[12px] font-semibold">amplio</div>
                <p className="mt-1 text-[11.5px] leading-snug text-tenue">
                  Solo lo estructural: que quepa, que no se encime con otro, que no
                  esté sobre un muro, y que se pueda llegar a él. Es la nube sin
                  recortar.
                </p>
              </div>
              <div className="rounded-md border border-linea bg-panel2 p-2.5">
                <div className="text-[12px] font-semibold">estricto</div>
                <p className="mt-1 text-[11.5px] leading-snug text-tenue">
                  La capa geométrica completa (G1–G6): además conos de salida
                  despejados y área útil conservada. Solo lo que aceptaría
                  protección civil.
                </p>
              </div>
            </div>
            <Nota tono="alerta">
              <b>Hacen falta los dos.</b> Filtrar por factibilidad antes de medir
              sesga la muestra hacia donde el propio criterio de diseño considera
              bueno, y entonces la correlación describe ese criterio en vez del
              problema. Medido: la misma población amplia partida por factibilidad
              da <Ei t="\rho=-0.216" /> en una mitad y <Ei t="+0.097" /> en la otra,
              siendo el total cero. Eso es un <b>efecto de selección</b>, y es la
              razón de que en el optimizador los infactibles no se descarten sino
              que se ordenen por dominancia restringida.
            </Nota>
          </Sec>

          {/* ------------------------------------------------ 8 */}
          <Sec n="8." titulo="Resultado 1 — ¿varía cada métrica?">
            <P>
              Esto va primero a propósito: si una métrica es prácticamente
              constante entre layouts, correlacionarla no significa nada, porque lo
              que se estaría ordenando es ruido. El coeficiente de variación es
              <Ei t="\ CV=\sigma/\lvert\mu\rvert" />, y por debajo de 1 % se
              considera que no informa.
            </P>

            <div className="my-3 flex flex-wrap items-center gap-2 rounded-md border
                            border-linea bg-panel px-3 py-2">
              <span className="text-[11px] text-tenue">Escenario</span>
              {escenarios.map((e) => (
                <button key={e.config} onClick={() => setSel(e.config)}
                  className={`rounded-md border px-2 py-1 text-[11px] transition-colors ${
                    e.config === sel ? "border-[#4C9BE8] bg-[#12243a] text-[#9ecbf5]"
                    : "border-linea bg-panel2 text-tenue hover:border-[#3d4757]"}`}>
                  {e.modo} · {e.aforo}
                  {marcar && <span className="ml-1 opacity-60">{corto(e.cfg?.f1_metodo)}</span>}
                </button>
              ))}
              <label className="ml-auto flex items-center gap-1.5 text-[11px] text-tenue">
                <input type="checkbox" checked={soloFactibles}
                       onChange={(ev) => setSoloFactibles(ev.target.checked)} />
                solo factibles
              </label>
            </div>

            {cargando && (
              <div className="flex items-center gap-2 py-3 text-[11.5px] text-tenue">
                <Loader2 size={13} className="animate-spin" /> calculando intervalos…
              </div>
            )}

            {nube && (
              <Tarjeta titulo="Dispersión de cada métrica" extra={`${nube.n} layouts`}>
                <table className="w-full text-[11.5px]">
                  <thead className="text-tenue">
                    <tr className="border-b border-linea">
                      <th className="py-1 text-left font-normal">métrica</th>
                      <th className="py-1 text-right font-normal">media</th>
                      <th className="py-1 text-right font-normal">desv.</th>
                      <th className="py-1 text-right font-normal">CV</th>
                      <th className="py-1 text-right font-normal">mín — máx</th>
                    </tr>
                  </thead>
                  <tbody>
                    {nube.dispersion.map((d) => (
                      <tr key={d.clave} className="border-b border-linea/40">
                        <td className="py-1">{d.nombre}
                          <span className="ml-1 text-tenue">{d.unidad}</span></td>
                        <td className="py-1 text-right font-mono">{num(d.media)}</td>
                        <td className="py-1 text-right font-mono">{num(d.desv)}</td>
                        <td className={`py-1 text-right font-mono ${d.informa ? "" : "text-rojo"}`}>
                          {pct(d.cv)}
                        </td>
                        <td className="py-1 text-right font-mono text-tenue">
                          {num(d.min)} — {num(d.max)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Tarjeta>
            )}
          </Sec>

          {nube && (
            <>
              {/* --------------------------------------------- 6 */}
              <Sec n="9." titulo="Resultado 2 — la nube y el frente de Pareto">
                <P>
                  Cada punto es un layout. En el eje horizontal <Ei t="f_1" />, en
                  el vertical la métrica de evacuación que elijas.{" "}
                  <b>En ambos ejes, menos es mejor</b>, así que lo bueno está abajo
                  a la izquierda. Un punto es <b>no dominado</b> si ningún otro es
                  mejor o igual en las dos cosas a la vez: ese conjunto es el frente
                  de Pareto.
                </P>
                <Nota tono="clave">
                  <b>Cómo saber si el frente significa algo.</b> Con <Ei t="n" />{" "}
                  puntos y dos objetivos <em>independientes</em>, el número esperado
                  de no dominados es el número armónico
                  <Ei t="\ H_n=\sum_{k=1}^{n}1/k \approx \ln n + 0.577" />, que para
                  <Ei t="\ n=300" /> da <b>6.3</b>. Si lo observado coincide, la
                  nube se comporta como dos objetivos sin relación; si es mucho
                  mayor, hay conflicto de verdad.
                </Nota>

                <div className="my-2 flex flex-wrap items-center gap-1.5">
                  <span className="text-[11px] text-tenue">eje vertical</span>
                  {nube.metricas.filter((m) => m.clave !== "f1").map((m) => (
                    <button key={m.clave} onClick={() => setMetricaY(m.clave)}
                      className={`rounded border px-2 py-0.5 text-[11px] ${
                        m.clave === metricaY ? "border-[#4C9BE8] bg-[#12243a] text-[#9ecbf5]"
                        : "border-linea bg-panel2 text-tenue hover:border-[#3d4757]"}`}>
                      {m.nombre}
                    </button>
                  ))}
                  <span className="ml-auto text-[10.5px] text-tenue">
                    frente: <b className="text-[#2bff88]">{frenteDatos.length}</b> no
                    dominados · el azar esperaría{" "}
                    {num(nube.frentes?.[metricaY]?.esperado_si_independientes, 1)}
                  </span>
                </div>

                {dispY && !dispY.informa && (
                  <div className="mb-2 flex items-start gap-1.5 rounded border border-rojo/40
                                  bg-rojo/10 px-2 py-1.5 text-[11px] text-rojo">
                    <AlertTriangle size={13} className="mt-px shrink-0" />
                    <span>CV de {pct(dispY.cv)}: esta métrica es casi la misma en
                    todos los layouts. Lo que se ve abajo es ruido, no estructura.</span>
                  </div>
                )}

                <div className="h-[320px] rounded-lg border border-linea bg-panel p-2">
                  <ResponsiveContainer>
                    <ScatterChart margin={{ top: 8, right: 14, bottom: 24, left: 8 }}>
                      <CartesianGrid stroke="#1e2530" />
                      <XAxis type="number" dataKey="x" name="f₁"
                             domain={["dataMin", "dataMax"]} tickFormatter={(v) => num(v)}
                             tick={{ fontSize: 10, fill: "#7c8798" }} stroke="#2b3444"
                             label={{ value: "f₁ acceso (m) — menos es mejor",
                                      position: "bottom", offset: 6,
                                      fontSize: 10.5, fill: "#7c8798" }} />
                      <YAxis type="number" dataKey="y" name={metaY?.nombre}
                             domain={["dataMin", "dataMax"]} tickFormatter={(v) => num(v)}
                             tick={{ fontSize: 10, fill: "#7c8798" }} stroke="#2b3444" width={62}
                             label={{ value: `${metaY?.nombre} (${metaY?.unidad})`, angle: -90,
                                      position: "insideLeft", fontSize: 10.5, fill: "#7c8798" }} />
                      <ZAxis range={[26, 26]} />
                      <Tooltip cursor={{ stroke: "#3d4757" }}
                        contentStyle={{ background: "#0d111a", border: "1px solid #2b3444",
                                        borderRadius: 6, fontSize: 11 }}
                        formatter={(v, n) => [num(v), n]} />
                      <Scatter data={datos} isAnimationActive={false}
                               onClick={(d) => setLlaveSel(d.llave)}>
                        {datos.map((d) => (
                          <Cell key={d.llave} cursor="pointer"
                            fill={d.llave === llaveSel ? "#ffffff" : d.frente ? "#2bff88"
                                  : d.factible ? "#4C9BE8" : "#4a5566"}
                            fillOpacity={d.llave === llaveSel ? 1 : d.frente ? 0.95 : 0.55} />
                        ))}
                      </Scatter>
                      <Scatter data={frenteDatos} line={{ stroke: "#2bff88", strokeWidth: 1 }}
                               shape={() => null} isAnimationActive={false} legendType="none" />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-3 text-[10.5px] text-tenue">
                  <span><b className="text-[#2bff88]">●</b> no dominado</span>
                  <span><b className="text-[#4C9BE8]">●</b> pasa la capa geométrica</span>
                  <span><b className="text-[#4a5566]">●</b> no la pasa</span>
                  <span className="ml-auto">clic en un punto → aparece a la derecha</span>
                </div>
              </Sec>

              {/* --------------------------------------------- 7 */}
              <Sec n="10." titulo="Resultado 3 — la matriz de correlación">
                <P>
                  Se usa la correlación de rangos de <b>Spearman</b> y no la de
                  Pearson porque a un optimizador por dominancia solo le importa el{" "}
                  <b>orden</b> entre soluciones, no la distancia entre sus valores.
                  Pearson mediría si la relación es una recta, que aquí no le sirve
                  a nadie.
                </P>
                <Ec t={String.raw`\rho_s = 1 - \frac{6\sum_i d_i^{\,2}}{n\,(n^2-1)},
                      \qquad d_i = \operatorname{rg}(x_i) - \operatorname{rg}(y_i)`} />
            <Simbolos ks={["rho_s"]} />
                <Nota tono="alerta">
                  <b>Lee el intervalo, no el número.</b> Con <Ei t="n" /> layouts el
                  error típico de <Ei t="\rho" /> es <Ei t="\approx 1/\sqrt{n-1}" />,
                  que con <Ei t="n=300" /> da 0.058. Un <Ei t="\rho" /> de 0.09{" "}
                  <b>no</b> es «correlación débil positiva»: es cero con ruido. Las
                  celdas <b>grises</b> son aquellas cuyo intervalo al 95 % cruza el
                  cero — ahí no se puede afirmar que exista relación.
                </Nota>
                <div className="overflow-x-auto rounded-lg border border-linea bg-panel p-3">
                  <table className="text-[11px]">
                    <thead>
                      <tr><th />
                        {nube.usables.map((k) => (
                          <th key={k} className="px-1 pb-1 font-normal text-tenue">
                            {nube.metricas.find((m) => m.clave === k)?.nombre}
                          </th>))}
                      </tr>
                    </thead>
                    <tbody>
                      {nube.usables.map((ka, a) => (
                        <tr key={ka}>
                          <td className="pr-2 text-right text-tenue">
                            {nube.metricas.find((m) => m.clave === ka)?.nombre}
                          </td>
                          {nube.usables.map((kb, b) => {
                            const r = nube.rho[a][b], ic = nube.ic[a][b];
                            const cruza = ic && ic[0] <= 0 && ic[1] >= 0;
                            return (
                              <td key={kb}
                                title={ic ? `IC 95 % [${num(ic[0])}, ${num(ic[1])}]` : "sin intervalo"}
                                className="border border-linea px-2.5 py-1.5 text-center font-mono"
                                style={{ background: a === b ? "#151b26"
                                         : cruza ? "rgba(120,130,145,.14)" : colorRho(r) }}>
                                {a === b ? "—" : num(r)}
                                {ic && <div className="text-[9px] opacity-60">
                                  {num(ic[0])} … {num(ic[1])}</div>}
                              </td>);
                          })}
                        </tr>))}
                    </tbody>
                  </table>
                  <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-tenue">
                    <span><span className="mr-1 inline-block h-2.5 w-4 align-middle"
                      style={{ background: colorRho(-0.8) }} />negativo: compromiso</span>
                    <span><span className="mr-1 inline-block h-2.5 w-4 align-middle"
                      style={{ background: colorRho(0.8) }} />positivo: van juntas</span>
                    <span><span className="mr-1 inline-block h-2.5 w-4 align-middle"
                      style={{ background: "rgba(120,130,145,.14)" }} />el intervalo cruza cero</span>
                  </div>
                </div>
                <Nota tono="clave">
                  <b>Cómo se lee, y su límite.</b> Si <Ei t="f_1" /> sale gris
                  contra todo lo demás, significa que en la muestra aleatoria{" "}
                  <b>una función no se puede deducir de la otra</b> — y eso ya
                  justifica el multiobjetivo, porque optimizar una dejaría la otra
                  al azar. Pero ojo: esta matriz describe la región{" "}
                  <em>típica</em>, y el frente de Pareto vive en el <em>borde</em>.
                  Al optimizar de verdad sí aparecen compromisos que aquí no se ven
                  (ver <span className="font-mono">experimentos/OPTIMIZADOR.md</span>).
                </Nota>
              </Sec>
            </>
          )}

          {/* ------------------------------------------------ 11 */}
          {frente && frente.frente && (
            <Sec n="11." titulo="Resultado 4 — el frente real, y por qué no basta un barrido de pesos">
              <P>
                Las secciones anteriores miran una muestra <b>al azar</b>, y una
                muestra al azar nunca llega a la frontera: se queda en la región
                típica. Para ver el frente de verdad hay que ir a buscarlo. Se
                usa el método <b>ε-restringido</b> (Haimes et al., 1971), que no
                escalariza sino que restringe:
              </P>
              <Ec t={String.raw`\begin{aligned}
                    \text{para cada tope } \tau:\quad
                    \min_{\text{layout}} \;& f_1(\text{acceso}) \\
                    \text{s.a.}\;& t_{\text{evac}} \le \tau \\
                    & \text{restricciones geométricas}
                    \end{aligned}`} />
              <P>
                Cada τ da un punto del frente; barriendo τ se traza la curva
                entera. Se eligió este método y no el algoritmo final justamente
                porque <b>alcanza todos los puntos del frente</b>, incluidos los
                de las regiones no convexas. Así sirve de árbitro imparcial para
                decidir qué algoritmo hace falta.
              </P>

              <Tarjeta titulo="El frente"
                       extra={`${frente.frente.length} puntos · aforo ${frente.aforo} · ${frente.corridas.length} topes × ${frente.gens} generaciones`}>
                <div className="h-[300px]">
                  <ResponsiveContainer>
                    <ScatterChart margin={{ top: 10, right: 16, bottom: 26, left: 8 }}>
                      <CartesianGrid stroke="#1e2530" />
                      <XAxis type="number" dataKey="x" domain={["dataMin", "dataMax"]}
                             tickFormatter={(v) => num(v)} stroke="#2b3444"
                             tick={{ fontSize: 10, fill: "#7c8798" }}
                             label={{ value: "accesibilidad f₁ (m) — menos es mejor",
                                      position: "bottom", offset: 6, fontSize: 10.5,
                                      fill: "#7c8798" }} />
                      <YAxis type="number" dataKey="y" domain={["dataMin", "dataMax"]}
                             tickFormatter={(v) => num(v)} stroke="#2b3444" width={58}
                             tick={{ fontSize: 10, fill: "#7c8798" }}
                             label={{ value: "tiempo de evacuación (s)", angle: -90,
                                      position: "insideLeft", fontSize: 10.5,
                                      fill: "#7c8798" }} />
                      <ZAxis range={[40, 40]} />
                      <Tooltip cursor={{ stroke: "#3d4757" }}
                        contentStyle={{ background: "#0d111a", border: "1px solid #2b3444",
                                        borderRadius: 6, fontSize: 11 }}
                        formatter={(v, n) => [num(v), n === "x" ? "f₁ (m)" : "t evac (s)"]} />
                      <Scatter name="al azar"
                               data={(frente.azar.acceso || []).map((a, i) => ({
                                 x: a, y: frente.azar.t_evac[i] }))}
                               fill="#3c4758" fillOpacity={0.55} isAnimationActive={false} />
                      <Scatter name="frente"
                               data={frente.frente.map((f) => ({
                                 x: f.acceso, y: f.t_evac,
                                 ok: f.alcanzable_por_pesos }))}
                               line={{ stroke: "#2bff88", strokeWidth: 1.4 }}
                               isAnimationActive={false}>
                        {frente.frente.map((f, i) => (
                          <Cell key={i} fill={f.alcanzable_por_pesos ? "#2bff88" : "#e2564f"} />
                        ))}
                      </Scatter>
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-1 flex flex-wrap gap-3 text-[10.5px] text-tenue">
                  <span><b className="text-[#3c4758]">●</b> layouts al azar ({frente.azar.n})</span>
                  <span><b className="text-[#2bff88]">●</b> en el frente, y un barrido de pesos lo alcanza</span>
                  <span><b className="text-rojo">●</b> en el frente, <b>inalcanzable con cualquier peso</b></span>
                </div>
              </Tarjeta>

              <div className="my-3 overflow-hidden rounded-lg border border-linea bg-panel">
                <table className="w-full text-[11.5px]">
                  <thead className="text-tenue">
                    <tr className="border-b border-linea">
                      <th className="px-3 py-1.5 text-right font-normal">accesibilidad f₁ (m)</th>
                      <th className="px-3 py-1.5 text-right font-normal">tiempo de evacuación (s)</th>
                      <th className="px-3 py-1.5 text-left font-normal">¿la alcanza una suma ponderada?</th>
                      <th className="px-3 py-1.5" />
                    </tr>
                  </thead>
                  <tbody>
                    {frente.frente.map((f, i) => (
                      <tr key={i} className={`border-b border-linea/40 ${
                        llaveSel === f.llave ? "bg-[#12243a]" : ""}`}>
                        <td className="px-3 py-1 text-right font-mono">{num(f.acceso)}</td>
                        <td className="px-3 py-1 text-right font-mono">{num(f.t_evac)}</td>
                        <td className={`px-3 py-1 ${f.alcanzable_por_pesos ? "text-tenue" : "text-rojo"}`}>
                          {f.alcanzable_por_pesos ? "sí" : "NO — inalcanzable"}
                        </td>
                        <td className="px-3 py-1 text-right">
                          <button
                            onClick={() => abrir({ llave: f.llave, recinto: frente.recinto,
                                                   layout: f.layout,
                                                   etiqueta: `τ = ${num(f.tau, 1)} s`,
                                                   metricas: { f1: f.acceso, t_des: f.t_evac } })}
                            className="rounded border border-linea px-2 py-0.5 text-[10.5px]
                                       text-tenue hover:border-[#4C9BE8] hover:text-[#9ecbf5]">
                            ver
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <Nota tono={frente.convexo ? "info" : "alerta"}>
                {frente.convexo ? (
                  <>
                    <b>El frente salió convexo.</b> Un barrido de pesos lo recorrería
                    entero y NSGA-II no se justifica por este argumento.
                  </>
                ) : (
                  <>
                    <b>El frente es NO CONVEXO.</b>{" "}
                    {frente.frente.filter((f) => !f.alcanzable_por_pesos).length} de{" "}
                    {frente.frente.length} soluciones son inalcanzables con{" "}
                    <em>cualquier</em> peso. Minimizar{" "}
                    <Ei t="w\,f_1 + (1-w)\,t_{\text{evac}}" /> equivale a deslizar
                    una recta hasta que toca el conjunto factible, y una recta solo
                    puede tocar el casco convexo: si el frente tiene una hendidura,
                    la recta pasa por encima. Esos puntos <b>no salen peores — el
                    método no puede verlos</b> (Das &amp; Dennis, 1997). Por eso hace
                    falta ordenar por dominancia y no por un escalar.
                  </>
                )}
              </Nota>

              <h3 className="mb-1 mt-5 text-[12.5px] font-semibold">
                11.1 Cómo converge cada punto del frente
              </h3>
              <P>
                Cada curva es un tope τ distinto, y cada punto una generación. Se
                ve de dónde arranca la búsqueda y cómo baja: al principio los topes
                más exigentes tienen que sacrificar accesibilidad para cumplir el
                tiempo, y luego la recuperan. Arrastra para girar.
              </P>
              <div className="rounded-lg border border-linea bg-panel p-2">
                <Grafica3D
                  alto={400}
                  ejes={{ x: "f₁ acceso (m)", y: "t evacuación (s)", z: "generación",
                         corto: { x: "f₁", y: "t evac", z: "gen" } }}
                  onPunto={(d) => abrir({
                    recinto: frente.recinto, layout: d.layout,
                    etiqueta: `τ = ${num(d.tau, 1)} s · generación ${d.g}`,
                    metricas: { f1: d.x, t_des: d.y } })}
                  series={frente.corridas.map((c, i) => {
                    const col = variantesColor("#4C9BE8", frente.corridas.length)[i];
                    return {
                      color: `rgb(${col[0]},${col[1]},${col[2]})`,
                      radio: 2.6,
                      puntos: c.traza.map((t) => ({
                        x: t.acceso, y: t.t_evac, z: t.g,
                        tau: c.tau, g: t.g, layout: t.layout,
                      })),
                    };
                  })}
                />
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-tenue">
                  {frente.corridas.map((c, i) => {
                    const col = variantesColor("#4C9BE8", frente.corridas.length)[i];
                    return (
                      <span key={i} className="flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full"
                              style={{ background: `rgb(${col[0]},${col[1]},${col[2]})` }} />
                        τ = {num(c.tau, 1)} s
                      </span>
                    );
                  })}
                </div>
              </div>
              <Nota>
                Esto NO es el optimizador del trabajo: es una búsqueda simple
                (μ+λ) corrida una vez por cada tope, solo para localizar la
                frontera. El algoritmo definitivo se decide con esta evidencia,
                no al revés.
              </Nota>
            </Sec>
          )}

          {/* ------------------------------------------------ 12 */}
          {pesos && pesos.soluciones && (
            <Sec n="12." titulo="Resultado 5 — el barrido de pesos, y lo que no puede ver">
              <P>
                Es la prueba clásica de si un problema es multiobjetivo: se
                minimiza una suma ponderada de los dos objetivos, barriendo el
                peso de 0.1 a 0.9.
              </P>
              <Ec t={String.raw`\min_{\text{layout}}\;\; w\cdot\hat f_1 \;+\;
                    (1-w)\cdot \hat t_{\text{evac}}
                    \qquad w \in \{0.1,\,0.2,\,\dots,\,0.9\}`} />
              <P>
                La lógica es sólida: <b>si todos los pesos devuelven la misma
                solución</b>, hay una sola solución buena y no hay nada que
                negociar — no sería multiobjetivo. <b>Si devuelven soluciones
                distintas repartidas en una curva</b>, cada peso es una postura
                distinta sobre qué importa más y ninguna domina a las otras.
              </P>
              <Nota>
                <b>Sumar metros con segundos no significa nada</b>, así que cada
                objetivo se lleva a [0,1] con el rango de la muestra al azar:
                acceso [{num(pesos.normalizacion.a0)},{" "}
                {num(pesos.normalizacion.a0 + pesos.normalizacion.da)}] m,
                tiempo [{num(pesos.normalizacion.t0)},{" "}
                {num(pesos.normalizacion.t0 + pesos.normalizacion.dt)}] s. Esa
                normalización es una <b>decisión</b>: cambiarla cambia qué
                solución sale para cada peso. Por eso se declara junto al
                resultado y no se esconde.
              </Nota>

              <Tarjeta titulo="Resultado del barrido"
                       extra={`${pesos.distintas} soluciones distintas de ${pesos.soluciones.length} pesos`}>
                <div className="h-[280px]">
                  <ResponsiveContainer>
                    <ScatterChart margin={{ top: 10, right: 16, bottom: 26, left: 8 }}>
                      <CartesianGrid stroke="#1e2530" />
                      <XAxis type="number" dataKey="x" domain={["dataMin", "dataMax"]}
                             tickFormatter={(v) => num(v)} stroke="#2b3444"
                             tick={{ fontSize: 10, fill: "#7c8798" }}
                             label={{ value: "accesibilidad f₁ (m)", position: "bottom",
                                      offset: 6, fontSize: 10.5, fill: "#7c8798" }} />
                      <YAxis type="number" dataKey="y" domain={["dataMin", "dataMax"]}
                             tickFormatter={(v) => num(v)} stroke="#2b3444" width={58}
                             tick={{ fontSize: 10, fill: "#7c8798" }}
                             label={{ value: "tiempo de evacuación (s)", angle: -90,
                                      position: "insideLeft", fontSize: 10.5,
                                      fill: "#7c8798" }} />
                      <ZAxis range={[46, 46]} />
                      <Tooltip cursor={{ stroke: "#3d4757" }}
                        contentStyle={{ background: "#0d111a", border: "1px solid #2b3444",
                                        borderRadius: 6, fontSize: 11 }}
                        formatter={(v, n) => [num(v), n === "x" ? "f₁ (m)" : "t evac (s)"]} />
                      {pesos.azar && (
                        <Scatter data={pesos.azar.acceso.map((a, i) => ({
                                   x: a, y: pesos.azar.t_evac[i] }))}
                                 fill="#3c4758" fillOpacity={0.5} isAnimationActive={false} />
                      )}
                      <Scatter
                        data={pesos.soluciones.map((z) => ({ x: z.acceso, y: z.t_evac, w: z.w }))}
                        line={{ stroke: "#e0a458", strokeWidth: 1.4 }}
                        fill="#e0a458" isAnimationActive={false}
                        onClick={(d) => {
                          const z = pesos.soluciones.find((q) => q.w === d.w);
                          if (z) abrir({ llave: z.llave, recinto: pesos.recinto,
                                         layout: z.layout, etiqueta: `w = ${z.w}`,
                                         metricas: { f1: z.acceso, t_des: z.t_evac } });
                        }} />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-1 flex flex-wrap gap-3 text-[10.5px] text-tenue">
                  <span><b className="text-[#3c4758]">●</b> layouts al azar</span>
                  <span><b className="text-ambar">●</b> solución de cada peso</span>
                  <span className="ml-auto">clic en un punto para abrirlo</span>
                </div>
              </Tarjeta>

              <div className="my-3 overflow-hidden rounded-lg border border-linea bg-panel">
                <table className="w-full text-[11.5px]">
                  <thead className="text-tenue">
                    <tr className="border-b border-linea">
                      <th className="px-3 py-1.5 text-right font-normal">peso de f₁<br/>
                        <span className="font-normal opacity-70">accesibilidad</span></th>
                      <th className="px-3 py-1.5 text-right font-normal">peso de f₂<br/>
                        <span className="font-normal opacity-70">t evacuación</span></th>
                      <th className="px-3 py-1.5 text-left font-normal">qué resuelve</th>
                      <th className="px-3 py-1.5 text-right font-normal">acceso (m)</th>
                      <th className="px-3 py-1.5 text-right font-normal">t evacuación (s)</th>
                      <th className="px-3 py-1.5" />
                    </tr>
                  </thead>
                  <tbody>
                    {pesos.soluciones.map((z, i) => {
                      const wa = z.w_acceso ?? z.w;
                      const wt = z.w_tiempo ?? (1 - z.w);
                      const extremo = wa === 0 || wa === 1;
                      return (
                      <tr key={i} className={`border-b border-linea/40 ${
                        (directo?.etiqueta === `w = ${z.w}` || llaveSel === z.llave)
                          ? "bg-[#12243a]" : extremo ? "bg-panel2/50" : ""}`}>
                        <td className={`px-3 py-1 text-right font-mono ${
                          wa === 1 ? "text-[#9ecbf5]" : wa === 0 ? "text-tenue" : ""}`}>
                          {num(wa, 1)}
                        </td>
                        <td className={`px-3 py-1 text-right font-mono ${
                          wt === 1 ? "text-[#9ecbf5]" : wt === 0 ? "text-tenue" : ""}`}>
                          {num(wt, 1)}
                        </td>
                        <td className={`px-3 py-1 ${extremo ? "text-[#9ecbf5]" : "text-tenue"}`}>
                          {wa === 1 ? "SOLO accesibilidad — mono-objetivo"
                           : wa === 0 ? "SOLO tiempo de evacuación — mono-objetivo"
                           : wa === 0.5 ? "las dos por igual"
                           : wa > 0.5 ? "más peso a la accesibilidad"
                           : "más peso al tiempo"}
                        </td>
                        <td className="px-3 py-1 text-right font-mono">{num(z.acceso)}</td>
                        <td className="px-3 py-1 text-right font-mono">{num(z.t_evac)}</td>
                        <td className="px-3 py-1 text-right">
                          <button
                            onClick={() => abrir({ llave: z.llave, recinto: pesos.recinto,
                                                   layout: z.layout, etiqueta: `w = ${z.w}`,
                                                   metricas: { f1: z.acceso, t_des: z.t_evac } })}
                            className="rounded border border-linea px-2 py-0.5 text-[10.5px]
                                       text-tenue hover:border-[#4C9BE8] hover:text-[#9ecbf5]">
                            ver
                          </button>
                        </td>
                      </tr>);
                    })}
                  </tbody>
                </table>
              </div>

              {(() => {
                const so = pesos.soluciones;
                const a = so.find((z) => (z.w_acceso ?? z.w) === 1);
                const t = so.find((z) => (z.w_acceso ?? z.w) === 0);
                if (!a || !t) return null;
                return (
                  <Nota tono="clave">
                    <b>Los dos extremos son los casos mono-objetivo</b>, y dicen
                    cuánto cuesta atender también a la otra función.
                    Optimizando <b>solo la accesibilidad</b> se llega a{" "}
                    {num(a.acceso)} m, y el tiempo queda en {num(a.t_evac)} s.
                    Optimizando <b>solo el tiempo</b> se llega a {num(t.t_evac)} s,
                    pero la accesibilidad se va a {num(t.acceso)} m —{" "}
                    <b>peor que la mediana de los layouts al azar</b>. Optimizar
                    una sola función no deja a la otra donde estaba: la empeora
                    activamente, y eso es precisamente lo que un método
                    multiobjetivo evita.
                  </Nota>
                );
              })()}

              <h3 className="mb-1 mt-5 text-[12.5px] font-semibold">
                12.1 Cómo converge cada peso
              </h3>
              <P>
                Una curva por peso, un punto por generación. Doble clic en
                cualquier punto para ver el layout de esa generación.
              </P>
              <div className="rounded-lg border border-linea bg-panel p-2">
                <Grafica3D
                  alto={400}
                  ejes={{ x: "f₁ acceso (m)", y: "t evacuación (s)", z: "generación",
                         corto: { x: "f₁", y: "t evac", z: "gen" } }}
                  onPunto={(d) => abrir({
                    recinto: pesos.recinto, layout: d.layout,
                    etiqueta: `w = ${num(d.w, 1)} · generación ${d.g}`,
                    metricas: { f1: d.x, t_des: d.y } })}
                  series={pesos.soluciones.map((z, i) => {
                    const c = variantesColor("#e0a458", pesos.soluciones.length)[i];
                    return {
                      color: `rgb(${c[0]},${c[1]},${c[2]})`, radio: 2.6,
                      puntos: z.traza.map((t) => ({
                        x: t.acceso, y: t.t_evac, z: t.g,
                        g: t.g, w: z.w, layout: t.layout })),
                    };
                  })}
                />
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-tenue">
                  {pesos.soluciones.map((z, i) => {
                    const c = variantesColor("#e0a458", pesos.soluciones.length)[i];
                    return (
                      <span key={i} className="flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full"
                              style={{ background: `rgb(${c[0]},${c[1]},${c[2]})` }} />
                        w = {num(z.w, 1)}
                      </span>);
                  })}
                </div>
              </div>

              {frente && frente.frente && (
                <Nota tono="alerta">
                  <b>Y aquí está el límite de esta prueba.</b> Un barrido de pesos
                  solo puede devolver puntos del <b>casco convexo</b>: minimizar{" "}
                  <Ei t="w\,f_1+(1-w)\,t" /> es deslizar una recta hasta que toca
                  el conjunto factible, y una recta nunca toca el fondo de una
                  hendidura. Por eso la curva que dibuja{" "}
                  <b>siempre se ve convexa</b> — es una propiedad del método, no
                  un hallazgo sobre el problema. Para saber si el frente tiene
                  hendiduras hace falta el barrido ε-restringido de §11, que
                  restringe en vez de escalarizar.
                </Nota>
              )}
            </Sec>
          )}

          {/* ------------------------------------------------ 13 */}
          <Sec n="13." titulo="Todas las variables, con su procedencia">
            <P>
              Regla del proyecto: <b>ningún número se inventa</b>. Cada parámetro
              declara de dónde sale y en qué estado está. Los marcados{" "}
              <span className="text-rojo">PENDIENTE</span> no tienen fuente
              verificada y bloquean la tesis — hoy son <b>{pend.length}</b>.
            </P>
            <div className="my-2 flex flex-wrap gap-x-4 gap-y-1 text-[10.5px]">
              {Object.entries(ESTADOS).map(([k, [c, d]]) => (
                <span key={k} className="flex items-center gap-1.5">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ background: c }} />
                  <b style={{ color: c }}>{k}</b>
                  <span className="text-tenue">{d}</span>
                </span>
              ))}
            </div>
            <div className="overflow-hidden rounded-lg border border-linea bg-panel">
              <table className="w-full text-[11px]">
                <thead className="text-tenue">
                  <tr className="border-b border-linea">
                    <th className="px-2 py-1.5 text-left font-normal">símbolo</th>
                    <th className="px-2 py-1.5 text-left font-normal">clave</th>
                    <th className="px-2 py-1.5 text-right font-normal">valor</th>
                    <th className="px-2 py-1.5 text-left font-normal">unidad</th>
                    <th className="px-2 py-1.5 text-left font-normal">estado</th>
                    <th className="px-2 py-1.5 text-left font-normal">qué es / de dónde sale</th>
                  </tr>
                </thead>
                <tbody>
                  {(verTodos ? params : params.slice(0, 12)).map((p) => (
                    <tr key={p.clave} className="border-b border-linea/40 align-top">
                      <td className="px-2 py-1.5 font-mono text-[12px]">{p.simbolo}</td>
                      <td className="px-2 py-1.5 font-mono text-[10px] text-tenue">{p.clave}</td>
                      <td className="px-2 py-1.5 text-right font-mono">
                        {typeof p.valor === "number" ? num(p.valor) : String(p.valor)}
                      </td>
                      <td className="px-2 py-1.5 text-tenue">{p.unidad}</td>
                      <td className="px-2 py-1.5">
                        <span className="rounded px-1.5 py-px text-[10px]"
                              style={{ background: (ESTADOS[p.estado]?.[0] || "#666") + "22",
                                       color: ESTADOS[p.estado]?.[0] || "#999" }}>
                          {p.estado}
                        </span>
                      </td>
                      <td className="px-2 py-1.5 text-[10.5px] leading-snug text-tenue">
                        {p.nota}
                        {p.fuente && p.fuente !== "-" && (
                          <span className="mt-0.5 block italic opacity-70">{p.fuente}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <button onClick={() => setVerTodos((v) => !v)}
                className="w-full border-t border-linea py-1.5 text-[11px] text-tenue hover:bg-panel2">
                {verTodos ? "mostrar menos" : `ver las ${params.length} variables`}
              </button>
            </div>
          </Sec>

          {/* ------------------------------------------------ 12 */}
          {nube && (
            <Sec n="14." titulo="Reproducibilidad">
              <P>
                Todo lo de arriba sale de esta configuración exacta, guardada junto
                a los resultados en la base. El barrido completo se reproduce con:
              </P>
              <pre className="my-2 overflow-x-auto rounded-md border border-linea bg-[#0b0f18]
                              px-3 py-2 font-mono text-[10.5px] text-[#9ecbf5]">
{`py -3.12 experimentos/correlacion.py -n 300 \\
    --aforos 2000 3000 4000 --modos amplio estricto
py -3.12 experimentos/analisis.py`}
              </pre>
              <div className="grid grid-cols-2 gap-x-6 rounded-lg border border-linea
                              bg-panel p-3 font-mono text-[10.5px]">
                {Object.entries(cfg).sort().map(([k, v]) => (
                  <div key={k} className="flex justify-between border-b border-linea/30 py-0.5">
                    <span className="text-tenue">{k}</span>
                    <span>{typeof v === "number" ? num(v) : String(v)}</span>
                  </div>
                ))}
              </div>
            </Sec>
          )}

          {/* ------------------------------------------------ 13 */}
          <Sec n="15." titulo="Lo que este experimento NO dice">
            <ul className="my-2 space-y-1.5 text-[12.5px] leading-relaxed text-[#c3ccda]">
              {[
                <><b>Una sola geometría.</b> Nave rectangular de 100×60 m con 4 salidas repartidas y 2 obstáculos fijos. Los resultados podrían ser de esta planta.</>,
                <><b>Reparto inicial uniforme.</b> Está medido que es el caso que MENOS discrimina entre layouts: con la multitud concentrada frente a un escenario las diferencias suben a 5–15 %.</>,
                <><b>El layout solo importa si el recinto no está lleno.</b> Al aforo de diseño (19 908 personas) la cota física de las puertas es de 563 s y todo layout se clava ahí. Por eso el aforo es un eje del barrido y no un dato.</>,
                <><b>Las unidades de atención por módulo siguen PENDIENTE.</b> <Ei t="f_1" /> depende de ellas: el método es correcto, los números son provisionales.</>,
                <><b>El exponente <Ei t="p" /> no tiene respaldo empírico.</b> Medido: al variarlo de 1 a 4 el orden de <Ei t="t_{\text{des}}" /> cae a 0.373 y el de <Ei t="E" /> aguanta en 0.573.</>,
              ].map((t, i) => (
                <li key={i} className="flex gap-2">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-tenue" />
                  <span>{t}</span>
                </li>
              ))}
            </ul>
          </Sec>

          <div className="h-10" />
        </div>
      </div>

      {/* ========================= EXPLORADOR DE LAYOUT ========================= */}
      <div className="min-w-0 overflow-y-auto border-l border-linea bg-panel/40 p-3">
        {!detalle ? (
          <div className="rounded-lg border border-dashed border-linea p-6 text-center">
            <p className="text-[12px] text-tenue">
              Haz clic en cualquier punto de la nube (§9) para ver ese layout, sus
              métricas y su simulación.
            </p>
          </div>
        ) : (
          <>
            <div className="rounded-lg border border-linea bg-panel">
              <div className="flex items-center gap-2 border-b border-linea px-3 py-1.5">
                <span className="text-[11.5px] font-semibold">
                  {detalle.etiqueta || `Layout #${detalle.i ?? "?"}`}
                </span>
                <span className="ml-auto text-[10.5px]">
                  {detalle.factible
                    ? <span className="text-verde">pasa la capa geométrica</span>
                    : <span className="text-ambar">violación {num(detalle.metricas.violacion)}</span>}
                </span>
              </div>
              <div className="p-2">
                {/* que funcion objetivo se esta viendo sobre la misma planta */}
                <div className="mb-2 flex rounded-md border border-linea bg-panel2 p-0.5">
                  {[["f2", "f₂ evacuación", Users], ["f1", "f₁ acceso", Route]]
                    .map(([k, t, I]) => (
                    <button key={k} onClick={() => setCapa(k)}
                      className={`flex flex-1 items-center justify-center gap-1.5 rounded
                                  px-2 py-1 text-[11px] transition-colors ${
                        capa === k ? "bg-[#12243a] text-[#9ecbf5]"
                                   : "text-tenue hover:text-texto"}`}>
                      <I size={12} /> {t}
                    </button>
                  ))}
                </div>

                <div className="h-[215px] overflow-hidden rounded border border-linea">
                  <Mapa catalogo={catalogo} recinto={detalle.recinto}
                        layout={detalle.layout}
                        sim={capa === "f2" ? sim : null} cuadro={cuadro} lut={lut}
                        vista={capa === "f1" ? "acceso" : undefined}
                        acceso={acceso} tipoAcceso={tipoAcc}
                        verRejilla={false}
                        etiqueta={capa === "f1"
                          ? (acceso ? `reparto de ${tipoAcc}` : "calculando el reparto…")
                          : sim
                            ? `t = ${num(sim.t[Math.min(cuadro, sim.t.length - 1)] ?? 0, 1)} s`
                            : "planta"} />
                </div>

                {capa === "f1" ? (
                  <>
                    <div className="mt-2 flex flex-wrap items-center gap-1">
                      <span className="mr-1 text-[10.5px] text-tenue">tipo</span>
                      {(catalogo.areas || []).map((a) => (
                        <button key={a.clave} onClick={() => setTipoAcc(a.clave)}
                          disabled={!acceso?.tipos?.[a.clave]}
                          className={`rounded border px-1.5 py-0.5 text-[10.5px]
                                      disabled:opacity-30 ${
                            tipoAcc === a.clave ? "border-[#4C9BE8] text-[#9ecbf5]"
                              : "border-linea text-tenue hover:border-[#3d4757]"}`}>
                          <span className="mr-1 inline-block h-2 w-2 rounded-sm align-middle"
                                style={{ background: a.color }} />
                          {a.clave}
                        </button>
                      ))}
                    </div>
                    {acceso?.tipos?.[tipoAcc] && (
                      <table className="mt-2 w-full text-[10.5px]">
                        <thead className="text-tenue">
                          <tr className="border-b border-linea">
                            <th className="py-0.5 text-left font-normal">módulo</th>
                            <th className="py-0.5 text-right font-normal">carga</th>
                            <th className="py-0.5 text-right font-normal">capacidad</th>
                          </tr>
                        </thead>
                        <tbody>
                          {acceso.tipos[tipoAcc].modulos.map((m, i) => {
                            const c = variantesColor(
                              catalogo.areas.find((a) => a.clave === tipoAcc)?.color
                              || "#4C9BE8", acceso.tipos[tipoAcc].modulos.length)[i];
                            return (
                              <tr key={i} className="border-b border-linea/30">
                                <td className="py-0.5">
                                  <span className="mr-1.5 inline-block h-2 w-3 rounded-sm align-middle"
                                        style={{ background: `rgb(${c[0]},${c[1]},${c[2]})` }} />
                                  #{m}
                                </td>
                                <td className="py-0.5 text-right font-mono">
                                  {pct(acceso.tipos[tipoAcc].carga[i])}
                                </td>
                                <td className="py-0.5 text-right font-mono text-tenue">
                                  {pct(acceso.tipos[tipoAcc].capacidad[i])}
                                </td>
                              </tr>);
                          })}
                        </tbody>
                      </table>
                    )}
                    <p className="mt-1.5 text-[10px] leading-snug text-tenue">
                      Cada celda del color del módulo que la atiende, más oscura
                      cuanto más lejos queda. <b>Las fronteras no son las del
                      módulo más cercano</b>: uno saturado le cede celdas a su
                      vecino aunque quede más lejos. Esa frontera desplazada es lo
                      que distingue la asignación capacitada de una de cercanía.
                    </p>
                  </>
                ) : (
                  <>
                    <div className="mt-2 flex items-center gap-2">
                      <button onClick={sim ? () => setReproduciendo((r) => !r) : simular}
                        disabled={simulando}
                        className="flex items-center gap-1.5 rounded-md border border-linea
                                   bg-panel2 px-2.5 py-1.5 text-[11.5px] hover:border-[#3d4757]
                                   disabled:opacity-50">
                        {simulando ? <Loader2 size={12} className="animate-spin" />
                         : reproduciendo ? <Pause size={12} /> : <Play size={12} />}
                        {simulando ? "simulando…" : sim
                          ? (reproduciendo ? "pausa" : "reproducir") : "simular evacuación"}
                      </button>
                      {sim && (<>
                        <input type="range" min={0.25} max={4} step={0.25} value={velocidad}
                               onChange={(e) => setVelocidad(+e.target.value)} className="w-16" />
                        <span className="font-mono text-[10.5px] text-tenue">{velocidad}×</span>
                      </>)}
                    </div>
                    {sim && (
                      <input type="range" min={0} max={nCuadros(sim) - 1} value={cuadro}
                             onChange={(e) => { setReproduciendo(false); setCuadro(+e.target.value); }}
                             className="mt-2 w-full" />
                    )}
                    <p className="mt-1.5 text-[10px] leading-snug text-tenue">
                      Se anima con el mismo Δt, k_c y aforo con que se midió. Con otra
                      discretización la película no correspondería a los números.
                    </p>
                  </>
                )}
              </div>
            </div>

            {nube && (
              <div className="mt-3 rounded-lg border border-linea bg-panel p-3">
                <div className="mb-1.5 text-[11.5px] font-semibold">Sus métricas</div>
                <table className="w-full text-[11.5px]">
                  <tbody>
                    {nube.metricas.map((m) => {
                      const v = detalle.metricas[m.clave];
                      const ps = nube.puntos.map((p) => p[m.clave])
                        .filter((z) => z !== null).sort((a, b) => a - b);
                      const q = v === null || v === undefined ? null
                        : Math.round(100 * ps.filter((z) => z < v).length / Math.max(1, ps.length));
                      return (
                        <tr key={m.clave} className="border-b border-linea/40">
                          <td className="py-1 text-tenue">{m.nombre}</td>
                          <td className="py-1 text-right font-mono">
                            {num(v)} <span className="text-tenue">{m.unidad}</span>
                          </td>
                          <td className="w-16 py-1 pl-2">
                            {q !== null && (
                              <div className="flex items-center gap-1">
                                <div className="h-1 flex-1 rounded bg-panel2">
                                  <div className="h-1 rounded bg-[#4C9BE8]"
                                       style={{ width: `${q}%` }} />
                                </div>
                                <span className="w-6 text-right text-[9.5px] text-tenue">{q}%</span>
                              </div>
                            )}
                          </td>
                        </tr>);
                    })}
                  </tbody>
                </table>
                <p className="mt-1.5 text-[10px] text-tenue">
                  La barra es el percentil dentro de este escenario: 0 % = el mejor
                  de los {nube.n}.
                </p>
              </div>
            )}

            {!!Object.keys(detalle.f1_detalle || {}).length && (
              <div className="mt-3 rounded-lg border border-linea bg-panel p-3">
                <div className="mb-1.5 text-[11.5px] font-semibold">f₁ por tipo de módulo</div>
                <table className="w-full text-[11.5px]">
                  <thead className="text-tenue">
                    <tr className="border-b border-linea">
                      <th className="py-1 text-left font-normal">tipo</th>
                      <th className="py-1 text-right font-normal">n</th>
                      <th className="py-1 text-right font-normal">dist. media</th>
                      <th className="py-1 text-right font-normal">peso</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(detalle.f1_detalle).map(([t, d]) => (
                      <tr key={t} className="border-b border-linea/40">
                        <td className="py-1">
                          <span className="mr-1.5 inline-block h-2 w-2 rounded-sm align-middle"
                            style={{ background: catalogo.areas.find((a) => a.clave === t)?.color }} />
                          {catalogo.areas.find((a) => a.clave === t)?.nombre ?? t}
                        </td>
                        <td className="py-1 text-right font-mono">{d.n}</td>
                        <td className="py-1 text-right font-mono">{num(d.d_media)} m</td>
                        <td className="py-1 text-right font-mono text-tenue">{d.peso}</td>
                      </tr>))}
                  </tbody>
                </table>
                <p className="mt-1.5 text-[10px] leading-snug text-tenue">
                  El peso es la capacidad instalada del tipo (unidades de atención):
                  un tipo con el doble de unidades atiende al doble de gente y pesa
                  el doble en f₁.
                </p>
              </div>
            )}
          </>
        )}
        {err && (
          <div className="mt-3 rounded-md border border-rojo/40 bg-rojo/10 px-3 py-2
                          text-[11.5px] text-rojo">{err}</div>
        )}
      </div>
    </div>
    </ProveedorGlosario>
  );
}
