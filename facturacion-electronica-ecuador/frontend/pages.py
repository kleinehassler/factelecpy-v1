"""
Páginas específicas para el sistema de facturación electrónica
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict

# Importar funciones de utilidades (importación relativa)
from utils import (
    format_currency,
    create_status_badge,
    create_search_filter,
    create_date_range_filter,
    create_status_filter,
    display_summary_stats,
    create_sales_chart,
    create_pie_chart,
    validate_ruc,
    validate_cedula,
    show_success_message,
    show_error_message,
    DataValidator
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
            search_term = create_search_filter("Buscar por número o cliente...", key="search_facturas_list")

        with col2:
            fecha_desde, fecha_hasta = create_date_range_filter(key_prefix="facturas_list")

        with col3:
            estado_filter = create_status_filter([
                "GENERADO", "FIRMADO", "AUTORIZADO", "RECHAZADO", "DEVUELTO"
            ], key="status_facturas_list")
        
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
        
        facturas = self.api_client.get("/facturas/", params)
        
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
                    col1, col2, col3, col4, col5, col6 = st.columns(6)

                    with col1:
                        if st.button("📧 Enviar Email", key="send_email"):
                            self._enviar_facturas_email(selected_facturas)

                    with col2:
                        if st.button("📄 Descargar PDF", key="download_pdf"):
                            self._descargar_facturas_pdf(selected_facturas)

                    with col3:
                        if st.button("🔄 Generar XML", key="generate_xml"):
                            for factura_id in selected_facturas:
                                self._generar_xml_factura(factura_id)

                    with col4:
                        if st.button("✍️ Firmar", key="sign"):
                            for factura_id in selected_facturas:
                                self._firmar_factura(factura_id)

                    with col5:
                        if st.button("🚀 Enviar SRI", key="send_sri"):
                            for factura_id in selected_facturas:
                                self._enviar_sri(factura_id)

                    with col6:
                        if st.button("🔍 Consultar SRI", key="check_sri"):
                            for factura_id in selected_facturas:
                                self._consultar_autorizacion(factura_id)

                        # Columnas a mostrar
                        columns_display = {
                            'numero_comprobante': 'Número',
                            'fecha_emision': 'Fecha',
                            'cliente_nombre': 'Cliente',
                            'valor_total_fmt': 'Total',
                            'estado_badge': 'Estado'
                        }

                        # Selección de facturas (permitir seleccionar por acciones individuales)
                        selected_facturas = st.multiselect(
                            "Seleccionar facturas para acciones:",
                            options=df['id'].tolist(),
                            format_func=lambda x: df[df['id']==x]['numero_comprobante'].iloc[0]
                        )

                        # Mostrar tabla de facturas
                        display_df = df.rename(columns=columns_display)[list(columns_display.values())]
                        st.dataframe(display_df, use_container_width=True, hide_index=True)

                        # Acciones individuales por factura
                        if selected_facturas:
                            st.markdown("### 🔧 Acciones Individuales")
                            for factura_id in selected_facturas:
                                factura = df[df['id'] == factura_id].iloc[0]
                                with st.expander(f"Factura {factura['numero_comprobante']} - {factura['cliente_nombre']}"):
                                    col1, col2, col3, col4, col5 = st.columns(5)

                                    with col1:
                                        if st.button("📧 Email", key=f"email_{factura_id}"):
                                            self._enviar_facturas_email([factura_id])

                                    with col2:
                                        if st.button("📄 PDF", key=f"pdf_{factura_id}"):
                                            self._descargar_facturas_pdf([factura_id])

                                    with col3:
                                        if st.button("📜 XML", key=f"xml_{factura_id}"):
                                            self._generar_xml_factura(factura_id)

                                    with col4:
                                        if factura.get('estado_sri') == 'GENERADO' and st.button("✍️ Firmar", key=f"sign_{factura_id}"):
                                            self._firmar_factura(factura_id)

                                    with col5:
                                        if factura.get('estado_sri') == 'FIRMADO' and st.button("🚀 Enviar SRI", key=f"sri_{factura_id}"):
                                            self._enviar_sri(factura_id)

                                    # Consultar autorización (si aplica)
                                    if factura.get('estado_sri') in ['ENVIADO_SRI', 'FIRMADO'] and st.button("🔍 Consultar Autorización", key=f"auth_{factura_id}"):
                                        self._consultar_autorizacion(factura_id)
        else:
            st.info("No se encontraron facturas con los filtros aplicados")

    def _render_nueva_factura(self):
        """Renderizar formulario de nueva factura"""
        st.subheader("➕ Nueva Factura Electrónica")

        # Inicializar estado de sesión para detalles
        if 'factura_detalles' not in st.session_state:
            st.session_state.factura_detalles = []
        if 'editing_item_index' not in st.session_state:
            st.session_state.editing_item_index = None

        # Mostrar fecha de emisión prominentemente
        col_fecha1, col_fecha2, col_fecha3 = st.columns([1, 2, 1])
        with col_fecha2:
            st.markdown("### 📅 Fecha de Emisión")
            fecha_emision = st.date_input(
                "Fecha",
                value=datetime.now().date(),
                key="fecha_emision_factura"
            )
            hora_emision = st.time_input(
                "Hora",
                value=datetime.now().time(),
                key="hora_emision_factura"
            )
            st.info(f"📆 Se emitirá el: {fecha_emision.strftime('%d/%m/%Y')} a las {hora_emision.strftime('%H:%M')}")

        st.markdown("---")

        # Sección 1: Datos del cliente
        st.markdown("#### 👤 Datos del Cliente")

        col1, col2 = st.columns(2)

        with col1:
            # Selección de cliente existente o nuevo
            cliente_option = st.radio(
                "Tipo de cliente:",
                ["Seleccionar existente", "Crear nuevo"],
                key="cliente_option_radio"
            )

            if cliente_option == "Seleccionar existente":
                clientes = self.api_client.get("/clientes/")
                if clientes:
                    cliente_options = {
                        f"{c['razon_social']} - {c['identificacion']}": c['id']
                        for c in clientes
                    }
                    cliente_seleccionado = st.selectbox(
                        "Cliente",
                        options=list(cliente_options.keys()),
                        key="cliente_seleccionado_select"
                    )
                    cliente_id = cliente_options.get(cliente_seleccionado)
                else:
                    st.warning("No hay clientes registrados")
                    cliente_id = None
            else:
                cliente_id = None

        with col2:
            if cliente_option == "Crear nuevo":
                tipo_id = st.selectbox("Tipo ID", ["05", "04", "06", "07", "08"], key="tipo_id_nuevo_cliente")
                identificacion = st.text_input("Identificación", key="identificacion_nuevo_cliente")
                razon_social = st.text_input("Razón Social", key="razon_social_nuevo_cliente")
                email = st.text_input("Email", key="email_nuevo_cliente")

                # Validaciones en tiempo real
                if identificacion:
                    if tipo_id == "05" and not DataValidator.validate_identification("05", identificacion):
                        st.error("❌ Cédula inválida")
                    elif tipo_id == "04" and not DataValidator.validate_identification("04", identificacion):
                        st.error("❌ RUC inválido")

                if email and not DataValidator.validate_email(email):
                    st.error("❌ Email inválido")

        st.markdown("---")

        # Sección 2: Agregar productos
        st.markdown("#### 🛒 Agregar Productos")

        col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])

        with col1:
            productos = self.api_client.get("/productos/")
            if productos:
                producto_options = {
                    f"{p['descripcion']} - {format_currency(p['precio_unitario'])}": p
                    for p in productos
                }
                producto_sel = st.selectbox(
                    "Producto",
                    options=list(producto_options.keys()),
                    key="producto_select_nuevo"
                )
            else:
                st.warning("No hay productos registrados")
                producto_sel = None

        with col2:
            cantidad = st.number_input("Cantidad", min_value=0.01, value=1.0, step=0.01, key="cantidad_input")

        with col3:
            precio_unit = st.number_input("Precio Unit.", min_value=0.01, value=1.0, step=0.01, key="precio_unit_input")

        with col4:
            descuento = st.number_input("Desc. %", min_value=0.0, max_value=100.0, value=0.0, key="descuento_input")

        with col5:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ Agregar", key="agregar_producto_btn", use_container_width=True):
                if producto_sel:
                    producto = producto_options[producto_sel]
                    # Convertir descuento de porcentaje a valor en dólares
                    subtotal_item = cantidad * precio_unit
                    descuento_dolares = (descuento / 100.0) * subtotal_item if descuento > 0 else 0.0

                    detalle = {
                        "codigo_principal": producto['codigo_principal'],
                        "codigo_auxiliar": producto.get('codigo_auxiliar'),
                        "descripcion": producto['descripcion'],
                        "cantidad": cantidad,
                        "precio_unitario": precio_unit,
                        "descuento": descuento_dolares,
                        "descuento_porcentaje": descuento  # Guardar también el porcentaje para mostrar
                    }
                    st.session_state.factura_detalles.append(detalle)
                    st.rerun()

        st.markdown("---")

        # Sección 3: Mostrar items agregados
        if st.session_state.factura_detalles:
            st.markdown("#### 📦 Items Agregados")

            # Crear tabla con los items
            for idx, detalle in enumerate(st.session_state.factura_detalles):
                with st.container():
                    col1, col2, col3, col4, col5, col6, col7 = st.columns([3, 1, 1.2, 1, 1.2, 0.8, 0.8])

                    with col1:
                        st.text(detalle['descripcion'])

                    with col2:
                        st.text(f"Cant: {detalle['cantidad']}")

                    with col3:
                        st.text(f"P.Unit: {format_currency(detalle['precio_unitario'])}")

                    with col4:
                        descuento_pct = detalle.get('descuento_porcentaje', 0)
                        st.text(f"Desc: {descuento_pct:.1f}%")

                    with col5:
                        subtotal = (detalle['cantidad'] * detalle['precio_unitario']) - detalle['descuento']
                        st.text(f"Total: {format_currency(subtotal)}")

                    with col6:
                        if st.button("✏️", key=f"edit_{idx}", help="Editar item"):
                            st.session_state.editing_item_index = idx
                            st.rerun()

                    with col7:
                        if st.button("🗑️", key=f"delete_{idx}", help="Eliminar item"):
                            st.session_state.factura_detalles.pop(idx)
                            st.rerun()

                    st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)

            # Mostrar totales
            st.markdown("---")
            col1, col2, col3 = st.columns([2, 1, 1])

            with col2:
                st.markdown("**Subtotal sin impuestos:**")
            with col3:
                subtotal_total = sum(
                    (d['cantidad'] * d['precio_unitario']) - d['descuento']
                    for d in st.session_state.factura_detalles
                )
                st.markdown(f"**{format_currency(subtotal_total)}**")
        else:
            st.info("ℹ️ No hay items agregados. Agregue productos para crear la factura.")

        # Modal de edición (si hay un item siendo editado)
        if st.session_state.editing_item_index is not None:
            idx = st.session_state.editing_item_index
            if idx < len(st.session_state.factura_detalles):
                detalle_edit = st.session_state.factura_detalles[idx]

                st.markdown("---")
                st.markdown(f"### ✏️ Editando: {detalle_edit['descripcion']}")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    nueva_cantidad = st.number_input(
                        "Cantidad",
                        min_value=0.01,
                        value=float(detalle_edit['cantidad']),
                        step=0.01,
                        key=f"edit_cantidad_{idx}"
                    )

                with col2:
                    nuevo_precio = st.number_input(
                        "Precio Unitario",
                        min_value=0.01,
                        value=float(detalle_edit['precio_unitario']),
                        step=0.01,
                        key=f"edit_precio_{idx}"
                    )

                with col3:
                    nuevo_descuento_pct = st.number_input(
                        "Descuento %",
                        min_value=0.0,
                        max_value=100.0,
                        value=float(detalle_edit.get('descuento_porcentaje', 0)),
                        key=f"edit_descuento_{idx}"
                    )

                with col4:
                    st.markdown("<br>", unsafe_allow_html=True)
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("💾 Guardar", key=f"save_edit_{idx}", use_container_width=True):
                            # Actualizar el detalle
                            subtotal_item = nueva_cantidad * nuevo_precio
                            nuevo_descuento_dolares = (nuevo_descuento_pct / 100.0) * subtotal_item if nuevo_descuento_pct > 0 else 0.0

                            st.session_state.factura_detalles[idx]['cantidad'] = nueva_cantidad
                            st.session_state.factura_detalles[idx]['precio_unitario'] = nuevo_precio
                            st.session_state.factura_detalles[idx]['descuento'] = nuevo_descuento_dolares
                            st.session_state.factura_detalles[idx]['descuento_porcentaje'] = nuevo_descuento_pct
                            st.session_state.editing_item_index = None
                            st.rerun()

                    with col_b:
                        if st.button("❌ Cancelar", key=f"cancel_edit_{idx}", use_container_width=True):
                            st.session_state.editing_item_index = None
                            st.rerun()

        st.markdown("---")

        # Sección 4: Información adicional
        st.markdown("#### 📝 Información Adicional")
        observaciones = st.text_area("Observaciones", key="observaciones_textarea")

        # Botón crear factura
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("💾 Crear Factura", type="primary", use_container_width=True, key="crear_factura_btn"):
                if self._validar_factura(cliente_id, cliente_option):
                    # Combinar fecha y hora
                    fecha_hora_emision = datetime.combine(fecha_emision, hora_emision)
                    self._crear_factura(cliente_id, cliente_option, observaciones, fecha_hora_emision)
            
    def _validar_factura(self, cliente_id, cliente_option):
        """Validar datos de la factura"""
        if cliente_option == "Seleccionar existente" and not cliente_id:
            show_error_message("Debe seleccionar un cliente")
            return False

        if not st.session_state.factura_detalles:
            show_error_message("Debe agregar al menos un producto")
            return False

        # Validar cliente nuevo si es necesario
        if cliente_option == "Crear nuevo":
            # Tomar valores desde la sesión, usando strings vacíos por defecto
            tipo_id = st.session_state.get("tipo_id_nuevo_cliente", "")
            identificacion = st.session_state.get("identificacion_nuevo_cliente", "")
            razon_social = st.session_state.get("razon_social_nuevo_cliente", "")
            email = st.session_state.get("email_nuevo_cliente", "")

            if not identificacion or not razon_social:
                show_error_message("Debe completar los datos del cliente")
                return False

            # Guardar datos temporales del cliente en la sesión para que estén
            # disponibles más adelante al crear la factura
            st.session_state["cliente_nuevo_temp"] = {
                "tipo_identificacion": tipo_id,
                "identificacion": identificacion,
                "razon_social": razon_social,
                "email": email
            }

            # Validar identificación según tipo
            if not DataValidator.validate_identification(tipo_id, identificacion):
                if tipo_id == "05":
                    show_error_message("Cédula inválida")
                elif tipo_id == "04":
                    show_error_message("RUC inválido")
                else:
                    show_error_message("Identificación inválida")
                return False

            # Validar email si se proporciona
            if email and not DataValidator.validate_email(email):
                show_error_message("Email inválido")
                return False

        # Validar detalles de productos
        for detalle in st.session_state.factura_detalles:
            if detalle.get("cantidad", 0) <= 0:
                show_error_message("La cantidad de todos los productos debe ser mayor a 0")
                return False

            if detalle.get("precio_unitario", 0) <= 0:
                show_error_message("El precio unitario de todos los productos debe ser mayor a 0")
                return False

            # Validar descuento en dólares (no puede ser negativo ni mayor que el subtotal)
            descuento_dolares = detalle.get("descuento", 0)
            subtotal_item = detalle.get("cantidad", 0) * detalle.get("precio_unitario", 0)
            if descuento_dolares < 0 or descuento_dolares > subtotal_item:
                show_error_message("El descuento no puede ser negativo ni mayor al subtotal del item")
                return False
        return True

    def _crear_factura(self, cliente_id, cliente_option, observaciones, fecha_hora_emision=None):
        """Crear nueva factura"""
        try:
            # Usar fecha y hora proporcionada o la actual
            if fecha_hora_emision is None:
                fecha_hora_emision = datetime.now()

            factura_data = {
                "cliente_id": cliente_id,
                "fecha_emision": fecha_hora_emision.isoformat(),
                "detalles": st.session_state.factura_detalles,
                "observaciones": observaciones
            }

            # Si es cliente nuevo, agregarlo a los datos
            if cliente_option == "Crear nuevo":
                cliente_nuevo_data = {
                    "tipo_identificacion": st.session_state.get("tipo_id_nuevo_cliente", "05"),
                    "identificacion": st.session_state.get("identificacion_nuevo_cliente", ""),
                    "razon_social": st.session_state.get("razon_social_nuevo_cliente", ""),
                }
                # Agregar campos opcionales solo si tienen valor
                email_nuevo = st.session_state.get("email_nuevo_cliente")
                if email_nuevo:
                    cliente_nuevo_data["email"] = email_nuevo

                factura_data["cliente_nuevo"] = cliente_nuevo_data

            resultado = self.api_client.post("/facturas/", factura_data)

            if resultado:
                show_success_message(f"Factura creada: {resultado['numero_comprobante']}")
                st.session_state.factura_detalles = []
                st.session_state.editing_item_index = None
                st.rerun()

        except Exception as e:
            show_error_message(f"Error al crear factura: {str(e)}")

    def _generar_xml_factura(self, factura_id):
        """Generar XML de factura"""
        try:
            resultado = self.api_client.post(f"/facturas/{factura_id}/generar-xml", {})
            if resultado:
                show_success_message("XML generado exitosamente")
                return True
            return False
        except Exception as e:
            show_error_message(f"Error generando XML: {str(e)}")
            return False

    def _firmar_factura(self, factura_id):
        """Firmar factura con certificado digital"""
        try:
            resultado = self.api_client.post(f"/facturas/{factura_id}/firmar", {})
            if resultado:
                show_success_message("Factura firmada exitosamente")
                return True
            return False
        except Exception as e:
            show_error_message(f"Error firmando factura: {str(e)}")
            return False

    def _enviar_sri(self, factura_id):
        """Enviar factura al SRI"""
        try:
            resultado = self.api_client.post(f"/facturas/{factura_id}/enviar-sri", {})
            if resultado:
                show_success_message("Factura enviada al SRI exitosamente")
                return True
            return False
        except Exception as e:
            show_error_message(f"Error enviando factura al SRI: {str(e)}")
            return False

    def _consultar_autorizacion(self, factura_id):
        """Consultar autorización en el SRI"""
        try:
            resultado = self.api_client.post(f"/facturas/{factura_id}/consultar-autorizacion", {})
            if resultado:
                show_success_message(f"Estado: {resultado.get('estado', 'Desconocido')}")
                return True
            return False
        except Exception as e:
            show_error_message(f"Error consultando autorización: {str(e)}")
            return False

    def _render_consultas_sri(self):
        """Renderizar consultas al SRI"""
        st.subheader("🔍 Consultas al SRI")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Consulta por Clave de Acceso")
            clave_acceso = st.text_input("Clave de Acceso (49 dígitos)")

            if st.button("🔍 Consultar Estado"):
                if len(clave_acceso) == 49:
                    try:
                        resultado = self.api_client.get(f"/sri/consultar/{clave_acceso}")
                        if resultado:
                            st.json(resultado)
                        else:
                            show_error_message("No se obtuvo respuesta del SRI para la clave proporcionada")
                    except Exception as e:
                        show_error_message(f"Error consultando al SRI: {str(e)}")
                else:
                    show_error_message("La clave de acceso debe tener 49 dígitos")

        with col2:
            st.markdown("#### Consulta Masiva")
            try:
                facturas_pendientes = self.api_client.get("/facturas/?estado=FIRMADO")
            except Exception as e:
                facturas_pendientes = None
                show_error_message(f"Error obteniendo facturas pendientes: {str(e)}")

            if facturas_pendientes:
                st.info(f"Hay {len(facturas_pendientes)} facturas pendientes de autorización")

                if st.button("🔄 Consultar Todas"):
                    errores = []
                    éxitos = 0
                    for factura in facturas_pendientes:
                        try:
                            resp = self.api_client.post(f"/facturas/{factura['id']}/consultar-sri", {})
                            if resp:
                                éxitos += 1
                        except Exception as e:
                            errores.append(f"ID {factura.get('id')}: {str(e)}")
                    if éxitos:
                        show_success_message(f"Se enviaron {éxitos} consultas al SRI")
                    if errores:
                        show_error_message(f"Errores en algunas consultas: {'; '.join(errores)}")
            if not DataValidator.validate_identification(tipo_id, identificacion):
                if tipo_id == "05":
                    show_error_message("Cédula inválida")
                elif tipo_id == "04":
                    show_error_message("RUC inválido")
                else:
                    show_error_message("Identificación inválida")
                return False

            # Validar email si se proporciona
            if email and not DataValidator.validate_email(email):
                show_error_message("Email inválido")
                return False

        # Validar detalles de productos
        for detalle in st.session_state.factura_detalles:
            if detalle.get("cantidad", 0) <= 0:
                show_error_message("La cantidad de todos los productos debe ser mayor a 0")
                return False

            if detalle.get("precio_unitario", 0) <= 0:
                show_error_message("El precio unitario de todos los productos debe ser mayor a 0")
                return False

            # Validar descuento en dólares (no puede ser negativo ni mayor que el subtotal)
            descuento_dolares = detalle.get("descuento", 0)
            subtotal_item = detalle.get("cantidad", 0) * detalle.get("precio_unitario", 0)
            if descuento_dolares < 0 or descuento_dolares > subtotal_item:
                show_error_message("El descuento no puede ser negativo ni mayor al subtotal del item")
                return False
        return True
    
    def _crear_factura(self, cliente_id, cliente_option, observaciones, fecha_hora_emision=None):
        """Crear nueva factura"""
        try:
            # Usar fecha y hora proporcionada o la actual
            if fecha_hora_emision is None:
                fecha_hora_emision = datetime.now()

            factura_data = {
                "cliente_id": cliente_id,
                "fecha_emision": fecha_hora_emision.isoformat(),
                "detalles": st.session_state.factura_detalles,
                "observaciones": observaciones
            }

            # Si es cliente nuevo, agregarlo a los datos
            if cliente_option == "Crear nuevo":
                cliente_nuevo_data = {
                    "tipo_identificacion": st.session_state.get("tipo_id_nuevo_cliente", "05"),
                    "identificacion": st.session_state.get("identificacion_nuevo_cliente", ""),
                    "razon_social": st.session_state.get("razon_social_nuevo_cliente", ""),
                }
                # Agregar campos opcionales solo si tienen valor
                email_nuevo = st.session_state.get("email_nuevo_cliente")
                if email_nuevo:
                    cliente_nuevo_data["email"] = email_nuevo

                factura_data["cliente_nuevo"] = cliente_nuevo_data

            resultado = self.api_client.post("/facturas/", factura_data)

            if resultado:
                show_success_message(f"Factura creada: {resultado['numero_comprobante']}")
                st.session_state.factura_detalles = []
                st.session_state.editing_item_index = None
                st.rerun()

        except Exception as e:
            show_error_message(f"Error al crear factura: {str(e)}")
    
    def _render_estadisticas(self):
        """Renderizar estadísticas de facturación"""
        st.subheader("📊 Estadísticas de Facturación")
        
        # Filtros de fecha
        fecha_desde, fecha_hasta = create_date_range_filter(key_prefix="facturas_estadisticas")
        
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
            facturas_pendientes = self.api_client.get("/facturas/?estado=FIRMADO")
            
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
            search_term = create_search_filter("Buscar cliente...", key="search_clientes_list")

        with col2:
            tipo_filter = st.selectbox("Tipo ID", ["Todos", "04", "05", "06", "07", "08"], key="tipo_clientes_list")

        with col3:
            activo_filter = st.selectbox("Estado", ["Todos", "Activo", "Inactivo"], key="estado_clientes_list")
        
        # Obtener clientes
        clientes = self.api_client.get("/clientes/")
        
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

        # Verificar si el cliente ya existe
        clientes = self.api_client.get("/clientes/")
        if clientes:
            for cliente in clientes:
                if cliente.get('identificacion') == identificacion:
                    show_error_message(f"Ya existe un cliente con la identificación {identificacion}")
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

            with st.spinner("Guardando cliente..."):
                resultado = self.api_client.post("/clientes/", cliente_data)

            if resultado:
                show_success_message(f"Cliente creado exitosamente: {razon_social}")
                st.rerun()
            else:
                show_error_message("No se pudo crear el cliente. Verifique que los datos sean correctos.")

        except Exception as e:
            error_msg = str(e)
            # Extraer el mensaje de error del JSON si existe
            if "Cliente con esta identificación ya existe" in error_msg:
                show_error_message(f"Ya existe un cliente con la identificación {identificacion}")
            else:
                show_error_message(f"Error al crear cliente: {error_msg}")
    
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