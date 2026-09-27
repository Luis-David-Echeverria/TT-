# El optimizador: qué sí, qué no, y por qué

Investigación del 2026-09-23, con todo medido sobre el recinto de ejemplo
(100×60 m, 4 salidas, 2 obstáculos fijos, 9 módulos, aforo 2 000, reparto
uniforme). Reproducible con:

```
py -3.12 experimentos/potencial.py      # costo, margen y efecto cruzado
py -3.12 experimentos/frente.py         # NSGA-II: cómo es el frente real
py -3.12 experimentos/restricciones.py  # rechazo vs dominancia restringida
py -3.12 experimentos/surrogado_f1.py   # se puede abaratar f1?
```

---

## 0. Lo que cambia respecto a lo que creíamos

**La nube aleatoria nos mintió, y por una razón que tiene nombre.**

El barrido de 1 776 layouts al azar dijo que f₁ y f₂ son independientes
(ρ ≈ +0.04 a +0.07). De ahí salió el argumento "son independientes, por eso hace
falta multiobjetivo". Ese argumento era correcto pero **débil, y por poco nos
lleva a elegir mal los objetivos**.

Al optimizar de verdad aparece otra cosa. Sobre el frente de Pareto de
(f₁, t_des):

| f₁ (m) | t_des (s) |
|---|---|
| 9.63 | 78.0 |
| 11.73 | 70.5 |
| 14.73 | 66.3 |

Eso es un compromiso claro, en una región donde la nube aleatoria no veía nada.
No es contradicción: la correlación mide cómo se mueven dos métricas en la
región **típica**, y el frente vive en el **borde**, donde casi no hay masa de
la distribución. Un optimizador no pasa su vida en la región típica — se va al
borde en las primeras generaciones.

**Consecuencia metodológica:** decidir la arquitectura del algoritmo mirando
solo correlaciones de muestras aleatorias es un error. La matriz de correlación
sigue siendo válida para lo que contestó (¿se puede deducir un objetivo del
otro? no), pero **no** sirve para elegir qué pares optimizar.

---

## 1. ¿Hay margen? Sí, y es grande

| métrica | mediana al azar | mejor de 120 al azar | mejor encontrado | ganancia |
|---|---|---|---|---|
| f₁ | 24.10 m | 19.03 m | **8.35 m** | **−65 %** |
| t_des | 81.90 s | 75.60 s | **64.20 s** | **−22 %** |
| E | 748.50 m²·s | 269.10 | **42.90** | **−94 %** |

El azar ni se acerca. Con 120 muestras aleatorias lo mejor en f₁ es 19.03 m;
NSGA-II llega a 8.35 m con 2 448 evaluaciones. **Hay tesis.**

Contexto de por qué el azar no basta: el espacio de búsqueda tiene
**10^45.2** layouts distintos quitando simetrías (posiciones cuantizadas a
0.25 m, 9 módulos, 2 rotaciones). A las 21 evaluaciones/s que medimos, enumerarlo
tomaría 10^36.5 años. La metaheurística no es una comodidad, es la única opción.

---

## 2. Qué objetivos — esta es la decisión importante

Cuatro corridas de NSGA-II, misma semilla, población 48, 50 generaciones,
2 448 evaluaciones cada una:

| objetivos | no dominados | recorrido 1º | recorrido 2º | veredicto |
|---|---|---|---|---|
| **f₁ vs E** | 18 | **142.8 %** | **451 %** | **el más ancho** |
| f₁ vs t_des | 18 | 57 % | 18.7 % | sirve |
| t_des vs E | 12 | 5.6 % | 146.2 % | t_des casi no se mueve |
| f₁ vs t_des vs E | **48 = toda la población** | — | — | **degenerado** |

### Los tres objetivos a la vez NO funcionan

Con tres objetivos, **el 100 % de la población queda no dominada** para la
generación 47. Cuando todo empata en rango, la selección se decide solo por
distancia de apinamiento — que es una medida de *diversidad*, no de *calidad*.
El algoritmo deja de optimizar y solo reparte puntos.

Es el modo de falla documentado de NSGA-II con muchos objetivos, y aquí aparece
ya en tres. Si se quisieran los tres haría falta NSGA-III o descomposición por
puntos de referencia. **Recomendación: dos objetivos.**

### Los dos que recomiendo: f₁ y E

1. **Es el frente más ancho por mucho** (142.8 % y 451 % de recorrido). Un
   frente ancho es lo que hace útil un multiobjetivo: si el frente es un punto,
   no hay decisión que tomar.
