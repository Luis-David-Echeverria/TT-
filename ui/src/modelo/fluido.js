/* La multitud como fluido: Weidmann + conservación de masa por Godunov/CTM.
 *
 * Puerto fiel de nucleo/fluido.py y nucleo/kernel.py. Las constantes NO se
 * escriben aquí: llegan del registro de parámetros de Python, para que no
 * puedan desviarse del modelo que produjo los resultados publicados.
 */
import { INF, caja, dilatar, gaussiano } from "./rejilla.js";
import { eikonal } from "./eikonal.js";

const N_TABLA = 32768;

/** Prepara las tablas y constantes derivadas. Se hace una vez. */
export function crearFisica(P) {
  const { v0, rho_max, gamma } = P;

  const vel = (r) => {
    const x = Math.min(Math.max(r, 1e-6), rho_max - 1e-6);
    return v0 * (1 - Math.exp(-gamma * (1 / x - 1 / rho_max)));
  };

  // q_max y rho_cap NO se ponen a mano: son el máximo de q(ρ) = ρ·v(ρ).
  // Se derivan con el mismo barrido de 20 000 puntos que usa Python.
  let qMax = 0, rhoCap = 0;
  for (let k = 0; k < 20000; k++) {
    const r = 1e-4 + (rho_max - 2e-4) * k / 19999;
    const q = r * vel(r);
    if (q > qMax) { qMax = q; rhoCap = r; }
  }

  // demanda y oferta tabuladas: son funciones puras de la densidad y se evalúan
  // dos veces por paso sobre toda la rejilla. La exponencial ahí costaba el
  // 29 % del tiempo en Python; tabulada, el costo es un indexado.
  const dem = new Float64Array(N_TABLA), ofe = new Float64Array(N_TABLA);
  for (let i = 0; i < N_TABLA; i++) {
    const r = rho_max * i / (N_TABLA - 1), q = r * vel(r);
    dem[i] = r <= rhoCap ? q : qMax;
    ofe[i] = r >= rhoCap ? q : qMax;
  }
  dem[0] = 0;
  ofe[N_TABLA - 1] = 0;

  return { P, vel, qMax, rhoCap, dem, ofe, esc: (N_TABLA - 1) / rho_max };
}

/* ------------------------------------------------------ estimador de densidad */
/* NO es un filtro cosmético: es parte del estimador de densidad (Treuille et
 * al. 2006). Sin él, cualquier hueco vacío tiene velocidad máxima, el gradiente
 * apunta HACIA el hueco, la gente se dirige a los huecos y la multitud se
 * fragmenta en islas. */
function densidadSuave(M, libre, area, W, H, sigma) {
  const c = new Float64Array(W * H), l = new Float64Array(W * H);
  for (let i = 0; i < W * H; i++) { if (libre[i]) { c[i] = M[i] / area; l[i] = 1; } }
  const num = gaussiano(c, W, H, sigma), den = gaussiano(l, W, H, sigma);
  const out = new Float64Array(W * H);
  for (let i = 0; i < W * H; i++)
    out[i] = libre[i] && den[i] > 1e-6 ? num[i] / den[i] : 0;
  return out;
}

/* -------------------------------------------------------- reparto en 2D */
/* Godunov resuelve por cara, en una dimensión. En la rejilla una celda puede
 * tener varios vecinos cuesta abajo y hay que repartir: w_j = (T_i − T_j)^p.
 * Ese exponente es el único parámetro del modelo sin respaldo empírico. */
const DI = [-1, 1, 0, 0], DJ = [0, 0, -1, 1];

function pesosDireccion(T, libre, W, H, p) {
  const Wt = [0, 1, 2, 3].map(() => new Float64Array(W * H));
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const i = y * W + x;
      if (!libre[i] || T[i] >= INF) continue;
      let tot = 0;
      for (let k = 0; k < 4; k++) {
        const yy = y + DI[k], xx = x + DJ[k];
        if (yy < 0 || yy >= H || xx < 0 || xx >= W) continue;
        const j = yy * W + xx;
        if (!libre[j] || T[j] >= INF) continue;
        const d = Math.max(T[i] - T[j], 0);
        const w = p === 1 ? d : Math.pow(d, p);
        Wt[k][i] = w;
        tot += w;
      }
      if (tot > 0) for (let k = 0; k < 4; k++) Wt[k][i] /= tot;
    }
  return Wt;
}

