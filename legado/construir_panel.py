"""Genera notebooks/00_panel.ipynb — el tablero interactivo."""
import os
import nbformat as nbf

C = []
def md(t): C.append(nbf.v4.new_markdown_cell(t.strip()))
def co(t): C.append(nbf.v4.new_code_cell(t.strip()))

md(r"""
<div style="background:#161b22;border:1px solid #272e38;border-radius:8px;padding:18px 22px">
<h1 style="color:#e6e1d7;margin:0 0 4px;font-weight:500">Tablero — distribución de áreas y evacuación</h1>
<p style="color:#8b949e;margin:0">Modelo continuo · Eikonal + Fast Marching · diagrama fundamental de Weidmann · esquema de Godunov</p>
</div>

**Para trastear.** La ciencia documentada —tabla de parámetros, estudio de convergencia,
hallazgos— está en [`01_evacuacion.ipynb`](01_evacuacion.ipynb).

Ejecuta las dos celdas de abajo (`Shift+Enter`) y juega con el tablero.
""")

co(r"""
%matplotlib widget
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join('..', 'nucleo')))
from panel import Panel
""")

co(r"""
p = Panel(h=1.0, aforo=6000, escala=18.0)
p.mostrar()
""")

md(r"""
---

### Cómo se usa

| Control | Qué hace |
|---|---|
| **aforo** | cuánta gente hay dentro al empezar la evacuación |
| **concentración** | qué tan apretado está el público hacia el escenario. Valores chicos = todos al frente |
| **repartir uniforme** | reparte a todos parejo. **Ojo: no es el peor caso**, es el que menos discrimina — con esto el layout deja de importar |
| **malla** | 1.0 m es la resolución convergida. 2.0 m va 4× más rápido pero **el orden entre layouts no se conserva** |
| **mover área** | selecciona una y haz **clic en el mapa** para moverla. Si el movimiento viola normativa, se rechaza y te dice cuál regla |
| **Simular** | corre la evacuación. Después arrastra la barra de tiempo para recorrerla |
| **Optimizar** | busca una mejor colocación minimizando t95 |

### Qué estás viendo

El **mapa de calor** es densidad de multitud. El color cálido empieza exactamente en
**4 pers/m²**, la densidad a la que la gente pierde el movimiento individual y pasa a ser
desplazada por la presión del grupo. Por eso el color significa lo mismo entre corridas
distintas, en vez de "lo más denso de esta vez".

Las **flechas** son −∇T: hacia dónde camina la gente en cada punto, calculado del campo de
tiempos, no dibujado a mano.

La **barra de estado** de abajo trae la cota por capacidad de puertas. Si t95 se le pega mucho,
la evacuación está saturada en las salidas y el layout ya no puede hacer gran cosa.

### Dos cosas que conviene que compruebes tú

1. **Marca "repartir uniforme" y mueve áreas.** Verás que t95 casi no cambia. Luego desmárcalo
   y baja "concentración" a ~10 m: ahí el layout sí mueve la aguja. La distribución inicial es
   lo que decide si hay algo que optimizar.

2. **Sube el aforo a 20 000.** t95 se pega a la cota por puertas y deja de responder al layout:
   el recinto queda saturado en las salidas.
""")

nb = nbf.v4.new_notebook(cells=C)
nb.metadata = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
               "language_info": {"name": "python", "version": "3.12"}}
os.makedirs("notebooks", exist_ok=True)
ruta = os.path.join("notebooks", "00_panel.ipynb")
with open(ruta, "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print("->", ruta, "|", len(C), "celdas")
