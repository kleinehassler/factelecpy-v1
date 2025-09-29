"""
Páginas específicas para el sistema de facturación electrónica
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
import requests
import json

from utils import (
    format_currency, format_date, create_metric_card, create_status_badge,
    display_factura_table, create_sales_chart, create_pie_chart,
    validate_ruc, validate_cedula, show_success_message, show_error_message,
    DataValidator, create_export_options, create_search_filter,
    create_date_range_filter, create_status_filter, display_summary_stats
)

class FacturasPage:
    """Página de gestión de facturas"""
    
    def __init__(self, api_client):
        self.api_client = api_client
    
    def render(self):
        """Renderizar página de facturas"""
        st.title("🧾 Gestión de Facturas Electrónicas")
        st.markdown("---")
        
        # Pestañas principales
        tab1, tab2, tab3, tab4 = st.tabs([
            "📋 Lista de Facturas", 
            "➕ Nueva Factura", 
            "📊 Estadísticas",
            "🔍 Consultas SRI"
        ])
        
        with tab1:
            self._render_facturas_list()
        
        with tab2:
            self._render_nueva_factura()
        
        with tab3:
            self._render_estadisticas()
        
        with tab4:
            self._render_consultas_sri()
    
    def _render_facturas_list(self):
        """Renderizar lista de facturas"""
        st.subheader("📋 Lista de Facturas")
        
        # Filtros
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            search_term = create_search_filter("Buscar por número o cliente...")
        
        with col2:
            fecha_desde, fecha_hasta = create_date_range_filter()
        
        with col3:
            estado_filter = create_status_filter([
                "GENERADO", "FIRMADO", "AUTORIZADO", "RECHAZADO", "DEVUELTO"
            ])
        
        with col4:
            limit = st.selectbox("Mostrar", [10, 25, 50, 100], index=1)
        
        # Obtener facturas
        params = {
            "limit": limit,
            "fecha_desde": fecha_desde.isoformat(),
            "fecha_hasta": fecha_hasta.isoformat()
        }
        
        if estado_filter != "Todos":
            params["estado"] = estado_filter
        
        if search_term:
            params["search"] = search_term
        
        facturas = self.api_client.get("/facturas", params)
        
        if facturas:
            # Estadísticas rápidas
            total_facturas = len(facturas)
            total_ventas = sum(f.get('valor_total', 0) for f in facturas)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Facturas", total_facturas)
            with col2:
                st.metric("Total Ventas", format_currency(total_ventas))
            with col3:
                promedio = total_ventas / total_facturas if total_facturas > 0 else 0
                st.metric("Promedio por Factura", format_currency(promedio))
            
            st.markdown("---")
            
            # Tabla de facturas
            df = pd.DataFrame(facturas)
            
            # Formatear datos para mostrar
            if not df.empty:
                df['fecha_emision'] = pd.to_datetime(df['fecha_emision']).dt.strftime('%d/%m/%Y %H:%M')
                df['valor_total_fmt'] = df['valor_total'].apply(format_currency)
                df['estado_badge'] = df['estado_sri'].apply(create_status_badge)
                
                # Columnas a mostrar
                columns_display = {
                    'numero_comprobante': 'Número',
                    'fecha_emision': 'Fecha',
                    'cliente_nombre': 'Cliente',
                    'valor_total_fmt': 'Total',
                    'estado_badge': 'Estado'
                }
                
                # Selección de facturas
                selected_facturas = st.multiselect(
                    "Seleccionar facturas para acciones:",
                    options=df['id'].tolist(),
                    format_func=lambda x: df[df['id']==x]['numero_comprobante'].iloc[0]
                )
                
                # Mostrar tabla
                display_df = df.rename(columns=columns_display)[list(columns_display.values())]
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                # Acciones masivas
                if selected_facturas:
                    st.markdown("### 🔧 Acciones")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        if st.button("📧 Enviar Email", key="send_email"):
                            self._enviar_facturas_email(selected_facturas)
                    
                    with col2:
                        if st.button("📄 Descargar PDF", key="download_pdf"):
                            self._descargar_facturas_pdf(selected_facturas)
                    
                    with col3:
                        if st.button("🔄 Consultar SRI", key="check_sri"):
                            self._consultar_estado_sri(selected_facturas)
                    
                    with col4:
                        if st.button("📊 Exportar Excel", key="export_excel"):
                            self._exportar_excel(selected_facturas)
        else:
            st.info("No se encontraron facturas con los filtros aplicados")
    
    def _render_nueva_factura(self):
        """Renderizar formulario de nueva factura"""
        st.subheader("➕ Nueva Factura Electrónica")
        
        # Inicializar estado de sesión para detalles
        if 'factura_detalles' not in st.session_state:
            st.session_state.factura_detalles = []
        
        with st.form("nueva_factura_form"):
            # Sección 1: Datos del cliente
            st.markdown("#### 👤 Datos del Cliente")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Selección de cliente existente o nuevo
                cliente_option = st.radio(
                    "Tipo de cliente:",
                    ["Seleccionar existente", "Crear nuevo"]
                )
                
                if cliente_option == "Seleccionar existente":
                    clientes = self.api_client.get("/clientes")
                    if clientes:
                        cliente_options = {
                            f"{c['razon_social']} - {c['identificacion']}": c['id'] 
                            for c in clientes
                        }
                        cliente_seleccionado = st.selectbox(
                            "Cliente", 
                            options=list(cliente_options.keys())
                        )
                        cliente_id = cliente_options.get(cliente_seleccionado)
                    else:
                        st.warning("No hay clientes registrados")
                        cliente_id = None
                else:
                    cliente_id = None
            
            with col2:
                if cliente_option == "Crear nuevo":
                    tipo_id = st.selectbox("Tipo ID", ["05", "04", "06", "07", "08"])
                    identificacion = st.text_input("Identificación")
                    razon_social = st.text_input("Razón Social")
                    email = st.text_input("Email")
            
            st.markdown("---")
            
            # Sección 2: Productos
            st.markdown("#### 📦 Productos/Servicios")
            
            # Agregar producto
            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
            
            with col1:
                productos = self.api_client.get("/productos")
                if productos:
                    producto_options = {
                        f"{p['descripcion']} - {format_currency(p['precio_unitario'])}": p 
                        for p in productos
                    }
                    producto_sel = st.selectbox("Producto", options=list(producto_options.keys()))
                else:
                    st.warning("No hay productos registrados")
                    producto_sel = None
            
            with col2:
                cantidad = st.number_input("Cantidad", min_value=0.01, value=1.0, step=0.01)
            
            with col3:
                precio_unit = st.number_input("Precio Unit.", min_value=0.01, value=1.0, step=0.01)
            
            with col4:
                descuento = st.number_input("Desc. %", min_value=0.0, max_value=100.0, value=0.0)
            
            with col5:
                agregar_producto = st.form_submit_button("➕ Agregar")
            
            # Procesar agregar producto
            if agregar_producto and producto_sel:
                producto = producto_options[producto_sel]
                detalle = {
                    "codigo_principal": producto['codigo_principal'],
                    "descripcion": producto['descripcion'],
                    "cantidad": cantidad,
                    "precio_unitario": precio_unit,
                    "descuento": descuento,
                    "subtotal": cantidad * precio_unit * (1 - descuento/100)
                }
                st.session_state.factura_detalles.append(detalle)
                st.rerun()
            
            # Mostrar productos agregados
            if st.session_state.factura_detalles:
                st.markdown("##### Productos Agregados:")
                df_detalles = pd.DataFrame(st.session_state.factura_detalles)
                df_detalles['precio_unitario_fmt'] = df_detalles['precio_unitario'].apply(format_currency)
                df_detalles['subtotal_fmt'] = df_detalles['subtotal'].apply(format_currency)
                
                st.dataframe(
                    df_detalles[['descripcion', 'cantidad', 'precio_unitario_fmt', 'descuento', 'subtotal_fmt']],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Totales
                subtotal = sum(d['subtotal'] for d in st.session_state.factura_detalles)
                iva = subtotal * 0.12
                total = subtotal + iva
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Subtotal", format_currency(subtotal))
                with col2:
                    st.metric("IVA 12%", format_currency(iva))
                with col3:
                    st.metric("TOTAL", format_currency(total))
                
                if st.form_submit_button("🗑️ Limpiar Productos"):
                    st.session_state.factura_detalles = []
                    st.rerun()
            
            st.markdown("---")
            
            # Sección 3: Información adicional
            st.markdown("#### 📝 Información Adicional")
            observaciones = st.text_area("Observaciones")
            
            # Botón crear factura
            crear_factura = st.form_submit_button("💾 Crear Factura", type="primary")
            
            if crear_factura:
                if self._validar_factura(cliente_id, cliente_option):
                    self._crear_factura(cliente_id, cliente_option, observaciones)
    
    def _validar_factura(self, cliente_id, cliente_option):
        """Validar datos de la factura"""
        if cliente_option == "Seleccionar existente" and not cliente_id:
            show_error_message("Debe seleccionar un cliente")
            return False
        
        if not st.session_state.factura_detalles:
            show_error_message("Debe agregar al menos un producto")
            return False
        
        return True
    
    def _crear_factura(self, cliente_id, cliente_option, observaciones):
        """Crear nueva factura"""
        try:
            factura_data = {
                "cliente_id": cliente_id,
                "detalles": st.session_state.factura_detalles,
                "observaciones": observaciones
            }
            
            # Si es cliente nuevo, agregarlo a los datos
            if cliente_option == "Crear nuevo":
                factura_data["cliente_nuevo"] = {
                    "tipo_identificacion": st.session_state.get("tipo_id"),
                    "identificacion": st.session_state.get("identificacion"),
                    "razon_social": st.session_state.get("razon_social"),
                    "email": st.session_state.get("email")
                }
            
            resultado = self.api_client.post("/facturas", factura_data)
            
            if resultado:
                show_success_message(f"Factura creada: {resultado['numero_comprobante']}")
                st.session_state.factura_detalles = []
                st.rerun()
            
        except Exception as e:
            show_error_message(f"Error al crear factura: {str(e)}")
    
    def _render_estadisticas(self):
        """Renderizar estadísticas de facturación"""
        st.subheader("📊 Estadísticas de Facturación")
        
        # Filtros de fecha
        fecha_desde, fecha_hasta = create_date_range_filter()
        
        # Obtener estadísticas
        stats = self.api_client.get(f"/facturas/estadisticas?desde={fecha_desde}&hasta={fecha_hasta}")
        
        if stats:
            # Métricas principales
            display_summary_stats({
                "Total Facturas": stats.get("total_facturas", 0),
                "Total Ventas": format_currency(stats.get("total_ventas", 0)),
                "Promedio": format_currency(stats.get("promedio_factura", 0)),
                "Autorizadas": stats.get("facturas_autorizadas", 0)
            })
            
            st.markdown("---")
            
            # Gráficos
            col1, col2 = st.columns(2)
            
            with col1:
                # Gráfico de ventas por día
                if stats.get("ventas_diarias"):
                    create_sales_chart(stats["ventas_diarias"], "line")
            
            with col2:
                # Gráfico de estados
                if stats.get("estados_distribucion"):
                    create_pie_chart(
                        stats["estados_distribucion"],
                        "cantidad",
                        "estado",
                        "Distribución por Estados"
                    )
    
    def _render_consultas_sri(self):
        """Renderizar consultas al SRI"""
        st.subheader("🔍 Consultas al SRI")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Consulta por Clave de Acceso")
            clave_acceso = st.text_input("Clave de Acceso (49 dígitos)")
            
            if st.button("🔍 Consultar Estado"):
                if len(clave_acceso) == 49:
                    resultado = self.api_client.get(f"/sri/consultar/{clave_acceso}")
                    if resultado:
                        st.json(resultado)
                else:
                    show_error_message("La clave de acceso debe tener 49 dígitos")
        
        with col2:
            st.markdown("#### Consulta Masiva")
            facturas_pendientes = self.api_client.get("/facturas?estado=FIRMADO")
            
            if facturas_pendientes:
                st.info(f"Hay {len(facturas_pendientes)} facturas pendientes de autorización")
                
                if st.button("🔄 Consultar Todas"):
                    for factura in facturas_pendientes:
                        self.api_client.post(f"/facturas/{factura['id']}/consultar-sri", {})
                    show_success_message("Consultas enviadas al SRI")
    
    def _enviar_facturas_email(self, facturas_ids):
        """Enviar facturas por email"""
        for factura_id in facturas_ids:
            resultado = self.api_client.post(f"/facturas/{factura_id}/enviar-email", {})
        show_success_message(f"Se enviaron {len(facturas_ids)} facturas por email")
    
    def _descargar_facturas_pdf(self, facturas_ids):
        """Descargar facturas en PDF"""
        for factura_id in facturas_ids:
            pdf_data = self.api_client.get(f"/facturas/{factura_id}/pdf")
            if pdf_data:
                st.download_button(
                    label=f"📄 Descargar PDF {factura_id}",
                    data=pdf_data['pdf_content'],
                    file_name=f"factura_{factura_id}.pdf",
                    mime="application/pdf"
                )
    
    def _consultar_estado_sri(self, facturas_ids):
        """Consultar estado en el SRI"""
        for factura_id in facturas_ids:
            self.api_client.post(f"/facturas/{factura_id}/consultar-sri", {})
        show_success_message(f"Se consultaron {len(facturas_ids)} facturas en el SRI")
    
    def _exportar_excel(self, facturas_ids):
        """Exportar facturas a Excel"""
        # Implementar exportación a Excel
        show_success_message("Funcionalidad de exportación en desarrollo")


class ClientesPage:
    """Página de gestión de clientes"""
    
    def __init__(self, api_client):
        self.api_client = api_client
    
    def render(self):
        """Renderizar página de clientes"""
        st.title("👥 Gestión de Clientes")
        st.markdown("---")
        
        tab1, tab2, tab3 = st.tabs(["📋 Lista de Clientes", "➕ Nuevo Cliente", "📊 Estadísticas"])
        
        with tab1:
            self._render_clientes_list()
        
        with tab2:
            self._render_nuevo_cliente()
        
        with tab3:
            self._render_estadisticas_clientes()
    
    def _render_clientes_list(self):
        """Renderizar lista de clientes"""
        st.subheader("📋 Lista de Clientes")
        
        # Filtros
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_term = create_search_filter("Buscar cliente...")
        
        with col2:
            tipo_filter = st.selectbox("Tipo ID", ["Todos", "04", "05", "06", "07", "08"])
        
        with col3:
            activo_filter = st.selectbox("Estado", ["Todos", "Activo", "Inactivo"])
        
        # Obtener clientes
        clientes = self.api_client.get("/clientes")
        
        if clientes:
            df = pd.DataFrame(clientes)
            
            # Aplicar filtros
            if search_term:
                mask = df['razon_social'].str.contains(search_term, case=False, na=False) | \
                       df['identificacion'].str.contains(search_term, case=False, na=False)
                df = df[mask]
            
            if tipo_filter != "Todos":
                df = df[df['tipo_identificacion'] == tipo_filter]
            
            if activo_filter != "Todos":
                activo_bool = activo_filter == "Activo"
                df = df[df['activo'] == activo_bool]
            
            # Formatear datos
            df['tipo_id_desc'] = df.apply(
                lambda row: f"{row['tipo_identificacion']} - {row['identificacion']}", 
                axis=1
            )
            
            # Mostrar tabla
            columns_display = {
                'razon_social': 'Razón Social',
                'tipo_id_desc': 'Identificación',
                'email': 'Email',
                'telefono': 'Teléfono',
                'activo': 'Activo'
            }
            
            display_df = df.rename(columns=columns_display)[list(columns_display.values())]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Estadísticas rápidas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Clientes", len(df))
            with col2:
                activos = len(df[df['activo'] == True])
                st.metric("Clientes Activos", activos)
            with col3:
                inactivos = len(df[df['activo'] == False])
                st.metric("Clientes Inactivos", inactivos)
        
        else:
            st.info("No hay clientes registrados")
    
    def _render_nuevo_cliente(self):
        """Renderizar formulario de nuevo cliente"""
        st.subheader("➕ Nuevo Cliente")
        
        with st.form("nuevo_cliente_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                tipo_id = st.selectbox(
                    "Tipo de Identificación",
                    options=["05", "04", "06", "07", "08"],
                    format_func=lambda x: {
                        "04": "04 - RUC",
                        "05": "05 - Cédula",
                        "06": "06 - Pasaporte",
                        "07": "07 - Consumidor Final",
                        "08": "08 - Identificación Exterior"
                    }[x]
                )
                
                identificacion = st.text_input("Número de Identificación")
                razon_social = st.text_input("Razón Social / Nombres")
                direccion = st.text_area("Dirección")
            
            with col2:
                telefono = st.text_input("Teléfono")
                email = st.text_input("Email")
                
                # Validaciones en tiempo real
                if identificacion:
                    if tipo_id == "05" and not validate_cedula(identificacion):
                        st.error("❌ Cédula inválida")
                    elif tipo_id == "04" and not validate_ruc(identificacion):
                        st.error("❌ RUC inválido")
                
                if email and not DataValidator.validate_email(email):
                    st.error("❌ Email inválido")
            
            # Botón guardar
            guardar_cliente = st.form_submit_button("💾 Guardar Cliente", type="primary")
            
            if guardar_cliente:
                if self._validar_cliente_data(tipo_id, identificacion, razon_social, email):
                    self._crear_cliente(tipo_id, identificacion, razon_social, direccion, telefono, email)
    
    def _validar_cliente_data(self, tipo_id, identificacion, razon_social, email):
        """Validar datos del cliente"""
        if not identificacion or not razon_social:
            show_error_message("Identificación y Razón Social son obligatorios")
            return False
        
        if tipo_id == "05" and not validate_cedula(identificacion):
            show_error_message("Cédula inválida")
            return False
        
        if tipo_id == "04" and not validate_ruc(identificacion):
            show_error_message("RUC inválido")
            return False
        
        if email and not DataValidator.validate_email(email):
            show_error_message("Email inválido")
            return False
        
        return True
    
    def _crear_cliente(self, tipo_id, identificacion, razon_social, direccion, telefono, email):
        """Crear nuevo cliente"""
        try:
            cliente_data = {
                "tipo_identificacion": tipo_id,
                "identificacion": identificacion,
                "razon_social": razon_social,
                "direccion": direccion,
                "telefono": telefono,
                "email": email
            }
            
            resultado = self.api_client.post("/clientes", cliente_data)
            
            if resultado:
                show_success_message(f"Cliente creado exitosamente: {razon_social}")
                st.rerun()
        
        except Exception as e:
            show_error_message(f"Error al crear cliente: {str(e)}")
    
    def _render_estadisticas_clientes(self):
        """Renderizar estadísticas de clientes"""
        st.subheader("📊 Estadísticas de Clientes")
        
        stats = self.api_client.get("/clientes/estadisticas")
        
        if stats:
            # Distribución por tipo de identificación
            if stats.get("tipos_identificacion"):
                create_pie_chart(
                    stats["tipos_identificacion"],
                    "cantidad",
                    "tipo",
                    "Distribución por Tipo de Identificación"
                )
            
            # Clientes más frecuentes
            if stats.get("clientes_frecuentes"):
                st.subheader("🏆 Clientes Más Frecuentes")
                df_frecuentes = pd.DataFrame(stats["clientes_frecuentes"])
                st.dataframe(df_frecuentes, use_container_width=True, hide_index=True)