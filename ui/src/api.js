/* Cliente de la API y utilidades de decodificación.
 *
 * REGLA DEL PROYECTO: la UI no calcula nada del modelo. No hay Weidmann, ni
 * Eikonal, ni umbrales escritos aquí. Hasta la paleta y la densidad crítica
 * vienen de /api/catalogo. Si la interfaz tuviera su propia copia del modelo,
 * las dos podrían desviarse y la visualización dejaría de ser evidencia.
 */

/* MODO ESTATICO.
 *
 * El informe se puede publicar sin backend: en vez de llamar a la API, lee
 * archivos JSON que se generaron una vez con experimentos/exportar_sitio.py.
 * Asi se comparte como una carpeta o un sitio estatico, sin nada que instalar
 * ni que mantener encendido.
 *
 * Lo que se pierde: solo se pueden animar y desglosar los layouts que se
 * precalcularon. Simular uno cualquiera necesita el modelo corriendo, y el
 * modelo no cabe en el navegador. La interfaz avisa cuando un punto no tiene
 * detalle en vez de fallar en silencio. */
export const ESTATICO = import.meta.env.VITE_ESTATICO === "1";

/** Traduce una ruta de la API al archivo que la contiene. */
function archivoDe(ruta) {
  const [camino, consulta] = ruta.split("?");
  const par = new URLSearchParams(consulta || "");
  const m = (re) => camino.match(re);
  let x;
  if (camino === "/api/catalogo") return "datos/catalogo.json";
  if (camino === "/api/resultados/escenarios") return "datos/escenarios.json";
  if (camino === "/api/resultados/frente") return "datos/frente.json";
  if (camino === "/api/resultados/pesos") return "datos/pesos.json";
  if (camino === "/api/resultados/nube") {
    return `datos/nube/${par.get("config")}${
      par.get("solo_factibles") === "true" ? "-factibles" : ""}.json`;
  }
  // los layouts de la nube van embebidos; solo tienen archivo propio los
  // de los barridos, que no salen de la base
  if ((x = m(/^\/api\/resultados\/layout\/(.+)$/))) return `datos/layout/${x[1]}.json`;
  if ((x = m(/^\/api\/resultados\/acceso\/(.+)$/))) return `datos/acceso/${x[1]}.json`;
  if ((x = m(/^\/api\/resultados\/simular\/(.+)$/))) return `datos/sim/${x[1]}.json`;
  return null;
}

export async function api(ruta, cuerpo) {
  if (ESTATICO) {
    const f = archivoDe(ruta);
    if (!f) throw new Error("sin backend: esta acción no está disponible en el informe publicado");
    const r = await fetch(f);
    if (!r.ok) {
      throw new Error(r.status === 404
        ? "este punto no trae detalle precalculado"
        : `${r.status} al leer ${f}`);
    }
    const datos = await r.json();
    // una simulacion precalculada se entrega como un trabajo ya terminado,
    // para que la interfaz no tenga que distinguir los dos modos
    if (ruta.includes("/simular/")) {
      return { id: "estatico", estado: "listo", progreso: 1, resultado: datos };
    }
    return datos;
  }

  const opciones = cuerpo
    ? { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo) }
    : {};
  const r = await fetch(ruta, opciones);
  if (!r.ok) throw new Error(`${r.status} — ${await r.text()}`);
  return r.json();
}

/** base64 -> Uint8Array */
export function debase64(s) {
  const bin = atob(s);
  const a = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i);
  return a;
}

/** Tabla de 256 colores a partir de los stops que sirve el backend. */
export function construirLUT(stops) {
  const lut = new Uint8ClampedArray(256 * 3);
  for (let i = 0; i < 256; i++) {
    const t = i / 255;
    let k = 0;
    while (k < stops.length - 2 && t > stops[k + 1].t) k++;
    const a = stops[k], b = stops[k + 1];
    const u = (t - a.t) / Math.max(1e-9, b.t - a.t);
    const ca = parseInt(a.c.slice(1), 16), cb = parseInt(b.c.slice(1), 16);
    lut[i * 3]     = ((ca >> 16) & 255) + (((cb >> 16) & 255) - ((ca >> 16) & 255)) * u;
    lut[i * 3 + 1] = ((ca >> 8) & 255)  + (((cb >> 8) & 255)  - ((ca >> 8) & 255)) * u;
    lut[i * 3 + 2] = (ca & 255)         + ((cb & 255)         - (ca & 255)) * u;
  }
  return lut;
}

/** Paleta del campo de tiempos (solo presentación, no tiene semántica física). */
export function colorTiempo(v) {
  const st = [[13,22,60],[40,90,140],[45,160,150],[150,200,90],[250,230,110]];
  const p = (v / 255) * 4, k = Math.min(3, Math.floor(p)), u = p - k;
  return [
    st[k][0] + (st[k+1][0] - st[k][0]) * u,
    st[k][1] + (st[k+1][1] - st[k][1]) * u,
    st[k][2] + (st[k+1][2] - st[k][2]) * u,
  ];
}

/** Lanza un trabajo y sondea hasta que termina, informando el avance. */
export async function correrTrabajo(peticion, alAvanzar) {
  let t = await api("/api/trabajos", peticion);
  while (t.estado === "encolado" || t.estado === "corriendo") {
    await new Promise((r) => setTimeout(r, 400));
    t = await api(`/api/trabajos/${t.id}`);
    alAvanzar?.(t);
  }
  return t;
}

export const dimensiones = (colocacion, catalogo) => {
  const t = catalogo.areas.find((a) => a.clave === colocacion.tipo);
  return colocacion.rot === 0 ? [t.ancho, t.fondo] : [t.fondo, t.ancho];
};

export const tipoDe = (clave, catalogo) =>
  catalogo.areas.find((a) => a.clave === clave);

/** Variantes distinguibles de un color base, una por módulo del mismo tipo.
 *
 * Los módulos de un tipo comparten color de catálogo. Para ver a cuál le toca
 * cada celda hacen falta tonos distintos, pero que se sigan leyendo como el
 * mismo tipo: se varía la luminosidad y se gira un poco el tono, en vez de usar
 * colores sin relación entre sí. */
export function variantesColor(hex, n) {
  const v = parseInt(hex.slice(1), 16);
  let r = (v >> 16) & 255, g = (v >> 8) & 255, b = v & 255;
  // a HSL
  const mx = Math.max(r, g, b) / 255, mn = Math.min(r, g, b) / 255;
  const l0 = (mx + mn) / 2, d = mx - mn;
  const s0 = d === 0 ? 0 : d / (1 - Math.abs(2 * l0 - 1));
  let h0 = 0;
  if (d !== 0) {
    const R = r / 255, G = g / 255, B = b / 255;
    h0 = mx === R ? ((G - B) / d) % 6 : mx === G ? (B - R) / d + 2 : (R - G) / d + 4;
    h0 *= 60;
    if (h0 < 0) h0 += 360;
  }
  const out = [];
  for (let i = 0; i < n; i++) {
    const t = n === 1 ? 0.5 : i / (n - 1);
    const h = (h0 + (t - 0.5) * 34 + 360) % 360;
    const l = 0.38 + t * 0.30;
    // de HSL a RGB
    const c = (1 - Math.abs(2 * l - 1)) * s0;
    const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
    const m = l - c / 2;
    const k = Math.floor(h / 60) % 6;
    const p = [[c,x,0],[x,c,0],[0,c,x],[0,x,c],[x,0,c],[c,0,x]][k];
    out.push([Math.round((p[0]+m)*255), Math.round((p[1]+m)*255), Math.round((p[2]+m)*255)]);
  }
  return out;
}
