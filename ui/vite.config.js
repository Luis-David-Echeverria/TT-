import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";

/* Dos salidas con el mismo codigo:
 *
 *   normal   -> ../web, servida por FastAPI bajo /estatico/. Es la herramienta
 *               completa: simulador + informe, con el modelo detras.
 *   sitio    -> ../sitio, sin backend. Solo el informe, con los datos ya
 *               calculados en archivos JSON. Rutas relativas para que funcione
 *               igual abierta desde una carpeta que desde cualquier hosting.
 */
export default defineConfig(({ mode }) => {
  const estatico = mode === "sitio";
  return {
    plugins: [react(), tailwind()],
    base: estatico ? "./" : "/estatico/",
    server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
    build: {
      outDir: estatico ? "../sitio" : "../web",
      // en modo sitio NO se vacia: los datos ya exportados viven ahi
      emptyOutDir: !estatico,
    },
  };
});
