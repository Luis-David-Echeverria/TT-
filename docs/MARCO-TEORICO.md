# TT — Distribución óptima de áreas de servicio en eventos masivos mediante algoritmos bioinspirados

Documento de trabajo. Explica **qué** se hace, **cómo** y **por qué**, en lenguaje llano.
Todo concepto técnico se explica la primera vez que aparece.

---

## Índice

1. [La idea en una frase](#1-la-idea-en-una-frase)
2. [El ciclo: las dos piezas que se turnan](#2-el-ciclo-las-dos-piezas-que-se-turnan)
3. [Pieza A — el algoritmo bioinspirado](#3-pieza-a--el-algoritmo-bioinspirado)
4. [Pieza B — el modelo de fluido](#4-pieza-b--el-modelo-de-fluido)
5. [Variables de decisión](#5-variables-de-decisión)
6. [Restricciones duras](#6-restricciones-duras)
7. [Las tres funciones objetivo](#7-las-tres-funciones-objetivo)
8. [Riesgo de aplastamiento](#8-riesgo-de-aplastamiento)
9. [Lo que el modelo NO puede hacer](#9-lo-que-el-modelo-no-puede-hacer)
10. [Validación](#10-validación)
11. [Estado del prototipo](#11-estado-del-prototipo)
12. [Cómo correrlo](#12-cómo-correrlo)
13. [Estado del arte y literatura](#13-estado-del-arte-y-literatura)
14. [Glosario](#14-glosario)

---

## 1. La idea en una frase

> Es el problema clásico de **acomodar áreas en una planta industrial**, más un **modelo de fluido**,
> para que evaluar una distribución no sea solo medir distancias sino responder:
> *"¿y si esto se llena muy muy lleno, cómo se comporta?"*

El problema base se llama **UA-FLP** (*Unequal Area Facility Layout Problem*): dado un espacio y
un conjunto de áreas de distinto tamaño, ¿dónde pones cada una? Tiene 40 años de literatura
resolviéndolo para naves industriales, minimizando distancias de transporte.

La diferencia aquí: en un evento masivo lo que importa no es la distancia entre departamentos,
sino **la seguridad de la multitud**. Y eso no se mide con una regla, se mide simulando.

**Por qué hace falta una metaheurística:** el problema es *NP-duro*, o sea que el número de
acomodos posibles crece tan rápido con el número de áreas que probarlos todos es imposible,
aunque tuvieras siglos. Con 30 bloques hay más combinaciones que átomos en la galaxia. Entonces
no se busca *el* óptimo demostrable: se busca una solución muy buena en tiempo razonable. Eso es
una **metaheurística**.

---

## 2. El ciclo: las dos piezas que se turnan

```
   ┌────────────────────────────────────────────┐
   │                                            │
   │   1. El algoritmo PROPONE una distribución │
   │      (aquí los baños, allá la comida...)   │
   │                     ↓                      │
   │   2. El fluido la EVALÚA                   │
   │      (mete a 14 000 personas y mide)       │
   │                     ↓                      │
   │   3. Las mejores SE REPRODUCEN y mutan     │
   │                     ↓                      │
   │            nueva generación ───────────────┘
```

- **Lo bioinspirado** es el paso 3: evolución (o enjambre, según el algoritmo).
- **El fluido** es el paso 2. Es el juez.

El algoritmo por sí solo no sabe si un layout es bueno. El fluido por sí solo no propone nada.
Se necesitan los dos.

> **Ojo:** la generación aleatoria ocurre **solo la primera vez**. Si el paso 1 se repitiera
> al azar cada vuelta, esto sería búsqueda aleatoria y no aprendería nada.

---

## 3. Pieza A — el algoritmo bioinspirado

### 3.1 NSGA-II

*Non-dominated Sorting Genetic Algorithm II* (Deb, 2002). Es un **algoritmo genético** —
imita la selección natural — diseñado para cuando hay **varios objetivos que se pelean entre sí**.

### 3.2 Por qué los objetivos NO se suman

Lo intuitivo sería `f = a·f1 + b·f2 + c·f3` y minimizar ese número. Tres problemas:

1. **No puedes justificar los pesos.** ¿Cuánto vale un segundo de evacuación en unidades de
   personas por metro cuadrado? No existe esa conversión.
2. **Las unidades no son comparables.** Es sumar peras con kilos.
3. **El problema técnico, que es el que de verdad importa:** una suma ponderada solo puede
   encontrar soluciones en la **envolvente convexa** del conjunto de óptimos. Si ese conjunto
   tiene "hundimientos", hay soluciones óptimas que **ningún juego de pesos puede alcanzar**.
   No es que sea difícil: es imposible por construcción.

Y hay un cuarto motivo, de fondo: **la decisión del compromiso no es del tesista**, es del
organizador y de protección civil. Esconderla dentro de un peso no la elimina, solo la vuelve
invisible.

### 3.3 Dominancia — el reemplazo de la suma

> **Dominancia:** un layout **A domina** a **B** si A es igual o mejor en *los tres* objetivos,
> y estrictamente mejor en al menos uno.

Si A domina a B, B no sirve para nada: A le gana en todo.

Pero si A es mejor en accesibilidad y B es mejor en evacuación, **ninguno domina al otro**.
Los dos son compromisos válidos y distintos.

> **Frente de Pareto:** el conjunto de todos los layouts que nadie domina.

**La salida del algoritmo no es un layout: es ese catálogo de compromisos.** Elegir uno es una
decisión humana, y eso es el producto, no una debilidad.

### 3.4 Qué pasa en una generación

Con población de 80 individuos:

| Paso | Qué hace |
|---|---|
| **Selección** | Torneo binario: agarra 2 al azar, gana el mejor. Repite hasta tener 80 padres |
| **Cruza** | Combina dos padres para producir hijos |
| **Mutación** | Cambios aleatorios pequeños: intercambia dos áreas, mueve una, voltea la orientación |
| **Competencia** | 160 individuos (80 padres + 80 hijos) compiten por 80 lugares |
| **Ordenamiento** | Se ordenan por capas de dominancia y sobreviven los mejores |

> **Elitismo:** que padres e hijos compitan juntos. Así una buena solución nunca se pierde
> por mala suerte.

> **Distancia de apiñamiento:** cuando una capa no cabe completa, se prefieren los individuos
> que están en zonas *vacías* del frente. Sin esto terminarías con 80 copias de la misma idea,
> y el frente saldría apelmazado en un rincón en vez de bien extendido.

### 3.5 Cruza OX — por qué no sirve la cruza normal

El individuo es una **permutación** (un orden de las 30 áreas). Si cortaras dos padres a la
mitad y los pegaras, saldrían layouts con dos baños C1 y ningún puesto de comida C3. Inválido.

> **OX (*order crossover*):** copia un tramo del padre A tal cual, y rellena los huecos con los
> elementos que faltan, en el orden en que aparecen en el padre B. El hijo siempre es una
> permutación válida.

### 3.6 Los tres algoritmos a comparar

El título dice "algoritmos" en plural porque se comparan **tres paradigmas bioinspirados distintos**:

| Algoritmo | Inspiración | Cómo busca |
|---|---|---|
| **NSGA-II** | selección natural | cruza y muta una población, ordena por dominancia |
| **MOEA/D** | evolución + descomposición | parte el problema en muchos subproblemas pequeños y los resuelve en paralelo compartiendo información entre vecinos |
| **MOPSO** | parvadas y cardúmenes | partículas que se mueven atraídas por su mejor posición y la del enjambre; sin cruza |

NSGA-II es la columna vertebral porque es *el* estándar: nadie lo cuestiona y sirve de referencia.

*Si preguntan por qué no NSGA-III:* NSGA-III es para 4 objetivos o más, donde NSGA-II se degrada.
Con 3, NSGA-II es lo apropiado.

---

## 4. Pieza B — el modelo de fluido

### 4.1 Por qué "fluido", y dónde se rompe la analogía

Una multitud se parece a un fluido en **una** cosa real y medida: **entre más apretada, más
lento camina la gente**. Eso está en los datos.

Pero **no** se mueve por presión como el agua. Se mueve porque quiere llegar a un lugar.
No es Navier-Stokes. Es **conservación de masa acoplada a un campo de destino**.

Consecuencias que hay que tener claras para la defensa:

- Las zonas lentas detrás de un obstáculo son **sombras de flujo** (la gente lo rodea
  anticipadamente), no estelas turbulentas.
- **No hay vórtices detrás de una barra de bebidas.**
- Físicamente, una multitud comprimida se parece mucho más a un **medio granular atascado**
  (arena en un silo) que a un líquido.

### 4.2 Enfoque macroscópico, no de agentes

Hay dos formas de simular multitudes:

| | Cómo | Costo |
|---|---|---|
| **Agentes** | cada persona es un objeto que decide | crece con el número de personas |
| **Continuo** (el nuestro) | campos sobre una rejilla: densidad, velocidad | crece con el número de **celdas** |

> **La clave:** simular 50 000 asistentes cuesta **lo mismo** que simular 500. Es lo que lo hace
> viable dentro de un ciclo evolutivo que va a evaluar miles de layouts.

Referencias: Hughes (2002), Treuille, Cooper & Popović (2006) *"Continuum crowds"*.

### 4.3 Los conceptos, uno por uno

#### Rejilla

El recinto se corta en cuadritos (aquí, de 1 m). Las áreas de servicio que coloca el optimizador
son **celdas obstáculo**: no se puede pasar por ahí.

#### Ecuación Eikonal y campo de tiempos

> **Campo de tiempos de llegada (T):** para cada punto del recinto, cuántos segundos tardas
> en llegar al destino más cercano (la salida, el baño...).

Se obtiene resolviendo la **ecuación Eikonal**, que en cristiano dice: *el tiempo de llegada
crece a razón de uno sobre la velocidad local*. Donde vas lento, el tiempo se acumula rápido.

Ese campo se calcula con **FMM** (*Fast Marching Method*): un algoritmo que va "inundando" el
recinto desde el destino hacia afuera, como una mancha de tinta que avanza más despacio en las
zonas congestionadas. Rodea obstáculos correctamente.

> **Y esto es lo importante:** la dirección en la que se mueve la gente es simplemente
> **hacia donde el tiempo baja más rápido**. Eso son las flechas que ves en las figuras.
> Es la pendiente del campo, nada más.

#### Diagrama fundamental de Weidmann

> La relación medida entre **densidad** (personas por m²) y **velocidad** (m/s).
> A más apretados, más lento. Es el único anclaje empírico del modelo.

Es crítico. Sin esto, el modelo predeciría que las multitudes *aceleran* en los cuellos de
botella, que es exactamente lo contrario de la realidad.

De esa relación sale un número clave: la **capacidad**, o sea el flujo máximo que puede pasar
por un metro de ancho. En nuestro modelo da **1.22 personas por segundo y por metro** — y eso
cae dentro del rango medido en experimentos reales de peatones. **No lo pusimos a mano: salió
del modelo.** Es la primera prueba de validación, y la pasa.

#### Punto fijo (para operación normal)

La densidad determina la velocidad → la velocidad determina los tiempos → los tiempos
determinan por dónde camina la gente → eso determina la densidad. Es circular.

> **Punto fijo:** repetir ese ciclo hasta que deje de cambiar. Unas 4 vueltas.

Sirve para operación normal porque, aunque la gente circula, el **patrón global** no cambia.
Es un orden de magnitud más barato que simular el tiempo paso a paso.

#### CTM — el transporte real (para evacuación)

Una evacuación **no** tiene punto fijo: el recinto se está vaciando, todo cambia. Hay que
simular el tiempo de verdad.

> **CTM** (*Cell Transmission Model*, Daganzo): el esquema numérico correcto para mover masa
> sobre una rejilla. Es el método de Godunov aplicado a la ley de conservación **LWR**
> (Lighthill–Whitham–Richards), que es la ecuación clásica del flujo de tráfico.

La regla, y es la que lo hace funcionar:

> Una celda no puede **enviar** más de lo que su densidad permite,
> **y sobre todo, una celda no puede recibir más de lo que le cabe.**

Sin la segunda condición la masa se apila sin límite, la densidad se dispara, Weidmann la deja
a velocidad cero y **se congela para siempre**. Con ella aparecen **colas de verdad**: la
congestión se propaga hacia atrás, como en el tráfico.

Además, cada celda congestionada **sí quiere descargar a capacidad** — lo que la frena es que
la de adelante no la acepta. Si se pone que una celda llena envía poco, las celdas llenas se
congelan y aparece un moteado de tablero de ajedrez. (Nos pasó; está corregido.)

**Las salidas tienen capacidad finita.** Ahí nace la fila en la puerta, que es el mecanismo
que domina el tiempo real de evacuación.

#### Dispersión

La gente **no** sigue exactamente la ruta óptima: hay variación en velocidad deseada y en
elección de ruta. Sin representar eso, la multitud se encanala en filamentos con huecos vacíos
entre medio, que no es como se ve una multitud.

Por eso la ecuación no es de pura advección sino de **advección–difusión**: se le suma un
término que dispersa lateralmente.

> **Regla importante:** la dispersión va **en el modelo**, nunca en el dibujo. Si la metes solo
> al renderizar, la imagen deja de corresponder a lo que simulaste, y entonces la visualización
> ya no es evidencia de nada. Como está en el modelo, afecta densidad, velocidad y por lo tanto
> a las funciones objetivo.

#### Escala del potencial

Un detalle que costó trabajo y vale la pena documentar: el campo de tiempos debe calcularse
con la densidad **suavizada a escala grande**.

Con densidad instantánea celda a celda, cualquier hueco vacío tiene velocidad máxima → tiempo
bajo → **el gradiente apunta hacia el hueco**. La gente se dirige a los huecos, eso abre más
huecos, y la multitud se fragmenta en islas. Realimentación positiva.

Justificación física: nadie decide su ruta por lo que pasa en el metro cuadrado de al lado,
sino por cómo se ve la zona.

### 4.4 Los tres escenarios

| Escenario | Régimen | Por qué |
|---|---|---|
| **Entrada** | cuasi-estacionario | las entradas son fuentes de masa |
| **Operación normal** | punto fijo | el patrón global no cambia |
| **Evacuación** | dinámico real (CTM) | el recinto se vacía, no hay estado estable |

Los momentos de mayor riesgo real son las **transiciones** (entrada masiva, intermedio, salida),
no el estado promedio.

---

## 5. Variables de decisión

### 5.1 Representación FBS

> **FBS** (*Flexible Bay Structure*): el recinto se corta en **bandas** paralelas, y cada banda
> se subdivide en bloques apilados, proporcionalmente al área que cada uno necesita.

**La gran ventaja: cero traslapes por construcción.** No hace falta detectar ni penalizar que
dos zonas se encimen, porque es geométricamente imposible que pase.

### 5.2 El individuo son tres cosas

| Variable | Qué es |
|---|---|
| **π** (permutación) | el orden de los 30 bloques |
| **δ** (cortes) | dónde se corta en bandas |
| **o** (orientación) | bandas verticales u horizontales |

### 5.3 Bloques ficticios

Un recinto de eventos es ~85% piso vacío, pero FBS reparte **todo** el espacio. ¿Qué se hace
con el vacío?

> **Departamentos ficticios** (*dummy departments*): bloques que representan piso libre de
> circulación. Es la técnica estándar en UA-FLP para manejar área no asignada.

Aquí: **10 servicios reales + 20 bloques de circulación**.

### 5.4 Lo que NO se optimiza

El **escenario** (banda preasignada) y las **salidas** (las dicta protección civil; el
organizador no las mueve). Lo que sí se optimiza es que sus **conos de aproximación** —el
espacio libre que debe haber enfrente— queden despejados.

---

## 6. Restricciones duras

### 6.1 Por qué duras y no penalizaciones blandas

Son **requisitos legales binarios**. Como penalización blanda, el optimizador produce layouts
que violan normativa pero compensan con buena accesibilidad y salen bien puntuados.

Además, la restricción dura es **verificable sin simular**. Si toda la seguridad descansara en
la simulación, un error de calibración daría layouts inseguros sin red de protección.

### 6.2 Las tres capas

| Capa | Qué verifica | Costo | Si falla |
|---|---|---|---|
| **0a — geometría** | aspecto, dimensión mínima, conos de aproximación, pasillos | microsegundos | se descarta antes de tocar el simulador |
| **0b — despeje** | ancho libre normativo + conectividad | milisegundos | se descarta, sigue sin simular |
| **1 — estancamiento** | ¿el layout se atasca? | necesita el fluido | infactible aunque puntúe bien |

**El grueso de la población muere en la capa 0 sin haber costado nada.** Ese es el ahorro real
de cómputo.

### 6.3 La lista

| Restricción | Qué evita |
|---|---|
| Relación de aspecto máxima | zonas degeneradas tipo 1×40 m |
| Dimensión mínima | zonas impracticables |
| Ancho libre entre elementos | pasillos-astilla por los que la gente intenta pasar y no cabe |
| Conos de aproximación despejados | tapar una salida |
| **Conectividad** | que la distribución **selle** una región y deje gente sin ruta a ninguna salida |
| Distancia máxima de recorrido a salida | requisito clásico de reglamento contra incendios |
| Ancho total de salidas contra aforo | la salida es cuello de botella por diseño |
| Acceso de emergencia al puesto médico | que pueda entrar una ambulancia |

> **Truco elegante:** el ancho libre y la conectividad se verifican de un solo golpe
> **erosionando** el piso libre por medio ancho normativo. Lo que queda es por donde sí cabe
> circular con el ancho de reglamento. Si una zona ocupable no conecta con ninguna salida a
> través de ese espacio, está sellada.

### 6.4 Dura no significa binaria al medirla

Dura significa que **ningún objetivo la compensa**. Pero sí se mide *cuánto* se violó, porque
eso es lo que le dice al algoritmo por dónde salirse de la región infactible. Si solo marcaras
sí/no, la búsqueda sería ciega ahí dentro.

> **Dominancia restringida (Deb):** factible le gana siempre a infactible. Entre dos infactibles,
> gana el que viola menos. Los infactibles **no se borran** de la población: se quedan
> rankeados hasta abajo.

⚠️ **Los valores numéricos hay que sacarlos de la fuente**, no inventarlos:
NOM-002-STPS, Reglamento de Construcciones de la CDMX + Normas Técnicas Complementarias,
Programa Especial de Protección Civil para eventos masivos.

---

## 7. Las tres funciones objetivo

### f1 — Accesibilidad *(minimizar)*

**Pregunta:** *¿qué tan lejos le queda a la gente lo que va a necesitar?*

Tiempo promedio para llegar al servicio más cercano de cada tipo, ponderado por **dónde está
realmente la gente** (no uniformemente sobre el piso: la multitud se apila hacia el escenario).

**Asignación capacitada:** "el más cercano" no basta. Si todos los que están junto al escenario
tienen los mismos baños como los más cercanos, esos baños se saturan y se hace fila. Entonces la
asignación respeta capacidades y el excedente paga tiempo de espera.

> Ahí queda absorbido el **balance de carga**. Sin esto necesitarías un cuarto objetivo que
> dijera "reparte parejo la demanda".

La asignación es **geodésica, no en línea recta**: un puesto a veinte metros pero del otro lado
de una barrera no es el más cercano.

**Se calcula a velocidad libre, a propósito.** Sin congestión. Así f1 mide **geometría pura**.
Si usara velocidad congestionada, estaría midiendo lo mismo que f2, y tendrías dos objetivos
correlacionados que *parecen* dos dimensiones pero son una.

*Nota:* dentro de f1 **sí** hay un promedio ponderado entre tipos de servicio. Eso es legítimo
porque los pesos no son preferencias del diseñador, son **fracciones de demanda medibles**
(qué porcentaje de la gente va al baño). Agregar sobre una población no es lo mismo que negociar
entre objetivos inconmensurables.

### f2 — Riesgo de congestión *(minimizar)*

**Pregunta:** *¿qué tan apretada se pone la multitud, y dónde?*

**Percentil 95** de la densidad sobre las celdas, tomando el **máximo entre escenarios**.

> **Percentil 95:** el valor que solo supera el 5% más denso. Es una medida de *cola*: no te
> reporta el promedio, te reporta las zonas malas.

**Por qué percentil y no máximo:** el máximo es una sola celda, es ruidoso — mueves un puesto
dos metros y salta. Eso vuelve **áspero el paisaje de fitness** y el algoritmo evolutivo no
puede navegar una superficie así: pierde la señal entre el ruido.

**Por qué el máximo entre escenarios y no el promedio:** el riesgo es del peor instante. Si
promediaras, un layout que opera de maravilla toda la noche y se vuelve mortal en la salida
saldría bien evaluado. **La seguridad no se promedia.**

### f3 — Tiempo de evacuación *(minimizar)*

**Pregunta:** *¿cuánto tarda en vaciarse?*

Tiempo hasta que ha salido el 95% de la gente.

**Por qué 95% y no 100%:** la última fracción es una cola larguísima dominada por rezagados y
artefactos numéricos. Un solo punto perdido en una esquina te dispara el 100% y no dice nada
del layout.

**La parte delicada:** hay dos cosas que determinan el tiempo — cuánto tardas en **llegar** a
una salida y cuánto tardas en **cruzarla** haciendo cola. Y **no son independientes**: el layout
decide cómo se reparte la multitud entre las salidas, y ese reparto decide las colas. Un layout
que empuja a todos hacia la misma puerta deja las otras ociosas.

Por eso f3 tiene que salir de la **simulación CTM con capacidad en las salidas**, no de comparar
dos cotas por separado.

### El conflicto que produce el frente

**f1 jala los servicios hacia la multitud** (cerca del escenario, que es donde está la gente).
**f2 y f3 los empujan fuera de las rutas** de circulación y de egreso.

Y el conflicto es estructural: **la masa está junto al escenario y las salidas están en el
perímetro**, así que casi todo lo que está "cerca de la gente" está también "sobre la ruta de
salida".

No es difícil ganar los tres: **es imposible**. Y esa imposibilidad tiene forma. Esa forma es
el frente de Pareto, y es la figura principal de la tesis.

---

## 8. Riesgo de aplastamiento

### 8.1 Los tres conceptos de Helbing

Helbing, Johansson & Al-Abideen (2007), analizando el desastre del puente Jamarat de 2006:

**Presión de multitud.** Densidad local × varianza de la velocidad. Alta cuando hay mucha gente
*y además* se mueven en direcciones inconsistentes. Tiene umbral crítico empírico publicado.

**Turbulencia de multitud.** El régimen donde, a densidades muy altas, la gente deja de caminar
y empieza a ser **desplazada involuntariamente** en movimientos erráticos. Ahí es donde la gente
se cae y muere.

> **No es turbulencia de fluido.** El nombre es analogía aceptada en la literatura, pero no hay
> vórtices ni cascada de energía. La gente está tan apretada que las fuerzas de contacto se
> propagan de cuerpo a cuerpo. Es física **granular**.

**Estancamiento.** El más importante y sin análogo en fluidos: cerca de la densidad máxima el
flujo no solo se reduce, **puede colapsar a cero y quedarse ahí**. Es atasco irreversible.

### 8.2 Por qué el estancamiento rompe el modelo

**El diagrama fundamental no tiene memoria.** La velocidad es *función* de la densidad: si la
densidad baja, la velocidad se recupera al instante.

Un atasco real no funciona así: una vez trabada, la multitud sigue trabada aunque la densidad
nominal baje. Hay **histéresis**. Y una función de una sola variable no puede tener dos estados
para la misma entrada — así que **no hay valor de los parámetros que lo arregle**. Es estructural.

El mecanismo concreto en una puerta es un **arco de carga**: la gente forma un arco que cruza el
vano, igual que los granos que se atoran en la tolva de un silo. Relacionado: el efecto
**"faster-is-slower"** (Helbing, Farkas & Vicsek, *Nature* 2000) — empujar más fuerte en una
salida **reduce** el flujo total.

**Consecuencia con dirección conocida:** el modelo da tiempos de evacuación **optimistas**.
Hay que declararlo y aplicar factor de seguridad para uso normativo.

### 8.3 Cómo se convierte en diseño

**Detectar, no simular.** No hace falta reproducir el atasco: hace falta **rechazar los layouts
que lo admiten**. Si la densidad se acerca al máximo en alguna celda, ese layout está atascando.
Señal binaria, barata, y encaja como restricción dura (capa 1).

### 8.4 Carga sobre muros y zonas de servicio

**La fórmula de fluidos no aplica.** En un fluido la fuerza sobre un muro viene de la presión
dinámica, que depende del cuadrado de la velocidad. Pero el movimiento peatonal es
**sobreamortiguado**: la gente no se estampa, camina y se detiene.

De hecho **los aplastamientos ocurren con velocidad cercana a cero**. Con presión dinámica, el
modelo diría que ahí no pasa nada, justo en el momento del desastre.

**La fuerza real viene de acumulación, no de impacto.** Cada persona empuja hacia adelante; los
de enfrente están bloqueados; los de atrás siguen empujando. Las fuerzas se **suman a lo largo
de la cadena de cuerpos**. Es carga cuasi-estática sostenida.

#### El problema: el modelo actual no puede producirla

La dirección de movimiento sale del campo de tiempos, que se resuelve **sobre el espacio libre**.
Nunca apunta hacia un obstáculo. El modelo asume que **todo el mundo sabe rodear todo**, con
información perfecta. Las multitudes reales no: empujan contra barreras porque no ven, no
conocen el recinto, o las empujan por detrás.

#### La solución: dos campos

| Campo | Qué representa |
|---|---|
| **Deseo** | hacia dónde quiere ir la gente, en línea recta, ignorando obstáculos (información nula) |
| **Factible** | el que rodea correctamente los obstáculos (información perfecta) |

**La discrepancia entre los dos es la señal.** Donde el deseo apunta contra algo que no cede,
ahí hay gente presionando.

En el prototipo se calcula por **trazado de rayos**: cada porción de multitud avanza en línea
recta hacia donde quiere ir; si llega a una salida, sale y no carga nada; si se topa con algo,
**deposita su masa justo delante del punto de choque**.

**Beneficio extra:** el peso entre los dos campos es un parámetro con significado real — *qué
tan bien conoce el público el recinto*. Un festival con público habitual no es lo mismo que un
evento nuevo. Da un análisis de sensibilidad que vale como resultado.

#### Qué es y qué no es

**No son newtons.** Es *propulsión bloqueada*. Sirve para decir *"este layout carga más esta
valla que aquel"*, no para dimensionar la valla. Volverlo fuerza requiere calibración empírica.

**Es el promedio, no el pico.** La carga en una multitud viaja por **cadenas de fuerza**: unos
pocos caminos de contacto se llevan la mayor parte, de forma desigual e intermitente. Lo que
aguanta un cuerpo concreto puede ser varias veces esto.

Entonces se puede decir *"aquí se acumula carga y allá no"*. **No** se puede decir *"aquí la
carga es segura"*.

#### Otras cantidades que salen gratis del mismo campo

Hoy solo se usa densidad. Del mismo campo salen:

- **Divergencia de la velocidad** — mide si el flujo se comprime o se expande. Divergencia
  negativa = entra más gente de la que sale = **compresión**. Es la mejor señal de riesgo de
  aplastamiento que se puede extraer de un continuo, y es una cantidad de mecánica de fluidos
  bien definida, no una analogía.
- **Tasa de cizalla** — qué tan distinto se mueve la gente que está pegada a ti. Es la condición
  donde se tropieza y se cae.
- **Contraflujo.** Los aplastamientos reales casi siempre pasan donde dos corrientes se cruzan.
  Un continuo con **una sola** velocidad por punto no puede representar dos multitudes
  atravesándose. **Pero ya llevamos un campo por cada tipo de destino**: si se guardan densidad
  y velocidad de cada grupo por separado, se puede calcular la cizalla *entre grupos* y detectar
  contraflujo. Convierte una limitación en un indicador.

#### Dónde meterlo

**No como cuarto objetivo** (con 4 objetivos NSGA-II se degrada, y estaría correlacionado con
congestión). Va como **restricción dura** si se consigue calibración, y como **salida de
diagnóstico** — el mapa de carga acompañando a cada solución del frente. Es un entregable que
un layout optimizado por distancias no puede dar.

---

## 9. Lo que el modelo NO puede hacer

Decirlo antes de que lo pregunten es más fuerte que defenderlo después.

| No puede | Por qué |
|---|---|
| Predecir un aplastamiento | Identifica *condiciones*. El salto de "condiciones peligrosas" a "hubo víctimas" necesita calibración empírica que el continuo no aporta |
| Reproducir turbulencia de multitud | Requiere fuerzas de contacto entre cuerpos |
| Representar atascos irreversibles | El diagrama fundamental no tiene memoria |
| Formar arcos en las puertas | No hay cuerpos, no hay contacto |
| Dar tiempos absolutos confiables | Son optimistas, por lo anterior |
| Representar contraflujo (hoy) | Una sola velocidad por punto — se resuelve con multiclase |

### El encuadre correcto

> El modelo predice **dónde y cuándo se alcanzan las condiciones** que preceden a la turbulencia
> de multitud. No simula el desastre — y no necesita hacerlo, porque para diseñar un layout lo
> que se quiere es que esas condiciones nunca se presenten.

Si preguntan *"¿tu modelo predice aplastamientos?"*, la respuesta es **"no, y no pretende:
predice el precursor, que es lo accionable"**. Es mucho más fuerte que intentar defender que sí.

---

## 10. Validación

### El reencuadre que lo hace alcanzable

**El optimizador no usa el valor de f3. Usa el orden.** Solo necesita saber que el layout A es
mejor que el B. Si el modelo es optimista por un factor parecido en todos los layouts,
**el ranking sobrevive aunque los números absolutos estén mal**.

Entonces el objetivo de validación no es "error absoluto menor a X%", es **correlación de rangos
contra un modelo de agentes**. Eso sí es alcanzable en un TT.

### Tres niveles

**Nivel 1 — mediciones publicadas.** Correr el modelo en geometrías triviales y verificar que
reproduzca números medidos: flujo por un pasillo, flujo por una puerta según su ancho
(experimentos de cuello de botella del grupo de Jülich).
✅ **Parcialmente hecho:** la capacidad sale en 1.22 pers/(s·m), dentro del rango publicado.

**Nivel 2 — RiMEA.** Guía alemana con una batería de casos de prueba estándar para simuladores
de evacuación, con criterios de aceptación. Es *la* prueba de admisión de este tipo de modelos
y es totalmente citable. También existe **ISO 20414** sobre verificación y validación de modelos
de evacuación.

**Nivel 3 — contraste con fuerza social.** Correr un modelo de agentes (Helbing & Molnár, 1995 —
el modelo de multitudes más famoso que existe, y es de agentes, no continuo) sobre las mejores
soluciones del frente y comparar **rankings**, no tiempos absolutos.

### Validación del algoritmo (aparte)

- **Benchmarks estándar de UA-FLP** (O7, O9, vC10, AB20, Nug) contra resultados publicados.
  Nota: esos no tienen fluido — validan f1, que es lo que conecta con la literatura existente.
- **Baselines honestos:** búsqueda aleatoria, greedy, layout diseñado a mano.
  *Si no le gana a búsqueda aleatoria por buen margen, algo está mal.*
- **Pruebas estadísticas:** Friedman + Wilcoxon sobre hipervolumen y spread, con ~30 repeticiones.

---

## 11. Estado del prototipo

### ✅ Funciona

| Componente | Archivo |
|---|---|
| Instancia (recinto, servicios, salidas, conos) | `prototipo/recinto.py` |
| Decodificación FBS + restricciones capa 0 | `prototipo/modelo.py` |
| Campo Eikonal con FMM + Weidmann + punto fijo | `prototipo/modelo.py` |
| **Transporte CTM con capacidad en salidas** | `prototipo/fluido.py` |
| Carga sobre fronteras (dos campos + rayos) | `prototipo/demo_carga.py` |
| NSGA-II con operadores propios (OX, etc.) | `prototipo/optimizar.py` |

### ⚠️ Pendiente

**1. f3 sigue rota en `objetivos.py`.**
Está como `max(tiempo_geodésico, cota_por_capacidad)`. Con la instancia actual la cota domina
siempre, así que **f3 da el mismo valor para todos los layouts** y el optimizador está corriendo
efectivamente con **dos objetivos, no tres** — o sea, el conflicto f1–f3 que es la contribución
central **no existe en el código**.
**El arreglo ya está escrito** (`fluido.py`); falta enchufarlo: sustituir la fórmula por una
llamada a `fluido.simular`. Con el transporte real, los dos layouts de prueba dan
**440 s vs 350 s** — o sea, ya discrimina.

**2. El optimizador no alcanza factibilidad.**
Converge muy cerca (la violación baja de ~26 a ~0.003) pero no cruza el umbral. Falta afinar
tolerancias o la siembra inicial.

**3. Los dos layouts de las figuras están puestos a mano.**
**No** los produjo el optimizador. Si alguien pregunta, la respuesta honesta es: *"el simulador
ya evalúa, el optimizador aún no cierra factibilidad"*.

**4. La instancia es estructuralmente insuficiente.**
Con 14 000 personas y 32 m de ancho de salidas, la evacuación está limitada por capacidad de
salidas casi sin importar la distribución. Hay que subir el ancho de salidas o bajar el aforo
hasta que la geometría sea lo que manda.

**5. Falta el resto.** Escenario de entrada, MOEA/D y MOPSO, benchmarks, API y Unity.

### Salidas generadas

| Archivo | Qué muestra |
|---|---|
| `salidas/01_operacion.png` | Operación normal, comparación lado a lado. p95 de densidad 3.55 vs 3.13 |
| `salidas/04_carga.png` | Campo de fluido + carga sobre fronteras. Carga pico 30 vs 24 |
| `salidas/06_fluido.gif` | **La evacuación con transporte real.** 98% evacuado en 446 s vs 342 s |

---

## 12. Cómo correrlo

**Usar Python 3.12, no 3.14.** En 3.14 no compilan `scikit-fmm` ni `pymoo` (no hay ruedas).

```bash
py -3.12 -m pip install numpy scipy scikit-fmm pymoo matplotlib

cd prototipo
py -3.12 demo.py           # figura de operación normal
py -3.12 demo_carga.py     # campo de fluido + carga
py -3.12 demo_fluido.py    # GIF de evacuación con transporte real
py -3.12 optimizar.py      # NSGA-II (no alcanza factibilidad todavía)
```

**Arquitectura prevista:** `Optimizador (Python) → FastAPI → Unity`, con **trabajos asíncronos**
(una optimización no cabe en un request HTTP). Regla defendible: **Unity NO simula.** Recibe
campos y los pinta.

> *"Unity calcula cómo se ve el campo, nunca cuál es el campo."*
> Si Unity corriera su propio fluido habría **dos modelos que no se hablan** y la visualización
> dejaría de ser evidencia. La pregunta inevitable del sinodal es *"¿lo que veo es lo que
> optimizaste?"*. Con un solo modelo a dos resoluciones la respuesta es sí, literalmente.

---

## 13. Estado del arte y literatura

> ⚠️ **Antes que nada.** Esta sección es un **mapa para orientarte**, no una bibliografía lista
> para pegar en la tesis. Verifica cada referencia en la fuente original antes de citarla:
> volumen, páginas, año exacto, y sobre todo **cualquier valor numérico**. Un umbral mal citado
> en una tesis de seguridad es un problema serio. Baja los PDF y léelos.

### 13.1 El proyecto está en el cruce de cinco líneas

```
  Facility Layout Problem  ─┐
  (dónde poner las cosas)   │
                            ├──►  ESTE TT
  Modelado de multitudes   ─┤     (el cruce es la contribución)
  (cómo se mueve la gente)  │
                            │
  Seguridad de multitudes  ─┤
  (cuándo se vuelve mortal) │
                            │
  Optimización multiobjetivo┤
  (cómo elegir sin sumar)   │
                            │
  Teoría de flujo de tráfico┘
  (cómo mover masa en una rejilla)
```

Cada línea por separado está muy madura. **Lo que aporta el TT es el acoplamiento**, en
particular usar un modelo continuo de multitud como *función de evaluación dentro de un ciclo
evolutivo* — que es viable precisamente porque el costo del continuo no depende del número de
personas.

---

### 13.2 Línea 1 — Facility Layout Problem

**Qué respalda:** que el problema base es conocido, NP-duro, y que la representación FBS es
estándar y no algo que inventamos.

| Referencia | Qué aporta |
|---|---|
| **Kusiak & Heragu (1987)**, *The facility layout problem*, European Journal of Operational Research | Formulación clásica del problema |
| **Drira, Pierreval & Hajri-Gabouj (2007)**, *Facility layout problems: A survey*, Annual Reviews in Control 31(2) | **Empieza por aquí.** Panorama general y taxonomía |
| **Sahni & Gonzalez (1976)**, *P-complete approximation problems*, Journal of the ACM | La dureza NP del QAP, que es de donde hereda el FLP |
| **Armour & Buffa (1963)** — CRAFT | El primer método clásico; contexto histórico |
| **Tate & Smith (1995)**, *Unequal-area facility layout by genetic search*, IIE Transactions 27(4) | **Clave.** FBS + algoritmo genético. Es el antecedente directo de nuestra representación |
| **Tong (1991)**, tesis doctoral | Origen de la *flexible bay structure*. Verifica la referencia exacta; suele citarse a través de Tate & Smith |
| **Kulturel-Konak & Konak**, trabajos sobre FBS con metaheurísticas | Variantes modernas de FBS |

**Cómo enmarcarlo:** *"El UA-FLP con representación FBS y metaheurísticas está bien establecido
desde los noventa. Lo que cambia aquí es la función de evaluación."*

---

### 13.3 Línea 2 — Modelado de multitudes

Esta es la que **respalda simular multitudes como un fluido**, que es lo que preguntaste.

#### Los dos paradigmas

| | Referencias fundacionales |
|---|---|
| **Microscópico** (agentes) | Helbing & Molnár (1995), autómatas celulares (Burstedde et al., 2001) |
| **Macroscópico** (continuo) | Hughes (2002), Treuille et al. (2006) |

#### El continuo — el respaldo directo de nuestro enfoque

| Referencia | Por qué importa |
|---|---|
| **Hughes, R.L. (2002)**, *A continuum theory for the flow of pedestrians*, Transportation Research Part B 36(6) | **La referencia fundacional.** Es quien formalizó tratar a la multitud como un continuo. Él acuñó la frase *"a thinking fluid"* — un fluido que piensa, justo para marcar que no es un fluido común |
| **Hughes, R.L. (2003)**, *The flow of human crowds*, Annual Review of Fluid Mechanics 35 | Revisión más accesible. **Buena para la introducción de la tesis** |
| **Treuille, Cooper & Popović (2006)**, *Continuum crowds*, ACM Transactions on Graphics (SIGGRAPH) 25(3) | La versión eficiente. **Es la que hace viable meterlo en un ciclo evolutivo**, y de donde viene la idea de un campo de potencial por grupo de destino |

> **La cita clave para tu defensa:** Hughes llamó a la multitud *"a thinking fluid"* precisamente
> porque **no** se mueve por gradiente de presión sino hacia un destino. Si un sinodal cuestiona
> la analogía, esa frase muestra que la limitación está reconocida desde el trabajo fundacional,
> no es un descuido tuyo.

#### El microscópico — nuestro contraste de validación

| Referencia | Por qué importa |
|---|---|
| **Helbing & Molnár (1995)**, *Social force model for pedestrian dynamics*, Physical Review E 51(5) | **El modelo de multitudes más citado que existe.** Es de agentes. Es contra lo que se valida, no lo que se usa para optimizar |
| **Helbing, Farkas & Vicsek (2000)**, *Simulating dynamical features of escape panic*, Nature 407 | Efecto **"faster-is-slower"** y formación de **arcos** en las salidas. Respalda por qué el continuo da tiempos optimistas |

---

### 13.4 Línea 3 — Seguridad de multitudes

**Qué respalda:** los umbrales de densidad, la relación densidad-velocidad, y todo el análisis
de aplastamientos.

#### Diagramas fundamentales (la única física empírica del modelo)

| Referencia | Qué aporta |
|---|---|
| **Weidmann, U. (1993)**, *Transporttechnik der Fußgänger*, IVT / ETH Zürich, Schriftenreihe 90 | **La relación densidad-velocidad que usa el código.** Está en alemán; suele citarse de segunda mano, pero consigue el original o una fuente que reproduzca la fórmula completa |
| **Fruin, J.J. (1971)**, *Pedestrian Planning and Design* | Los **niveles de servicio** peatonales, origen de los umbrales de densidad que se usan en normativa |
| **Seyfried, Steffen, Klingsch & Boltes (2005)**, *The fundamental diagram of pedestrian movement revisited*, J. Statistical Mechanics | Mediciones controladas modernas. **Es contra estas que se valida el 1.22 pers/(s·m)** |
| **Seyfried et al.**, trabajos sobre flujo en cuellos de botella (grupo de Jülich) | Flujo por una puerta según su ancho. **La prueba de nivel 1 de tu validación** |
| **Zhang, Klingsch, Schadschneider & Seyfried**, diagramas fundamentales en distintas geometrías | Que el diagrama depende de la geometría — limitación a declarar |

#### Desastres de multitud

| Referencia | Qué aporta |
|---|---|
| **Helbing, Johansson & Al-Abideen (2007)**, *Dynamics of crowd disasters: An empirical study*, Physical Review E 75, 046109 | **La referencia central.** Presión de multitud, turbulencia de multitud, ondas de paro y arranque. Analiza el desastre del puente Jamarat de 2006. **De aquí sale el umbral crítico — sácalo del paper, no de terceros** |
| **Fruin, J.J. (1993)**, *The causes and prevention of crowd disasters* | Análisis clásico de causas |
| **Still, G.K. (2000)**, tesis doctoral *Crowd Dynamics*, University of Warwick; y **Still (2014)**, *Introduction to Crowd Science* | **El referente práctico** en seguridad de multitudes en eventos. Más orientado a la práctica que a la física — útil para justificar el problema, no el método |

**Casos recientes** para motivar la introducción: Astroworld (2021), Itaewon (2022), Kanjuruhan
(2022). Úsalos para justificar la relevancia, con fuentes periodísticas o informes oficiales
claramente identificados como tales.

---

### 13.5 Línea 4 — Optimización multiobjetivo

| Referencia | Qué aporta |
|---|---|
| **Deb, Pratap, Agarwal & Meyarivan (2002)**, *A fast and elitist multiobjective genetic algorithm: NSGA-II*, IEEE Trans. Evolutionary Computation 6(2) | **El algoritmo.** Ordenamiento no dominado, distancia de apiñamiento, elitismo |
| **Deb, K. (2000)**, *An efficient constraint handling method for genetic algorithms*, Computer Methods in Applied Mechanics and Engineering 186 | **La dominancia restringida** que usamos para las restricciones duras |
| **Zhang & Li (2007)**, *MOEA/D: A multiobjective evolutionary algorithm based on decomposition*, IEEE TEC 11(6) | Comparativo 1 |
| **Coello Coello, Pulido & Lechuga (2004)**, *Handling multiple objectives with particle swarm optimization*, IEEE TEC 8(3) | Comparativo 2 (MOPSO) |
| **Blank & Deb (2020)**, *pymoo: Multi-objective optimization in Python*, IEEE Access 8 | La biblioteca. **Cítala, la estás usando** |
| **Deb, K. (2001)**, *Multi-Objective Optimization using Evolutionary Algorithms* (libro) | Referencia de fondo para el marco teórico |

> 🇲🇽 **Detalle que te conviene:** **Carlos A. Coello Coello** (CINVESTAV-IPN) es una de las
> figuras mundiales de optimización evolutiva multiobjetivo. Citarlo es natural, correcto, y en
> una tesis del IPN cae particularmente bien.

**Para las pruebas estadísticas:**
- **Derrac, García, Molina & Herrera (2011)**, *A practical tutorial on the use of nonparametric
  statistical tests...*, Swarm and Evolutionary Computation 1(1). Friedman, Wilcoxon, correcciones
  post-hoc. **Es la guía práctica estándar** para comparar metaheurísticas.
- **Zitzler & Thiele** sobre hipervolumen como indicador de calidad.

---

### 13.6 Línea 5 — Teoría de flujo de tráfico

**Qué respalda el CTM**, o sea el transporte que mueve la masa en la evacuación.

| Referencia | Qué aporta |
|---|---|
| **Lighthill & Whitham (1955)**, *On kinematic waves II: A theory of traffic flow on long crowded roads*, Proc. Royal Society A 229 | La ecuación **LWR** |
| **Richards, P.I. (1956)**, *Shock waves on the highway*, Operations Research 4(1) | La "R" de LWR, independiente |
| **Daganzo, C.F. (1994)**, *The cell transmission model...*, Transportation Research Part B 28(4) | **El esquema que implementamos.** La regla de demanda contra oferta |
| **Daganzo, C.F. (1995)**, *The cell transmission model, part II: Network traffic*, TR-B 29(2) | Extensión a redes |
| **Sethian, J.A. (1996)**, *A fast marching level set method...*, PNAS 93(4) | **FMM**, el algoritmo que resuelve el campo de tiempos |
| **Zhao, H. (2005)**, *A fast sweeping method for Eikonal equations*, Mathematics of Computation 74 | La alternativa que consideramos y descartamos |

**Cómo enmarcarlo:** *"El transporte de la multitud se resuelve con el mismo esquema numérico
que la ingeniería de tráfico usa desde los noventa para flujo vehicular. No es un método
improvisado."* Esto es un argumento fuerte: le da respaldo a la parte que un sinodal podría
ver como "código casero".

---

### 13.7 Validación de modelos de evacuación

| Referencia | Qué aporta |
|---|---|
| **RiMEA** — *Richtlinie für Mikroskopische Entfluchtungsanalysen* | **La batería de casos de prueba estándar.** Verifica la versión vigente y la lista exacta de casos |
| **ISO 20414** — Verificación y validación de modelos de evacuación de edificios | Norma internacional. Confirma número, año y alcance |
| **IMO MSC.1/Circ.1238** | Análogo para evacuación de buques; a veces citado por su metodología |
| **Ronchi, Nilsson y colaboradores** | Trabajos sobre verificación y validación de modelos de evacuación. **Busca revisiones recientes suyas** |

---

### 13.8 El hueco: dónde entra tu contribución

Lo que **sí** existe abundantemente:

- Optimización de layout minimizando distancia o flujo × distancia (décadas de trabajo)
- Simulación de evacuación para **evaluar** un diseño ya dado
- Optimización de rutas de evacuación y ubicación de salidas
- Modelos continuos de multitud, muy maduros

Lo que **parece** no existir, y es donde entra el TT:

> **Usar un modelo continuo de multitud como función de evaluación dentro de un ciclo de
> optimización multiobjetivo, para decidir la distribución de áreas de servicio en recintos de
> eventos masivos, con restricciones normativas duras.**

⚠️ **"Parece" es la palabra clave.** No afirmes que nadie lo ha hecho hasta haber corrido una
búsqueda sistemática. Un sinodal que conozca un trabajo previo que no citaste es el peor
escenario posible.

**Cómo hacer esa búsqueda:**

1. **Bases:** Scopus, Web of Science, IEEE Xplore, ScienceDirect. Google Scholar solo para
   rastrear citas, no como fuente primaria.
2. **Combinaciones a probar:**
   - `facility layout` + `evacuation`
   - `layout optimization` + `pedestrian` / `crowd`
   - `crowd simulation` + `optimization` / `genetic algorithm`
   - `event venue` / `mass gathering` + `layout`
   - `continuum crowd` + `optimization`
   - `evacuation-aware design` / `safety-oriented layout`
3. **Rastreo hacia atrás y hacia adelante:** de cada paper relevante, revisa sus referencias
   (hacia atrás) y quién lo cita (hacia adelante). Suele dar más que la búsqueda por palabras.
4. **Documenta la búsqueda**: cadenas, fechas, número de resultados. Si el capítulo de estado
   del arte muestra la metodología de búsqueda, la afirmación del hueco se vuelve defendible en
   vez de ser una opinión.

---

### 13.9 Tabla rápida: qué respalda cada decisión

Para cuando te pregunten *"¿y eso en qué te basas?"*:

| Decisión del TT | Referencia que la respalda |
|---|---|
| Tratar a la multitud como continuo | Hughes (2002, 2003); Treuille et al. (2006) |
| Que el costo no dependa del número de personas | Treuille et al. (2006) |
| Que a más densidad menos velocidad | Weidmann (1993); Fruin (1971); Seyfried et al. (2005) |
| El valor de capacidad ~1.2 pers/(s·m) | Seyfried et al. (2005) y trabajos de cuello de botella |
| Umbrales de densidad crítica | Fruin (1971); Helbing et al. (2007); normativa local |
| Presión y turbulencia de multitud | Helbing, Johansson & Al-Abideen (2007) |
| Que el continuo da tiempos optimistas | Helbing, Farkas & Vicsek (2000) — arcos y faster-is-slower |
| Resolver el campo de tiempos con FMM | Sethian (1996) |
| El esquema CTM para el transporte | Daganzo (1994); LWR (1955–56) |
| Representación FBS | Tong (1991); Tate & Smith (1995) |
| Departamentos ficticios para el área libre | Práctica estándar en la literatura de FBS |
| NSGA-II y por qué no suma ponderada | Deb et al. (2002); Deb (2001) |
| Dominancia restringida para restricciones duras | Deb (2000) |
| MOEA/D y MOPSO como comparativos | Zhang & Li (2007); Coello et al. (2004) |
| Friedman + Wilcoxon | Derrac et al. (2011) |
| Batería de validación de evacuación | RiMEA; ISO 20414 |
| Normativa mexicana | NOM-002-STPS; RCDF + NTC; Programa Especial de PC |

---

### 13.10 Por dónde empezar a leer

Si tienes poco tiempo, en este orden:

1. **Drira et al. (2007)** — panorama del FLP en una sentada
2. **Hughes (2003)** en *Annual Review of Fluid Mechanics* — el continuo, accesible
3. **Deb et al. (2002)** — NSGA-II, el paper original es claro y corto
4. **Helbing et al. (2007)** — el de los desastres; es el que más te va a servir para argumentar
   por qué el problema importa
5. **Tate & Smith (1995)** — para ver FBS + GA funcionando, que es casi tu esqueleto
6. **Daganzo (1994)** — solo si te cuestionan el esquema numérico

---

## 14. Glosario

| Término | En cristiano |
|---|---|
| **UA-FLP** | Problema de acomodar áreas de distinto tamaño en un espacio |
| **NP-duro** | Las combinaciones crecen tan rápido que probarlas todas es imposible |
| **Metaheurística** | Método que busca una solución muy buena sin garantizar la óptima |
| **FBS** | Cortar el recinto en bandas y apilar bloques dentro de cada una |
| **Departamento ficticio** | Bloque que representa piso libre, para que FBS pueda repartir todo |
| **Eikonal** | Ecuación cuya solución es "cuánto tardas en llegar" desde cada punto |
| **FMM** | Algoritmo que la resuelve inundando desde el destino hacia afuera |
| **Campo de tiempos (T)** | Mapa de segundos hasta el destino más cercano |
| **Gradiente** | La dirección en la que un campo cambia más rápido; aquí, hacia dónde caminar |
| **Diagrama fundamental** | La relación medida densidad ↔ velocidad de peatones |
| **Weidmann** | La fórmula concreta de esa relación |
| **Punto fijo** | Repetir un cálculo circular hasta que deje de cambiar |
| **LWR** | Ecuación clásica de conservación del flujo de tráfico |
| **CTM** | Esquema numérico que la resuelve sobre una rejilla, con colas |
| **Godunov** | La receta para calcular cuánta masa pasa entre dos celdas vecinas |
| **Advección** | Que algo sea arrastrado por una corriente |
| **Difusión** | Que algo se disperse por sí solo |
| **Percentil 95** | El valor que solo supera el 5% más alto |
| **Dominancia** | A es mejor o igual en todo, y mejor en algo |
| **Frente de Pareto** | El conjunto de compromisos que nadie supera en todo |
| **Elitismo** | Que los buenos padres compitan contra sus hijos |
| **Distancia de apiñamiento** | Preferir soluciones en zonas vacías, para que el frente salga extendido |
| **OX** | Cruza que respeta que el hijo siga siendo una permutación |
| **Presión de multitud** | Densidad × variación de velocidad. Indicador de peligro (Helbing) |
| **Turbulencia de multitud** | Régimen donde la gente es desplazada sin control |
| **Estancamiento** | Atasco irreversible: el flujo colapsa a cero y no se recupera |
| **Cadenas de fuerza** | Unos pocos caminos de contacto cargan casi todo el empuje |
| **Histéresis** | Que el estado dependa de la historia, no solo de las condiciones actuales |
