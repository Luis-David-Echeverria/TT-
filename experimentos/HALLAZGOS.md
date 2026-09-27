# ¿Es multiobjetivo el problema? — resultado del barrido f₁ vs f₂

Registro del experimento del 2026-09-23. Reproducible con:

```
py -3.12 experimentos/correlacion.py -n 300 --aforos 2000 3000 4000 --modos amplio estricto
py -3.12 experimentos/analisis.py
py -3.12 experimentos/seleccion.py
```

1 776 evaluaciones en `datos/evaluaciones.db`, exportadas a `datos/correlacion_f1_f2.csv`.
La configuración completa de cada fila está en la tabla `configs` de la misma base,
así que el CSV se puede leer dentro de un año sin tener el código a mano.

**Parámetros:** h = 1 m, dt = 0.3 s, k_c = 8, p = 3, t_max = 600 s, σ = 1.0,
reparto inicial uniforme, recinto 100×60 m con 4 salidas y 2 obstáculos fijos.

---

## Lo que se midió

| | |
|---|---|
| **f₁** | distancia media caminando por visita, con asignación capacitada resuelta por transporte exacto |
| **f₂** | t_des (desalojo), t95, E (exposición sobre ρ_c), ρ_pico |

Dos poblaciones de layouts: **amplia** (solo lo estructural + alcanzable) y
**estricta** (capa geométrica completa). Tres aforos.

---

## Resultado 1 — f₁ y f₂ son independientes

Spearman entre f₁ y t_des, en las seis combinaciones:

| modo | aforo | ρ | IC 95 % |
|---|---|---|---|
| amplio | 2000 | +0.068 | [−0.049, +0.181] |
| amplio | 3000 | +0.037 | [−0.082, +0.160] |
| amplio | 4000 | +0.064 | [−0.058, +0.181] |
| estricto | 2000 | −0.098 | [−0.213, +0.017] |
| estricto | 3000 | −0.260 | [−0.358, −0.156] |
| estricto | 4000 | −0.203 | [−0.310, −0.094] |

Nunca hay correlación positiva fuerte. Eso descarta la hipótesis que habría
matado al multiobjetivo: **f₂ no se puede deducir de f₁**.

## Resultado 2 — el conflicto del modo estricto lo fabrica el filtro

La misma población amplia, partida por factibilidad:

| aforo | sin filtrar | solo factibles | solo infactibles |
|---|---|---|---|
| 2000 | +0.068 | −0.175 | +0.144 |
| 3000 | +0.037 | **−0.216** | +0.097 |
| 4000 | +0.064 | −0.039 | +0.066 |

El total es cero y las dos mitades tienen signos opuestos. Es el patrón de un
**efecto de selección**: condicionar sobre un criterio que se relaciona con los
dos objetivos induce correlación entre ellos aunque sean independientes.

**Consecuencia para el diseño del algoritmo:** filtrar por factibilidad antes de
medir contamina la medición. Coincide con lo que ya se había decidido para el
optimizador — los infactibles se quedan en la población y se ordenan por
dominancia restringida, no se rechazan.

## Resultado 3 — el frente de Pareto es del tamaño que predice la independencia

Con n puntos y dos objetivos independientes, el número esperado de no dominados
es el número armónico H_n ≈ ln n + 0.577 ≈ **6.3** para n = 300.

Observado: 4, 5, 5, 6, 7, 8. No hay un solo escenario donde el frente sea mayor
que lo que predice la pura independencia. Confirma el resultado 1 por otra vía.

## Resultado 4 — tres de las cuatro métricas de f₂ sobran

| par | ρ | lectura |
|---|---|---|
| t_des ~ t95 | +0.65 a +0.81 | redundantes |
| t_des ~ E | +0.26 a +0.49 | E aporta algo propio |
| t_des ~ ρ_pico | +0.14 a +0.44 | — |

Y **ρ_pico no sirve como objetivo**: CV de 1.2 % a 3.0 %, siempre entre 4.8 y
5.1 p/m². Se satura en la densidad de atasco frente a las puertas en todos los
layouts, así que no distingue nada. Se descarta.

f₂ debe ser **una** métrica de evacuación, no cuatro. Candidatas: t_des o E.

## Resultado 5 — el layout solo importa si el recinto no está lleno

Medido aparte, con 10 layouts:

| aforo | t_des/t_mín | CV t_des | señal/ruido |
|---|---|---|---|
| 2000 | 1.51 | 11.9 % | 56.6 |
| 4000 | 1.15 | 3.7 % | 6.3 |
| 6000 | 1.11 | 3.3 % | 8.6 |
| 16000 | 1.02 | 1.2 % | — |

Al aforo de diseño (ρ_d = 3.5 → 19 908 personas) la cota física de las puertas
es de 563 s y todo layout se clava ahí: **no habría experimento**. Por eso el
aforo se trató como eje del barrido y no como dato.

---

## Qué queda justificado

**El multiobjetivo, sí** — pero el argumento no es "hay conflicto" sino
**"son independientes"**: optimizar f₁ deja a f₂ prácticamente al azar, y al
revés. Es un argumento más fuerte que el conflicto, y es el que sostienen los
datos.

**La suma ponderada, no.** Con objetivos independientes, barrer pesos de 0.1 a
0.9 no recorre un compromiso: se desliza por un eje y luego por el otro. La
prueba de suma ponderada que se había planteado al principio ya no tiene sentido
como forma de decidir si el problema es multiobjetivo — esta matriz lo contesta
directamente.

## Límites de este resultado

No se ha medido más que esto, y conviene escribirlo antes de que se cite de más:

1. **Una sola geometría.** Nave rectangular 100×60 con 4 salidas repartidas y 2
   obstáculos fijos. La independencia podría ser de esta planta.
2. **Reparto inicial uniforme.** Ya estaba medido que es el caso que menos
   discrimina; con la multitud concentrada frente a un escenario la diferencia
   entre layouts sube a 5–15 %. Falta repetir el barrido así.
3. **σ = 1 y unidades de catálogo sin ficha.** f₁ depende de cuántas unidades de
   atención tiene cada módulo; esas cifras siguen PENDIENTE.
4. **p = 3 sin respaldo empírico.** Es el único parámetro del modelo sin fuente.
   Medido: el orden de t_des es frágil a p, el de E aguanta mejor. Razón extra
   para preferir E como métrica de f₂.
