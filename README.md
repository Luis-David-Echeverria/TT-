# Distribución óptima de áreas de servicio en eventos masivos mediante algoritmos bioinspirados

Trabajo Terminal — Ingeniería en Inteligencia Artificial, ESCOM · IPN.

**▶ Informe interactivo: https://luis-david-echeverria.github.io/TT-/**

No hace falta instalar nada. Trae las ecuaciones, los datos, y las gráficas y
simulaciones corriendo de verdad en el navegador.

---

Herramienta que decide **dónde colocar los módulos de servicio** (sanitarios,
comida, bebidas, primeros auxilios) dentro de un recinto para un evento masivo.
El usuario dibuja los muros y las salidas y dice **cuántos** módulos de cada
tipo quiere; dónde van lo decide el sistema.

Lo que la distingue de un problema de acomodo clásico es cómo se evalúa cada
distribución: no con distancias en línea recta, sino con un **modelo continuo de
multitud** que simula la evacuación. Así un acomodo que estorba una ruta se
castiga solo, sin necesidad de una regla que lo prohíba.

---

## La pregunta de esta etapa, y su respuesta

> ¿Acercar a la gente a los servicios pelea con evacuar rápido? Es decir: ¿es
> este un problema genuinamente multiobjetivo, o basta optimizar una sola cosa?

De la respuesta depende toda la arquitectura del trabajo, así que se midió antes
de implementar el optimizador.

**Sí es multiobjetivo.** Con dos funciones objetivo:

| | qué mide | de dónde sale |
|---|---|---|
| **f₁** accesibilidad | distancia media que camina una persona hasta el módulo que la atiende | problema de transporte capacitado |
| **f₂** tiempo de evacuación | segundo en que el recinto queda vacío | simulación de fluido |

### La evidencia, en cuatro pasos

**1. Las dos varían con el layout.** Sobre 100 layouts factibles al azar
(aforo 2 000): f₁ con CV de 12.3 % (rango 20.3–37.3 m) y el tiempo con CV de
11.4 % (73.2–121.5 s). Si una saliera constante, no habría nada que optimizar en
ella — así se descartó ρ pico, con CV de 1.2 a 3.0 %.

**2. Ninguna predice a la otra.** Spearman **ρ = +0.014**, intervalo al 95 %
**[−0.200, +0.238]**. El error típico esperado para n = 100 es ±0.101, así que
ese +0.014 es cero con ruido, no «correlación débil positiva».

> Lo que habría matado al multiobjetivo era un ρ alto y positivo (≈ +0.8): ahí
> una función predice a la otra y basta optimizar una. No ocurrió en ninguno de
> los 6 escenarios del barrido.

**3. Existe un frente de Pareto real.** La correlación sobre muestras aleatorias
no puede verlo —una muestra al azar nunca llega a la frontera— así que se trazó
con un **barrido ε-restringido** (Haimes et al., 1971): para cada tope τ,
minimizar f₁ sujeto a que el tiempo no pase de τ.

| f₁ (m) | t evacuación (s) | ¿la alcanza un barrido de pesos? |
|---|---|---|
| 16.882 | 80.4 | sí |
| 16.989 | 78.6 | sí |
| **18.158** | **75.9** | **NO — inalcanzable** |
| **19.283** | **73.5** | **NO — inalcanzable** |
| 19.419 | 71.7 | sí |
| 21.149 | 69.6 | sí |
| 25.176 | 68.1 | sí |

**4. El frente es no convexo**, y eso decide el método. Minimizar
`w·f₁ + (1−w)·f₂` equivale a deslizar una recta hasta que toca el conjunto
factible, y una recta solo puede tocar el casco convexo: si el frente tiene una
hendidura, la recta pasa por encima. Esos dos puntos **no salen peores — el
método no puede verlos** (Das & Dennis, 1997). Por eso hace falta ordenar por
dominancia y no por un escalar.

### Lo que dijo el barrido de pesos

Es la prueba clásica, y **la pasa**: 9 soluciones distintas de 11 pesos,
recorriendo 70 % en accesibilidad y 17 % en tiempo. Los extremos son los casos
mono-objetivo y son los más informativos:

| peso de f₁ | peso de f₂ | acceso | t evac | |
|---|---|---|---|---|
| 0.0 | 1.0 | 28.57 m | 69.0 s | solo tiempo |
| 0.5 | 0.5 | 17.02 m | 77.7 s | equilibrio |
| 1.0 | 0.0 | 16.92 m | 77.4 s | solo accesibilidad |

Optimizando **solo el tiempo**, la accesibilidad se va a 28.57 m — **peor que la
mediana de los layouts al azar (24.76 m)**. No es que deje la otra función donde
estaba: la empeora activamente.

**Un matiz que conviene llevar a la junta.** Un barrido de pesos solo puede
devolver puntos del casco convexo, así que la curva que dibuja *siempre* se ve
convexa. «Salió convexo» es una propiedad del método, no un hallazgo sobre el
problema. El barrido sirve para probar que **es** multiobjetivo; no sirve para
medir la forma del frente.

---

## Decisiones de modelado, y por qué

Cada una se tomó midiendo, y varias corrigieron una versión anterior. Están
explicadas con sus ilustraciones en el informe interactivo.

### Las dos funciones objetivo

**f₁ por transporte capacitado, no por «cada quien al más cercano».** Un módulo
atiende a un ritmo finito; si todos van al mismo, ese se satura. La versión
voraz —recorrer celdas mandando cada una a la más cercana con cupo— da un
resultado **que depende del orden en que se recorre la rejilla**. Medido: ese
ruido es de 5.4 % en promedio y hasta 13 %, contra 2.0 % de separación real entre
layouts. **2.7× la señal**: ordenaría por el barrido de la rejilla, no por el
layout.

**Distancia geodésica sembrada en el borde del módulo, no en su centroide.** El
centroide cae dentro de un obstáculo y el campo no tiene por dónde propagarse;
medido en línea recta, atraviesa el propio módulo y los muros. La gente llega a
la barra, no al centro del puesto.

**Tiempos de servicio y tasas de visita: descartados.** La primera versión de f₁
derivaba la capacidad de `unidades/τ` y la demanda de `aforo·tasa`. Se cayó por
dos motivos, y el segundo es el grave: con valores plausibles la demanda salía
3 a 8 veces la capacidad, lo que vuelve el transporte **infactible** y deja f₁
sin definir; y τ y la tasa de visita no son constantes físicas ni dimensiones de
producto, son comportamiento de público. Ahora la capacidad relativa sale del
**conteo de unidades de atención** del módulo, que sí es ficha de proveedor.

**E (exposición) y ρ pico se miden pero no se optimizan.** Por una razón física:
la densidad alta ya se castiga sola en el tiempo, porque por Weidmann donde la
gente se apretuja camina más lento. Una métrica de densidad aparte no agrega un
compromiso nuevo — es otra forma de mirar lo mismo. Se reportan como datos.

### El modelo de multitud

**Continuo y no agentes.** Por encima de ρ_c = 4 pers/m² la gente pierde el
movimiento propio y la desplaza la presión del grupo (van Toll et al., 2021):
justamente la decisión individual que los modelos de agentes simulan es la que
deja de ocurrir.

**Esquema de Godunov con oferta y demanda separadas.** Si el flujo saliente se
calculara como ρ·v(ρ), una celda saturada tendría velocidad cero, dejaría de
entregar masa y **se congelaría para siempre**, con un moteado de tablero
alrededor. La demanda se satura en q_max en vez de caer a cero; lo que cae es la
oferta. La cola se forma por el que recibe, que es el mecanismo real.

**Las puertas son sección transversal con zona de drenaje.** Drenando solo la
fila del borde, una puerta de 12 m rendía **71 %** de su capacidad nominal,
porque el reparto de Godunov manda parte de la masa de lado. Con la zona de
drenaje trabaja al 100 % a todos los anchos. Comprobado además que igualar
J_s = q_max **no** lo arregla (seguía en 76–81 %): la zona es necesaria de todos
modos.

### La geometría

**Un recoveco no es una infracción: es superficie que no se puede usar.** La
primera versión contaba los huecos donde no se entra con el ancho de reglamento
como violación de seguridad, y rechazaba el 87 % de las colocaciones. Al
reformularlo —esa superficie simplemente sale del área útil— la aceptación subió
al **88 %** sin relajar ningún criterio.

