# Prototipo de sistema para la distribución óptima de áreas de servicio en eventos masivos mediante algoritmos bioinspirados

**Trabajo Terminal 2027-A126**
Echeverría Pérez Luis David · Martínez Meneses Monserrat Alejandra
Directores: Dr. Daniel Molina Pérez · Dr. Jacobo Torres Figueroa

---

## 1. Introducción

En un evento masivo, la ubicación de sanitarios, puestos de comida, barras de
bebidas y módulos de primeros auxilios suele decidirse por experiencia. Esa
decisión afecta dos cosas: qué tanto camina la gente para llegar a los servicios
y qué tan rápido puede salir en una emergencia. Este trabajo desarrolla un
prototipo que propone dónde colocar esas áreas considerando ambos criterios y
las restricciones de seguridad aplicables en la Ciudad de México.

Como primer paso se comprobó que el problema es multiobjetivo: al comparar
accesibilidad y tiempo de evacuación sobre cientos de distribuciones, ninguna
resultó la mejor en ambos criterios, y optimizar solo uno deja al otro sin
control. Con base en ello se seleccionó un algoritmo genético multiobjetivo.

---

## 2. Planteamiento del problema

La organización de eventos masivos requiere distribuir el espacio de manera
adecuada para asegurar la seguridad de quienes asisten. Cuando se junta una gran
cantidad de personas en un lugar delimitado, decidir la ubicación de las áreas de
servicio resulta muy importante para el movimiento dentro del recinto.

Sin embargo, la planeación de estas áreas suele realizarse sin un análisis
previo. Esta situación genera dos problemas principales: las personas tienen que
caminar mucho para llegar a los servicios, y se generan aglomeraciones que
dificultan y hacen más lenta una evacuación en caso de emergencia.

### 2.1 Justificación

Los desastres de multitud rara vez son accidentales: se originan en factores de
diseño y de gestión del espacio, como la sobrepoblación o una disposición
inadecuada del recinto [1]. La mayoría de las víctimas no se deben a estampidas
por pánico, sino a la compresión que se produce cuando la densidad es tan alta que
las personas no pueden moverse ni respirar, fenómeno que aparece por la sola
acumulación de gente [1], [2]. Por depender de la densidad y la geometría, es un
riesgo que puede prevenirse desde el diseño. El incendio de la discoteca Kiss en
Santa María, Brasil, en 2013, es un ejemplo de sus consecuencias [3].

En la Ciudad de México, los eventos con aforo a partir de 500 personas requieren
un Programa Especial de Protección Civil, y los de más de 10,000 asistentes se
consideran eventos masivos [4, art. 73]. Ese programa debe analizar, entre otros
riesgos, el que representan las instalaciones provisionales para los asistentes
[4, art. 74], que es justamente lo que son las áreas de servicio. A nivel federal,
la NOM-002-STPS-2010 exige que rutas y salidas de evacuación estén libres de
obstáculos y que ningún punto quede a más de 40 m de la ruta de evacuación; si se
excede esa distancia, el desalojo debe completarse en un máximo de tres minutos
[5, nums. 7.15 y 7.16]. Además, el PROY-NOM-011-SSPC-2025 busca regular los
requisitos de protección civil y los aforos máximos en eventos masivos [6].

La normativa pide analizar el riesgo, pero no dice cómo verificarlo. Esa
verificación requiere simular el flujo de personas, y sus resultados no son
evidentes: en el recinto de prueba de este trabajo, una nave de 100×60 m con
cuatro salidas, parte del piso queda a más de 40 m de la salida más cercana, por
lo que aplica el límite de tres minutos; y a su aforo de diseño de 19,908
personas, las puertas por sí solas imponen un desalojo mínimo de 563 s, de modo
que ningún acomodo interior podría cumplirlo.

