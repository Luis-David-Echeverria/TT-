# Legado

Intentos anteriores que ya no forman parte de la herramienta. Se conservan
porque documentan decisiones, no porque se usen.

| qué | por qué se abandonó |
|---|---|
| `prototipo/` | primer prototipo con partículas. Se descartó al pasar al modelo continuo: el render tenía que corresponder al modelo, y un modelo de fluido no se dibuja con partículas. |
| `notebooks/`, `construir_notebook.py` | panel en JupyterLab con ipywidgets. Se descartó por inusable; se reemplazó por FastAPI + React. |
| `construir_panel.py`, `panel.py` | lo mismo. |
| `lab.bat` | lanzador de JupyterLab. |

Nada de aquí se importa desde `nucleo/`, `api/` ni `experimentos/`.
Sus dependencias (IPython, ipywidgets, nbformat) **no** están en
`requirements.txt` a propósito.
