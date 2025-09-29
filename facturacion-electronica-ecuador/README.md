# Sistema de Facturación Electrónica SRI Ecuador

Sistema completo para emisión de documentos electrónicos según la normativa del Servicio de Rentas Internas (SRI) de Ecuador, versión 2.0.0 del esquema.

## Características

- ✅ Generación de Facturas Electrónicas según esquema SRI v2.0.0
- ✅ Generación de Proformas Electrónicas
- ✅ Firma digital XAdES-BES
- ✅ Generación de RIDE (Representación Impresa Digitalizada Electrónica) en PDF
- ✅ Envío automático por correo electrónico
- ✅ Integración con servicios web del SRI
- ✅ Base de datos MySQL completa
- ✅ API REST con FastAPI
- ✅ Frontend web con Streamlit
- ✅ Validación de XML contra esquema XSD

## Requisitos del Sistema

- Python 3.8+
- MySQL 5.7+ o MariaDB
- Certificado digital PKCS#12 (.p12) emitido por el SRI
- Acceso a internet para comunicación con servicios web del SRI

## Instalación

1. **Clonar el repositorio:**
```bash
git clone <repositorio>
cd facturacion-electronica-ecuador
```

2. **Crear entorno virtual:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows
```

3. **Instalar dependencias:**
```bash
pip install -r requirements.txt
```

4. **Configurar variables de entorno:**
```bash
cp .env.example .env
# Editar .env con tus configuraciones
```

5. **Configurar base de datos:**
```bash
# Ejecutar el script database/schema.sql en tu servidor MySQL
mysql -u usuario -p < database/schema.sql
```

## Configuración

### Variables de Entorno (.env)

```env
# Configuración de Base de Datos
DB_HOST=localhost
DB_PORT=3306
DB_NAME=facturacion_electronica
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña

# Configuración de la Aplicación
SECRET_KEY=tu_clave_secreta_muy_segura
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Configuración del SRI
SRI_AMBIENTE=1  # 1=Pruebas, 2=Producción
SRI_TIPO_EMISION=1  # 1=Normal, 2=Contingencia

# Configuración de Correo
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=tu_email@gmail.com
SMTP_PASSWORD=tu_app_password
SMTP_FROM_EMAIL=tu_email@gmail.com

# Configuración de Certificado Digital
CERT_PATH=certificados/certificado.p12
CERT_PASSWORD=contraseña_certificado

# Configuración de la Empresa
EMPRESA_RUC=1234567890001
EMPRESA_RAZON_SOCIAL=Mi Empresa S.A.
EMPRESA_NOMBRE_COMERCIAL=Mi Empresa
```

## Uso del Sistema

### 🚀 Inicio Rápido

#### Opción 1: Inicialización Automática
```bash
# Linux/Mac
bash init.sh

# Windows
init.bat
```

#### Opción 2: Inicio Manual

**1. Iniciar Backend (API):**
```bash
cd backend
python main.py
```
La API estará disponible en `http://localhost:8000`

**2. Iniciar Frontend (Interfaz Web):**
```bash
# Linux/Mac
bash run_frontend.sh

# Windows
run_frontend.bat
```
La interfaz web estará disponible en `http://localhost:8501`

#### Opción 3: Desarrollo (Backend + Frontend simultáneo)
```bash
npm run dev-full
```

### 🌐 Acceso a la Aplicación

- **Frontend Web**: http://localhost:8501
- **API REST**: http://localhost:8000
- **Documentación API**: http://localhost:8000/docs

### 🔐 Credenciales por Defecto

- **Usuario**: admin
- **Contraseña**: admin123

## 🖥️ Frontend Web (Streamlit)

El sistema incluye una interfaz web completa desarrollada en Python con Streamlit:

### Funcionalidades del Frontend

#### 🏠 Dashboard
- Métricas principales en tiempo real
- Gráficos de ventas y facturación
- Facturas recientes
- Alertas y notificaciones