La innovación del proyecto está en integrar un algoritmo bioinspirado con una
simulación de multitud, de forma que la distribución se elija evaluando cómo se
mueve la gente y no solo la geometría. Asimismo, se emplea la plataforma Unity
para la visualización de la simulación en un entorno bidimensional para recintos
de una sola planta.

### 2.2 Alcances y limitaciones

**Alcances**

- Recintos de una sola planta, abiertos o cerrados: salones de fiestas, centros
  de convenciones, naves industriales o explanadas.
- Interfaz para trazar muros, obstáculos, accesos y salidas, y para configurar la
  cantidad y el tipo de áreas de servicio.
- Generación de un conjunto de distribuciones de compromiso entre accesibilidad y
  tiempo de evacuación, de entre las cuales el usuario elige.

**Limitaciones**

- No contempla espacios tridimensionales ni edificaciones de varias plantas.
- Se limita a la normativa aplicable en la Ciudad de México.
- La multitud se modela como un fluido, por lo que no representa conductas
  individuales como pánico, grupos que se buscan o personas con movilidad
  reducida.
- Las pruebas se realizaron sobre un solo recinto y suponiendo a la gente
  repartida de forma uniforme al iniciar la evacuación.
- Algunos parámetros siguen siendo provisionales mientras se confirma su fuente
  (sección 5.2).

### 2.3 Objetivos

**Objetivo general.** Desarrollar un prototipo de sistema de software,
implementando un algoritmo bioinspirado que permita la distribución óptima de
áreas de servicio en espacios de una sola planta para eventos masivos,
considerando restricciones de seguridad en la Ciudad de México.

**Objetivos específicos**

1. Analizar los lineamientos de Protección Civil vigentes para establecer los
   criterios de seguridad aplicables a eventos masivos.
2. Plantear el problema de optimización multiobjetivo para la distribución
   eficiente de las áreas de servicio dentro del recinto.
3. Seleccionar un algoritmo bioinspirado adecuado para resolver el problema de
   optimización planteado.
4. Diseñar la interfaz y la lógica del entorno de simulación en Unity para la
   representación bidimensional (2D).
5. Integrar el algoritmo bioinspirado con el entorno de simulación en Unity para
   visualizar los resultados de la distribución.

---

## 3. Marco teórico

### 3.1 Conceptos fundamentales

**Densidad de multitud.** Número de personas por metro cuadrado. Es la variable
que gobierna el movimiento: a mayor densidad, menor velocidad.

**Diagrama fundamental.** Relación medida entre densidad y velocidad de marcha. Se
usa la de Weidmann [7]:

&nbsp;&nbsp;&nbsp;&nbsp;v(ρ) = v₀ · [ 1 − exp( −γ · (1/ρ − 1/ρ_max) ) ]

con velocidad libre v₀ = 1.34 m/s, γ = 1.913 y densidad máxima ρ_max = 5.4 p/m²,
a la cual la velocidad es cero.

**Distancia geodésica.** La distancia caminando entre dos puntos rodeando muros y
obstáculos, en lugar de la distancia en línea recta.

**Optimización multiobjetivo.** Cuando se optimizan dos criterios a la vez, en
general no existe una solución que sea la mejor en ambos. Las soluciones en las
que no se puede mejorar un criterio sin empeorar el otro forman el **frente de
Pareto**, y el usuario elige entre ellas.

### 3.2 Modelos matemáticos de optimización

**La multitud como fluido.** Simular a cada persona por separado es demasiado
costoso para un algoritmo que debe evaluar miles de distribuciones. Por eso la
multitud se modela como un fluido, siguiendo el modelo de Hughes [8]: la densidad
se mueve por el recinto con la velocidad que le asigna el diagrama de Weidmann, y
en dirección a la salida a la que se llega más rápido con la gente que hay en ese
momento. Ese camino se recalcula cada 2.4 s, así que la multitud rodea las
aglomeraciones y puede cambiar de salida. Así se simulan miles de personas en
milisegundos.

