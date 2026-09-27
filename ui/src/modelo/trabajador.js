/* El modelo corriendo en un hilo aparte.
 *
 * Una simulación completa toma ~300 ms. En el hilo principal eso congela la
 * interfaz cada vez que se abre un layout — se nota y se siente roto. En un
 * worker el usuario puede seguir navegando mientras se calcula.
 */
import { crearRecinto, zonaOcupable } from "./recinto.js";
import { crearFisica, simular } from "./fluido.js";
import { f1 } from "./acceso.js";
import { eikonal } from "./eikonal.js";
import { celdasAtencion } from "./recinto.js";

let rec = null, fis = null, cat = null, P = null;

/** Densidad a uint8 sobre [0, rho_max], igual que hace el backend. */
function aByte(campo, rhoMax) {
  const o = new Uint8Array(campo.length);
  for (let i = 0; i < campo.length; i++) {
    let v = campo[i] / rhoMax;
    if (v < 0) v = 0; else if (v > 1) v = 1;
    o[i] = (v * 255) | 0;
  }
  return o;
}

self.onmessage = (ev) => {
  const m = ev.data;
  try {
    if (m.tipo === "iniciar") {
      P = m.P; cat = m.catalogo;
      rec = crearRecinto(m.recinto, P.h);
      fis = crearFisica(P);
      self.postMessage({ id: m.id, ok: true });
      return;
    }

    if (!rec) {
      // no deberia pasar -- el puente hace esperar a la preparacion -- pero un
      // mensaje claro vale mas que "Cannot destructure property 'nx' of null"
      self.postMessage({ id: m.id, ok: false,
        error: "el motor no tiene recinto cargado todavía" });
      return;
    }
    const libre = zonaOcupable(rec, m.layout, cat, P);

    if (m.tipo === "campo") {
      /* El campo de distancias o de tiempos, para poder DIBUJARLO.
         desde = "salidas"  -> cuanto falta para salir desde cada punto
         desde = {modulo:k} -> cuanto hay que caminar hasta ese modulo */
      const N = rec.nx * rec.ny;
      const bloq = new Uint8Array(N);
      let semillas = [];
      if (m.desde === "salidas") {
        for (let i = 0; i < N; i++) bloq[i] = libre[i] || rec.mascaraSalidas[i] ? 0 : 1;
        for (let i = 0; i < N; i++) if (rec.mascaraSalidas[i]) semillas.push(i);
      } else {
        const sem = celdasAtencion(rec, m.layout[m.desde.modulo], libre, cat);
        for (let i = 0; i < N; i++) bloq[i] = libre[i] ? 0 : 1;
        for (let i = 0; i < N; i++) if (sem[i]) { semillas.push(i); bloq[i] = 0; }
      }
      const T = eikonal(rec.nx, rec.ny, bloq, semillas, null, rec.hc);
      let tmax = 0;
      for (let i = 0; i < N; i++) if (libre[i] && T[i] < 1e8 && T[i] > tmax) tmax = T[i];
      const q = new Uint8Array(N).fill(255);   // 255 = sin ruta
      for (let i = 0; i < N; i++)
        if (libre[i] && T[i] < 1e8) q[i] = Math.min(254, (T[i] / (tmax || 1)) * 254) | 0;
      const semMask = new Uint8Array(N);
      for (const i of semillas) semMask[i] = 1;
      self.postMessage({ id: m.id, ok: true, resultado: {
        nx: rec.nx, ny: rec.ny, h: rec.hc, tmax, campo: q,
        libre, muros: rec.muros, salidas: rec.mascaraSalidas, semillas: semMask,
      } });
      return;
    }

    if (m.tipo === "zona") {
      const z = zonaOcupable(rec, m.layout, cat, P, true);
      self.postMessage({ id: m.id, ok: true, resultado: {
        nx: rec.nx, ny: rec.ny, h: rec.hc, radio: z.r,
        libre: z.libre, erosionado: z.erod, conectado: z.red, ocupable: z.oc,
        muros: rec.muros, salidas: rec.mascaraSalidas,
      } });
      return;
    }

    if (m.tipo === "acceso") {
      // sigma chico = capacidades enormes = nadie se satura = reparto por
      // cercania pura. Sirve para enseñar LADO A LADO lo que hace la capacidad.
      const Pd = m.sigma ? { ...P, sigma: m.sigma } : P;
      const r = f1(rec, m.layout, libre, cat, Pd, true);
      const tipos = {};
      const N = rec.nx * rec.ny;
      for (const [t, d] of Object.entries(r.tipos)) {
        // a rejilla completa: 255 = celda sin dato
        const quien = new Uint8Array(N).fill(255);
        const dist = new Float64Array(N);
        let dmax = 0;
        r.idxLibres.forEach((celda, a) => {
          quien[celda] = d.quien[a];
          dist[celda] = isFinite(d.dist[a]) ? d.dist[a] : 0;
          if (dist[celda] > dmax) dmax = dist[celda];
        });
        const db = new Uint8Array(N);
        for (let i = 0; i < N; i++) db[i] = ((dist[i] / (dmax || 1)) * 255) | 0;
        tipos[t] = {
          quien, dist: db, dmax,
          modulos: d.modulos, carga: d.carga,
          capacidad: Array.from(d.capacidad), d_media: d.d_media,
        };
      }
      self.postMessage({ id: m.id, ok: true, resultado: {
        nx: rec.nx, ny: rec.ny, h: rec.hc, f1: r.valor, tipos,
        mascara: libre,
      } });
      return;
    }

    if (m.tipo === "simular") {
      const r = simular(rec, libre, m.aforo, fis, m.opciones || {});
      if (!r) { self.postMessage({ id: m.id, ok: false, error: "recinto sin área útil" }); return; }
      self.postMessage({ id: m.id, ok: true, resultado: {
        nx: rec.nx, ny: rec.ny, h: rec.hc, rho_max: P.rho_max,
        mascara: libre,
        cuadros: r.cuadros.map((c) => aByte(c, P.rho_max)),
        t: r.t, pct: r.pct, t95: r.t95, t_des: r.t_des,
        exposicion: r.exposicion, rho_pico: r.rho_pico,
      } });
      return;
    }
    self.postMessage({ id: m.id, ok: false, error: "orden desconocida: " + m.tipo });
  } catch (e) {
    self.postMessage({ id: m.id, ok: false, error: String(e && e.message || e) });
  }
};
