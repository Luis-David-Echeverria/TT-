/* f₁ — accesibilidad por asignación capacitada. Puerto de nucleo/acceso.py.
 *
 * El reparto óptimo NO es "cada quien al más cercano": un módulo atiende a un
 * ritmo finito, y si todos van al mismo, ese se satura. Se resuelve el problema
 * de transporte de verdad, que además no depende del orden en que se recorran
 * las celdas — la versión voraz sí, y su ruido resultó ser 2.7× la señal que
 * hay que distinguir entre layouts.
 */
import { INF } from "./rejilla.js";
import { eikonal } from "./eikonal.js";
import { celdasAtencion } from "./recinto.js";

/* ------------------------------------------------------- casos cerrados */

/** Dos módulos: óptimo exacto con un solo ordenamiento, sin iterar.
 *
 * Con dos destinos la celda va al módulo 0 si d0−d1 no pasa de cierto umbral.
 * Entonces basta ordenar por esa diferencia y llenar el módulo 0 desde el
 * extremo hasta agotar su capacidad. Es exacto: el transporte con dos destinos
 * y costes lineales tiene esta solución cerrada. */
function transporteDos(D, q, cap) {
  const m = q.length;
  const dif = new Float64Array(m);
  for (let i = 0; i < m; i++) {
    const a = D[0][i], b = D[1][i];
    dif[i] = (a < INF && b < INF) ? a - b : (a < INF ? -Infinity : Infinity);
  }
  const o = Array.from({ length: m }, (_, i) => i).sort((p, r) => dif[p] - dif[r]);
  let acum = 0, coste = 0, k = 0;
  while (k < m && acum + q[o[k]] <= cap[0]) { coste += q[o[k]] * D[0][o[k]]; acum += q[o[k]]; k++; }
  if (k < m) {
    const resto = Math.min(Math.max(cap[0] - acum, 0), q[o[k]]);
    coste += resto * D[0][o[k]] + (q[o[k]] - resto) * D[1][o[k]];
    for (let z = k + 1; z < m; z++) coste += q[o[z]] * D[1][o[z]];
  }
  return coste;
}

/** Precio que deja a un módulo EXACTAMENTE en su capacidad. */
function precioExacto(margen, q, cap) {
  const m = margen.length;
  const o = Array.from({ length: m }, (_, i) => i).sort((a, b) => margen[b] - margen[a]);
  let acum = 0;
  for (let k = 0; k < m; k++) {
    acum += q[o[k]];
    if (acum >= cap) return margen[o[k]];
  }
  return margen[o[m - 1]] - 1;
}

/** Tres o más: descenso por coordenadas, cada una resuelta exacta.
 *
 * Fijados los demás precios, el precio óptimo de UN módulo tiene fórmula
 * cerrada — el mismo argumento de ordenamiento del caso de dos, aplicado a una
 * coordenada. Se barre módulo por módulo y converge en pocos barridos. */
function transporteCoordenadas(D, q, cap, barridos = 12) {
  const n = D.length, m = q.length;
  const pi = new Float64Array(n);
  const C = D.map((d) => Float64Array.from(d));
  const margen = new Float64Array(m);

  for (let s = 0; s < barridos; s++) {
    let cambio = 0;
    for (let j = 0; j < n; j++) {
      for (let i = 0; i < m; i++) {
        let otros = INF;
        for (let k = 0; k < n; k++) if (k !== j && C[k][i] < otros) otros = C[k][i];
        margen[i] = otros - D[j][i];
      }
      const nuevo = precioExacto(margen, q, cap[j]);
      if (!isFinite(nuevo)) continue;
      cambio = Math.max(cambio, Math.abs(nuevo - pi[j]));
      pi[j] = nuevo;
      for (let i = 0; i < m; i++) C[j][i] = D[j][i] + nuevo;
    }
    if (cambio <= 1e-9) break;
  }

  // el reparto que inducen esos precios
  const quien = new Int32Array(m);
  let coste = 0;
  for (let i = 0; i < m; i++) {
    let mejor = 0, mv = C[0][i];
    for (let j = 1; j < n; j++) if (C[j][i] < mv) { mv = C[j][i]; mejor = j; }
    quien[i] = mejor;
    coste += q[i] * D[mejor][i];
  }
  return { coste, pi, quien };
}

function transporte(D, q, cap) {
  const n = D.length;
  if (n === 0) return 0;
  if (n === 1) { let s = 0; for (let i = 0; i < q.length; i++) s += q[i] * D[0][i]; return s; }
  if (n === 2) return transporteDos(D, q, cap);
  return transporteCoordenadas(D, q, cap).coste;
}