**Hacia dónde camina la gente.** Para cada punto del recinto se calcula el tiempo
mínimo para llegar a una salida resolviendo la ecuación Eikonal,
‖∇T‖ = 1 / v, con el método Fast Marching [9]. La gente se desplaza en la
dirección en que ese tiempo disminuye más rápido. El mismo cálculo, con velocidad
constante, da la distancia geodésica que se usa para la accesibilidad.

**El problema de la velocidad cero.** Con Weidmann, una zona que alcanza la
densidad máxima tiene velocidad cero, y un cálculo directo la deja trabada para
siempre. Se resolvió con el esquema de Godunov [10] en la forma de Daganzo [11],
que van Wageningen-Kessels *et al.* extienden a dos dimensiones para peatones [21]:
entre dos celdas vecinas se compara cuánta gente quiere salir de una con cuánta
cabe en la otra, y pasa el mínimo de ambas. Así una zona saturada sigue
vaciándose hacia donde hay espacio, que es lo que ocurre en una aglomeración real.
Ese mismo trabajo demuestra que, si el paso de tiempo cumple la condición CFL, la
densidad nunca pasa del atasco; con celdas de 1 m y pasos de 0.3 s se cumple con
margen (0.40 m ≤ 0.71 m).

**Accesibilidad con capacidad.** Cada módulo atiende a un número limitado de
personas, así que no todos pueden ir al más cercano. La asignación de cada zona
del recinto a un módulo se resuelve como un problema de transporte con
capacidades, de forma exacta.

### 3.3 Herramientas y tecnologías de apoyo

**Algoritmos bioinspirados.** Métodos de búsqueda que imitan procesos naturales,
como la selección natural. Son adecuados aquí porque el número de distribuciones
posibles es tan grande que no se pueden revisar todas, y porque el tiempo de
evacuación sale de una simulación y no de una fórmula que se pueda resolver
directamente. Se emplea NSGA-II [12], un algoritmo genético multiobjetivo.

**Unity.** Motor de desarrollo de aplicaciones interactivas con soporte 2D [13],
previsto como entorno de visualización de la simulación. En la etapa actual la
interfaz se prototipó en web (React [14] con un servicio en Python mediante
FastAPI [15]) por su integración directa con el núcleo de cálculo, lo que permitió
validar el modelo antes de construir el entorno en Unity.

---

## 4. Estado del arte

### 4.1 Análisis de soluciones existentes

**Simuladores de evacuación.** Herramientas como Pathfinder o MassMotion simulan
el desalojo con gran detalle, pero solo evalúan la configuración que el usuario
propone; no buscan la mejor.

**Optimización de ubicaciones.** Zhong *et al.* optimizan la ubicación de
refugios urbanos minimizando el tiempo de evacuación con un algoritmo genético
multiobjetivo [16], a escala de ciudad y no dentro de un recinto. Li, Cai y Kana
optimizan con algoritmos genéticos el diseño de instalaciones para evacuación
[17]. Nguyen *et al.* usan NSGA-II para acomodar obras de construcción
minimizando distancias y maximizando seguridad [18], un problema parecido al
nuestro pero sin simulación de personas.

**Mobiliario y desalojo.** Li y Chen comparan distintos acomodos de mobiliario en
laboratorios escolares y muestran que la disposición interior cambia los puntos
de congestión durante la evacuación [19], aunque solo comparan unas cuantas
opciones fijas.

**Lo que no existe.** No se encontró un sistema que optimice la ubicación de áreas
de servicio dentro de un recinto considerando a la vez accesibilidad y
evacuación, con simulación de multitud y restricciones de la normativa mexicana.

---

## 5. Análisis, diseño y modelado de la propuesta

### 5.1 Propuesta a desarrollar

El sistema tiene tres partes: un **evaluador** que, dada una distribución,
calcula su accesibilidad y su tiempo de evacuación; un **optimizador** que busca
las mejores distribuciones usando al evaluador; y una **interfaz** para dibujar
el recinto y ver los resultados.