**G6 hubo que agregarla.** El sistema colocó un módulo sanitario dentro de una
bolsa sellada por los muros del usuario: no pisaba nada, no invadía ningún cono
de salida, y como esa bolsa ya era inservible tampoco reducía el área útil.
**Pasaba las cinco reglas anteriores siendo un baño al que nadie podía entrar.**

**El aforo de referencia se congela.** Si variara por layout, encerrar espacio
quitaría gente y menos gente evacúa más rápido: el optimizador descubriría que
amurallar el recinto mejora su aptitud. Con el aforo fijo ocurre lo contrario —
la misma gente en menos espacio sube la densidad y empeora el tiempo.

### El experimento

**El aforo es un eje del barrido, no un dato.** Al aforo de diseño de este
recinto (19 908 personas) la cota física de las puertas es de 563 s y **todo
layout se clava ahí**. Medido, el CV del tiempo entre layouts cae de 11.9 % con
2 000 personas a 1.2 % con 16 000. O sea: **el layout solo importa si el recinto
no está lleno.**

**Filtrar por factibilidad antes de medir contamina la medición.** La misma
población amplia partida por factibilidad da ρ = −0.216 en una mitad y +0.097 en
la otra, siendo el total cero. Es un efecto de selección: condicionar sobre un
criterio que se relaciona con los dos objetivos induce correlación entre ellos
aunque sean independientes.

**Dos poblaciones, a propósito.** «Amplia» (solo lo estructural) da la nube sin
recortar; «estricta» (la capa geométrica completa) solo lo que aceptaría
protección civil. Si las dos matrices coinciden, la conclusión aguanta.

### Un resultado que contradijo lo que suponíamos

Damos por hecho que el muestreo por rechazo es peor que las reglas de
factibilidad de Deb (2000). **Medido con el mismo presupuesto y 3 semillas:
empatan.** La diferencia quedó dentro del ruido y el tiempo fue el mismo —
probablemente porque la región factible aquí es amplia y bien conectada, así que
el rechazo casi nunca bloquea un camino que importe.

Se usará dominancia restringida igual (en multiobjetivo hace falta de todos
modos), pero **no se puede presentar como una mejora de rendimiento**.

---

## Discretización: elegida midiendo el ORDEN, no el valor

Lo que un optimizador por dominancia usa es el **orden** entre layouts. Un
parámetro numérico puede converger en valor mucho antes de converger en orden, y
medir lo primero lleva a elegirlo demasiado grueso.

| | valor | por qué |
|---|---|---|
| `h` lado de celda | 1 m | A 2 m el orden entre layouts se rompe: ρ = 0.107 |
| `Δt` paso de tiempo | 0.3 s | Cota CFL = h/v₀ = 0.746 s. Con 1.0 s se viola y el orden cae a 0.798 |
| `k_c` refresco del campo | 8 pasos | Medido sobre 14 layouts contra k_c=2: k_c=6 → 0.945; **k_c=8 → 0.941 y 19 % más barato**; k_c=12 → 0.843 ✗ |
| `p` exponente de reparto | 3 | **El único parámetro del modelo sin respaldo empírico.** Sensibilidad medida: al variar p de 1 a 4, el orden de t_des cae a 0.373 |

---

## Validaciones

| qué | resultado |
|---|---|
| Conservación de masa | error relativo 5×10⁻¹⁵ |
| q_max y ρ_opt derivados de Weidmann | 1.2249 pers/(m·s) y 1.751 pers/m² — no se ponen a mano |
| Capacidad de salidas | 100 % del flujo nominal, a todos los anchos |
| Solver de transporte por coordenadas vs programación lineal | **ρ = 1.000000, cero inversiones en 1 225 pares**, y 9.6× más rápido |
| Kernel compilado con Numba vs NumPy | idénticos a 4.3×10⁻¹⁴ |
| Motor de JavaScript vs motor de Python | ver abajo |

### El motor del navegador

El informe no lleva simulaciones precalculadas: las calcula el navegador con el
mismo modelo portado a JavaScript. Eso solo se sostiene si coincide con Python,
que es la fuente de verdad. El criterio no es «¿dan el mismo número?» sino
**¿la diferencia entre motores es chica frente a la diferencia entre layouts?**

