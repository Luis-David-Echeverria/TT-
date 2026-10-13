---
title: "Tabla de parámetros con su fuente normativa"
subtitle: "TT 2027-A126 · Evidencia 1 del periodo 29 de septiembre – 12 de octubre de 2026"
---

**Actividad del cronograma:** investigación de normas y sustento teórico, extracción y citación de los parámetros que estaban sin fuente verificada: densidad admisible, ancho libre de circulación, distancia máxima a salida y tiempo máximo de desalojo (Martínez).

**Resultado:** los parámetros sin fuente bajaron de **6 a 4**. La distancia máxima y el tiempo máximo ya están citados a la NOM-002-STPS-2010. Para los otros dos se verificó que la NOM-002 **no** fija la cifra y se dejó dicho dónde hay que buscarla.

## 1. Verificación contra el texto de la NOM-002-STPS-2010

Revisado contra el texto publicado en el Diario Oficial de la Federación (<https://dof.gob.mx/normasOficiales/4228/stps/stps.htm>), el 13 de octubre de 2026.

| Numeral | Qué dice | Cómo entra al modelo |
|---|---|---|
| 7.15 b) | Las rutas de evacuación deben estar «libres de obstáculos que impidan la circulación de los trabajadores y demás ocupantes». | Restricción G4: zona despejada frente a cada salida. |
| 7.15 d) | La distancia «desde el punto más alejado del interior de una edificación» hasta cualquier punto de la ruta de evacuación no debe ser mayor de **40 m**. Si lo es, el tiempo máximo de evacuación de los ocupantes a un lugar seguro debe ser de **tres minutos**. | `DIST_MAX_SALIDA` = 40 m y `T_EVAC_MAX` = 180 s, ahora en estado *normativo*. |
| 7.16 f) | Las puertas consideradas salidas de emergencia deben estar «libres de obstáculos, candados, picaportes o cerraduras» que impidan usarlas. | Las salidas nunca cuentan como obstáculo en la simulación. |

**Lo que la NOM-002 no dice:** ningún numeral de 7.15 ni de 7.16 fija un **ancho mínimo** de pasillo o de salida. Por eso `ANCHO_LIBRE_MIN` sigue pendiente: la cifra tiene que salir de las Normas Técnicas Complementarias para el Proyecto Arquitectónico de la Ciudad de México.

**Un matiz de 7.15 d):** la norma mide los 40 m hasta *cualquier punto de la ruta de evacuación*; el modelo los mide hasta la salida, que es más estricto. En el recinto de prueba el piso vacío ya pasa de 40 m, así que el límite se revisa por recinto y no por distribución, y aplica la alternativa de los tres minutos, que es lo que mide $f_2$.

## 2. PROY-NOM-011-SSPC-2025

