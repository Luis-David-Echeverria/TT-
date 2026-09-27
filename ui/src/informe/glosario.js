/* Glosario de notación del informe.
 *
 * Cada símbolo que aparece en una ecuación tiene aquí su nombre, qué significa
 * en palabras y su unidad. Los que además son parámetros del modelo llevan
 * `clave`: con ella se lee el VALOR y la PROCEDENCIA del registro de Python, en
 * vez de repetirlos aquí y arriesgarse a que se desvíen.
 *
 * Lo que vive en este archivo es notación —cómo se llama cada cosa—, no el
 * modelo. El modelo sigue siendo Python.
 */
export const GLOSARIO = {
  /* --- diagrama fundamental --- */
  v0:      { tex: "v_0", nombre: "velocidad libre", unidad: "m/s", clave: "V0",
             que: "A qué velocidad camina una persona cuando no tiene a nadie estorbándole." },
  rho_max: { tex: "\\rho_{\\max}", nombre: "densidad de atasco", unidad: "pers/m²", clave: "RHO_MAX",
             que: "La densidad a la que ya nadie avanza. Es el techo físico: no cabe más gente." },
  gamma:   { tex: "\\gamma", nombre: "parámetro de forma", unidad: "pers/m²", clave: "GAMMA",
             que: "Qué tan rápido cae la velocidad al apretujarse la gente. Sale del ajuste de Weidmann." },
  rho:     { tex: "\\rho", nombre: "densidad", unidad: "pers/m²",
             que: "Cuánta gente hay por metro cuadrado en un punto y un instante." },
  v:       { tex: "v(\\rho)", nombre: "velocidad de marcha", unidad: "m/s",
             que: "A qué velocidad camina la gente con esa densidad. Baja al apretujarse." },
  q:       { tex: "q(\\rho)", nombre: "flujo específico", unidad: "pers/(m·s)",
             que: "Cuántas personas cruzan un metro de ancho por segundo. Tiene un máximo: más densidad no da más flujo." },
  q_max:   { tex: "q_{\\max}", nombre: "flujo máximo", unidad: "pers/(m·s)", clave: "Q_MAX",
             que: "La capacidad del diagrama fundamental. NO se pone a mano: es el máximo de ρ·v(ρ)." },
  rho_cap: { tex: "\\rho_{\\text{cap}}", nombre: "densidad de capacidad", unidad: "pers/m²", clave: "RHO_CAP",
             que: "La densidad que produce el flujo máximo. Separa el régimen libre del congestionado." },
  rho_c:   { tex: "\\rho_c", nombre: "densidad crítica", unidad: "pers/m²", clave: "RHO_PERDIDA_CONTROL",
             que: "Por encima de aquí una persona pierde el movimiento propio y la desplaza la presión del grupo. Es la precondición del aplastamiento." },
  rho_d:   { tex: "\\rho_d", nombre: "densidad de diseño", unidad: "pers/m²", clave: "RHO_DISENO",
             que: "La densidad con la que se calcula el aforo de referencia del recinto." },

  /* --- campos y geometría --- */
  T:       { tex: "T(x)", nombre: "tiempo de llegada", unidad: "s",
             que: "Cuántos segundos faltan para salir desde ese punto. Su gradiente dice hacia dónde caminar." },
  Omega:   { tex: "\\Omega", nombre: "zona ocupable", unidad: "celdas",
             que: "El piso al que la gente puede llegar de verdad circulando con el ancho normativo, partiendo de una salida." },
  L:       { tex: "L", nombre: "piso libre", unidad: "celdas",
             que: "Todo lo que no es muro ni módulo. Más amplio que la zona ocupable: incluye recovecos a los que no se entra." },
  Br:      { tex: "B_r", nombre: "disco de radio r", unidad: "celdas",
             que: "La forma con que se erosiona y se dilata. Su radio es medio ancho de circulación." },
  h:       { tex: "h", nombre: "lado de celda", unidad: "m", clave: "H_CELDA",
             que: "El tamaño de cada cuadrito de la rejilla. La unidad física del modelo es el metro cuadrado." },
  w_min:   { tex: "w_{\\min}", nombre: "ancho libre mínimo", unidad: "m", clave: "ANCHO_LIBRE_MIN",
             que: "El ancho de circulación que exige el reglamento. Lo que no se puede recorrer con ese ancho no cuenta como área útil." },

  /* --- salidas y aforo --- */
  N:       { tex: "N", nombre: "aforo de referencia", unidad: "pers",
             que: "Cuánta gente hay dentro al empezar la evacuación. Es la misma para todos los layouts, a propósito." },
  J_s:     { tex: "J_s", nombre: "flujo específico de salida", unidad: "pers/(s·m)", clave: "J_ESPECIFICO",
             que: "Cuántas personas por segundo pasan por cada metro de ancho útil de una puerta." },
  b:       { tex: "b", nombre: "capa límite", unidad: "m", clave: "CAPA_LIMITE",
             que: "La franja pegada a cada jamba que la gente no usa. El ancho útil de una puerta es el real menos dos veces esto." },
  t_min:   { tex: "t_{\\min}", nombre: "cota de las puertas", unidad: "s",
             que: "Lo más rápido que se puede vaciar el recinto, dado el ancho total de salidas. Ningún layout baja de ahí." },

  /* --- esquema numérico --- */
  dt:      { tex: "\\Delta t", nombre: "paso de tiempo", unidad: "s", clave: "DT",
             que: "Cada cuánto avanza la simulación. Tiene que cumplir la condición CFL o el esquema se vuelve inestable." },
  k_c:     { tex: "k_c", nombre: "refresco del campo", unidad: "pasos", clave: "REFRESCO_CAMPO",
             que: "Cada cuántos pasos se vuelve a resolver hacia dónde camina la gente. Resolverlo es lo caro." },
  p:       { tex: "p", nombre: "exponente de reparto", unidad: "—", clave: "EXP_REPARTO",
             que: "Cómo se reparte el flujo de una celda entre sus vecinos cuesta abajo. Es el ÚNICO parámetro del modelo sin respaldo empírico." },
  eps:     { tex: "\\varepsilon", nombre: "tolerancia de vaciado", unidad: "—", clave: "EPS_VACIADO",
             que: "Qué fracción puede quedar dentro para dar el recinto por vacío. Existe porque la masa decae de forma asintótica." },
  sigma_k: { tex: "\\sigma_k", nombre: "ancho del núcleo", unidad: "celdas", clave: "SIGMA_KERNEL",
             que: "Con qué suavidad se estima la densidad continua a partir de la masa discreta. Es parte del estimador, no un filtro de dibujo." },
  D:       { tex: "D(\\rho)", nombre: "demanda", unidad: "pers/(m·s)",
             que: "Lo que una celda QUIERE mandar río abajo. No cae a cero al atascarse: la gente apretujada avanza si el de adelante se movió." },
  S:       { tex: "S(\\rho)", nombre: "oferta", unidad: "pers/(m·s)",
             que: "Lo que una celda PUEDE recibir. Es lo que cae al llenarse, y por eso la cola se forma por el que recibe." },

  /* --- accesibilidad --- */
  f1:      { tex: "f_1", nombre: "accesibilidad", unidad: "m",
             que: "Distancia media que camina una persona hasta el módulo que la atiende, midiendo por donde se puede caminar." },
  d_ij:    { tex: "d_{ij}", nombre: "distancia caminando", unidad: "m",
             que: "De la celda i al módulo j, rodeando muros y otros módulos. No es en línea recta." },
  q_i:     { tex: "q_i", nombre: "demanda de la celda", unidad: "—",
             que: "Cuánta gente de esa celda va a necesitar el servicio. Con reparto uniforme, igual en todas." },
  c_j:     { tex: "c_j", nombre: "capacidad del módulo", unidad: "—",
             que: "Qué fracción de la demanda puede absorber ese módulo. Sale de sus unidades de atención." },
  y_ij:    { tex: "y_{ij}", nombre: "fracción asignada", unidad: "—",
             que: "Qué parte de la demanda de la celda i se atiende en el módulo j. Es lo que resuelve el problema de transporte." },
  w_t:     { tex: "w_t", nombre: "peso del tipo", unidad: "unidades",
             que: "Cuánto pesa cada tipo de servicio en f₁: proporcional a su capacidad instalada total." },
  sigma:   { tex: "\\sigma", nombre: "saturación", unidad: "—", clave: "SATURACION",
             que: "Qué fracción de la capacidad instalada se usa. Con 1.0 todos los módulos trabajan a tope, que es el caso que más discrimina." },

  /* --- evacuación y análisis --- */
  t_evac:  { tex: "t_{\\text{evac}}", nombre: "tiempo de evacuación", unidad: "s",
             que: "Segundo en que el recinto queda vacío. Sale de la simulación, no de una fórmula de distancias." },
  t95:     { tex: "t_{95}", nombre: "tiempo del 95 %", unidad: "s",
             que: "Cuándo ha salido el 95 % del aforo. Si queda lejos del total, un sector se rezagó." },
  E:       { tex: "E", nombre: "exposición", unidad: "m²·s",
             que: "Cuánto piso, y por cuánto tiempo, estuvo por encima de la densidad crítica." },
  rho_pico:{ tex: "\\rho_{\\text{pico}}", nombre: "densidad pico", unidad: "pers/m²",
             que: "La densidad más alta alcanzada en cualquier celda y momento." },
  rho_s:   { tex: "\\rho_s", nombre: "correlación de rangos", unidad: "—",
             que: "Qué tanto coincide el ORDEN de los layouts según dos medidas. Va de −1 a +1." },
  Hn:      { tex: "H_n", nombre: "número armónico", unidad: "—",
             que: "1 + 1/2 + … + 1/n. Con dos objetivos independientes, es el número esperado de soluciones no dominadas." },
};