| | dif. entre motores | dif. entre layouts | razón |
|---|---|---|---|
| f₁ accesibilidad | 0.166 m | 2.140 m | **0.08** |
| tiempo de evacuación | 1.080 s | 8.627 s | **0.13** |
| E exposición | 117 | 174 | 0.67 ✗ |

Los dos objetivos se reproducen. E no, y la razón es estructural: cuenta celdas
que cruzan un umbral de densidad, así que una diferencia de milésimas hace saltar
el conteo. No es objetivo, así que se muestra el valor medido en Python.

**El bug que lo destrabó:** `scikit-fmm` usa estencil de **segundo orden** por
defecto y el barrido inicial era de primero — un sesgo del 1.9 % en todo el
campo. Con el estencil de tres puntos, f₁ pasó de ρ = 0.993 a 1.000000.

---

## Lo que NO está medido

Hay que decirlo antes de que se cite de más:

1. **Una sola geometría.** Nave rectangular de 100×60 m con 4 salidas repartidas
   y 2 obstáculos fijos. Los recorridos del frente podrían ser de esta planta.
2. **Reparto inicial uniforme.** Está medido que es el caso que MENOS discrimina
   entre layouts; con la multitud concentrada frente a un escenario las
   diferencias suben a 5–15 %. Falta repetir el barrido así.
3. **No se comparó NSGA-II contra otras metaheurísticas.** Si la tesis afirma que
   es *el* método adecuado, eso hay que medirlo. Lo que está establecido es que
   hace falta un método por dominancia, no que sea ese en particular.
4. **6 parámetros PENDIENTE** sin fuente verificada — ver abajo.
5. **El optimizador no está implementado.** `nucleo/optimizar.py` es de un solo
   objetivo, optimiza una métrica redundante, y su función serial está rota
   (llama a un nombre que no existe). Ver `experimentos/OPTIMIZADOR.md`.

### Parámetros sin fuente verificada

`P.pendientes()` los lista. Hoy son 6, y bloquean la tesis hasta que se citen:

| símbolo | qué es | dónde buscar |
|---|---|---|
| `J_s` | flujo específico máximo de salida | Seyfried et al., experimentos de cuello de botella |
| `b` | capa límite por jamba | Seyfried et al. |
| `w_min` | ancho libre mínimo de circulación | RCDF + NTC de Proyecto Arquitectónico |
| `d_max` | distancia máxima a una salida | NOM-002-STPS-2010 / reglamento contra incendios |
| `t_lim` | tiempo máximo de desalojo | Programa Especial de Protección Civil |
| `d_s` | profundidad del área de descarga de salidas | RCDF / NTC |

> **Cuidado con la cifra de 40 s** que circula como tiempo de desalojo. La cota
> física es `t_min = N/(J_s·ancho_útil)` y ninguna distribución la baja: para
> 5 000 personas en 40 s harían falta 95 m de salida útil, y para 20 000, 379 m —
> más que el perímetro completo de una nave de 100×60 m. No puede referirse al
> desalojo total de un evento masivo.

---

## Cómo correrlo

### Solo ver el informe

https://luis-david-echeverria.github.io/TT-/ — o, localmente:

```bash
cd sitio && py -3.12 -m http.server 8080
```

No sirve abrir `index.html` con doble clic: el navegador bloquea leer los JSON
por `file://`.

### La herramienta completa, con el simulador

```bash
py -3.12 -m pip install -r requirements.txt
py -3.12 -m uvicorn api.main:app --port 8000      # o: servir.bat
```

En **http://localhost:8000** hay dos pestañas: *Simulador* (dibujar muros y
salidas, comparar acomodos) y *Resultados* (el informe).

La interfaz viene compilada en `web/`, así que no hace falta Node. Solo para
modificarla:

```bash
cd ui && npm install
npm run dev          # desarrollo, puerto 5173
npm run build        # recompila a ../web/
npm run build:sitio  # recompila el sitio estático a ../sitio/
npm run prueba       # las dos pruebas del motor de JavaScript
```

### Reproducir los experimentos

Nada se recalcula si ya está en la base, así que volver a correrlos es barato.

