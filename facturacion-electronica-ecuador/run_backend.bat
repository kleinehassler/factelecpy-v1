@echo off
REM Script para iniciar el servidor backend de la API
REM Sistema de Facturación Electrónica SRI Ecuador

echo === Iniciando Backend API - Sistema de Facturación Electrónica ===

REM Verificar si existe el entorno virtual
if not exist "venv" (
    echo ❌ No se encontró el entorno virtual. Ejecute primero init.bat
    pause
    exit /b 1
)

REM Activar entorno virtual
echo 🔄 Activando entorno virtual...
call venv\Scripts\activate.bat

REM Verificar si las dependencias están instaladas
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo ❌ FastAPI no está instalado. Instalando dependencias...
    pip install -r requirements.txt
)

REM Configurar variables de entorno
set PYTHONPATH=%cd%

echo 🚀 Iniciando servidor API...
echo 📡 La API estará disponible en: http://localhost:8000
echo 📚 Documentación: http://localhost:8000/docs
echo 🔧 Para detener el servidor presione Ctrl+C
echo.

REM Ejecutar la aplicación desde el directorio correcto
python backend\main.py

pause