2. **E es la métrica de seguridad defendible.** E = superficie×tiempo por encima
   de ρ_c = 4 pers/m², que es la densidad a la que la gente pierde el
   movimiento individual (van Toll et al. 2021). Eso es literalmente la
   precondición del aplastamiento. Lo que mata en eventos masivos es la densidad,
   no la lentitud.
3. **E aguanta el único parámetro sin respaldo que tiene el modelo.** Medido
   antes: al variar p de 1 a 4, el orden de t_des cae a 0.373 y el de E aguanta
   en 0.573. Optimizar t_des es optimizar en parte el exponente p.
4. **No regala t_des en silencio.** Verificado: a lo largo del frente (f₁, E) el
   t_des va de 68.4 a 84.3 s, y el peor está apenas +2.9 % sobre la mediana al
   azar. Esto había que comprobarlo porque optimizando E **a solas** t_des sí se
   degrada un 18 % — la presión de f₁ es la que lo compensa.

**t_des se reporta, no se optimiza.** Y ojo: como objetivo normativo no sirve de
restricción, porque con aforos de 2 000 a 4 000 da 65–130 s contra un tope de
600 s. Nunca ata. Sería una restricción decorativa.

---

## 3. Presupuesto: no es el cuello de botella

Costo de una evaluación completa, medido sobre 120 layouts:

| | antes | ahora |
|---|---|---|
| capa geométrica | 5.3 ms (0.8 %) | 5.4 ms (1.4 %) |
| f₁ acceso | 327.2 ms (50.5 %) | **93.7 ms (23.4 %)** |
| f₂ evacuación | 315.3 ms (48.7 %) | 301.5 ms (75.3 %) |
| **serial** | 647.8 ms | **400.6 ms** |
| **en paralelo (12 procesos)** | 70.7 ms | **48.2 ms** |

### De dónde salió el 3.5× en f₁

Perfilando f₁ resultó que el cuello **no era el FMM** (13 %) sino el solver de
transporte: el subgradiente 1/√k agotaba las 400 iteraciones sin converger en el
**39 %** de las llamadas.

La solución no fue afinar el paso sino cambiar de algoritmo. Fijados los precios
de los demás módulos, **el precio óptimo de uno solo tiene fórmula cerrada** —
se ordenan las celdas por cuánto ganan viniendo a ese módulo y se corta donde la
demanda acumulada llega a la capacidad. Entonces se barre módulo por módulo
resolviendo cada uno exacto:

| solver | ms/problema | dif. máx vs LP |
|---|---|---|
| LP exacto (HiGHS) | 139.9 | 0 |
| subgradiente | 34.4 | 5.6e-4 |
| **coordenadas exactas** | **14.6** | **2.0e-4** |

Validado de punta a punta: **ρ = 1.000000 contra el LP exacto, cero inversiones
en 1 225 pares**. Y re-corriendo el barrido completo de 1 776 layouts, las 12
correlaciones salen idénticas a tres decimales. El cambio es neutral.

*(Probé también un paso de Polyak: salió peor — 663 ms — porque la cota superior
que necesita obliga a llamar a la reparación, que es un bucle de Python sobre
5 700 celdas. Descartado.)*

### Qué alcanza

| presupuesto | tiempo | qué es |
|---|---|---|
| 2 448 evals | 2 min | pob 48 × 50 gen (lo que corrí aquí) |
| 10 000 evals | 8 min | |
| 25 000 evals | 20 min | pob 100 × 250 gen — **NSGA-II en serio** |

**El presupuesto no es la restricción.** Se puede correr un NSGA-II de tamaño
publicable en 20 minutos. Y el frente todavía crecía en la generación 50
(6 → 22 soluciones), así que más generaciones sí aportan.

### Lo que NO sirve para abaratar

Probé sustituir f₁ por versiones baratas:

| variante | ms | ρ vs exacto | inversiones |
|---|---|---|---|
| distancia al más cercano (1 FMM, sin capacidades) | 2.2 | **0.2598** | **729/1770** |
| transporte capacitado con distancia euclidiana | 141.7 | 0.9939 | 44/1770 |

La primera es 70× más barata y **ordena prácticamente al azar**. Eso no es un
fracaso: es la mejor validación que tenemos de que la asignación capacitada no
es un adorno — es lo que decide el orden. La segunda conserva el orden pero solo
ahorra 1.1×, no vale la pena.

---

## 4. Manejo de restricciones: **lo medido contradice lo que asumimos**

Habíamos dado por hecho que el muestreo por rechazo estaba mal y que las reglas
de Deb (2000) serían mejores. **Medido con el mismo presupuesto, 3 semillas:**

