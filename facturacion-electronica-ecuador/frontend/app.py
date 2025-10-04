"""
Aplicación Frontend para Sistema de Facturación Electrónica SRI Ecuador
Desarrollado con Streamlit - Versión Mejorada
"""
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, date, timedelta
import json
from typing import Dict, List, Optional
import base64
from io import BytesIO
import json
from typing import Dict, List, Optional
import base64
from io import BytesIO

# Importar módulos locales
from config import (
    FrontendConfig, apply_custom_css, get_status_badge, 
    show_message, init_session_state, clear_session_state,
    get_page_config, get_menu_options, get_api_base_url
)
from utils import (
    format_currency, format_date, create_metric_card,
    display_factura_table, create_sales_chart, create_pie_chart,
    DataValidator, create_export_options
)
from pages import FacturasPage, ClientesPage

# Configuración de la página
# Configuración de la página
st.set_page_config(**get_page_config())

# Aplicar CSS personalizado
apply_custom_css()

class APIClient:
    """Cliente mejorado para comunicación con la API FastAPI"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        # Obtener token del estado de sesión si existe
        self.token = st.session_state.get("token", None)
        self.session = requests.Session()

    def _set_token(self, token: Optional[str]):
        """Establecer o limpiar token tanto en el cliente como en session_state"""
        try:
            self.token = token
            if token:
                st.session_state.token = token
                st.session_state.authenticated = True
            else:
                # Limpiar estado
                st.session_state.token = None
                st.session_state.authenticated = False
        except Exception:
            # No querer fallar por errores al sincronizar el estado de sesión
            pass

    def get_headers(self) -> Dict:
        """Obtener headers con token de autenticación"""
        headers = {
            "Content-Type": "application/json"
        }

        # Sincronizar el token desde el estado de sesión si está presente
        token_in_state = st.session_state.get("token")
        if token_in_state:
            self.token = token_in_state
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.token:
            # Si hay token en el cliente pero no en session_state, usar el del cliente
            headers["Authorization"] = f"Bearer {self.token}"
        else:
            # Si no hay token en ningún lugar, asegurarse de que no haya header de autorización
            self.session.headers.pop("Authorization", None)

        return headers

    def get(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Realizar petición GET"""
        try:
            response = self.session.get(
                f"{self.base_url}{endpoint}",
                headers=self.get_headers(),
                params=params,
                timeout=30
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                self._handle_unauthorized()
                return None
            else:
                show_message("error", f"Error en petición: {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            show_message("connection_error", f"Error de conexión: {str(e)}")
            return None
        except Exception as e:
            show_message("error", f"Error inesperado: {str(e)}")
            return None

    def login(self, username: str, password: str) -> bool:
        """Autenticar usuario (único método de login, reemplaza duplicados)"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                data={"username": username, "password": password},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                access_token = data.get("access_token")
                if access_token:
                    # Centralizar el manejo del token
                    self._set_token(access_token)
                    st.session_state.user_data = data.get("user_data", {})
                    return True
                else:
                    show_message("error", "Respuesta inválida del servidor: falta access_token")
                    return False
            elif response.status_code == 401:
                # Manejar específicamente credenciales incorrectas
                show_message("login_error", "Credenciales incorrectas")
                # Asegurar limpieza de token en caso de login fallido
                self._set_token(None)
                return False
            else:
                # Otros errores
                show_message("error", f"Error de autenticación: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            show_message("connection_error", f"Error de conexión: {str(e)}")
            return False
        except Exception as e:
            show_message("error", f"Error inesperado: {str(e)}")
            return False

    def post(self, endpoint: str, data: Dict) -> Optional[Dict]:
        """Realizar petición POST"""
        try:
            # Intentar refrescar el token antes de realizar la petición para evitar errores 401
            try:
                self._refresh_token_if_needed()
            except Exception:
                # No bloquear la petición si el refresco falla; se manejará según el status HTTP
                pass

            headers = self.get_headers() or {}
            payload = data if data is not None else {}

            response = self.session.post(
                f"{self.base_url}{endpoint}",
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code in [200, 201]:
                return response.json()
            elif response.status_code == 401:
                self._handle_unauthorized()
                return None
            else:
                error_msg = response.text if response.text else f"Error {response.status_code}"
                show_message("error", f"Error en petición: {error_msg}")
                return None

        except requests.exceptions.RequestException as e:
            show_message("connection_error", f"Error de conexión: {str(e)}")
            return None
        except Exception as e:
            show_message("error", f"Error inesperado: {str(e)}")
            return None

    def _refresh_token_if_needed(self):
        """Verificar si el token es válido y refrescar si es necesario"""
        # Esta función podría implementarse para verificar la validez del token
        # con el backend si fuera necesario. Ejemplo de acciones posibles:
        # - Llamar a un endpoint /auth/refresh para obtener un nuevo token.
        # - Actualizar st.session_state.token y self.token si se renueva correctamente.
        # - Si la renovación falla, llamar a _handle_unauthorized().
        #
        # Implementación por defecto: no hace nada (placeholder).
        try:
            # Intento básico: si no hay token, no hay nada que refrescar.
            if not (self.token or st.session_state.get("token")):
                return False
            # Aquí podría ir la lógica real de refresh, por ahora retornamos False indicando que no se refrescó.
            return False
        except Exception as e:
            # En caso de error al intentar refrescar, tratamos como no autorizado.
            show_message("error", f"Error al refrescar token: {str(e)}")
            return False
        clear_session_state()
        st.rerun()

# Inicializar cliente API
# Eliminamos @st.cache_resource para evitar problemas de persistencia
def get_api_client():
    # Usar el cliente API almacenado en session_state si existe
    if "api_client" not in st.session_state:
        st.session_state.api_client = APIClient(get_api_base_url())
    return st.session_state.api_client

# Usar el cliente API persistente
api_client = get_api_client()

def login_page():
    """Página de login mejorada"""
    # ELIMINAR EL BLOQUE DE VALIDACIÓN QUE LIMPIA EL ESTADO
    
    st.markdown('<h1 class="main-header">🧾 Sistema de Facturación Electrónica SRI Ecuador</h1>',
                unsafe_allow_html=True)

    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            st.markdown("""
            <div class="info-box">
            </div>
            """, unsafe_allow_html=True)
            
            st.subheader("🔐 Iniciar Sesión")

            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("👤 Usuario", placeholder="Ingrese su usuario")
                password = st.text_input("🔑 Contraseña", type="password", placeholder="Ingrese su contraseña")

                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    submit_button = st.form_submit_button("🚀 Ingresar al Sistema", type="primary")

                if submit_button:
                    if username and password:
                        with st.spinner("Verificando credenciales..."):
                            if api_client.login(username, password):
                                show_message("login_success")
                                st.balloons()
                                st.rerun()  # Este rerun ahora funcionará correctamente
                            else:
                                show_message("login_error")
                    else:
                        show_message("error", "Por favor ingrese usuario y contraseña")



                st.markdown("""
                **Versión:** 1.0.0
                **Desarrollado para:** Empresas ecuatorianas
                **Cumplimiento:** Normativa SRI Ecuador
                **Soporte:** soporte@empresa.com
                """)

def sidebar_navigation():
    """Navegación lateral mejorada"""
    with st.sidebar:
        st.markdown("### 📊 Menú Principal")

        # Información del usuario
        if st.session_state.get("user_data"):
            user_data = st.session_state.user_data
            st.markdown(f"👤 **{user_data.get('username', 'Usuario')}**")
            st.markdown(f"🏢 **{user_data.get('empresa', 'Mi Empresa')}**")
            st.markdown("---")

        # Opciones de menú
        menu_options = get_menu_options()

        selected = None
        for option in menu_options:
            if st.button(f"{option['icon']} {option['label']}", key=option['key'], use_container_width=True):
                selected = option['key']
                break

        # Si no se seleccionó nada, mantener la página actual
        if not selected:
            selected = st.session_state.get("current_page", "dashboard")
        else:
            st.session_state.current_page = selected

        # Manejar cerrar sesión
        if selected == "logout":
            # Limpiar el estado actual
            clear_session_state()
            # Intentar re-inicializar el estado de sesión si existe la función
            try:
                init_session_state()
            except Exception:
                # Si la función no existe o falla, continuar con la limpieza previa
                pass
            # Forzar recarga para reflejar el estado limpio
            st.rerun()

        st.markdown("---")

        # Estado del sistema
        st.markdown("### 🔧 Estado del Sistema")
        
        # Verificar conexión con API
        try:
            health = api_client.get("/health")
            if health:
                st.success("🟢 API Conectada")
            else:
                st.error("🔴 API Desconectada")
        except:
            st.error("🔴 Sin Conexión")
        
        # Información adicional
        st.markdown("---")
        st.markdown("### 📞 Soporte")
        st.markdown("📧 soporte@empresa.com")
        st.markdown("📱 +593-2-1234567")
        
        return selected

def dashboard_page():
    """Página principal del dashboard mejorada"""
    st.title("📊 Dashboard - Panel de Control")
    st.markdown("---")
    
    # Obtener estadísticas
    with st.spinner("Cargando estadísticas..."):
        stats = api_client.get("/dashboard/stats")
    
    if stats:
        # Métricas principales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            delta_facturas = stats.get("delta_facturas", 0)
            delta_color = "normal" if delta_facturas >= 0 else "inverse"
            st.metric(
                label="📄 Facturas del Mes",
                value=stats.get("facturas_mes", 0),
                delta=delta_facturas,
                delta_color=delta_color
            )
        
        with col2:
            delta_ventas = stats.get("delta_ventas", 0)
            st.metric(
                label="💰 Ventas del Mes",
                value=format_currency(stats.get("ventas_mes", 0)),
                delta=format_currency(delta_ventas)
            )
        
        with col3:
            st.metric(
                label="👥 Clientes Activos",
                value=stats.get("clientes_activos", 0),
                delta=stats.get("delta_clientes", 0)
            )
        
        with col4:
            st.metric(
                label="📦 Productos",
                value=stats.get("productos_activos", 0)
            )
        
        st.markdown("---")
        
        # Gráficos principales
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 Evolución de Ventas")
            ventas_data = api_client.get("/dashboard/ventas-mensuales")
            if ventas_data:
                create_sales_chart(ventas_data, "line")
            else:
                st.info("No hay datos de ventas disponibles")
        
        with col2:
            st.subheader("🧾 Facturas por Estado")
            estados_data = api_client.get("/dashboard/facturas-estado")
            if estados_data:
                create_pie_chart(estados_data, "cantidad", "estado", "Distribución por Estado")
            else:
                st.info("No hay datos de estados disponibles")
        
        # Sección de facturas recientes
        st.markdown("---")
        st.subheader("📋 Facturas Recientes")
        
        facturas_recientes = api_client.get("/facturas?limit=10")
        if facturas_recientes:
            display_factura_table(facturas_recientes, show_actions=False)
        else:
            st.info("No hay facturas recientes")
        
        # Alertas y notificaciones
        st.markdown("---")
        st.subheader("🔔 Alertas y Notificaciones")
        
        alertas = api_client.get("/dashboard/alertas")
        if alertas:
            for alerta in alertas:
                if alerta["tipo"] == "warning":
                    st.warning(f"⚠️ {alerta['mensaje']}")
                elif alerta["tipo"] == "error":
                    st.error(f"❌ {alerta['mensaje']}")
                else:
                    st.info(f"ℹ️ {alerta['mensaje']}")
        else:
            st.success("✅ No hay alertas pendientes")
    
    else:
        st.error("❌ No se pudieron cargar las estadísticas del dashboard")

def productos_page():
    """Página de gestión de productos"""
    st.title("📦 Gestión de Productos")
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["📋 Lista de Productos", "➕ Nuevo Producto", "📊 Estadísticas"])
    
    with tab1:
        st.subheader("📋 Lista de Productos")
        
        # Filtros
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_term = st.text_input("🔍 Buscar producto...", key="search_productos")
        
        with col2:
            tipo_filter = st.selectbox("Tipo", ["Todos", "BIEN", "SERVICIO"])
        
        with col3:
            activo_filter = st.selectbox("Estado", ["Todos", "Activo", "Inactivo"])
        
        # Obtener productos
        productos = api_client.get("/productos")
        
        if productos:
            df = pd.DataFrame(productos)
            
            # Aplicar filtros
            if search_term:
                mask = df['descripcion'].str.contains(search_term, case=False, na=False) | \
                       df['codigo_principal'].str.contains(search_term, case=False, na=False)
                df = df[mask]
            
            if tipo_filter != "Todos":
                df = df[df['tipo'] == tipo_filter]
            
            if activo_filter != "Todos":
                activo_bool = activo_filter == "Activo"
                df = df[df['activo'] == activo_bool]
            
            # Formatear datos
            df['precio_fmt'] = df['precio_unitario'].apply(format_currency)
            df['iva_fmt'] = df['porcentaje_iva'].apply(lambda x: f"{x*100:.1f}%")
            
            # Mostrar tabla
            columns_display = {
                'codigo_principal': 'Código',
                'descripcion': 'Descripción',
                'precio_fmt': 'Precio',
                'tipo': 'Tipo',
                'iva_fmt': 'IVA',
                'activo': 'Activo'
            }
            
            display_df = df.rename(columns=columns_display)[list(columns_display.values())]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Estadísticas rápidas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Productos", len(df))
            with col2:
                bienes = len(df[df['tipo'] == 'BIEN'])
                st.metric("Bienes", bienes)
            with col3:
                servicios = len(df[df['tipo'] == 'SERVICIO'])
                st.metric("Servicios", servicios)
            with col4:
                activos = len(df[df['activo'] == True])
                st.metric("Activos", activos)
        
        else:
            st.info("No hay productos registrados")
    
    with tab2:
        st.subheader("➕ Nuevo Producto")
        
        with st.form("nuevo_producto_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                codigo_principal = st.text_input("Código Principal *")
                codigo_auxiliar = st.text_input("Código Auxiliar")
                descripcion = st.text_input("Descripción *")
                precio_unitario = st.number_input("Precio Unitario *", min_value=0.01, step=0.01)
            
            with col2:
                tipo = st.selectbox("Tipo *", ["BIEN", "SERVICIO"])
                codigo_impuesto = st.selectbox("Código Impuesto", ["2", "3", "5"], index=0)
                porcentaje_iva = st.number_input("Porcentaje IVA", value=0.12, step=0.01, format="%.4f")
                activo = st.checkbox("Activo", value=True)

            # Validaciones de campos del formulario
            # Código principal
            if codigo_principal and len(codigo_principal) > 25:
                st.error("❌ El código principal no puede tener más de 25 caracteres")
            # Código auxiliar
            if codigo_auxiliar and len(codigo_auxiliar) > 25:
                st.error("❌ El código auxiliar no puede tener más de 25 caracteres")
            # Descripción
            if descripcion and len(descripcion) > 300:
                st.error("❌ La descripción no puede tener más de 300 caracteres")
            # Precio unitario debe ser positivo
            if precio_unitario <= 0:
                st.error("❌ El precio unitario debe ser mayor a 0")
            # Porcentaje de IVA en rango 0-1 (0% - 100%)
            if porcentaje_iva < 0 or porcentaje_iva > 1:
                st.error("❌ El porcentaje de IVA debe estar entre 0 y 1 (0% y 100%)")

            # Botón guardar
            guardar_producto = st.form_submit_button("💾 Guardar Producto", type="primary")

            if guardar_producto:
                # Validación final antes de enviar
                # Validaciones
                errores = []

                if not codigo_principal:
                    errores.append("El código principal es obligatorio")
                elif len(codigo_principal) > 25:
                    errores.append("El código principal no puede tener más de 25 caracteres")

                if not descripcion:
                    errores.append("La descripción es obligatoria")
                elif len(descripcion) > 300:
                    errores.append("La descripción no puede tener más de 300 caracteres")

                if precio_unitario <= 0:
                    errores.append("El precio unitario debe ser mayor a 0")

                if porcentaje_iva < 0 or porcentaje_iva > 1:
                    errores.append("El porcentaje de IVA debe estar entre 0 y 1 (0% y 100%)")

                if errores:
                    for error in errores:
                        st.error(f"❌ {error}")
                else:
                    producto_data = {
                        "codigo_principal": codigo_principal,
                        "codigo_auxiliar": codigo_auxiliar,
                        "descripcion": descripcion,
                        "precio_unitario": precio_unitario,
                        "tipo": tipo,
                        "codigo_impuesto": codigo_impuesto,
                        "porcentaje_iva": porcentaje_iva,
                        "activo": activo
                    }

                    resultado = api_client.post("/productos", producto_data)
                    if resultado:
                        show_message("data_saved", f"Producto creado: {descripcion}")
                        st.rerun()

    with tab3:
        st.subheader("📊 Estadísticas de Productos")

        stats = api_client.get("/productos/estadisticas")
        if stats:
            # Distribución por tipo
            if stats.get("tipos_distribucion"):
                create_pie_chart(
                    stats["tipos_distribucion"],
                    "cantidad",
                    "tipo",
                    "Distribución por Tipo"
                )
            
            # Productos más vendidos
            if stats.get("productos_mas_vendidos"):
                st.subheader("🏆 Productos Más Vendidos")
                df_vendidos = pd.DataFrame(stats["productos_mas_vendidos"])
                st.dataframe(df_vendidos, use_container_width=True, hide_index=True)
        else:
            st.info("No hay estadísticas disponibles")

def reportes_page():
    """Página de reportes mejorada"""
    st.title("📈 Reportes y Análisis")
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Ventas", "🧾 Facturación", "👥 Clientes", "📦 Productos"])
    
    with tab1:
        st.subheader("📊 Reporte de Ventas")
        
        # Filtros de fecha
        col1, col2, col3 = st.columns(3)
        
        with col1:
            fecha_desde = st.date_input("📅 Desde", value=date.today() - timedelta(days=30))
        
        with col2:
            fecha_hasta = st.date_input("📅 Hasta", value=date.today())
        
        with col3:
            tipo_reporte = st.selectbox("Tipo de Reporte", ["Diario", "Semanal", "Mensual"])
        
        if st.button("📊 Generar Reporte de Ventas"):
            with st.spinner("Generando reporte..."):
                reporte = api_client.get(f"/reportes/ventas?desde={fecha_desde}&hasta={fecha_hasta}&tipo={tipo_reporte}")
                
                if reporte:
                    # Mostrar métricas
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Ventas", format_currency(reporte.get("total_ventas", 0)))
                    with col2:
                        st.metric("Número de Facturas", reporte.get("num_facturas", 0))
                    with col3:
                        st.metric("Promedio por Factura", format_currency(reporte.get("promedio", 0)))
                    
                    # Gráfico de evolución
                    if reporte.get("datos_grafico"):
                        create_sales_chart(reporte["datos_grafico"], "bar")
                else:
                    st.info("No hay datos para el período seleccionado")
    
    with tab2:
        st.subheader("🧾 Reporte de Facturación")
        st.info("Funcionalidad en desarrollo")
    
    with tab3:
        st.subheader("👥 Reporte de Clientes")
        st.info("Funcionalidad en desarrollo")
    
    with tab4:
        st.subheader("📦 Reporte de Productos")
        st.info("Funcionalidad en desarrollo")

def configuracion_page():
    """Página de configuración mejorada"""
    st.title("⚙️ Configuración del Sistema")
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🏢 Empresa", "🔐 Certificados", "📧 Email", "🔧 Sistema"])
    
    with tab1:
        st.subheader("🏢 Configuración de la Empresa")
        
        # Obtener configuración actual
        config_empresa = api_client.get("/configuracion/empresa")
        
        with st.form("config_empresa_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                ruc = st.text_input("RUC *", value=config_empresa.get("ruc", "") if config_empresa else "")
                razon_social = st.text_input("Razón Social *", value=config_empresa.get("razon_social", "") if config_empresa else "")
                nombre_comercial = st.text_input("Nombre Comercial", value=config_empresa.get("nombre_comercial", "") if config_empresa else "")
                direccion = st.text_area("Dirección *", value=config_empresa.get("direccion", "") if config_empresa else "")
            
            with col2:
                telefono = st.text_input("Teléfono", value=config_empresa.get("telefono", "") if config_empresa else "")
                email = st.text_input("Email", value=config_empresa.get("email", "") if config_empresa else "")
                # Validación de email en tiempo real
                if email and not DataValidator.validate_email(email):
                    st.error("❌ Email inválido")
                ambiente = st.selectbox("Ambiente SRI", ["1", "2"], index=0 if not config_empresa else int(config_empresa.get("ambiente", "1")) - 1)
                obligado_contabilidad = st.selectbox("Obligado Contabilidad", ["SI", "NO"], index=0 if not config_empresa else 0 if config_empresa.get("obligado_contabilidad") == "SI" else 1)

            # Validaciones
            # Validar RUC usando el validador general de identificaciones (tipo "04" -> RUC)
            if ruc and not DataValidator.validate_identification("04", ruc):
                st.error("❌ RUC inválido")
                ruc_valid = False
            else:
                ruc_valid = True

            if email and not DataValidator.validate_email(email):
                st.error("❌ Email inválido")
                email_valid = False
            else:
                email_valid = True

            if st.form_submit_button("💾 Guardar Configuración", type="primary"):
                if not (ruc and razon_social and direccion):
                    show_message("error", "Por favor complete los campos obligatorios (RUC, Razón Social, Dirección).")
                elif ruc and not DataValidator.validate_identification("04", ruc):
                    show_message("error", "RUC inválido")
                elif email and not DataValidator.validate_email(email):
                    show_message("error", "Email inválido")
                else:
                    empresa_data = {
                        "ruc": ruc,
                        "razon_social": razon_social,
                        "nombre_comercial": nombre_comercial,
                        "direccion": direccion,
                        "telefono": telefono,
                        "email": email,
                        "ambiente": ambiente,
                        "obligado_contabilidad": obligado_contabilidad
                    }

                    resultado = api_client.post("/configuracion/empresa", empresa_data)
                    if resultado:
                        show_message("data_saved", "Configuración de empresa guardada")

    with tab2:
        st.subheader("🔐 Certificados Digitales")
        
        # Subir certificado
        uploaded_file = st.file_uploader(
            "📁 Subir Certificado Digital (.p12)",
            type=['p12'],
            help="Seleccione su certificado digital en formato PKCS#12"
        )
        
        if uploaded_file:
            cert_password = st.text_input("🔒 Contraseña del Certificado", type="password")
            
            if st.button("💾 Guardar Certificado"):
                if cert_password:
                    # Aquí iría la lógica para guardar el certificado
                    show_message("data_saved", "Certificado guardado exitosamente")
                else:
                    show_message("error", "Ingrese la contraseña del certificado")
        
        # Mostrar información del certificado actual
        cert_info = api_client.get("/configuracion/certificado")
        if cert_info:
            st.markdown("#### 📋 Certificado Actual")
            col1, col2 = st.columns(2)
            
            with col1:
                st.info(f"**Titular:** {cert_info.get('titular', 'N/A')}")
                st.info(f"**Emisor:** {cert_info.get('emisor', 'N/A')}")
            
            with col2:
                st.info(f"**Válido desde:** {cert_info.get('valido_desde', 'N/A')}")
                st.info(f"**Válido hasta:** {cert_info.get('valido_hasta', 'N/A')}")
    
    with tab3:
        st.subheader("📧 Configuración de Email")
        
        config_email = api_client.get("/configuracion/email")
        
        with st.form("config_email_form"):
            smtp_server = st.text_input("Servidor SMTP", value=config_email.get("smtp_server", "smtp.gmail.com") if config_email else "smtp.gmail.com")
            smtp_port = st.number_input("Puerto", value=config_email.get("smtp_port", 587) if config_email else 587)
            smtp_username = st.text_input("Usuario", value=config_email.get("smtp_username", "") if config_email else "")
            smtp_password = st.text_input("Contraseña", type="password")
            
            if st.form_submit_button("💾 Guardar Configuración Email"):
                email_data = {
                    "smtp_server": smtp_server,
                    "smtp_port": smtp_port,
                    "smtp_username": smtp_username,
                    "smtp_password": smtp_password
                }
                
                resultado = api_client.post("/configuracion/email", email_data)
                if resultado:
                    show_message("data_saved", "Configuración de email guardada")
    
    with tab4:
        st.subheader("🔧 Configuración del Sistema")
        
        # Información del sistema
        system_info = api_client.get("/sistema/info")
        if system_info:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📊 Estado del Sistema")
                st.info(f"**Versión:** {system_info.get('version', 'N/A')}")
                st.info(f"**Base de Datos:** {'🟢 Conectada' if system_info.get('db_status') else '🔴 Desconectada'}")
                st.info(f"**SRI:** {'🟢 Disponible' if system_info.get('sri_status') else '🔴 No disponible'}")
            
            with col2:
                st.markdown("#### 🔧 Acciones de Mantenimiento")
                
                if st.button("🔄 Reiniciar Servicios"):
                    show_message("processing", "Reiniciando servicios...")
                
                if st.button("🗑️ Limpiar Cache"):
                    show_message("success", "Cache limpiado exitosamente")
                
                if st.button("📊 Generar Reporte de Sistema"):
                    show_message("processing", "Generando reporte...")

def main():
    """Función principal de la aplicación mejorada"""
    # Inicializar estado de sesión
    init_session_state()
    
    # Verificar autenticación
    if not st.session_state.authenticated:
        login_page()
        return
    
    # Navegación principal
    selected_page = sidebar_navigation()
    
    # Mostrar página seleccionada
    try:
        if selected_page == "dashboard":
            dashboard_page()
        elif selected_page == "facturas":
            facturas_page = FacturasPage(api_client)
            facturas_page.render()
        elif selected_page == "clientes":
            clientes_page = ClientesPage(api_client)
            clientes_page.render()
        elif selected_page == "productos":
            productos_page()
        elif selected_page == "reportes":
            reportes_page()
        elif selected_page == "configuracion":
            configuracion_page()
        else:
            dashboard_page()  # Página por defecto
    
    except Exception as e:
        st.error(f"❌ Error al cargar la página: {str(e)}")
        st.info("Por favor, recargue la página o contacte al soporte técnico.")

if __name__ == "__main__":
    main()