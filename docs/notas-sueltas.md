SPH-enhanced crowd simulation
As explained in Section 1, a ‘traditional’ agent-based crowd simulation is not suitable for extreme densities due to its simplistic collision handling. In this section, we describe how to enrich any agent-based simulation with SPH to improve this aspect. We will keep the discussion as general as possible. Section 5 will describe the implementation and settings used for our experiments.
https://www.sciencedirect.com/science/article/abs/pii/S0097849321001205

High density behavior: When a crowd exceeds 4 people per square meter, people lose individual free movement and get pushed by the pressure of the surrounding group. [1] (https://inria.hal.science/hal-03270915/document), [2] (https://www.sciencedirect.com/science/article/abs/pii/S0097849321001205)

Hibridación por Densidad Dinámica (Gatillado por Umbral)Este es el enfoque más común. El sistema evalúa constantemente la densidad local del espacio y cambia el modelo de simulación en tiempo real para cada individuo o zona.

3. Enfoque Euleriano-Lagrangiano (Partículas en Fluido)Inspirado directamente en la física de fluidos multifásicos (como la arena en el agua o el humo con cenizas):Fase Euleriana (El tablero): El espacio se divide en una rejilla fija donde se resuelven las ecuaciones de fluidos para representar el "aire" o el "clima social" de la multitud (la presión masiva, el flujo general, el pánico propagado).Fase Lagrangiana (Los peatones): Los peatones son partículas/agentes que flotan y se mueven empujados por ese fluido subyacente, pero que también aplican sus propias fuerzas internas (deseos de ir en dirección contraria, resistencia física a ser empujados).

