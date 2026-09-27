/* Prueba de contrato del motor.
 *
 * Corre el modelo y verifica que devuelve EXACTAMENTE los campos que la
 * interfaz lee. Existe por un error concreto: al mover la simulación del
 * backend al navegador, el motor pasó a devolver `cuadros` mientras la
 * interfaz seguía leyendo `cuadros_b64`. Nada lo detectó — ESLint no ve
 * propiedades, solo variables — y reventó en pantalla.
 *
 * Va en `npm run build`, así que una desviación del contrato rompe la
 * compilación en vez de romper la página.
 */
import { crearRecinto, zonaOcupable } from "./src/modelo/recinto.js";
import { crearFisica, simular } from "./src/modelo/fluido.js";
import { f1 } from "./src/modelo/acceso.js";

let fallos = 0;
function exige(cond, que) {
  if (!cond) { console.error("  FALLA:", que); fallos++; }
}

const P = {
  h: 1, dt: 0.3, k_c: 8, p: 3, eps: 0.005, v0: 1.34, rho_max: 5.4,
  gamma: 1.913, rho_c: 4, J_s: 1.32, capa_limite: 0.15, sigma_k: 2,
  w_min: 3, sigma: 1,
  servicio: { SAN: { unidades: 8 }, COM: { unidades: 4 },
              BEB: { unidades: 6 }, MED: { unidades: 2 } },
};
const catalogo = { areas: [
  { clave: "SAN", ancho: 8, fondo: 3 }, { clave: "COM", ancho: 5, fondo: 5 },
  { clave: "BEB", ancho: 8, fondo: 2.5 }, { clave: "MED", ancho: 5, fondo: 5 },
] };
const recinto = {
  W: 100, H: 60,
  muros: [{ x: 46, y: 24, w: 4, h: 4 }, { x: 0, y: 50, w: 22, h: 3 }],
  salidas: [{ nombre: "S1", lado: "S", centro: 20, ancho: 8 },
            { nombre: "S2", lado: "S", centro: 70, ancho: 8 },
            { nombre: "O1", lado: "O", centro: 30, ancho: 6 },
            { nombre: "E1", lado: "E", centro: 35, ancho: 6 }],
};
const layout = [
  { tipo: "SAN", x: 10, y: 10, rot: 0 }, { tipo: "SAN", x: 30, y: 40, rot: 1 },
  { tipo: "SAN", x: 70, y: 12, rot: 0 }, { tipo: "COM", x: 55, y: 40, rot: 0 },
  { tipo: "COM", x: 20, y: 25, rot: 0 }, { tipo: "COM", x: 80, y: 35, rot: 0 },
  { tipo: "BEB", x: 40, y: 8, rot: 0 }, { tipo: "BEB", x: 60, y: 50, rot: 0 },
  { tipo: "MED", x: 88, y: 5, rot: 0 },
];

console.log("prueba de contrato del motor");
const rec = crearRecinto(recinto, P.h);
const fis = crearFisica(P);
const libre = zonaOcupable(rec, layout, catalogo, P);

let n = 0;
for (let i = 0; i < libre.length; i++) if (libre[i]) n++;
exige(n > 1000, `zona ocupable razonable (salieron ${n} celdas)`);
exige(Math.abs(fis.qMax - 1.2249) < 0.01, `q_max derivado ~1.2249 (salió ${fis.qMax.toFixed(4)})`);
exige(Math.abs(fis.rhoCap - 1.751) < 0.01, `rho_cap derivado ~1.751 (salió ${fis.rhoCap.toFixed(4)})`);

// --- lo que la interfaz lee de una simulación ---
const sim = simular(rec, libre, 2000, fis, { n_cuadros: 8 });
exige(sim !== null, "simular devuelve algo");
for (const k of ["cuadros", "t", "pct", "t_des", "t95", "exposicion", "rho_pico"])
  exige(sim[k] !== undefined, `la simulación trae '${k}'`);
exige(Array.isArray(sim.cuadros) && sim.cuadros.length > 0, "cuadros es un arreglo no vacío");
exige(sim.cuadros.length === sim.t.length, "hay un tiempo por cuadro");
exige(sim.cuadros[0] instanceof Float64Array, "cada cuadro es un campo de densidad");
exige(sim.t_des > 0 && sim.t_des < 600, `t_des plausible (salió ${sim.t_des})`);