#### 🧾 Gestión de Facturas
- Lista de facturas con filtros avanzados
- Creación de nuevas facturas
- Selección/creación de clientes
- Agregado de productos con cálculo automático
- Envío por email y descarga de PDF
- Consultas al SRI

#### 👥 Gestión de Clientes
- Lista de clientes con búsqueda
- Creación de nuevos clientes
- Validación de RUC y cédula ecuatoriana

#### 📦 Gestión de Productos
- Catálogo de productos y servicios
- Creación y edición de productos
- Estadísticas de productos

#### 📈 Reportes
- Reportes de ventas por período
- Gráficos interactivos
- Análisis de tendencias

#### ⚙️ Configuración
- Configuración de empresa
- Gestión de certificados digitales
- Configuración de email

### Características Técnicas del Frontend
- **Framework**: Streamlit 1.28.1
- **Gráficos**: Plotly interactivos
- **Validaciones**: Tiempo real
- **Responsive**: Adaptable a dispositivos
- **Temas**: Claro y oscuro

## 📡 API REST (FastAPI)

### Endpoints principales

#### Autenticación
- `POST /auth/login` - Iniciar sesión
- `POST /auth/logout` - Cerrar sesión

#### Clientes
- `GET /clientes/` - Listar clientes
- `POST /clientes/` - Crear nuevo cliente
- `GET /clientes/{id}` - Obtener cliente por ID

#### Productos
- `GET /productos/` - Listar productos
- `POST /productos/` - Crear nuevo producto
- `GET /productos/{id}` - Obtener producto por ID

#### Facturas
- `GET /facturas/` - Listar facturas
- `POST /facturas/` - Crear nueva factura
- `GET /facturas/{id}` - Obtener factura por ID
- `POST /facturas/{id}/generar-xml` - Generar XML
- `POST /facturas/{id}/firmar` - Firmar factura
- `POST /facturas/{id}/generar-ride` - Generar PDF RIDE
- `POST /facturas/{id}/enviar-email` - Enviar por correo

#### Dashboard
- `GET /dashboard/stats` - Estadísticas principales
- `GET /dashboard/ventas-mensuales` - Datos de ventas
- `GET /dashboard/facturas-estado` - Estados de facturas

## Estructura del Proyecto

```
facturacion-electronica-ecuador/
├── backend/
│   ├── main.py          # API REST con FastAPI
│   ├── models.py        # Modelos de base de datos
│   └── database.py      # Gestión de base de datos
├── frontend/
│   ├── app.py           # Aplicación Streamlit
│   ├── config.py        # Configuración del frontend
│   ├── utils.py         # Utilidades y componentes
│   ├── pages.py         # Páginas específicas
│   └── README.md        # Documentación del frontend
├── config/
│   └── settings.py      # Configuración de la aplicación
├── database/
│   └── schema.sql       # Esquema de base de datos
├── schemas/
│   └── factura_v2.0.0.xsd  # Esquema XSD del SRI
├── utils/
│   ├── xml_generator.py    # Generador de XML
│   ├── firma_digital.py    # Firma XAdES-BES
│   ├── ride_generator.py   # Generador de RIDE PDF
│   └── email_sender.py     # Envío de correos
├── .streamlit/
│   └── config.toml         # Configuración de Streamlit
├── requirements.txt        # Dependencias de Python
├── run_frontend.sh         # Script para ejecutar frontend (Linux/Mac)
├── run_frontend.bat        # Script para ejecutar frontend (Windows)
├── init.sh                 # Script de inicialización (Linux/Mac)
├── init.bat                # Script de inicialización (Windows)
└── .env.example           # Ejemplo de variables de entorno
```

## Flujo de Trabajo

### Usando la Interfaz Web (Recomendado)
1. **Acceder** a http://localhost:8501
2. **Iniciar sesión** con las credenciales
3. **Configurar empresa** en la sección de configuración
4. **Crear clientes y productos** según necesidad
5. **Generar facturas** desde la interfaz
6. **Enviar por email** o descargar PDF automáticamente

