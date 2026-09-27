@echo off
REM Desarrollo de la interfaz: Vite con recarga en caliente en 5173,
REM mandando /api a FastAPI (que debe estar corriendo con servir.bat).
cd /d "%~dp0"
npm run dev
