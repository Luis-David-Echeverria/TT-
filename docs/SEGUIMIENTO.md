# Revisión de seguimiento — 13 de octubre de 2026

TT 2027-A126 · *Prototipo de sistema para la distribución óptima de áreas de servicio en eventos masivos mediante algoritmos bioinspirados* · Echeverría Pérez Luis David y Martínez Meneses Monserrat Alejandra · Directores: Dr. Daniel Molina Pérez y Dr. Jacobo Torres Figueroa.

El cronograma está en `entregas/Cronograma_TT_2027-A126_FINAL.docx`. Abajo, cada evidencia comprometida y dónde está.

## Periodo 1 · 24 de agosto – 28 de septiembre

| # | Responsable | Evidencia | Dónde |
|---|---|---|---|
| 1 | Martínez | Informe técnico, secciones 1 a 3: planteamiento, escenario y criterios de seguridad | `entregas/evidencias/Informe-tecnico-TT-2027-A126.pdf` |
| 2 | Martínez | Informe técnico, sección 3: las seis restricciones duras | mismo PDF |
| 3 | Martínez | Informe técnico, secciones 12 y 13: barrido de pesos y tabla de variables | mismo PDF · `datos/barrido_pesos.json` |
| 4 | Echeverría | Informe técnico, secciones 5 a 11 y 14: modelo, funciones objetivo, resultados, reproducibilidad | mismo PDF · `datos/correlacion_f1_f2.csv`, `datos/evaluaciones.db`, `datos/frente_epsilon.json` |
| 5 | Echeverría | Capturas del editor, la simulación y los mapas de densidad | `entregas/evidencias/Evidencia-5-editor-simulacion-densidad.pdf` · capturas `01` a `03` |

## Periodo 2 · 29 de septiembre – 12 de octubre

| # | Responsable | Evidencia | Dónde |
|---|---|---|---|
| 1 | Martínez | Tabla de parámetros con su fuente normativa | `docs/PARAMETROS-NORMATIVOS.md` · `entregas/evidencias/Periodo2-1-Parametros-normativos.pdf` |
| 2 | Martínez | Diseño del algoritmo: representación, operadores y manejo de restricciones | `docs/DISENO-ALGORITMO.md` · `entregas/evidencias/Periodo2-2-Diseno-del-algoritmo.pdf` · código en `experimentos/frente.py` |
| 3 | Echeverría | Acoplamiento del evaluador y costo por evaluación | `docs/ACOPLAMIENTO-Y-COSTO.md` · `entregas/evidencias/Periodo2-3-Acoplamiento-y-costo.pdf` · `experimentos/costo_evaluacion.py` · `datos/costo_evaluacion.json` |

**Material de apoyo:** el reporte técnico (`docs/REPORTE-TECNICO.md`) y seis cuadernos que explican cada parte del modelo con comparaciones visuales (`cuadernos/`).

## Correcciones hechas en esta revisión

Al preparar los cuadernos se revisó el modelo pieza por pieza y aparecieron tres errores. Se corrigieron y se dejan a la vista porque cambian resultados anteriores.

| Qué | Efecto | Estado |
|---|---|---|
| **Cruce del NSGA-II de investigación** (`experimentos/frente.py`): emparejaba los módulos por posición y no por tipo, y producía hijos con otra composición (por ejemplo 4 comidas y 1 sanitario). | Infla $f_1$: en una corrida de prueba, el "mejor" llegaba a 12.4 m sin bebidas ni primeros auxilios; con el cruce corregido, a 19.0 m. Afecta las secciones 0 a 2 de `experimentos/OPTIMIZADOR.md`. | Corregido. Hay que volver a correr esas corridas. Lo publicado en el sitio no sale de ahí. |
| **Ancho mínimo de paso** en la zona ocupable (`nucleo/geometria.py`): el radio de erosión exigía pasillos de 5 m en vez de 3 m. | De los 1,776 layouts del experimento, los válidos pasan de 1,206 (67.9 %) a 1,227 (69.1 %); ninguno deja de serlo. | Corregido. Los datos del experimento se calcularon con la versión anterior. |
| **«El frente es no convexo»** (README y sección 11 del informe interactivo). | Los 7 puntos del barrido ε-restringido quedan dominados por soluciones del barrido de pesos: el ε no llegó al frente, así que no se puede afirmar su forma. El reporte técnico ya no lo afirmaba. | Retirado del README y del informe interactivo. La forma del frente se medirá con NSGA-II. |

Además, en esta revisión:

- `DIST_MAX_SALIDA` (40 m) y `T_EVAC_MAX` (180 s) quedaron citados a la NOM-002-STPS-2010, num. 7.15 d), verificada contra el texto del DOF.
- El reporte técnico ahora cita el esquema de Godunov en 2D para peatones (van Wageningen-Kessels *et al.*, 2018) con su condición de estabilidad, incluye los diagramas de la sección 5.4 y el costo por evaluación medido hoy.

## Pendiente

| Qué | Cuándo |
|---|---|
| Volver a correr el NSGA-II con el cruce corregido, con repeticiones independientes y análisis de variabilidad entre semillas | periodo 3 (13–26 de octubre), ya en el cronograma |
| Volver a exportar los datos del informe interactivo con el ancho de paso corregido | periodo 3 |
| Fuentes de los 4 parámetros pendientes (ancho libre, despeje de salidas, flujo específico, capa límite) y la densidad del PROY-NOM-011 | periodo 3 |
| Cambiar el reparto con exponente `p` (único parámetro del modelo sin respaldo) por el reparto de van Wageningen-Kessels *et al.* | a decidir con los directores |
| Costo estimado de horas de desarrollo (reporte técnico, sección 6.3) | lo completa el equipo |