```bash
py -3.12 experimentos/correlacion.py -n 300 --aforos 2000 3000 4000 --modos amplio estricto
py -3.12 experimentos/analisis.py            # matriz de correlación con intervalos
py -3.12 experimentos/seleccion.py           # ¿el conflicto lo fabrica el filtro?
py -3.12 experimentos/correlacion_simple.py  # 100 layouts: acceso vs evacuación
py -3.12 experimentos/frente_epsilon.py      # el frente real, por ε-restricción
py -3.12 experimentos/barrido_pesos.py       # la prueba del barrido de pesos
py -3.12 experimentos/validar_js.py          # ¿coincide el motor del navegador?
py -3.12 experimentos/exportar_sitio.py      # regenera sitio/ para publicar
```

Las corridas que exploran el optimizador (`potencial.py`, `frente.py`,
`restricciones.py`, `surrogado_f1.py`) están documentadas en
`experimentos/OPTIMIZADOR.md`.

---

## Cómo está organizado

```
nucleo/          el modelo. No sabe que existe una API ni una interfaz.
  parametros.py    TODOS los números, cada uno con su procedencia y su estado
  recinto.py       recinto, catálogo de módulos, representación del layout
  campos.py        ecuación Eikonal (Fast Marching) y estimación de aforo
  fluido.py        Weidmann + conservación de masa por Godunov/CTM
  kernel.py        el paso de Godunov compilado con Numba
  geometria.py     las restricciones duras G1–G6
  acceso.py        f₁: asignación capacitada por transporte exacto
  muestreo.py      generación de layouts para experimentar
  almacen.py       persistencia en SQLite: no recalcular lo ya calculado
  optimizar.py     de un solo objetivo — hay que reescribirlo (ver OPTIMIZADOR.md)

api/             FastAPI. Contrato estable, internos libres.
ui/              React + Vite + Tailwind
  src/modelo/      el modelo portado a JavaScript, para que el informe calcule
  src/informe/     las secciones del informe y sus ilustraciones
web/             la interfaz compilada que sirve la API
sitio/           el informe como sitio estático — esto es lo que publica Pages
experimentos/    los scripts que producen los resultados, y los hallazgos
datos/           los resultados: base SQLite, CSV y los dos frentes
docs/            marco teórico y estado del arte
```

### Los resultados vienen incluidos

| archivo | qué es |
|---|---|
| `datos/evaluaciones.db` | 3 552 evaluaciones (SQLite). Cada fila trae su layout, sus métricas y el hash de su configuración; la tabla `configs` guarda esa configuración completa, así que la base se puede leer sin el código. |
| `datos/correlacion_f1_f2.csv` | la misma tabla, para figuras |
| `datos/frente_epsilon.json` | el frente ε-restringido, con la trayectoria de cada corrida |
| `datos/barrido_pesos.json` | el barrido de pesos, con los extremos mono-objetivo |
| `experimentos/HALLAZGOS.md` | ¿es multiobjetivo el problema? |
| `experimentos/OPTIMIZADOR.md` | investigación del optimizador: qué sí, qué no |
| `docs/MARCO-TEORICO.md` | qué se hace, cómo y por qué, con estado del arte y glosario |

---

## Tres reglas del proyecto

**1. Ningún número se inventa.** Cada parámetro vive en `nucleo/parametros.py`
declarando su estado y su fuente:

| estado | qué significa |
|---|---|
| `medido` | valor empírico publicado → se cita |
| `derivado` | se calcula de otros → no requiere cita propia |
| `normativo` | lo fija un reglamento → se cita artículo |
| `catalogo` | dimensión de equipo comercial → ficha de proveedor |
| `numerico` | discretización → requiere análisis de convergencia |
| `calibrar` | modelado → requiere análisis de sensibilidad |
| `PENDIENTE` | sin fuente verificada → **bloquea la tesis** |

**2. La interfaz no calcula nada del modelo por su cuenta.** Ni Weidmann, ni
umbrales, ni la paleta: todo viene del registro de parámetros. El motor de
JavaScript es un puerto medido contra Python, no una segunda opinión — y su
acuerdo se verifica en `experimentos/validar_js.py`.

**3. Todo experimento es reproducible.** Semilla explícita, configuración
completa guardada junto a los resultados, y `SeedSequence.spawn` para que el
layout *k* sea el mismo aunque cambie *n* o el orden de ejecución.