**¿Es realmente multiobjetivo?** Antes de elegir el algoritmo había que saber si
bastaba con optimizar un solo criterio. Se evaluaron 1 776 distribuciones al azar
en seis escenarios y se compararon ambos criterios. La correlación de Spearman
entre ellos quedó entre −0.26 y +0.07: saber qué tan accesible es una
distribución no dice qué tan rápido se evacúa. Después se hizo un barrido de
pesos, optimizando combinaciones de ambos criterios:

| Peso accesibilidad | Peso evacuación | Accesibilidad (m) | Evacuación (s) |
|---|---|---|---|
| 0.0 | 1.0 | 28.569 | 69.0 |
| 0.1 | 0.9 | 21.707 | 66.9 |
| 0.2 | 0.8 | 19.652 | 68.4 |
| 0.3 | 0.7 | 18.928 | 70.2 |
| 0.4 | 0.6 | 18.347 | 69.0 |
| 0.5 | 0.5 | 17.018 | 77.7 |
| 0.6 | 0.4 | 17.108 | 77.1 |
| 0.7 | 0.3 | 16.822 | 77.7 |
| 0.8 | 0.2 | 17.269 | 71.1 |
| 0.9 | 0.1 | 17.030 | 78.6 |
| 1.0 | 0.0 | 16.919 | 77.4 |

Ninguna distribución es la mejor en ambos criterios: la de mejor accesibilidad
tarda más en evacuarse y la de mejor evacuación queda más lejos de los servicios.
Además, optimizar solo la evacuación dejó la accesibilidad en 28.57 m, peor que
la mediana de 24.4 m de las distribuciones colocadas al azar. Por lo
tanto, el problema es multiobjetivo.

### 5.2 Definición de variables y restricciones del modelo

**Variables.** Para cada módulo, su posición (x, y) y su rotación (0° o 90°). Las
posiciones se mueven en pasos de 0.25 m: es una precisión realista para colocar
un módulo en el lugar y reduce el número de opciones que el algoritmo debe
explorar.

**Malla.** El recinto se divide en celdas de 1 m para la simulación, un punto
medio entre el tiempo de cálculo y el detalle de la respuesta.

**Funciones objetivo.**

- **Accesibilidad (f₁):** distancia geodésica media de cada celda al módulo que le
  corresponde, respetando la capacidad de atención de cada módulo.
- **Evacuación (f₂):** tiempo que tarda la multitud, simulada como fluido, en
  salir del recinto, hasta que queda dentro menos del 0.5 % del aforo. En el
  prototipo interactivo el optimizador usa el tiempo en que sale el 95 % (t₉₅),
  porque la última fracción de densidad se vacía cada vez más lento y alarga la
  simulación sin distinguir mejor entre distribuciones.

**Restricciones.** Seis restricciones duras, agrupadas por su origen:

| Origen | Restricciones |
|---|---|
| Legal [5, nums. 7.15 b) y 7.16 f)] | Salidas despejadas y ancho libre de circulación |
| Geométrico | Módulos dentro del recinto, sin encimarse entre sí ni sobre muros |
| Criterio de diseño | Cada módulo debe ser alcanzable, y la distribución no debe dejar inservible más del 3 % del área útil |

Al principio, el espacio que quedaba encerrado detrás de un módulo se contaba como
violación de seguridad, y eso rechazaba el 87 % de las distribuciones. Como en
realidad no es una infracción sino superficie que no se puede aprovechar, se
reformuló como pérdida de área útil y la aceptación subió al 88 % sin relajar
ningún criterio.

El límite de 40 m de la NOM-002 se verifica por recinto y no por distribución,
porque en el recinto de prueba el piso vacío ya lo excede y, como restricción,
invalidaría todas las distribuciones por una causa ajena a ellas.

**Parámetros provisionales.** El ancho libre de circulación (3 m), el despeje
frente a las salidas, el flujo máximo por metro de puerta y las unidades de
atención de cada módulo tienen valores provisionales mientras se confirma su
fuente. La NOM-002 obliga a mantener rutas y salidas libres, pero no fija esas
medidas.

