/* Secciones de método: el problema, la preparación del recinto y las
 * restricciones. Describen lo que está IMPLEMENTADO, no lo que se planea. */
import { Ec, Nota, Origen, P, Sec, Simbolos, Sub, Tabla, V } from "./comun";
import DemoErosion from "./demos/Erosion";

export function SecProblema({ catalogo }) {
  const areas = catalogo?.areas || [];
  return (
    <Sec n="1." titulo="El problema y qué decide el sistema">
      <P>
        Dado un recinto con sus muros y sus salidas, y un conjunto de módulos de
        servicio, encontrar dónde colocarlos. El usuario dice <b>cuántos</b>
        {" "}módulos de cada tipo quiere; <b>dónde van lo decide el sistema</b>.
      </P>
      <P>
        El problema vive en el cruce de tres literaturas, y cada una aporta una
        pieza que las otras no tienen:
      </P>
      <ul className="my-2 space-y-1.5 text-[12.5px] leading-relaxed text-[#c3ccda]">
        <li className="flex gap-2">
          <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-tenue" />
          <span><b>Facility Layout Problem</b> — la geometría: cómo acomodar áreas de
          tamaño desigual sin traslapes. Es NP-duro, y eso es lo que justifica
          usar metaheurísticas en vez de enumerar.</span>
        </li>
        <li className="flex gap-2">
          <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-tenue" />
          <span><b>Localización de instalaciones</b> — la accesibilidad: la p-mediana
          capacitada (Hakimi, 1964), que es exactamente f₁.</span>
        </li>
        <li className="flex gap-2">
          <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-tenue" />
          <span><b>Dinámica de peatones</b> — lo que ninguna de las dos tiene:
          congestión. El layout industrial no la modela porque los montacargas no
          se aplastan entre sí, y la localización clásica supone que la demanda
          llega sin estorbarse.</span>
        </li>
      </ul>

      <Sub>1.1 Qué da el usuario y qué se calcula</Sub>
      <Tabla
        cols={["Entidad", "Lo que define el usuario", "¿Es variable de decisión?"]}
        filas={[
          ["Recinto", "Forma y dimensiones", "no"],
          ["Salidas", "Posición y ancho sobre el perímetro", "no — estructurales y dictaminadas"],
          ["Muros y obstáculos", "Los dibuja sobre la planta", "no"],
          ["Módulos de servicio", `Cuántos de cada tipo (${areas.map((a) => a.clave).join(", ")})`,
           <b key="v">sí: posición y rotación</b>],
          ["Área transitable", "No la define: se calcula (§2.1)", "no"],
        ]}
      />
      <P>
        Todo lo que se le pide se puede <b>contar o medir</b>: cuántos módulos,
        de qué tipo. Nada que tenga que estimar, como tiempos de cola o tasas de
        visita — de hecho una versión anterior de f₁ los pedía y se descartó
        justamente por eso (§6.1).
      </P>

      <Nota>
        <b>¿Por qué las salidas no se optimizan?</b> Las salidas de un recinto
        real son parte de la estructura del inmueble y están dictaminadas por
        Protección Civil. Un organizador no puede moverlas. Si el sistema las
        optimizara estaría resolviendo un problema de diseño arquitectónico, y
        su resultado no sería aplicable por quien lo usa.
      </Nota>

      <Nota>
        <b>¿Por qué un módulo es obstáculo y destino a la vez?</b> Para colisión
        y navegación, un puesto es idéntico a un muro. Pero además es destino, y
        el destino son las <b>celdas libres pegadas a él</b>: la gente llega a la
        barra, no al centro del puesto. Sembrar el campo de distancias ahí hace
        que un módulo con su frente contra un muro se castigue solo, sin reglas
        adicionales (§6.2).
      </Nota>
    </Sec>
  );
}

