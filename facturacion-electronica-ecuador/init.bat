@echo off
REM Script de inicialización del sistema de facturación electrónica SRI Ecuador

echo === Sistema de Facturación Electrónica SRI Ecuador ===
echo Inicializando sistema...

REM Crear directorios necesarios
echo Creando directorios...
mkdir logs certificados uploads temp output backup rides 2>nul

REM Verificar si existe el entorno virtual
if not exist "venv" (
    echo Creando entorno virtual...
    python -m venv venv
)

REM Activar entorno virtual
echo Activando entorno virtual...
call venv\Scripts\activate

REM Actualizar pip
echo Actualizando pip...
pip install --upgrade pip

REM Instalar dependencias
echo Instalando dependencias...
pip install -r requirements.txt

REM Verificar instalación de dependencias críticas
echo Verificando instalación de dependencias críticas...
python -c "import fastapi; print('✓ FastAPI instalado')"
python -c "import sqlalchemy; print('✓ SQLAlchemy instalado')"
python -c "import cryptography; print('✓ Cryptography instalado')"
python -c "import lxml; print('✓ lxml instalado')"
python -c "import reportlab; print('✓ ReportLab instalado')"

REM Crear archivo .env si no existe
if not exist ".env" (
    echo Creando archivo .env desde ejemplo...
    copy .env.example .env
    echo ⚠️  Recuerda editar el archivo .env con tus configuraciones
)

REM Inicializar base de datos
echo Inicializando base de datos...
python -c "from backend.database import inicializar_base_datos; inicializar_base_datos()"

REM Verificar configuración
echo Verificando configuración...
python -c "from config.settings import settings, validate_config; validate_config()"

REM Crear certificado de prueba si no existe
if not exist "certificados\test_cert.pem" (
    echo Creando certificado de prueba...
    python -c "from utils.firma_digital import create_test_certificate; create_test_certificate()"
)

echo.
echo === Inicialización completada ===
echo.
echo Siguientes pasos:
echo 1. Edita el archivo .env con tus configuraciones
echo 2. Coloca tu certificado digital en la carpeta certificados\
echo 3. Ejecuta 'python backend\main.py' para iniciar el servidor
echo 4. Accede a la documentación en http://localhost:8000/docs
echo.
echo ¡Sistema listo para usar!