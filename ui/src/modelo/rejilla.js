/* Rejilla y morfología: lo que en Python hacen numpy y scipy.ndimage.
 *
 * Por qué existe este archivo. La simulación es DETERMINISTA: dado el layout y
 * las constantes, el resultado está fijado. No hay nada aleatorio que haya que
 * guardar. Precalcular una película por layout era un error de diseño — ocupaba
 * 24 MB y dejaba la mayoría de los puntos sin poder abrirse. El cliente puede
 * calcularla, y entonces TODO punto es explorable.
 *
 * REGLA QUE ESTE PUERTO NO PUEDE ROMPER: Python es la única fuente de verdad.
 * Este código no inventa constantes — las recibe del registro de parámetros que
 * sirve el backend. Y su acuerdo con Python se mide, no se supone: ver
 * experimentos/validar_js.py, que compara ambos motores sobre los mismos
 * layouts y reporta la diferencia.
 */

export const INF = 1e9;

/* ------------------------------------------------------------------ discos */
/** Disco de radio r como en geometria._disco: x²+y² <= r²+0.5 */
export function disco(r) {
  const n = 2 * r + 1, m = new Uint8Array(n * n);
  for (let y = -r; y <= r; y++)
    for (let x = -r; x <= r; x++)
      m[(y + r) * n + (x + r)] = (x * x + y * y) <= r * r + 0.5 ? 1 : 0;
  return { n, r, m };
}

/** Cuadrado de lado 2r+1, el structure de np.ones((3,3)) cuando r = 1. */
export function caja(r) {
  const n = 2 * r + 1;
  return { n, r, m: new Uint8Array(n * n).fill(1) };
}

/* ------------------------------------------------------- erosión/dilatación */
export function erosionar(src, W, H, st) {
  const out = new Uint8Array(W * H);
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      let ok = 1;
      for (let dy = -st.r; dy <= st.r && ok; dy++)
        for (let dx = -st.r; dx <= st.r; dx++) {
          if (!st.m[(dy + st.r) * st.n + (dx + st.r)]) continue;
          const yy = y + dy, xx = x + dx;
          // fuera del borde cuenta como fondo, igual que scipy con el default
          if (yy < 0 || yy >= H || xx < 0 || xx >= W || !src[yy * W + xx]) { ok = 0; break; }
        }
      out[y * W + x] = ok;
    }
  return out;
}

export function dilatar(src, W, H, st, veces = 1) {
  let cur = src;
  for (let it = 0; it < veces; it++) {
    const out = new Uint8Array(W * H);
    for (let y = 0; y < H; y++)
      for (let x = 0; x < W; x++) {
        if (!cur[y * W + x]) continue;
        for (let dy = -st.r; dy <= st.r; dy++)
          for (let dx = -st.r; dx <= st.r; dx++) {
            if (!st.m[(dy + st.r) * st.n + (dx + st.r)]) continue;
            const yy = y + dy, xx = x + dx;
            if (yy >= 0 && yy < H && xx >= 0 && xx < W) out[yy * W + xx] = 1;
          }
      }
    cur = out;
  }
  return cur;
}

/** Componentes conexas con vecindad de cruz, como scipy.ndimage.label. */
export function etiquetar(src, W, H) {
  const lab = new Int32Array(W * H).fill(0);
  const pila = new Int32Array(W * H);
  let n = 0;
  for (let i = 0; i < W * H; i++) {
    if (!src[i] || lab[i]) continue;
    n++;
    let sp = 0;
    pila[sp++] = i;
    lab[i] = n;
    while (sp > 0) {
      const p = pila[--sp], px = p % W, py = (p / W) | 0;
      const vec = [[px - 1, py], [px + 1, py], [px, py - 1], [px, py + 1]];
      for (const [qx, qy] of vec) {
        if (qx < 0 || qx >= W || qy < 0 || qy >= H) continue;
        const q = qy * W + qx;
        if (src[q] && !lab[q]) { lab[q] = n; pila[sp++] = q; }
      }
    }
  }
  return { lab, n };
}

/* --------------------------------------------------------- filtro gaussiano */
/** Gaussiano separable, equivalente a scipy.ndimage.gaussian_filter.
 *  El radio de 4σ es el mismo truncamiento que usa scipy por defecto. */
export function gaussiano(src, W, H, sigma) {
  const r = Math.max(1, Math.ceil(4 * sigma));
  const k = new Float64Array(2 * r + 1);
  let s = 0;
  for (let i = -r; i <= r; i++) { k[i + r] = Math.exp(-(i * i) / (2 * sigma * sigma)); s += k[i + r]; }
  for (let i = 0; i < k.length; i++) k[i] /= s;

  const tmp = new Float64Array(W * H), out = new Float64Array(W * H);
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      let a = 0;
      for (let i = -r; i <= r; i++) {
        let xx = x + i;
        if (xx < 0) xx = -xx - 1;                    // reflejo, como scipy
        if (xx >= W) xx = 2 * W - xx - 1;
        a += k[i + r] * src[y * W + xx];
      }
      tmp[y * W + x] = a;
    }
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      let a = 0;
      for (let i = -r; i <= r; i++) {
        let yy = y + i;
        if (yy < 0) yy = -yy - 1;
        if (yy >= H) yy = 2 * H - yy - 1;
        a += k[i + r] * tmp[yy * W + x];
      }
      out[y * W + x] = a;
    }
  return out;
}

/* ------------------------------------------------------------ rasterización */
/** Celdas cuyo centro cae en el rectángulo, igual que Recinto.mascara_rect. */
export function rectAMascara(rec, [x, y, w, h]) {
  const { nx, ny, hc } = rec, m = new Uint8Array(nx * ny);
  for (let j = 0; j < ny; j++) {
    const cy = (j + 0.5) * hc;
    if (cy < y || cy >= y + h) continue;
    for (let i = 0; i < nx; i++) {
      const cx = (i + 0.5) * hc;
      if (cx >= x && cx < x + w) m[j * nx + i] = 1;
    }
  }
  return m;
}