export function SecPreparacion({ cfg, catalogo, recinto, layout }) {
  const v = {};
  for (const p of catalogo?.parametros || []) v[p.clave] = p.valor;
  return (
    <Sec n="2." titulo="Preparación del recinto">
      <P>
        Antes de evaluar nada hay que saber qué piso se puede usar de verdad y
        cuánta gente cabe. Las dos cosas se calculan del recinto, no se preguntan.
      </P>

      <Sub>2.1 Zona ocupable: el piso al que se puede llegar circulando</Sub>
      <P>
        No basta con que una celda esté libre: tiene que poder <em>alcanzarse</em>
        {" "}desde una salida circulando con el ancho normativo. El cálculo erosiona
        el piso libre por medio ancho de circulación, se queda con la parte de esa
        red conectada a una salida, y la vuelve a dilatar:
      </P>
      <Ec t={String.raw`\Omega = \Big[\big(L \ominus B_{r}\big)\big|_{\text{conexo a salidas}}\Big]
            \oplus B_{r} \;\cap\; L,
            \qquad r = \frac{w_{\min}}{2h} = ${Math.max(1, Math.round((v.ANCHO_LIBRE_MIN ?? 3) / 2))}\ \text{celdas}`} />
      <Simbolos ks={["Omega", "L", "Br", "w_min", "h"]} />
      <P>
        En palabras: se encoge el piso libre por medio ancho de pasillo, se
        conserva lo que sigue conectado a una salida, y se vuelve a inflar. Los
        símbolos <V k="Omega" />, <V k="L" /> y <V k="Br" /> llevan su
        significado encima — pasa el cursor por cualquiera.
      </P>

      {recinto && layout && (
        <DemoErosion recinto={recinto} layout={layout} />
      )}
      <Nota tono="clave">
        <b>Un recoveco detrás de un puesto no es una infracción: es superficie
        que no se puede usar.</b> Esa distinción resolvió un problema real. La
        primera versión contaba esos huecos como violación de seguridad y
        rechazaba el 87 % de las colocaciones. Al reformularlo —lo que no se
        puede pisar con el ancho de reglamento simplemente sale del área útil—
        la tasa de aceptación subió al 88 % sin relajar ningún criterio.
      </Nota>

      <Sub>2.2 Aforo de referencia</Sub>
      <P>
        Para evaluar la evacuación hay que fijar cuánta gente hay, y tiene que
        ser <b>la misma para todos los layouts</b>: si variara, encerrar espacio
        quitaría gente y «mejoraría» el tiempo. El optimizador encontraría que
        amurallar el recinto le conviene.
      </P>
      <Ec t={String.raw`N = \rho_d \cdot \big(|\Omega| - A_{\text{servicios}}\big)`} />
      <Simbolos ks={["N", "rho_d", "Omega"]} />
      <P>
        Se usa la densidad de diseño <V k="rho_d" /> y no el factor normativo de
        m² por persona porque conecta directo con el régimen físico que simula el
        modelo; el factor normativo sirve de <em>contraste</em> del resultado, no
        de entrada.
      </P>
      <Nota tono="alerta">
        <b>Y aquí hay un hallazgo que cambió el experimento.</b> Con el aforo de
        diseño de este recinto —19 908 personas— la cota física de las puertas es
        de 563 s, y <b>todo layout se clava ahí</b>: el tiempo de evacuación deja
        de distinguir un acomodo de otro. Medido, el CV entre layouts cae de
        11.9 % con 2 000 personas a 1.2 % con 16 000.
        <br /><br />
        O sea: <b>el layout solo importa si el recinto no está lleno</b>. Por eso
        el aforo se trató como un eje del barrido y no como un dato, y por eso
        los resultados de abajo son a {cfg?.aforo ?? 2000} personas.
      </Nota>
      <P>
        La cota de las puertas es aritmética y no necesita simulación:
      </P>
      <Ec t={String.raw`t_{\min} = \frac{N}{\sum_e J_s\,(W_e - 2b)}`} />
      <Simbolos ks={["t_min", "N", "J_s", "b"]} />
      <P>
        Sirve de piso contra el que comparar cualquier tiempo simulado: la
        diferencia entre <V k="t_evac" /> y <V k="t_min" /> es{" "}
        <b>lo que el layout le cuesta a la evacuación</b>.
      </P>
      <Nota>
        <b>Cuidado con la cifra de 40 s</b> que circula como tiempo de desalojo.
        Para 5 000 personas en 40 s harían falta 95 m de salida útil; para
        20 000, 379 m — más que el perímetro completo de una nave de 100×60 m. No
        puede referirse al desalojo total de un evento masivo.
      </Nota>
    </Sec>
  );
}

