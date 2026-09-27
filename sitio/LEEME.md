# Informe publicado

Sitio estatico. No necesita servidor ni instalar nada.

- **Verlo aqui:** `py -3.12 -m http.server 8080` dentro de esta carpeta,
  y abrir http://localhost:8080
- **Publicarlo:** subir esta carpeta tal cual a GitHub Pages, Netlify,
  Vercel o Cloudflare Pages. No hay paso de compilacion.

No abras `index.html` con doble clic: el navegador bloquea la lectura
de los JSON con el protocolo `file://`. Hace falta servirlo por HTTP,
aunque sea el servidor de una linea de arriba.

Se regenera con:

    py -3.12 experimentos/exportar_sitio.py