/* --------------------------------------------------------------------- f₁ */

/** Distancias caminando de cada celda libre a cada módulo del tipo. */
function matrizDistancias(rec, layout, libre, tipo, catalogo, idxLibres) {
  const { nx, ny, hc } = rec;
  const bloq = new Uint8Array(nx * ny);
  for (let i = 0; i < bloq.length; i++) bloq[i] = libre[i] ? 0 : 1;

  const idx = [];
  layout.forEach((c, k) => { if (c.tipo === tipo) idx.push(k); });
  const D = [];
  for (const k of idx) {
    const sem = celdasAtencion(rec, layout[k], libre, catalogo);
    const semillas = [];
    for (let i = 0; i < sem.length; i++) if (sem[i]) semillas.push(i);
    // el campo se propaga por el espacio libre MÁS las propias semillas
    const dom = Uint8Array.from(bloq);
    for (const s of semillas) dom[s] = 0;
    const T = eikonal(nx, ny, dom, semillas, null, hc);
    const fila = new Float64Array(idxLibres.length);
    for (let a = 0; a < idxLibres.length; a++) {
      const v = T[idxLibres[a]];
      // Sin corregir media celda, a diferencia de Python. Alla skfmm mide al
      // nivel cero de phi, que cae a media celda del centro de la semilla, y
      // por eso se le suma h/2 para que la semilla quede en 0. Aqui las
      // semillas YA valen 0 por construccion: sumar otra vez las dejaria en
      // 0.5 y correria el campo entero (medido: +3.9 % en f1).
      fila[a] = v >= INF ? INF : Math.max(v, 0);
    }
    D.push(fila);
  }
  return { D, idx };
}

function capacidades(layout, tipo, servicio, sigma) {
  const u = layout.filter((c) => c.tipo === tipo).map(() => servicio[tipo].unidades);
  const s = u.reduce((a, b) => a + b, 0);
  return u.map((x) => x / s / sigma);
}

const pesoTipo = (layout, tipo, servicio) =>
  layout.filter((c) => c.tipo === tipo).length * servicio[tipo].unidades;

/**
 * f₁ = distancia media por visita, en metros.
 *
 * No depende del aforo: con reparto uniforme, el aforo multiplica por igual a
 * todas las celdas y se cancela al promediar. Que no dependa del aforo es
 * deseable — comparar layouts no arrastra el supuesto de cuánta gente hay.
 */
export function f1(rec, layout, libre, catalogo, P, conDetalle = false) {
  const N = rec.nx * rec.ny;
  const idxLibres = [];
  for (let i = 0; i < N; i++) if (libre[i]) idxLibres.push(i);
  if (!idxLibres.length) return conDetalle ? { valor: Infinity, tipos: {} } : Infinity;

  const m = idxLibres.length;
  const q = new Float64Array(m).fill(1 / m);
  const servicio = P.servicio, sigma = P.sigma ?? 1.0;

  let suma = 0, peso = 0;
  const tipos = {};
  for (const tipo of Object.keys(servicio)) {
    const { D, idx } = matrizDistancias(rec, layout, libre, tipo, catalogo, idxLibres);
    if (!D.length) continue;
    // una celda sin ruta a ningún módulo deja f₁ indefinida
    for (let i = 0; i < m; i++) {
      let alguno = false;
      for (let j = 0; j < D.length; j++) if (D[j][i] < INF) { alguno = true; break; }
      if (!alguno) return conDetalle ? { valor: Infinity, tipos: {} } : Infinity;
    }
    const cap = capacidades(layout, tipo, servicio, sigma);
    const w = pesoTipo(layout, tipo, servicio);

    if (conDetalle) {
      const n = D.length;
      let coste, quien, carga;
      if (n === 1) {
        quien = new Int32Array(m);
        coste = 0;
        for (let i = 0; i < m; i++) coste += q[i] * D[0][i];
      } else {
        const r = transporteCoordenadas(D, q, cap);
        coste = r.coste; quien = r.quien;
      }
      carga = new Float64Array(n);
      for (let i = 0; i < m; i++) carga[quien[i]] += q[i];
      const dist = new Float64Array(m);
      for (let i = 0; i < m; i++) dist[i] = D[quien[i]][i];
      tipos[tipo] = { quien, dist, modulos: idx, carga: Array.from(carga),
                      capacidad: cap, d_media: coste };
      suma += w * coste; peso += w;
    } else {
      suma += w * transporte(D, q, cap); peso += w;
    }
  }
  const valor = peso > 0 ? suma / peso : Infinity;
  return conDetalle ? { valor, tipos, idxLibres } : valor;
}