### 5.3 Selección y justificación del algoritmo bioinspirado

Se eligió **NSGA-II** [12] porque entrega en una sola ejecución el conjunto
completo de distribuciones de compromiso, sin tener que fijar de antemano cuánto
pesa cada criterio, y porque es el algoritmo de referencia en optimización
multiobjetivo. Su diseño:

- **Individuo:** la posición y rotación de cada módulo.
- **Cruce:** se intercambian módulos completos entre padres, emparejados por tipo:
  el primer sanitario del hijo viene del primer sanitario de uno de los dos
  padres. No se promedian coordenadas, porque eso produce hijos con módulos
  encimados.
- **Mutación:** desplazamientos que empiezan grandes y se reducen conforme avanza
  la búsqueda, más cambios ocasionales de rotación.
- **Restricciones:** la población inicial se genera cumpliendo todas las
  restricciones; después ningún candidato se descarta, sino que los que violan
  alguna se ordenan por qué tanto la violan, con la regla de Deb [20].

### 5.4 Diagramas conceptuales

**Arquitectura.** Tres capas: la interfaz web no calcula nada por su cuenta, el
servicio recibe y encola peticiones, y el núcleo contiene todo el modelo.

```
 Interfaz web (React, ui/)        Servicio (FastAPI, api/)        Núcleo (Python, nucleo/)
 ─────────────────────────        ────────────────────────        ───────────────────────────────
 editor de recinto        ──────▶ /api/geometria         ──────▶ geometria.py   restricciones G1–G6
 simulación paso a paso   ──────▶ /api/campo                     acceso.py      f₁: transporte capacitado
 informe de resultados    ──────▶ /api/trabajos          ──────▶ fluido.py      f₂: evacuación
                                  (cola de optimizaciones)        kernel.py      paso de Godunov
                                                                  optimizar.py   ciclo del algoritmo
```

**Evaluador.** Del recinto dibujado a las dos funciones objetivo:

```
 recinto (muros, salidas) + distribución (tipo, x, y, rotación de cada módulo)
   │
   ├── capa geométrica G1–G6 ............ violación total (0 = válida)
   ├── zona ocupable ..................... celdas a las que llega la gente
   ├── f₁: una Eikonal por módulo ─▶ transporte capacitado ─▶ distancia media (m)
   └── f₂: Eikonal con Weidmann cada 2.4 s ─▶ paso de Godunov ─▶ tiempo de evacuación (s)
```

**Modelo de datos.**

| Entidad | Atributos |
|---|---|
| Recinto | ancho, largo, tamaño de celda, muros, salidas |
| Salida | nombre, lado (N, S, E, O), centro, ancho |
| Tipo de módulo | nombre, ancho, fondo, unidades de atención |
| Colocación | tipo, x, y, rotación |
| Evaluación | llave de la distribución, f₁, tiempo de evacuación (t₉₅ y desalojo), violación, tiempo de cálculo |

### 5.5 Flujos del modelo

1. **Configuración:** el usuario dibuja el recinto, coloca salidas y elige
   cuántos módulos de cada tipo necesita.
2. **Evaluación:** para una distribución, el sistema verifica restricciones,
   simula la evacuación y calcula ambos criterios.
3. **Optimización:** el algoritmo genera distribuciones, las evalúa y las mejora
   generación tras generación.
4. **Entrega:** el usuario revisa las distribuciones obtenidas, ve su simulación
   y elige una.

---

## 6. Estudio de factibilidad

En este apartado se detalla la viabilidad del prototipo mediante el análisis de
los recursos técnicos, operativos y económicos necesarios.

### 6.1 Factibilidad técnica