/* ----------------------------------------------------------------- salidas */
/* Una puerta es una SECCIÓN TRANSVERSAL con capacidad fija, no una celda que
 * almacena. La zona de drenaje abarca varias celdas hacia adentro porque, si
 * solo se drenara la fila del borde, el reparto de Godunov manda parte de la
 * masa de lado y la puerta rinde el 71 % de lo nominal (medido). */
export function capacidadSalidas(rec, P, alcance = 2) {
  const { nx, ny, hc, W, H } = rec, out = [];
  for (const s of rec.salidas) {
    const a = s.centro - s.ancho / 2, b = s.centro + s.ancho / 2;
    const m = new Uint8Array(nx * ny);
    for (let j = 0; j < ny; j++)
      for (let i = 0; i < nx; i++) {
        const cx = (i + 0.5) * hc, cy = (j + 0.5) * hc;
        let dentro = false;
        if (s.lado === "S") dentro = cx >= a && cx < b && cy < hc;
        else if (s.lado === "N") dentro = cx >= a && cx < b && cy >= H - hc;
        else if (s.lado === "O") dentro = cy >= a && cy < b && cx < hc;
        else dentro = cy >= a && cy < b && cx >= W - hc;
        if (dentro) m[j * nx + i] = 1;
      }
    const zona = dilatar(m, nx, ny, caja(1), alcance);
    const util = Math.max(0, s.ancho - 2 * P.capa_limite);
    out.push({ zona, cap: P.J_s * util });
  }
  return out;
}

/* ------------------------------------------------------ un paso de Godunov */
/* Tres recorridos y en este orden: el factor de escala depende de la demanda
 * total que llega, que no se conoce hasta terminar el reparto. */
function paso(M, Wt, libre, fis, salidas, area, h, dt, mMax, W, H, buf) {
  const { dem, ofe, esc } = fis;
  const { entrante, envio, escala } = buf;
  const N = W * H;
  entrante.fill(0); envio.fill(0); escala.fill(1);

  // 1) cuánto QUIERE enviar cada celda, repartido cuesta abajo
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const i = y * W + x;
      if (!libre[i]) continue;
      let idx = (M[i] / area * esc) | 0;
      if (idx < 0) idx = 0; else if (idx >= N_TABLA) idx = N_TABLA - 1;
      let e = dem[idx] * h * dt;
      if (e > M[i]) e = M[i];
      envio[i] = e;
      if (e <= 0) continue;
      for (let k = 0; k < 4; k++) {
        const w = Wt[k][i];
        if (w <= 0) continue;
        const yy = y + DI[k], xx = x + DJ[k];
        if (yy < 0 || yy >= H || xx < 0 || xx >= W) continue;
        entrante[yy * W + xx] += e * w;
      }
    }

  // 2) cuánto PUEDE aceptar: rama de oferta, y lo que le cabe
  for (let i = 0; i < N; i++) {
    const ent = entrante[i];
    if (ent <= 1e-12) continue;
    let idx = (M[i] / area * esc) | 0;
    if (idx < 0) idx = 0; else if (idx >= N_TABLA) idx = N_TABLA - 1;
    let sp = ofe[idx] * h * dt;
    const hueco = Math.max(mMax - M[i], 0);
    if (hueco < sp) sp = hueco;
    if (sp < ent) escala[i] = sp / ent;
  }

  // 3) aplicar los flujos ya escalados
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const i = y * W + x;
      if (!libre[i] || envio[i] <= 0) continue;
      for (let k = 0; k < 4; k++) {
        const w = Wt[k][i];
        if (w <= 0) continue;
        const yy = y + DI[k], xx = x + DJ[k];
        if (yy < 0 || yy >= H || xx < 0 || xx >= W) continue;
        const j = yy * W + xx;
        const q = envio[i] * w * escala[j];
        M[i] -= q; M[j] += q;
      }
    }

  // cada salida deja pasar solo su capacidad: aquí nace la fila en la puerta
  let salieron = 0;
  for (const { zona, cap } of salidas) {
    let masa = 0;
    for (let i = 0; i < N; i++) if (zona[i]) masa += M[i];
    if (masa <= 1e-12) continue;
    const sale = Math.min(cap * dt, masa), f = 1 - sale / masa;
    for (let i = 0; i < N; i++) if (zona[i]) M[i] *= f;
    salieron += sale;
  }
  return salieron;
}

