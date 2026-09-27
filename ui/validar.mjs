/* Corre el motor JS sobre los layouts que le pasa Python y devuelve las mismas
 * métricas, para poder compararlas.
 *
 *   node validar.mjs entrada.json salida.json
 *
 * No es parte del sitio: es el arnés de validación. Existe porque mantener dos
 * motores solo se justifica si se mide cuánto se parecen; si divergen y nadie
 * lo comprueba, no hay forma de saber cuál creer.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { crearRecinto, zonaOcupable } from "./src/modelo/recinto.js";
import { crearFisica, simular } from "./src/modelo/fluido.js";
import { f1 } from "./src/modelo/acceso.js";

const ent = JSON.parse(readFileSync(process.argv[2], "utf8"));
const rec = crearRecinto(ent.recinto, ent.P.h);
const fis = crearFisica(ent.P);
const salida = [];

for (const caso of ent.casos) {
  const t0 = Date.now();
  const libre = zonaOcupable(rec, caso.layout, ent.catalogo, ent.P);
  let celdas = 0;
  for (let i = 0; i < libre.length; i++) if (libre[i]) celdas++;

  const acc = f1(rec, caso.layout, libre, ent.catalogo, ent.P);
  const tf1 = Date.now();
  const sim = simular(rec, libre, caso.aforo, fis, {
    dt: ent.P.dt, t_max: ent.P.t_max, k_c: ent.P.k_c, p: ent.P.p,
    n_cuadros: 4,
  });
  salida.push({
    i: caso.i,
    celdas_libres: celdas,
    f1: isFinite(acc) ? acc : null,
    t_des: sim ? sim.t_des : null,
    t95: sim ? sim.t95 : null,
    exposicion: sim ? sim.exposicion : null,
    rho_pico: sim ? sim.rho_pico : null,
    ms_f1: tf1 - t0,
    ms_sim: Date.now() - tf1,
  });
  if (salida.length % 5 === 0) process.stderr.write(".");
}
writeFileSync(process.argv[3], JSON.stringify(salida));
process.stderr.write("\n");
