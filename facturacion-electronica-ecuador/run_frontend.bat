@echo off
REM Script para ejecutar el frontend de Streamlit en Windows
REM Sistema de Facturación Electrónica SRI Ecuador

echo === Iniciando Frontend - Sistema de Facturación Electrónica ===

REM Verificar si existe el entorno virtual
if not exist "venv" (
    echo ❌ No se encontró el entorno virtual. Ejecute primero init.bat
    pause
    exit /b 1
)

REM Activar entorno virtual
echo 🔄 Activando entorno virtual...
call venv\Scripts\activate.bat

REM Verificar si Streamlit está instalado
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo ❌ Streamlit no está instalado. Instalando dependencias...
    pip install -r requirements.txt
)

REM Configurar variables de entorno para Streamlit
set STREAMLIT_SERVER_PORT=8501
set STREAMLIT_SERVER_ADDRESS=localhost
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

REM Crear directorio de logs si no existe
if not exist "logs" mkdir logs

echo 🚀 Iniciando servidor Streamlit...
echo 📱 La aplicación estará disponible en: http://localhost:8501
echo 🔧 Para detener el servidor presione Ctrl+C
echo.

REM Ejecutar Streamlit
cd frontend
streamlit run app.py ^
    --server.port 8501 ^
    --server.address localhost ^
    --browser.gatherUsageStats false ^
    --theme.base light ^
    --theme.primaryColor "#1f77b4" ^
    --theme.backgroundColor "#ffffff" ^
    --theme.secondaryBackgroundColor "#f0f2f6" ^
    --theme.textColor "#262730"

pause