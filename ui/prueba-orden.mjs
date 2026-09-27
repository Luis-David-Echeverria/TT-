/* ¿Aguanta el motor que le pidan cálculos ANTES de darle el recinto?
 *
 * Es el orden real en React: los efectos de los hijos corren antes que los del
 * padre, así que las ilustraciones piden su cálculo antes de que la página
 * prepare el motor. El bug salió dos veces —primero reventando al destructurar
 * null, después rechazando con "todavía no tiene un recinto"— así que se prueba
 * en vez de razonarlo.
 *
 * El worker se sustituye por un doble que anota qué mensajes recibe y en qué
 * orden: lo que se verifica es la coreografía, no el modelo.
 */
const recibidos = [];
globalThis.Worker = class {
  constructor() { this.onmessage = null; this.onerror = null; }
  postMessage(m) {
    recibidos.push(m.tipo);
    // el worker real responde de forma asíncrona
    setTimeout(() => this.onmessage({ data: { id: m.id, ok: true, resultado: { tipo: m.tipo } } }), 0);
  }
};

const { iniciarMotor, zonaLayout, accesoLayout } = await import("./src/motor.js");

let fallos = 0;
const exige = (c, q) => { if (!c) { console.error("  FALLA:", q); fallos++; } };

console.log("prueba de orden de arranque");

// 1) los hijos piden PRIMERO, como hace React
const antes = [zonaLayout([]), accesoLayout([])];
let resueltoAntesDeIniciar = false;
antes.forEach((p) => p.then(() => { resueltoAntesDeIniciar = true; }));
await new Promise((r) => setTimeout(r, 20));
exige(!resueltoAntesDeIniciar, "no se resuelve nada mientras no hay recinto");
exige(recibidos.length === 0, "no se le manda nada al worker todavía");

// 2) el padre prepara el motor DESPUÉS
const catalogo = { parametros: [{ clave: "H_CELDA", valor: 1 }], areas: [] };
await iniciarMotor({ W: 10, H: 10, muros: [], salidas: [] }, catalogo);

// 3) las peticiones que estaban esperando deben completarse
const r = await Promise.all(antes);
exige(r.length === 2 && r.every(Boolean), "las peticiones que esperaban se completan");
exige(recibidos[0] === "iniciar", `'iniciar' llega primero al worker (llegó '${recibidos[0]}')`);
exige(recibidos.includes("zona") && recibidos.includes("acceso"),
      "y después los cálculos que estaban en cola");

// 4) pedir de nuevo, ya preparado, sigue funcionando
await accesoLayout([]);
exige(recibidos.filter((x) => x === "acceso").length === 2,
      "una petición posterior también pasa");

if (fallos) { console.error(`\n${fallos} fallas.`); process.exit(1); }
console.log(`  orden al worker: ${recibidos.join(" → ")}`);
console.log("  orden de arranque OK");