---

## Fuentes

**Dinámica de peatones y flujo**

- **Weidmann, U.** (1993). *Transporttechnik der Fussgänger.* Schriftenreihe des IVT Nr. 90, ETH Zürich. — el diagrama fundamental: v₀, ρ_max, γ.
- **Fruin, J. J.** (1971). *Pedestrian Planning and Design.* — ajuste alternativo que da ρ_max = 4.08; la discrepancia con Weidmann exige análisis de sensibilidad.
- **Helbing, D., Johansson, A., & Al-Abideen, H. Z.** (2007). Dynamics of crowd disasters: an empirical study. *Physical Review E*, 75(4), 046109.
- **van Toll, W., et al.** (2021). SPH-enhanced crowd simulation. *Computers & Graphics.* INRIA hal-03270915. — la densidad a la que se pierde el movimiento propio.
- **Seyfried, A., et al.** Experimentos de cuello de botella, grupo de Jülich. — J_s y la capa límite. *Cita exacta pendiente.*
- **SFPE.** *Handbook of Fire Protection Engineering*, cálculo de egreso.

**Modelo continuo y esquema numérico**

- **Lighthill, M. J., & Whitham, G. B.** (1955) y **Richards, P. I.** (1956). — la ley de conservación (LWR).
- **Hughes, R. L.** (2002). A continuum theory for the flow of pedestrians. *Transportation Research Part B*, 36(6), 507–535.
- **Treuille, A., Cooper, S., & Popović, Z.** (2006). Continuum crowds. *ACM TOG*, 25(3), 1160–1168. — separar dirección y magnitud; el estimador de densidad por núcleo.
- **Daganzo, C. F.** (1994). The cell transmission model. *Transportation Research Part B*, 28(4), 269–287. — oferta y demanda.
- **Lebacque, J. P.** (1996). The Godunov scheme and what it means for first order traffic flow models. *13th ISTTT.*
- **Sethian, J. A.** (1996). A fast marching level set method for monotonically advancing fronts. *PNAS*, 93(4), 1591–1595.
- **Quinn, P., et al.** (1991) y **Holmgren, P.** (1994). — algoritmos de dirección de flujo múltiple en hidrología; la analogía citable para el exponente p.

**Localización y transporte**

- **Hakimi, S. L.** (1964). Optimum locations of switching centers… *Operations Research*, 12(3), 450–459. — la p-mediana.
- **Kariv, O., & Hakimi, S. L.** (1979). An algorithmic approach to network location problems. II: The p-medians. *SIAM J. Appl. Math.*, 37(3), 539–560. — la parte NP-dura es la ubicación, no la asignación.
- **Ahuja, R. K., Magnanti, T. L., & Orlin, J. B.** (1993). *Network Flows.* Prentice Hall.
- **Bertsekas, D. P.** (1988). The auction algorithm. *Annals of Operations Research*, 14, 105–123. — ajuste de precios duales.

**Optimización multiobjetivo**

- **Deb, K.** (2000). An efficient constraint handling method for genetic algorithms. *CMAME*, 186(2–4), 311–338. — dominancia restringida.
- **Deb, K., Pratap, A., Agarwal, S., & Meyarivan, T.** (2002). NSGA-II. *IEEE Trans. Evol. Comput.*, 6(2), 182–197.
- **Das, I., & Dennis, J. E.** (1997). A closer look at drawbacks of minimizing weighted sums of objectives… *Structural Optimization*, 14(1), 63–69. — por qué la suma ponderada no alcanza las regiones no convexas.
- **Haimes, Y. Y., et al.** (1971). — el método ε-restringido.

**Geometría y normativa**

- **Soille, P.** (2003). *Morphological Image Analysis.* Springer. — erosión y dilatación.
- **Secretaría del Trabajo y Previsión Social.** NOM-002-STPS-2010. *Verificar redacción.*
- **RCDF + Normas Técnicas Complementarias** para el Proyecto Arquitectónico. *Por extraer.*
- **PSAI — Portable Sanitation Association International.** *Standards for Special Events.*

**Herramientas**

numpy · scipy (HiGHS, ndimage, stats) · scikit-fmm · numba · FastAPI · Pydantic ·
React · Vite · Tailwind · Recharts · KaTeX