| objetivo | modo | mejor | peor | mediana | seg |
|---|---|---|---|---|---|
| f₁ | rechazo | 16.49 | 16.74 | **16.61** | 25 |
| f₁ | Deb | 16.78 | 16.98 | 16.91 | 23 |
| E | rechazo | 13.50 | 124.50 | **98.10** | 23 |
| E | Deb | 23.40 | 117.00 | 98.70 | 22 |

**Empate.** La diferencia (1.8 % en f₁) está dentro del ruido con 3 semillas, y
el costo en tiempo es el mismo. El rechazo descarta 220–275 mutaciones por
corrida y aun así no pierde.

Probablemente porque la región factible aquí es amplia y bien conectada (88 % de
aceptación medido antes): el rechazo casi nunca bloquea un camino que importe.

**Pero hay que separar dos cosas que se estaban confundiendo:**

- **Para BUSCAR**: rechazo y Deb dan lo mismo (medido aquí).
- **Para MEDIR**: filtrar por factibilidad **sí** contamina. Está medido en el
  barrido: la misma población partida por factibilidad da ρ = −0.216 en una
  mitad y +0.097 en la otra, siendo el total cero. Es un efecto de selección.

Entonces: se usa dominancia restringida **igual**, porque en multiobjetivo hace
falta de todos modos (no se puede "rechazar" hacia un frente) y porque es lo
correcto conceptualmente — pero **no se puede vender como una mejora de
rendimiento**, porque no lo es. Decirlo al revés en la tesis sería inventar un
resultado.

---

## 5. Lo que hay que arreglar en `nucleo/optimizar.py`

1. **`optimizar()` está rota.** Llama a `ev(s)` y `ev` no está definida en
   ninguna parte del módulo. Solo `optimizar_par()` funciona. Nunca se detectó
   porque la API siempre usa la versión paralela.
2. **Optimiza `t95`, que sobra.** Medido: ρ(t_des, t95) = +0.65 a +0.81. Son la
   misma información.
3. **Es de un solo objetivo con suma implícita.** Hay que reescribirla como
   NSGA-II sobre (f₁, E).
4. **La memoización no paga** (1 % de aciertos medido, con mutación gaussiana
   continua). Mantenerla cuesta más de lo que ahorra; el almacén en SQLite sí
   sirve porque es entre corridas, no dentro.
5. **El `dt=0.5` y `t_max=2500` por defecto** no coinciden con lo calibrado
   (dt=0.3, k_c=8, t_max=600).

---

## 6. Lo que haría

```
NSGA-II sobre (f₁, E)
  representación   colocación directa, (x, y, rot) por módulo, cuantizada a 0.25 m
  población        100
  generaciones     250            (~20 min, 25 000 evaluaciones)
  cruce            uniforme por MÓDULO, p = 0.9
                   — nunca promediar coordenadas: el hijo no se parece a ningún
                     padre y casi siempre tiene traslapes
  mutación         gaussiana con σ decreciente 10 → 2 m,
                   + 8 % de salto largo (reubicación uniforme),
                   + 20 % de volteo de rotación
  restricciones    dominancia restringida (Deb 2000), sin rechazo
  semilla inicial  generador en modo amplio (estructural + alcanzable)
  se reporta       t_des sobre todo el frente, como diagnóstico
```

Y antes de dar por bueno cualquier resultado: **repetir con 10+ semillas**. La
optimización de E es muy rugosa — entre 3 semillas salió de 13.50 a 124.50, un
factor 9. Una sola corrida no dice nada.

---

## 7. Lo que NO está medido (y hay que decirlo antes de citarlo de más)

1. **Una sola geometría.** Todo esto es la nave 100×60 con 4 salidas repartidas.
   Los anchos del frente podrían ser de esta planta.
2. **Reparto uniforme.** Ya sabíamos que es el caso que menos discrimina. Con la
   multitud concentrada frente al escenario los márgenes cambian.
3. **No se comparó contra otras metaheurísticas.** No hay evidencia de que
   NSGA-II gane a, digamos, MOEA/D o SPEA2 en este problema. Si la tesis afirma
   que NSGA-II es *el* adecuado, eso hay que medirlo, no suponerlo.
4. **Las comparaciones del optimizador tienen 3 repeticiones.** Suficiente para
   ver que rechazo y Deb empatan; insuficiente para afirmar que uno gana.
5. **El frente no ha convergido a las 50 generaciones** (seguía creciendo). Los
   anchos reportados son cotas inferiores.
6. **Las unidades de atención por módulo siguen PENDIENTE.** f₁ depende de
   ellas. Sin ficha de proveedor, los números de f₁ son provisionales aunque el
   método sea correcto.