El aviso de consulta pública publicado en el DOF (<https://dof.gob.mx/normasOficiales/9519/seguridad/seguridad.html>) solo trae la síntesis del proyecto: busca regular los rangos máximos de aforo con un enfoque de prevención. **No trae el articulado ni valores numéricos.** El texto completo se consulta en la plataforma PLATIICA (<https://platiica.economia.gob.mx/procesos-participativos/>). Mientras no se revise, la densidad de diseño se mantiene como parámetro a calibrar (`RHO_DISENO` = 3.5 p/m²), acotada por la densidad de pérdida de control medida (4 p/m²).

## 3. Los 27 parámetros del modelo

Generada del registro del código (`nucleo/parametros.py` y los módulos que registran los suyos). Cada parámetro declara su estado:

- **medido:** valor empírico publicado.
- **normativo:** lo fija un reglamento.
- **derivado:** se calcula de otros.
- **catálogo:** dimensión de equipo comercial.
- **numérico:** discretización.
- **calibrar:** criterio de modelado.
- **PENDIENTE:** sin fuente verificada.

| Clave | Símbolo | Valor | Estado | Fuente |
|---|---|---|---|---|
| `V0` | v₀ | 1.34 m/s | medido | Weidmann (1993) |
| `RHO_MAX` | ρ_max | 5.4 p/m² | medido | Weidmann (1993) |
| `GAMMA` | γ | 1.913 p/m² | medido | Weidmann (1993) |
| `RHO_PERDIDA_CONTROL` | ρ_c | 4.0 p/m² | medido | van Toll *et al.* (2021) |
| `DIST_MAX_SALIDA` | d_max | 40 m | **normativo** | NOM-002-STPS-2010, 7.15 d) |
| `T_EVAC_MAX` | t_lim | 180 s | **normativo** | NOM-002-STPS-2010, 7.15 d) |
| `Q_MAX` | q_max | 1.2249 p/(m·s) | derivado | máximo de ρ·v(ρ) de Weidmann |
| `RHO_CAP` | ρ_cap | 1.751 p/m² | derivado | donde ρ·v(ρ) es máximo |
| `UNID_SAN` | u_SAN | 8 unidades | catálogo | ficha de proveedor |
| `UNID_COM` | u_COM | 4 unidades | catálogo | ficha de proveedor |
| `UNID_BEB` | u_BEB | 6 unidades | catálogo | ficha de proveedor |
| `UNID_MED` | u_MED | 2 unidades | catálogo | ficha de proveedor |
| `H_CELDA` | h | 1.0 m | numérico | — |
| `DT` | Δt | 0.3 s | numérico | condición CFL: 0.40 ≤ 0.71 m |
| `REFRESCO_CAMPO` | k_c | 8 pasos | numérico | medido sobre 14 distribuciones |
| `EPS_VACIADO` | ε | 0.005 | numérico | — |
| `RHO_DISENO` | ρ_d | 3.5 p/m² | calibrar | acotado por ρ_c |
| `EXP_REPARTO` | p | 3 | calibrar | sin respaldo (ver nota) |
| `SIGMA_KERNEL` | σ_k | 2 celdas | calibrar | Treuille *et al.* (2006) |
| `FRACCION_PERDIDA_MAX` | φ_max | 0.03 | calibrar | criterio de diseño |
| `FRENTE_MIN` | f_min | 3 m | calibrar | criterio de diseño |
| `SATURACION` | σ | 1.0 | calibrar | criterio del proyecto |
| `PASO_POS` | Δx | 0.25 m | calibrar | precisión de replanteo |
| `ANCHO_LIBRE_MIN` | w_min | 3 m | **PENDIENTE** | NTC Proyecto Arquitectónico CDMX |
| `PROF_DESPEJE_SALIDA` | d_s | 1.5 × ancho | **PENDIENTE** | NTC: área de descarga de salidas |
| `J_ESPECIFICO` | J_s | 1.32 p/(m·s) | **PENDIENTE** | Seyfried *et al.*: falta el valor exacto con su experimento |
| `CAPA_LIMITE` | b | 0.15 m | **PENDIENTE** | Seyfried *et al.*: falta verificar |

**Nota sobre `EXP_REPARTO`:** es el único parámetro del modelo de multitud sin respaldo empírico. van Wageningen-Kessels, Daamen y Hoogendoorn (2018) reparten el flujo entre celdas vecinas con las componentes de la dirección de marcha, sin exponente; adoptar su reparto eliminaría este parámetro.

## 4. Lo que queda pendiente

| Parámetro | Dónde buscarlo |
|---|---|
| Ancho libre de circulación | NTC para el Proyecto Arquitectónico (CDMX): tabla de anchos mínimos de circulaciones y fecha de publicación. |
| Despeje frente a salidas | Las mismas NTC: área de descarga de salidas. |
| Densidad admisible | Texto completo del PROY-NOM-011-SSPC-2025 en PLATIICA. |
| Flujo específico y capa límite | Seyfried *et al.*: el valor exacto con su experimento de cuello de botella. |

## Referencias

- Secretaría del Trabajo y Previsión Social (2010). NOM-002-STPS-2010, *Condiciones de seguridad — Prevención y protección contra incendios en los centros de trabajo*. Diario Oficial de la Federación, 9 de diciembre de 2010.
- Secretaría de Seguridad y Protección Ciudadana (2025). Aviso de consulta pública del PROY-NOM-011-SSPC-2025. Diario Oficial de la Federación.
- Weidmann, U. (1993). *Transporttechnik der Fussgänger*. Schriftenreihe des IVT Nr. 90, ETH Zürich.
- van Wageningen-Kessels, F., Daamen, W. y Hoogendoorn, S. P. (2018). Two-Dimensional Approximate Godunov Scheme and What It Means For Continuum Pedestrian Flow Models. *Transportation Science*, 52(3), 547–563.
