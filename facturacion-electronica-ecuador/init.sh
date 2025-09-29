#!/bin/bash

# Script de inicialización del sistema de facturación electrónica SRI Ecuador

echo "=== Sistema de Facturación Electrónica SRI Ecuador ==="
echo "Inicializando sistema..."

# Crear directorios necesarios
echo "Creando directorios..."
mkdir -p logs certificados uploads temp output backup rides

# Verificar si existe el entorno virtual
if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    python -m venv venv
fi

# Activar entorno virtual
echo "Activando entorno virtual..."
source venv/bin/activate

# Actualizar pip
echo "Actualizando pip..."
pip install --upgrade pip

# Instalar dependencias
echo "Instalando dependencias..."
pip install -r requirements.txt

# Verificar instalación de dependencias críticas
echo "Verificando instalación de dependencias críticas..."
python -c "import fastapi; print('✓ FastAPI instalado')"
python -c "import sqlalchemy; print('✓ SQLAlchemy instalado')"
python -c "import cryptography; print('✓ Cryptography instalado')"
python -c "import lxml; print('✓ lxml instalado')"
python -c "import reportlab; print('✓ ReportLab instalado')"

# Crear archivo .env si no existe
if [ ! -f ".env" ]; then
    echo "Creando archivo .env desde ejemplo..."
    cp .env.example .env
    echo "⚠️  Recuerda editar el archivo .env con tus configuraciones"
fi

# Inicializar base de datos
echo "Inicializando base de datos..."
python -c "
from backend.database import inicializar_base_datos
if inicializar_base_datos():
    print('✓ Base de datos inicializada correctamente')
else:
    print('✗ Error al inicializar base de datos')
"

# Verificar configuración
echo "Verificando configuración..."
python -c "
from config.settings import settings, validate_config
try:
    validate_config()
    print('✓ Configuración válida')
except Exception as e:
    print(f'✗ Error en configuración: {e}')
"

# Crear certificado de prueba si no existe
if [ ! -f "certificados/test_cert.pem" ]; then
    echo "Creando certificado de prueba..."
    python -c "
from utils.firma_digital import create_test_certificate
cert_path, cert_pass = create_test_certificate()
if cert_path:
    print('✓ Certificado de prueba creado')
else:
    print('✗ Error al crear certificado de prueba')
"
fi

echo ""
echo "=== Inicialización completada ==="
echo ""
echo "Siguientes pasos:"
echo "1. Edita el archivo .env con tus configuraciones"
echo "2. Coloca tu certificado digital en la carpeta certificados/"
echo "3. Ejecuta 'python backend/main.py' para iniciar el servidor"
echo "4. Accede a la documentación en http://localhost:8000/docs"
echo ""
echo "¡Sistema listo para usar!"