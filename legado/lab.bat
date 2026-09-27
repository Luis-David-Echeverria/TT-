@echo off
REM Lanza JupyterLab con el Python correcto (3.12).
REM El comando `jupyter` no esta en el PATH, por eso se invoca como modulo.
cd /d "%~dp0"
py -3.12 -m jupyterlab --notebook-dir="%~dp0"
