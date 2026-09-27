/* Puente entre la interfaz y el modelo que corre en el navegador.
 *
 * POR QUÉ EL NAVEGADOR CALCULA EN VEZ DE DESCARGAR.
 * La simulación es determinista: dado el layout y las constantes, el resultado
 * está fijado. No hay nada aleatorio que guardar. Precalcular una película por
 * layout ocupaba 24 MB y aun así dejaba a la mayoría de los puntos sin poder
 * abrirse — calcularlas en el momento cuesta ~300 ms y las deja abrir todas.
 *
 * LAS CONSTANTES NO SE ESCRIBEN AQUÍ. Salen del registro de parámetros que
 * sirve /api/catalogo, que es el mismo de Python. Si la interfaz tuviera su
 * propia copia, las dos podrían desviarse y lo que se ve dejaría de ser
 * evidencia de lo que se midió.
 *
 * CUÁNTO SE PARECE AL MOTOR DE PYTHON. Medido sobre 30 layouts
 * (experimentos/validar_js.py), comparando la diferencia entre motores contra
 * la diferencia entre layouts:
 *
 *     accesibilidad f₁       0.08   sirve para comparar
 *     tiempo de evacuación   0.13   sirve para comparar
 *     E exposición           0.67   NO — se muestra el valor de Python
 *
 * E cuenta celdas que cruzan un umbral de densidad, así que una diferencia de
 * milésimas hace saltar el conteo. No es objetivo del experimento, así que no
 * estorba: se reporta el valor medido en Python, que viene con cada layout.
 */

/* EL ORDEN DE ARRANQUE, Y POR QUÉ NO BASTA CON RECHAZAR.
 *
 * El worker no puede calcular nada hasta que se le mandó el recinto. Pero en
 * React los efectos de los HIJOS corren antes que los del padre, así que las
 * ilustraciones piden su cálculo antes de que la página haya tenido ocasión de
 * preparar el motor. Fallar ahí con "todavía no hay recinto" es culpar al hijo
 * de un orden que no eligió.
 *
 * Lo correcto es ESPERAR: se crea de entrada una promesa que se resuelve cuando
 * alguien llama a iniciarMotor(). Toda petición la aguarda, venga antes o
 * después. Si pasan varios segundos sin que nadie inicie el motor, se falla con
 * un mensaje que dice qué pasó de verdad, en vez de colgarse en silencio.
 */
let worker = null, sig = 0;
const pendientes = new Map();

let preparado = null;                       // la carga del recinto en curso
let avisarListo;                            // se dispara al iniciar el motor
const hayRecinto = new Promise((r) => { avisarListo = r; });

function crear() {
  worker = new Worker(new URL("./modelo/trabajador.js", import.meta.url),
                      { type: "module" });
  worker.onmessage = (ev) => {
    const { id, ok, resultado, error } = ev.data;
    const p = pendientes.get(id);
    if (!p) return;
    pendientes.delete(id);
    ok ? p.res(resultado) : p.rej(new Error(error));
  };
  worker.onerror = (e) => {
    for (const [, p] of pendientes) p.rej(new Error(e.message || "falló el motor"));
    pendientes.clear();
  };
}

function enviar(msg) {
  if (!worker) crear();
  const id = ++sig;
  return new Promise((res, rej) => {
    pendientes.set(id, { res, rej });
    worker.postMessage({ ...msg, id });
  });
}

const conLimite = (prom, ms, queja) => Promise.race([
  prom,
  new Promise((_, rej) => setTimeout(() => rej(new Error(queja)), ms)),
]);

/** Toda petición de cálculo espera a que haya un recinto cargado. */
async function pedir(msg) {
  await conLimite(hayRecinto, 15000,
                  "nadie preparó el motor con un recinto");
  await preparado;
  return enviar(msg);
}

/** Extrae del catálogo los parámetros que el modelo necesita. */
export function parametrosDe(catalogo) {
  const v = {};
  for (const p of catalogo.parametros) v[p.clave] = p.valor;
  const serv = {};
  for (const a of catalogo.areas) {
    const u = v["UNID_" + a.clave];
    if (u !== undefined) serv[a.clave] = { unidades: u };
  }
  return {
    h: v.H_CELDA, dt: v.DT, k_c: v.REFRESCO_CAMPO, p: v.EXP_REPARTO,
    eps: v.EPS_VACIADO, v0: v.V0, rho_max: v.RHO_MAX, gamma: v.GAMMA,
    rho_c: v.RHO_PERDIDA_CONTROL, J_s: v.J_ESPECIFICO,
    capa_limite: v.CAPA_LIMITE, sigma_k: v.SIGMA_KERNEL,
    w_min: v.ANCHO_LIBRE_MIN, sigma: v.SATURACION ?? 1.0,
    servicio: serv,
  };
}

let recintoActual = null;

/** Prepara el motor para un recinto. Se llama al cambiar de escenario.
 *  Es idempotente: repetirlo con el mismo recinto no vuelve a cargarlo. */
export function iniciarMotor(recinto, catalogo) {
  const huella = JSON.stringify(recinto);
  if (preparado && recintoActual === huella) return preparado;
  recintoActual = huella;
  const P = parametrosDe(catalogo);
  preparado = enviar({ tipo: "iniciar", recinto, catalogo, P }).then(() => P);
  avisarListo(preparado);      // suelta a quien ya estaba esperando
  return preparado;
}

export const motorListo = () => preparado !== null;

/** Anima un layout. `opciones` puede fijar aforo, dt, k_c, p, t_max. */
export function simularLayout(layout, aforo, opciones = {}) {
  return pedir({ tipo: "simular", layout, aforo, opciones });
}

/** El campo de distancias, para dibujarlo.
 *  desde = "salidas" da cuánto falta para salir desde cada punto;
 *  desde = {modulo:k} da cuánto hay que caminar hasta ese módulo. */
export function campoLayout(layout, desde = "salidas") {
  return pedir({ tipo: "campo", layout, desde });
}

/** Los pasos de la zona ocupable: piso libre, erosión, parte conectada a una
 *  salida, y el resultado. Sirve para poder enseñar la cadena y no solo su
 *  resultado. */
export function zonaLayout(layout) {
  return pedir({ tipo: "zona", layout });
}

/** El reparto de f₁ de un layout: a qué módulo le toca cada celda.
 *  Con `sigma` chico las capacidades se vuelven enormes y el reparto degenera
 *  en "cada quien al más cercano": es la comparación que enseña qué hace la
 *  capacidad. */
export function accesoLayout(layout, sigma) {
  return pedir({ tipo: "acceso", layout, sigma });
}