El evaluador ya está construido y validado: la simulación conserva el número de
personas con un error de 5×10⁻¹⁵ y respeta la capacidad de las puertas, y el
cálculo de accesibilidad ordena las distribuciones exactamente igual que una
solución exacta por programación lineal. En un equipo AMD Ryzen 5 5600GT con
32 GB de memoria, repartiendo el cálculo en sus 12 hilos, cada evaluación cuesta
34.4 ms en promedio (188 ms en un solo hilo; medido el 13 de octubre de 2026 con
`experimentos/costo_evaluacion.py`), por lo que una optimización de 25 000
evaluaciones toma alrededor de 15 minutos.

### 6.2 Factibilidad operativa

El usuario previsto es el organizador del evento o el responsable de protección
civil. Solo necesita un plano del recinto y saber cuántos módulos requiere; no
necesita conocer el modelo ni el algoritmo. El sistema es una herramienta de
apoyo y no sustituye el Programa Especial de Protección Civil [4].

### 6.3 Factibilidad económica

Todas las herramientas son libres o tienen licencia gratuita para uso educativo,
y el informe de resultados está publicado en hospedaje gratuito. ⟨Agregar el
costo estimado de horas de desarrollo.⟩

---

## 7. Conclusiones

Se comprobó que distribuir áreas de servicio en eventos masivos es un problema
multiobjetivo: accesibilidad y tiempo de evacuación no se pueden mejorar a la vez,
y optimizar solo uno deja al otro sin control. Por eso se eligió NSGA-II, que
entrega el conjunto de opciones de compromiso para que el organizador decida.

El modelo de evaluación ya funciona: simula la multitud como un fluido con el
diagrama de Weidmann, resuelve la saturación con el esquema de Godunov y calcula
la accesibilidad respetando la capacidad de cada módulo. Además, permite
verificar criterios normativos que hoy no se revisan de forma cuantitativa, como
el límite de tres minutos de la NOM-002.

Queda pendiente implementar el algoritmo, probarlo en más recintos y confirmar
los parámetros provisionales.

---

## 8. Referencias

[1] J. J. Fruin, "The causes and prevention of crowd disasters", en *Engineering for Crowd Safety*, R. A. Smith y J. F. Dickie, Eds. Ámsterdam: Elsevier, 1993.

[2] D. Helbing, A. Johansson y H. Z. Al-Abideen, "Dynamics of crowd disasters: An empirical study", *Physical Review E*, vol. 75, n.º 4, art. 046109, 2007, doi: 10.1103/PhysRevE.75.046109.

[3] BBC Mundo, "Brasil: más de 231 muertos en incendio en discoteca", 27-ene.-2013. [En línea]. Disponible en: https://www.bbc.com/mundo/ultimas_noticias/2013/01/130127_ultnot_brasil_incendio_discoteca_dp [Accedido: 01-mar.-2026].

[4] Congreso de la Ciudad de México, "Ley de Gestión Integral de Riesgos y Protección Civil de la Ciudad de México", última reforma publicada en la Gaceta Oficial de la Ciudad de México el 02-mar.-2021. [En línea]. Disponible en: https://www.congresocdmx.gob.mx/archivos/legislativas/Ley_Gestion_Integral_Riesgos_Proteccion_Civil_CDMX.pdf [Accedido: 08-oct.-2026].

[5] Secretaría del Trabajo y Previsión Social, "NOM-002-STPS-2010, Condiciones de seguridad — Prevención y protección contra incendios en los centros de trabajo", *Diario Oficial de la Federación*, México, 09-dic.-2010. [En línea]. Disponible en: https://dof.gob.mx/normasOficiales/4228/stps/stps.htm [Accedido: 08-oct.-2026].

[6] Secretaría de Seguridad y Protección Ciudadana, "Aviso de consulta pública del Proyecto de Norma Oficial Mexicana PROY-NOM-011-SSPC-2025, Requisitos mínimos y generales de protección civil aplicables en espectáculos y eventos masivos, a fin de regular rangos máximos de capacidad de aforo de personas", *Diario Oficial de la Federación*, México, 2025. [En línea]. Disponible en: https://dof.gob.mx/normasOficiales/9519/seguridad/seguridad.html [Accedido: 08-oct.-2026].