/* ------------------------------------------------------------- simulación */
/**
 * Evacuación desde aforo lleno repartido uniformemente. Puerto de
 * fluido.simular. `alPaso` permite animar sin bloquear el hilo.
 */
export function simular(rec, libre, aforo, fis, opts = {}) {
  const P = fis.P;
  const dt = opts.dt ?? P.dt;
  const tMax = opts.t_max ?? 600;
  const refresco = opts.k_c ?? P.k_c;
  const p = opts.p ?? P.p;
  const eps = opts.eps ?? P.eps;
  const rhoC = opts.rho_c ?? P.rho_c;
  const nCuadros = opts.n_cuadros ?? 30;

  const { nx: W, ny: H, hc: h } = rec;
  const N = W * H, area = h * h;
  const mMax = (P.rho_max - 1e-3) * area;

  let nCeldas = 0;
  for (let i = 0; i < N; i++) if (libre[i]) nCeldas++;
  if (!nCeldas) return null;

  const M = new Float64Array(N);
  for (let i = 0; i < N; i++) if (libre[i]) M[i] = aforo / nCeldas;
  const total = aforo;

  const salidas = capacidadSalidas(rec, P);
  const buf = {
    entrante: new Float64Array(N), envio: new Float64Array(N),
    escala: new Float64Array(N),
  };
  const semillas = [];
  for (let i = 0; i < N; i++) if (rec.mascaraSalidas[i]) semillas.push(i);
  const velCampo = new Float64Array(N);
  let Tcampo = new Float64Array(N), Wt = null;

  const cuadros = [], ts = [], pcts = [];
  let fuera = 0, t = 0, t95 = null, tDes = null, expo = 0, rhoPico = 0;
  const nPasos = Math.floor(tMax / dt);
  const cada = Math.max(1, Math.round(2.0 / dt));

  for (let k = 0; k < nPasos; k++) {
    if (k % refresco === 0) {
      const rho = densidadSuave(M, libre, area, W, H, P.sigma_k);
      for (let i = 0; i < N; i++) velCampo[i] = libre[i] ? fis.vel(rho[i]) : 1e-3;
      const alcanzable = new Uint8Array(N);
      for (let i = 0; i < N; i++) alcanzable[i] = libre[i] || rec.mascaraSalidas[i] ? 0 : 1;
      Tcampo = eikonal(W, H, alcanzable, semillas, velCampo, h, Tcampo);
      Wt = pesosDireccion(Tcampo, libre, W, H, p);
    }
    fuera += paso(M, Wt, libre, fis, salidas, area, h, dt, mMax, W, H, buf);

    if (t95 === null && fuera >= 0.95 * total) t95 = t;
    if (tDes === null && (total - fuera) <= eps * total) tDes = t;

    let sobre = 0, mx = 0;
    for (let i = 0; i < N; i++) {
      if (!libre[i]) continue;
      const r = M[i] / area;
      if (r > rhoC) sobre++;
      if (r > mx) mx = r;
    }
    expo += sobre * area * dt;
    if (mx > rhoPico) rhoPico = mx;

    if (k % cada === 0) {
      const c = new Float64Array(N);
      for (let i = 0; i < N; i++) c[i] = M[i] / area;
      cuadros.push(c); ts.push(t); pcts.push(100 * fuera / total);
    }
    t += dt;

    let masa = 0;
    for (let i = 0; i < N; i++) masa += M[i];
    if (masa <= 0.005 * total) break;
  }

  // submuestreo uniforme al número de cuadros pedido
  let cu = cuadros, tt = ts, pp = pcts;
  if (cuadros.length > nCuadros) {
    const sel = [];
    for (let i = 0; i < nCuadros; i++)
      sel.push(Math.round(i * (cuadros.length - 1) / (nCuadros - 1)));
    cu = sel.map((i) => cuadros[i]);
    tt = sel.map((i) => ts[i]);
    pp = sel.map((i) => pcts[i]);
  }
  return {
    cuadros: cu, t: tt, pct: pp, t95, t_des: tDes,
    exposicion: expo, rho_pico: rhoPico, total, T: Tcampo,
  };
}