// --- lo que la interfaz lee del reparto de f₁ ---
const acc = f1(rec, layout, libre, catalogo, P, true);
for (const k of ["valor", "tipos", "idxLibres"])
  exige(acc[k] !== undefined, `el reparto trae '${k}'`);
exige(acc.valor > 5 && acc.valor < 60, `f₁ plausible (salió ${acc.valor.toFixed(2)})`);
for (const [t, d] of Object.entries(acc.tipos)) {
  for (const k of ["quien", "dist", "modulos", "carga", "capacidad", "d_media"])
    exige(d[k] !== undefined, `${t} trae '${k}'`);
  const suma = d.carga.reduce((a, b) => a + b, 0);
  exige(Math.abs(suma - 1) < 1e-6, `${t}: la carga suma 1 (salió ${suma.toFixed(6)})`);
  d.carga.forEach((c, i) => exige(c <= d.capacidad[i] + 1e-3,
    `${t}: el módulo ${i} no pasa su capacidad (${c.toFixed(4)} vs ${d.capacidad[i].toFixed(4)})`));
}

/* --- y lo que la interfaz LEE de esos objetos ---
 *
 * Lo de arriba comprueba que el motor devuelve lo que promete. Falta el otro
 * lado: que la interfaz no lea un campo que no existe. Ese fue el error real —
 * el motor pasó a devolver `cuadros` y la interfaz siguió leyendo
 * `cuadros_b64`. ESLint no lo ve, porque son propiedades y no variables.
 *
 * El contrato es lo que entrega el WORKER, no `simular()` a secas: el worker
 * agrega la rejilla y la máscara, y es su objeto el que llega a la interfaz.
 */
const DEL_WORKER_SIM = ["nx", "ny", "h", "rho_max", "mascara", "cuadros",
                        "t", "pct", "t95", "t_des", "exposicion", "rho_pico"];
const DEL_WORKER_ACC = ["nx", "ny", "h", "f1", "tipos", "mascara"];
// formas equivalentes que llegan del backend en lugar del motor local
const DEL_BACKEND = ["cuadros_b64", "mascara_b64", "direcciones",
                     "evacuado_final", "quien_b64", "dist_b64"];

for (const k of DEL_WORKER_SIM)
  if (!["nx", "ny", "h", "rho_max", "mascara"].includes(k))
    exige(sim[k] !== undefined, `el motor entrega '${k}' en la simulación`);
for (const k of ["tipos", "f1"])
  exige(k === "f1" ? acc.valor !== undefined : acc.tipos !== undefined,
        `el motor entrega '${k}' en el reparto`);

const CAMPOS_SIM = new Set([...DEL_WORKER_SIM, ...DEL_BACKEND]);
const CAMPOS_ACC = new Set([...DEL_WORKER_ACC, ...DEL_BACKEND]);

// rutas relativas al script y no al directorio de trabajo: si no, la
// prueba pasa o falla segun desde donde se invoque
const { readFileSync } = await import("node:fs");
const { fileURLToPath } = await import("node:url");
const { dirname, join } = await import("node:path");
const AQUI = dirname(fileURLToPath(import.meta.url));
for (const archivo of ["src/Resultados.jsx", "src/Mapa.jsx"]) {
  const txt = readFileSync(join(AQUI, archivo), "utf8");
  for (const [re, campos, nombre] of [
    // el (?<![.\w]) evita confundir `pesos.azar.acceso` con el reparto
    [/(?<![.\w])sim[?]?\.(\w+)/g, CAMPOS_SIM, "simulación"],
    [/(?<![.\w])acceso[?]?\.(\w+)/g, CAMPOS_ACC, "reparto"],
  ]) {
    for (const m of txt.matchAll(re)) {
      exige(campos.has(m[1]),
        `${archivo} lee '${m[1]}' de la ${nombre}, y el contrato no lo tiene`);
    }
  }
}

if (fallos) {
  console.error(`\n${fallos} fallas de contrato.`);
  process.exit(1);
}
console.log(`  f₁ = ${acc.valor.toFixed(2)} m · t_evac = ${sim.t_des.toFixed(1)} s · ` +
            `${sim.cuadros.length} cuadros · ${n} celdas`);
console.log("  contrato OK");
