/* Ecuación Eikonal: |∇T| = 1/v, con T = 0 en el destino.
 *
 *   ‖∇T(x)‖ = 1/v(x)      T = 0 en el destino
 *
 * Python la resuelve con Fast Marching (scikit-fmm). Aquí se usa BARRIDO
 * RÁPIDO (fast sweeping, Zhao 2005): recorre la rejilla en las cuatro
 * diagonales, actualizando cada celda con el mismo estencil de Godunov que usa
 * FMM, y repite hasta que no cambia nada.
 *
 * Por qué barrido y no fast marching: FMM necesita una cola de prioridad, que
 * en JavaScript sale lenta y larga de escribir. El barrido son cuatro bucles
 * anidados y converge en pocas pasadas porque la información viaja por
 * características que siempre siguen una de las cuatro diagonales. Los dos
 * resuelven la MISMA ecuación con el MISMO estencil, así que convergen a la
 * misma solución discreta; lo que cambia es el orden en que se recorre.
 *
 * Eso no se da por hecho: experimentos/validar_js.py compara este solver
 * contra scikit-fmm celda por celda y reporta la diferencia.
 *
 * El estencil, que es el corazón: si a y b son los mínimos de los vecinos en
 * cada eje y f = h/v es el costo de cruzar una celda,
 *
 *   |a − b| ≥ f   →  el frente llega por un solo eje:   T = min(a,b) + f
 *   |a − b| < f   →  llega en diagonal, y T sale de resolver la cuadrática:
 *                    T = (a + b + √(2f² − (a−b)²)) / 2
 */
import { INF } from "./rejilla.js";

const DIAG = [[1, 1], [-1, 1], [1, -1], [-1, -1]];

/* Estencil de SEGUNDO ORDEN, que es el que usa scikit-fmm por defecto.
 *
 * Con un solo vecino por eje el campo sale ~1.9 % mas largo que el de Python
 * (medido comparando skfmm con order=1 contra order=2, su default). Ese sesgo
 * se arrastra a f1 y al campo de rutas, asi que el navegador ordenaria los
 * layouts con un modelo distinto al que produjo los resultados publicados.
 *
 * El arreglo es mirar DOS celdas hacia atras en cada eje. Si la segunda no es
 * mayor que la primera, la derivada se estima con tres puntos
 *
 *      a = (4·T1 - T2) / 3       con peso 9/4
 *
 * en vez de a = T1 con peso 1. Luego se resuelve
 *
 *      suma_d  w_d · (T - a_d)^2  =  f^2
 *
 * tomando la raiz mayor. Si esa raiz queda por debajo de algun a_d, ese eje no
 * participa de verdad -- la caracteristica no viene de ahi -- y se rehace sin el.
 */
function resolverCelda(T, bloq, W, H, x, y, i, f) {
  let aX = 0, wX = 0, usaX = false;
  let aY = 0, wY = 0, usaY = false;

  let t1 = INF, dir = 0;
  if (x > 0 && !bloq[i - 1] && T[i - 1] < t1) { t1 = T[i - 1]; dir = -1; }
  if (x < W - 1 && !bloq[i + 1] && T[i + 1] < t1) { t1 = T[i + 1]; dir = 1; }
  if (t1 < INF) {
    usaX = true; aX = t1; wX = 1;
    const x2 = x + 2 * dir, i2 = i + 2 * dir;
    if (x2 >= 0 && x2 < W && !bloq[i2] && T[i2] <= t1) {
      aX = (4 * t1 - T[i2]) / 3; wX = 2.25;
    }
  }

  t1 = INF; dir = 0;
  if (y > 0 && !bloq[i - W] && T[i - W] < t1) { t1 = T[i - W]; dir = -1; }
  if (y < H - 1 && !bloq[i + W] && T[i + W] < t1) { t1 = T[i + W]; dir = 1; }
  if (t1 < INF) {
    usaY = true; aY = t1; wY = 1;
    const y2 = y + 2 * dir, i2 = i + 2 * dir * W;
    if (y2 >= 0 && y2 < H && !bloq[i2] && T[i2] <= t1) {
      aY = (4 * t1 - T[i2]) / 3; wY = 2.25;
    }
  }

  if (!usaX && !usaY) return INF;
  if (!usaX) return aY + f / Math.sqrt(wY);
  if (!usaY) return aX + f / Math.sqrt(wX);

  const A = wX + wY, B = -2 * (wX * aX + wY * aY);
  const C = wX * aX * aX + wY * aY * aY - f * f;
  const disc = B * B - 4 * A * C;
  if (disc >= 0) {
    const t = (-B + Math.sqrt(disc)) / (2 * A);
    if (t >= aX && t >= aY) return t;
  }
  return aX < aY ? aX + f / Math.sqrt(wX) : aY + f / Math.sqrt(wY);
}

/**
 * @param W,H      tamaño de la rejilla
 * @param bloq     Uint8Array: 1 donde no se puede pasar
 * @param semillas array de índices con T = 0
 * @param vel      Float64Array de velocidad por celda, o null para v = 1
 * @param h        lado de celda en metros
 */
export function eikonal(W, H, bloq, semillas, vel, h = 1.0, T = null) {
  const N = W * H;
  if (!T) T = new Float64Array(N);
  T.fill(INF);
  for (const s of semillas) if (!bloq[s]) T[s] = 0;

  let cambio = true;
  for (let pas = 0; pas < 12 && cambio; pas++) {
    cambio = false;
    for (let d = 0; d < 4; d++) {
      const sx = DIAG[d][0], sy = DIAG[d][1];
      for (let yy = 0; yy < H; yy++) {
        const y = sy > 0 ? yy : H - 1 - yy;
        for (let xx = 0; xx < W; xx++) {
          const x = sx > 0 ? xx : W - 1 - xx;
          const i = y * W + x;
          if (bloq[i] || T[i] === 0) continue;
          const f = vel ? h / Math.max(vel[i], 1e-3) : h;
          const t = resolverCelda(T, bloq, W, H, x, y, i, f);
          if (t < T[i] - 1e-12) { T[i] = t; cambio = true; }
        }
      }
    }
  }
  return T;
}

/** −∇T normalizado: hacia dónde se camina. Igual que campos.direccion. */
export function direccion(T, libre, W, H, h) {
  const ux = new Float64Array(W * H), uy = new Float64Array(W * H);
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const i = y * W + x;
      if (!libre[i] || T[i] >= INF) continue;
      const xl = x > 0 && T[i - 1] < INF ? T[i - 1] : T[i];
      const xr = x < W - 1 && T[i + 1] < INF ? T[i + 1] : T[i];
      const yd = y > 0 && T[i - W] < INF ? T[i - W] : T[i];
      const yu = y < H - 1 && T[i + W] < INF ? T[i + W] : T[i];
      const gx = (xr - xl) / (2 * h), gy = (yu - yd) / (2 * h);
      const m = Math.hypot(gx, gy);
      if (m > 1e-9) { ux[i] = -gx / m; uy[i] = -gy / m; }
    }
  return { ux, uy };
}