[7] U. Weidmann, *Transporttechnik der Fussgänger: Transporttechnische Eigenschaften des Fussgängerverkehrs*, 2.ª ed., Schriftenreihe des IVT, n.º 90. Zúrich: ETH Zürich, 1993.

[8] R. L. Hughes, "A continuum theory for the flow of pedestrians", *Transportation Research Part B: Methodological*, vol. 36, n.º 6, pp. 507–535, 2002, doi: 10.1016/S0191-2615(01)00015-7.

[9] J. A. Sethian, "A fast marching level set method for monotonically advancing fronts", *Proceedings of the National Academy of Sciences*, vol. 93, n.º 4, pp. 1591–1595, 1996, doi: 10.1073/pnas.93.4.1591.

[10] S. K. Godunov, "A difference scheme for numerical computation of discontinuous solutions of hydrodynamic equations", *Matematicheskii Sbornik*, vol. 47(89), n.º 3, pp. 271–306, 1959.

[11] C. F. Daganzo, "The cell transmission model: A dynamic representation of highway traffic consistent with the hydrodynamic theory", *Transportation Research Part B: Methodological*, vol. 28, n.º 4, pp. 269–287, 1994, doi: 10.1016/0191-2615(94)90002-7.

[12] K. Deb, A. Pratap, S. Agarwal y T. Meyarivan, "A fast and elitist multiobjective genetic algorithm: NSGA-II", *IEEE Transactions on Evolutionary Computation*, vol. 6, n.º 2, pp. 182–197, 2002, doi: 10.1109/4235.996017.

[13] Unity Technologies, "Unity User Manual". [En línea]. Disponible en: https://docs.unity3d.com/Manual/index.html [Accedido: 08-oct.-2026].

[14] Meta Platforms, "React". [En línea]. Disponible en: https://react.dev [Accedido: 08-oct.-2026].

[15] S. Ramírez, "FastAPI". [En línea]. Disponible en: https://fastapi.tiangolo.com [Accedido: 08-oct.-2026].

[16] G. Zhong, Y. Lu, W. Chen y G. Zhai, "Multi-objective optimization approach of shelter location with maximum equity: an empirical study in Xin Jiekou district of Nanjing, China", *Geomatics, Natural Hazards and Risk*, vol. 14, n.º 1, art. 2165973, 2023, doi: 10.1080/19475705.2023.2165973.

[17] Y. Li, W. Cai y A. A. Kana, "Design of level of service on facilities for crowd evacuation using genetic algorithm optimization", *Safety Science*, vol. 120, pp. 237–247, 2019, doi: 10.1016/j.ssci.2019.06.044.

[18] X. T. Nguyen, D. H. Pham y B.-L. Dang, "Application of the NSGA-II algorithm for optimizing construction site layout planning", en *Lecture Notes in Civil Engineering*. Cham: Springer, 2025, pp. 707–714, doi: 10.1007/978-3-032-04645-1_82.

[19] X. Li e Y. Chen, "Evaluation and optimization of secondary school laboratory layout based on simulation of students' evacuation behavior", *Buildings*, vol. 16, n.º 2, art. 405, 2026, doi: 10.3390/buildings16020405.

[20] K. Deb, "An efficient constraint handling method for genetic algorithms", *Computer Methods in Applied Mechanics and Engineering*, vol. 186, n.º 2–4, pp. 311–338, 2000, doi: 10.1016/S0045-7825(99)00389-8.

[21] F. van Wageningen-Kessels, W. Daamen y S. P. Hoogendoorn, "Two-Dimensional Approximate Godunov Scheme and What It Means For Continuum Pedestrian Flow Models", *Transportation Science*, vol. 52, n.º 3, pp. 547–563, 2018, doi: 10.1287/trsc.2017.0793.
