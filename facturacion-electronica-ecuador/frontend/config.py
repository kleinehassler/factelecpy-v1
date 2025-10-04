"""
Configuración del frontend Streamlit
"""
import streamlit as st
import os
from typing import Dict, Any

class FrontendConfig:
    """Configuración del frontend"""
    
    # Configuración de la API
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
    
    # Configuración de la aplicación
    APP_TITLE = "Sistema de Facturación Electrónica SRI Ecuador"
    APP_ICON = "🧾"
    
    # Configuración de página
    PAGE_CONFIG = {
        "page_title": APP_TITLE,
        "page_icon": APP_ICON,
        "layout": "wide",
        "initial_sidebar_state": "expanded",
        "menu_items": {
            'Get Help': 'https://docs.streamlit.io/',
            'Report a bug': "mailto:soporte@empresa.com",
            'About': f"# {APP_TITLE}\nSistema completo de facturación electrónica para Ecuador"
        }
    }
    
    # Tema y estilos
    CUSTOM_CSS = """
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    
    .status-autorizado {
        color: #28a745;
        font-weight: bold;
    }
    
    .status-rechazado {
        color: #dc3545;
        font-weight: bold;
    }
    
    .status-generado {
        color: #ffc107;
        font-weight: bold;
    }
    
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
    }
    
    .stButton > button {
        width: 100%;
        border-radius: 0.5rem;
    }
    
    .success-message {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 0.75rem;
        border-radius: 0.25rem;
        margin: 1rem 0;
    }
    
    .error-message {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 0.75rem;
        border-radius: 0.25rem;
        margin: 1rem 0;
    }
    
    .info-box {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.25rem;
    }
    
    .warning-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.25rem;
    }
    </style>
    """
    
    # Configuración de menú
    MENU_OPTIONS = [
        {"icon": "🏠", "label": "Dashboard", "key": "dashboard"},
        {"icon": "🧾", "label": "Facturas", "key": "facturas"},
        {"icon": "👥", "label": "Clientes", "key": "clientes"},
        {"icon": "📦", "label": "Productos", "key": "productos"},
        {"icon": "📈", "label": "Reportes", "key": "reportes"},
        {"icon": "⚙️", "label": "Configuración", "key": "configuracion"},
        {"icon": "🚪", "label": "Cerrar Sesión", "key": "logout"}
    ]
    
    # Configuración de estados SRI
    ESTADOS_SRI = {
        "GENERADO": {"color": "#ffc107", "icon": "🟡"},
        "FIRMADO": {"color": "#17a2b8", "icon": "🔵"},
        "AUTORIZADO": {"color": "#28a745", "icon": "🟢"},
        "RECHAZADO": {"color": "#dc3545", "icon": "🔴"},
        "DEVUELTO": {"color": "#fd7e14", "icon": "🟠"}
    }
    
    # Configuración de tipos de identificación
    TIPOS_IDENTIFICACION = {
        "04": "RUC",
        "05": "Cédula",
        "06": "Pasaporte",
        "07": "Consumidor Final",
        "08": "Identificación Exterior"
    }
    
    # Configuración de gráficos
    CHART_CONFIG = {
        "theme": "streamlit",
        "displayModeBar": False,
        "responsive": True
    }
    
    # Configuración de tablas
    TABLE_CONFIG = {
        "use_container_width": True,
        "hide_index": True,
        "height": 400
    }
    
    # Mensajes del sistema
    MESSAGES = {
        "login_success": "¡Bienvenido al sistema!",
        "login_error": "Credenciales incorrectas",
        "connection_error": "Error de conexión con el servidor",
        "data_saved": "Datos guardados exitosamente",
        "data_error": "Error al guardar los datos",
        "no_data": "No hay datos para mostrar",
        "loading": "Cargando...",
        "processing": "Procesando...",
        "email_sent": "Email enviado exitosamente",
        "pdf_generated": "PDF generado exitosamente",
        "sri_consulted": "Estado consultado en el SRI"
    }
    
    # Configuración de validaciones
    VALIDATION_RULES = {
        "ruc_length": 13,
        "cedula_length": 10,
        "clave_acceso_length": 49,
        "max_file_size": 5 * 1024 * 1024,  # 5MB
        "allowed_file_types": [".p12", ".pdf", ".xml"]
    }
    
    # Configuración de paginación
    PAGINATION = {
        "default_page_size": 25,
        "page_size_options": [10, 25, 50, 100],
        "max_pages": 100
    }

def apply_custom_css():
    """Aplicar CSS personalizado"""
    st.markdown(FrontendConfig.CUSTOM_CSS, unsafe_allow_html=True)

def get_status_badge(status: str) -> str:
    """Obtener badge de estado con formato"""
    config = FrontendConfig.ESTADOS_SRI.get(status, {"icon": "⚪", "color": "#6c757d"})
    return f"{config['icon']} {status}"

def format_identification(tipo: str, identificacion: str) -> str:
    """Formatear identificación"""
    tipo_desc = FrontendConfig.TIPOS_IDENTIFICACION.get(tipo, "Desconocido")
    return f"{tipo_desc}: {identificacion}"

def show_message(message_type: str, custom_message: str = None):
    """Mostrar mensaje del sistema"""
    if custom_message:
        message = custom_message
    else:
        message = FrontendConfig.MESSAGES.get(message_type, "Mensaje del sistema")
    
    if message_type in ["success", "data_saved", "email_sent", "pdf_generated", "sri_consulted"]:
        st.success(f"✅ {message}")
    elif message_type in ["error", "login_error", "connection_error", "data_error"]:
        st.error(f"❌ {message}")
    elif message_type in ["warning"]:
        st.warning(f"⚠️ {message}")
    else:
        st.info(f"ℹ️ {message}")

def init_session_state():
    """Inicializar estado de sesión"""
    default_values = {
        "authenticated": False,
        "token": None,
        "user_data": None,
        "current_page": "dashboard",
        "factura_detalles": [],
        "selected_items": [],
        "filters": {},
        "theme": "light"
    }

    for key, value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = value
def clear_session_state():
    """Limpiar estado de sesión"""
    keys_to_clear = [
        "authenticated", "token", "user_data", "factura_detalles",
        "selected_items", "filters", "current_page"
    ]

    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

def init_session_state():
    """Inicializar estado de sesión"""
    default_values = {
        "authenticated": False,
        "token": None,
        "user_data": None,
        "current_page": "dashboard",
        "factura_detalles": [],
        "selected_items": [],
        "filters": {},
        "theme": "light"
    }

    for key, value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = value

def get_page_config():
    """Obtener configuración de página"""
    return FrontendConfig.PAGE_CONFIG

def get_menu_options():
    """Obtener opciones de menú"""
    return FrontendConfig.MENU_OPTIONS

def get_api_base_url():
    """Obtener URL base de la API"""
    return FrontendConfig.API_BASE_URL