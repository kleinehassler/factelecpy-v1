#!/bin/bash

# Script para ejecutar el frontend de Streamlit
# Sistema de Facturación Electrónica SRI Ecuador

echo "=== Iniciando Frontend - Sistema de Facturación Electrónica ==="

# Verificar si existe el entorno virtual
if [ ! -d "venv" ]; then
    echo "❌ No se encontró el entorno virtual. Ejecute primero init.sh"
    exit 1
fi

# Activar entorno virtual
echo "🔄 Activando entorno virtual..."
source venv/bin/activate

# Verificar si Streamlit está instalado
if ! python -c "import streamlit" 2>/dev/null; then
    echo "❌ Streamlit no está instalado. Instalando dependencias..."
    pip install -r requirements.txt
fi

# Configurar variables de entorno para Streamlit
export STREAMLIT_SERVER_PORT=8501
export STREAMLIT_SERVER_ADDRESS=localhost
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Crear directorio de logs si no existe
mkdir -p logs

echo "🚀 Iniciando servidor Streamlit..."
echo "📱 La aplicación estará disponible en: http://localhost:8501"
echo "🔧 Para detener el servidor presione Ctrl+C"
echo ""

# Ejecutar Streamlit
cd frontend
streamlit run app.py \
    --server.port 8501 \
    --server.address localhost \
    --browser.gatherUsageStats false \
    --theme.base light \
    --theme.primaryColor "#1f77b4" \
    --theme.backgroundColor "#ffffff" \
    --theme.secondaryBackgroundColor "#f0f2f6" \
    --theme.textColor "#262730"