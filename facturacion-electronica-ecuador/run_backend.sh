#!/bin/bash

# Script para iniciar el servidor backend de la API
# Sistema de Facturación Electrónica SRI Ecuador

echo "=== Iniciando Backend API - Sistema de Facturación Electrónica ==="

# Verificar si existe el entorno virtual
if [ ! -d "venv" ]; then
    echo "❌ No se encontró el entorno virtual. Ejecute primero init.sh"
    exit 1
fi

# Activar entorno virtual
echo "🔄 Activando entorno virtual..."
source venv/bin/activate

# Verificar si las dependencias están instaladas
if ! python -c "import fastapi" 2>/dev/null; then
    echo "❌ FastAPI no está instalado. Instalando dependencias..."
    pip install -r requirements.txt
fi

# Configurar variables de entorno
export PYTHONPATH=$(pwd)

echo "🚀 Iniciando servidor API..."
echo "📡 La API estará disponible en: http://localhost:8000"
echo "📚 Documentación: http://localhost:8000/docs"
echo "🔧 Para detener el servidor presione Ctrl+C"
echo ""

# Ejecutar la aplicación desde el directorio correcto
python backend/main.py