export function SecRestricciones() {
  return (
    <Sec n="3." titulo="Restricciones, y de dónde sale cada una">
      <P>
        No todas vienen de la ley, y separarlas por origen es lo que permite
        defenderlas. Las <Origen tipo="legal" /> no se discuten: sin ellas el
        evento no se autoriza. Las <Origen tipo="consistencia" /> son condiciones
        sin las cuales el modelo no tiene sentido físico. Las{" "}
        <Origen tipo="diseno" /> son umbrales que el organizador elige; si
        alguien las cuestiona, la respuesta es que son configurables, no que la
        norma las exige.
      </P>
      <Nota tono="alerta">
        Presentar un umbral de diseño como si fuera legal es el error más fácil
        de señalar en una revisión, y por eso la tabla lleva la columna.
      </Nota>
      <Tabla
        cols={["", "Qué verifica", "Origen", "Cómo se mide"]}
        filas={[
          ["G1", "El módulo cabe dentro del recinto", <Origen key="1" tipo="consistencia" />, "geometría"],
          ["G2", "No se encima con otro módulo", <Origen key="2" tipo="consistencia" />, "geometría"],
          ["G3", "No está encima de un muro o elemento fijo", <Origen key="3" tipo="consistencia" />, "rasterización"],
          ["G4", "No invade el área de descarga de una salida", <Origen key="4" tipo="legal" />, "conos de salida"],
          ["G5", "No inutiliza más de una fracción del área útil", <Origen key="5" tipo="diseno" />, "zona ocupable (§2.1)"],
          ["G6", "Se puede llegar al módulo: tiene frente accesible", <Origen key="6" tipo="consistencia" />, "frente sobre la zona ocupable"],
        ]}
      />
      <Nota tono="clave">
        <b>G6 no estaba al principio y hubo que agregarla.</b> El sistema colocó
        un módulo sanitario dentro de una bolsa sellada por los muros que había
        dibujado el usuario: no pisaba nada, no invadía ningún cono, y como esa
        bolsa ya era inservible tampoco reducía el área útil. <b>Pasaba las cinco
        reglas anteriores siendo un baño al que nadie podía entrar.</b>
      </Nota>

      <Sub>3.1 Duras, pero no eliminatorias durante la búsqueda</Sub>
      <P>
        «Duras» significa que ninguna solución final puede violarlas. No
        significa que se eliminen mientras se busca, y la diferencia importa: si
        al arrancar la mayoría falla y se descartan, todos los supervivientes
        valen lo mismo, no hay gradiente y la búsqueda se queda ciega.
      </P>
      <Nota>
        <b>Lo medimos, y el resultado no fue el que esperábamos.</b> Comparando
        muestreo por rechazo contra las reglas de factibilidad de Deb (2000) con
        el mismo presupuesto: <b>empatan</b>. La diferencia quedó dentro del ruido
        de tres semillas y el tiempo fue el mismo. Probablemente porque aquí la
        región factible es amplia y bien conectada, así que el rechazo casi nunca
        bloquea un camino que importe.
        <br /><br />
        Se usará dominancia restringida igual —en multiobjetivo hace falta de
        todos modos— pero <b>no se puede presentar como una mejora de
        rendimiento</b>, porque no lo es.
      </Nota>
      <P>
        Donde el filtrado <em>sí</em> hace daño es al <b>medir</b>, y eso está en
        §7: recortar la muestra por factibilidad antes de correlacionar induce
        una correlación que en la población sin filtrar no existe.
      </P>
    </Sec>
  );
}