### Usando la API REST
1. **Crear cliente y productos** en el sistema
2. **Generar factura** con detalles
3. **Generar XML** del comprobante
4. **Firmar digitalmente** el XML
5. **Generar RIDE** en PDF
6. **Enviar al SRI** para autorización
7. **Enviar por email** al cliente

## Ejemplos de Uso

### Crear Factura via API

```python
import requests

# Crear cliente
cliente_data = {
    "tipo_identificacion": "05",
    "identificacion": "1234567890",
    "razon_social": "Juan Pérez",
    "email": "juan@email.com"
}
cliente = requests.post("http://localhost:8000/clientes/", json=cliente_data)

# Crear factura
factura_data = {
    "cliente_id": cliente.json()["id"],
    "detalles": [
        {
            "codigo_principal": "001",
            "descripcion": "Producto de prueba",
            "cantidad": 1,
            "precio_unitario": 10.00
        }
    ]
}
factura = requests.post("http://localhost:8000/facturas/", json=factura_data)
```

### Usar Frontend Web

1. Abrir navegador en http://localhost:8501
2. Iniciar sesión
3. Ir a "Facturas" → "Nueva Factura"
4. Seleccionar cliente o crear nuevo
5. Agregar productos
6. Guardar factura
7. La factura se genera, firma y envía automáticamente

## 🔧 Scripts Disponibles

```bash
# Inicialización
npm run init          # Inicializar proyecto (Linux/Mac)
npm run init-win      # Inicializar proyecto (Windows)

# Ejecución
npm run start         # Iniciar solo backend
npm run frontend      # Iniciar solo frontend
npm run dev           # Iniciar backend en modo desarrollo
npm run dev-full      # Iniciar backend + frontend

# Base de datos
npm run db-init       # Inicializar base de datos

# Desarrollo
npm run test          # Ejecutar pruebas
npm run lint          # Verificar código
npm run format        # Formatear código
```

## Tecnologías Utilizadas

### Backend
- **FastAPI 0.104.1** - Framework web moderno
- **SQLAlchemy 2.0.23** - ORM para base de datos
- **PyMySQL 1.1.0** - Conector MySQL
- **Cryptography 3.4.8** - Operaciones criptográficas
- **lxml 4.9.3** - Procesamiento XML
- **ReportLab 4.0.7** - Generación de PDF
- **SignXML 3.2.0** - Firma digital XAdES

### Frontend
- **Streamlit 1.28.1** - Framework web para Python
- **Plotly 5.17.0** - Gráficos interactivos
- **Pandas 2.1.4** - Manipulación de datos
- **Requests 2.31.0** - Cliente HTTP

### Base de Datos
- **MySQL 5.7+** o **MariaDB**
- Esquema optimizado para facturación electrónica
- Índices para consultas rápidas
- Integridad referencial

## Seguridad

- ✅ Autenticación JWT
- ✅ Validación de datos de entrada
- ✅ Firma digital XAdES-BES
- ✅ Certificados digitales PKCS#12
- ✅ Conexiones HTTPS
- ✅ Validación de esquemas XML

## Cumplimiento Normativo

- ✅ Esquema SRI v2.0.0
- ✅ Clave de acceso de 49 dígitos
- ✅ Numeración secuencial
- ✅ Campos obligatorios según SRI
- ✅ Validaciones de RUC y cédula
- ✅ Formato de fechas ecuatoriano

## Soporte y Documentación

- **Documentación API**: http://localhost:8000/docs
- **Frontend**: Interfaz intuitiva con ayuda contextual
- **Logs**: Sistema completo de logging
- **Validaciones**: Mensajes de error descriptivos

## Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.

## Contacto

- **Email**: soporte@empresa.com
- **Teléfono**: +593-2-1234567
- **Sitio Web**: https://empresa.com

## Agradecimientos

- Servicio de Rentas Internas (SRI) del Ecuador
- Comunidad Python Ecuador
- Contribuidores del proyecto