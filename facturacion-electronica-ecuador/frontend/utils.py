"""
Utilidades y componentes reutilizables para el frontend
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from typing import Dict, List, Optional
import base64
from io import BytesIO

def format_currency(amount: float) -> str:
    """Formatear cantidad como moneda"""
    return f"${amount:,.2f}"

def format_date(date_obj) -> str:
    """Formatear fecha"""
    if isinstance(date_obj, str):
        return date_obj
    return date_obj.strftime("%d/%m/%Y")

def create_metric_card(title: str, value: str, delta: Optional[str] = None, delta_color: str = "normal"):
    """Crear tarjeta de métrica personalizada"""
    with st.container():
        st.metric(
            label=title,
            value=value,
            delta=delta,
            delta_color=delta_color
        )

def create_status_badge(status: str) -> str:
    """Crear badge de estado con colores"""
    status_colors = {
        "AUTORIZADO": "🟢",
        "GENERADO": "🟡", 
        "FIRMADO": "🔵",
        "RECHAZADO": "🔴",
        "DEVUELTO": "🟠"
    }
    
    color = status_colors.get(status, "⚪")
    return f"{color} {status}"

def display_factura_table(facturas: List[Dict], show_actions: bool = True):
    """Mostrar tabla de facturas con formato"""
    if not facturas:
        st.info("No hay facturas para mostrar")
        return
    
    df = pd.DataFrame(facturas)
    
    # Formatear columnas
    if 'fecha_emision' in df.columns:
        df['fecha_emision'] = pd.to_datetime(df['fecha_emision']).dt.strftime('%d/%m/%Y')
    
    if 'valor_total' in df.columns:
        df['valor_total'] = df['valor_total'].apply(lambda x: f"${x:,.2f}")
    
    if 'estado_sri' in df.columns:
        df['estado'] = df['estado_sri'].apply(create_status_badge)
    
    # Seleccionar columnas a mostrar
    columns_to_show = ['numero_comprobante', 'fecha_emision', 'cliente', 'valor_total', 'estado']
    available_columns = [col for col in columns_to_show if col in df.columns]
    
    st.dataframe(
        df[available_columns],
        use_container_width=True,
        hide_index=True
    )

def create_sales_chart(data: List[Dict], chart_type: str = "line"):
    """Crear gráfico de ventas"""
    if not data:
        st.info("No hay datos para mostrar")
        return
    
    df = pd.DataFrame(data)
    
    if chart_type == "line":
        fig = px.line(df, x='fecha', y='ventas', title='Evolución de Ventas')
    elif chart_type == "bar":
        fig = px.bar(df, x='fecha', y='ventas', title='Ventas por Período')
    else:
        fig = px.area(df, x='fecha', y='ventas', title='Área de Ventas')
    
    fig.update_layout(
        xaxis_title="Fecha",
        yaxis_title="Ventas ($)",
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_pie_chart(data: List[Dict], values_col: str, names_col: str, title: str):
    """Crear gráfico de torta"""
    if not data:
        st.info("No hay datos para mostrar")
        return
    
    df = pd.DataFrame(data)
    
    fig = px.pie(
        df, 
        values=values_col, 
        names=names_col, 
        title=title
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig, use_container_width=True)

def validate_ruc(ruc: str) -> bool:
    """Validar RUC ecuatoriano"""
    if not ruc or len(ruc) != 13:
        return False
    
    # Algoritmo de validación de RUC
    try:
        # Los primeros dos dígitos deben ser válidos (01-24)
        provincia = int(ruc[:2])
        if provincia < 1 or provincia > 24:
            return False
        
        # Tercer dígito debe ser menor a 6 para personas naturales
        # o 6 para sociedades privadas, 9 para sociedades públicas
        tercer_digito = int(ruc[2])
        if tercer_digito < 0 or tercer_digito > 9:
            return False
        
        return True
    except ValueError:
        return False

def validate_cedula(cedula: str) -> bool:
    """Validar cédula ecuatoriana"""
    if not cedula or len(cedula) != 10:
        return False
    
    try:
        # Algoritmo de validación de cédula
        provincia = int(cedula[:2])
        if provincia < 1 or provincia > 24:
            return False
        
        # Algoritmo módulo 10
        coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        suma = 0
        
        for i in range(9):
            valor = int(cedula[i]) * coeficientes[i]
            if valor >= 10:
                valor = valor - 9
            suma += valor
        
        digito_verificador = (10 - (suma % 10)) % 10
        return digito_verificador == int(cedula[9])
    
    except ValueError:
        return False

def show_loading():
    """Mostrar indicador de carga"""
    return st.spinner("Cargando...")

def show_success_message(message: str):
    """Mostrar mensaje de éxito"""
    st.success(f"✅ {message}")

def show_error_message(message: str):
    """Mostrar mensaje de error"""
    st.error(f"❌ {message}")

def show_warning_message(message: str):
    """Mostrar mensaje de advertencia"""
    st.warning(f"⚠️ {message}")

def show_info_message(message: str):
    """Mostrar mensaje informativo"""
    st.info(f"ℹ️ {message}")

def create_download_button(data: bytes, filename: str, mime_type: str, label: str):
    """Crear botón de descarga"""
    return st.download_button(
        label=label,
        data=data,
        file_name=filename,
        mime=mime_type
    )

def format_identification(tipo: str, identificacion: str) -> str:
    """Formatear identificación según tipo"""
    tipos = {
        "04": "RUC",
        "05": "Cédula",
        "06": "Pasaporte", 
        "07": "Consumidor Final",
        "08": "Identificación Exterior"
    }
    
    tipo_desc = tipos.get(tipo, "Desconocido")
    return f"{tipo_desc}: {identificacion}"

def create_confirmation_dialog(message: str, key: str) -> bool:
    """Crear diálogo de confirmación"""
    if st.button(f"⚠️ {message}", key=key):
        return st.checkbox("Confirmar acción", key=f"{key}_confirm")
    return False

class DataValidator:
    """Validador de datos"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validar email"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validar teléfono"""
        import re
        # Formato ecuatoriano: 02-1234567 o 09-12345678
        pattern = r'^0[2-9]-?\d{7,8}$'
        return re.match(pattern, phone.replace(' ', '')) is not None
    
    @staticmethod
    def validate_required_fields(data: Dict, required_fields: List[str]) -> List[str]:
        """Validar campos requeridos"""
        missing_fields = []
        for field in required_fields:
            if not data.get(field) or str(data.get(field)).strip() == "":
                missing_fields.append(field)
        return missing_fields

def create_export_options():
    """Crear opciones de exportación"""
    st.subheader("📤 Opciones de Exportación")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Exportar a Excel"):
            st.info("Funcionalidad en desarrollo")
    
    with col2:
        if st.button("📄 Exportar a PDF"):
            st.info("Funcionalidad en desarrollo")
    
    with col3:
        if st.button("📧 Enviar por Email"):
            st.info("Funcionalidad en desarrollo")

def create_search_filter(placeholder: str = "Buscar...") -> str:
    """Crear filtro de búsqueda"""
    return st.text_input("🔍", placeholder=placeholder)

def create_date_range_filter():
    """Crear filtro de rango de fechas"""
    col1, col2 = st.columns(2)
    
    with col1:
        fecha_desde = st.date_input("📅 Desde", value=date.today().replace(day=1))
    
    with col2:
        fecha_hasta = st.date_input("📅 Hasta", value=date.today())
    
    return fecha_desde, fecha_hasta

def create_status_filter(statuses: List[str], default: str = "Todos"):
    """Crear filtro de estado"""
    options = [default] + statuses
    return st.selectbox("🏷️ Estado", options)

def display_summary_stats(stats: Dict):
    """Mostrar estadísticas resumidas"""
    if not stats:
        return
    
    cols = st.columns(len(stats))
    
    for i, (key, value) in enumerate(stats.items()):
        with cols[i]:
            if isinstance(value, dict):
                st.metric(
                    label=key,
                    value=value.get('value', 0),
                    delta=value.get('delta', None)
                )
            else:
                st.metric(label=key, value=value)