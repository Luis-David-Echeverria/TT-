/* Recinto rasterizado y zona ocupable. Puerto de nucleo/recinto.py y de
 * geometria.zona_ocupable. */
import { caja, disco, dilatar, erosionar, etiquetar, rectAMascara } from "./rejilla.js";

/** Construye la rejilla del recinto a partir de la definición que sirve la API. */
export function crearRecinto(def, hc = 1.0) {
  const W = def.W, H = def.H;
  const nx = Math.round(W / hc), ny = Math.round(H / hc);
  const rec = { W, H, hc, nx, ny, salidas: def.salidas || [] };

  rec.muros = new Uint8Array(nx * ny);
  for (const m of def.muros || []) {
    const r = rectAMascara(rec, [m.x, m.y, m.w, m.h]);
    for (let i = 0; i < r.length; i++) if (r[i]) rec.muros[i] = 1;
  }

  rec.mascaraSalidas = new Uint8Array(nx * ny);
  for (const s of rec.salidas) {
    const a = s.centro - s.ancho / 2, b = s.centro + s.ancho / 2;
    for (let j = 0; j < ny; j++)
      for (let i = 0; i < nx; i++) {
        const cx = (i + 0.5) * hc, cy = (j + 0.5) * hc;
        let d = false;
        if (s.lado === "S") d = cx >= a && cx < b && cy < hc;
        else if (s.lado === "N") d = cx >= a && cx < b && cy >= H - hc;
        else if (s.lado === "O") d = cy >= a && cy < b && cx < hc;
        else d = cy >= a && cy < b && cx >= W - hc;
        if (d) rec.mascaraSalidas[j * nx + i] = 1;
      }
  }
  return rec;
}

/** Rectángulo de una colocación, con su rotación aplicada. */
export function rectDe(col, catalogo) {
  const t = catalogo.areas.find((a) => a.clave === col.tipo);
  const [w, f] = col.rot === 0 ? [t.ancho, t.fondo] : [t.fondo, t.ancho];
  return [col.x, col.y, w, f];
}

/** Muros + áreas de servicio. Una salida nunca es obstáculo. */
export function obstaculos(rec, layout, catalogo) {
  const o = Uint8Array.from(rec.muros);
  for (const c of layout || []) {
    const m = rectAMascara(rec, rectDe(c, catalogo));
    for (let i = 0; i < m.length; i++) if (m[i]) o[i] = 1;
  }
  for (let i = 0; i < o.length; i++) if (rec.mascaraSalidas[i]) o[i] = 0;
  return o;
}

/**
 * Piso al que la gente REALMENTE puede llegar circulando con el ancho
 * normativo, partiendo de alguna salida.
 *
 * Se erosiona el piso libre por medio ancho normativo: lo que sobrevive es la
 * red de circulación por la que sí se puede transitar. Se conserva la parte
 * conectada a alguna salida y se vuelve a dilatar.
 *
 * Un recoveco detrás de un puesto, al que no se entra con el ancho de
 * reglamento, NO es una violación de seguridad: es superficie que no se puede
 * usar. Por eso sale de la zona ocupable en vez de contar como infracción.
 */
export function zonaOcupable(rec, layout, catalogo, P, conPasos = false) {
  const { nx, ny, hc } = rec, N = nx * ny;
  const obst = obstaculos(rec, layout, catalogo);
  const libre = new Uint8Array(N);
  for (let i = 0; i < N; i++) libre[i] = obst[i] ? 0 : 1;

  const r = Math.max(1, Math.round((P.w_min / 2) / hc));
  const st = disco(r);
  const erod = erosionar(libre, nx, ny, st);
  const vacio = new Uint8Array(N);
  if (!erod.some(Boolean)) return conPasos ? { oc: vacio, libre, erod, red: vacio, r } : vacio;

  const { lab } = etiquetar(erod, nx, ny);
  const cerca = dilatar(rec.mascaraSalidas, nx, ny, st);
  const etiq = new Set();
  for (let i = 0; i < N; i++) if (cerca[i] && erod[i] && lab[i]) etiq.add(lab[i]);
  if (!etiq.size) return conPasos ? { oc: vacio, libre, erod, red: vacio, r } : vacio;

  const red = new Uint8Array(N);
  for (let i = 0; i < N; i++) if (etiq.has(lab[i])) red[i] = 1;
  const dil = dilatar(red, nx, ny, st);
  const oc = new Uint8Array(N);
  for (let i = 0; i < N; i++) oc[i] = dil[i] && libre[i] ? 1 : 0;
  // con pasos: para poder ENSEÑAR la cadena, no solo su resultado
  return conPasos ? { oc, libre, erod, red, r } : oc;
}

/** Celdas libres pegadas al módulo: por ahí se entra y por ahí se mide. */
export function celdasAtencion(rec, col, libre, catalogo) {
  const { nx, ny } = rec;
  const cuerpo = rectAMascara(rec, rectDe(col, catalogo));
  const dil = dilatar(cuerpo, nx, ny, { n: 3, r: 1, m: Uint8Array.from([0, 1, 0, 1, 1, 1, 0, 1, 0]) });
  const out = new Uint8Array(nx * ny);
  for (let i = 0; i < out.length; i++) out[i] = dil[i] && libre[i] && !cuerpo[i] ? 1 : 0;
  return out;
}

export { caja, disco };
