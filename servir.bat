@echo off
REM Levanta la API con la interfaz React ya compilada.  http://localhost:8000
cd /d "%~dp0"
start "" http://localhost:8000
py -3.12 -m uvicorn api.main:app --reload --port 8000
   
   