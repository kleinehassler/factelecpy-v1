# 🧾 Sistema de Facturación Electrónica para Ecuador - Documentación Completa

## 📋 Índice
1. [Descripción General](#descripción-general)
2. [Características Principales](#características-principales)
3. [Arquitectura del Sistema](#arquitectura-del-sistema)
4. [Requisitos del Sistema](#requisitos-del-sistema)
5. [Instalación y Configuración](#instalación-y-configuración)
6. [Estructura del Proyecto](#estructura-del-proyecto)
7. [Componentes Principales](#componentes-principales)
8. [Base de Datos](#base-de-datos)
9. [API REST](#api-rest)
10. [Frontend Web](#frontend-web)
11. [Generación de Documentos](#generación-de-documentos)
12. [Firma Digital](#firma-digital)
13. [Integración con SRI](#integración-con-sri)
14. [Envío de Correos](#envío-de-correos)
15. [Seguridad](#seguridad)
16. [Pruebas y Validación](#pruebas-y-validación)
17. [Mantenimiento](#mantenimiento)
18. [Solución de Problemas](#solución-de-problemas)
19. [Licencia](#licencia)

---

## 📖 Descripción General

El Sistema de Facturación Electrónica para Ecuador es una solución completa desarrollada para cumplir con las normativas del Servicio de Rentas Internas (SRI) versión 2.0.0. El sistema permite la generación, firma digital, envío y autorización de facturas electrónicas conforme a la legislación ecuatoriana.

Este sistema está compuesto por:
- **Backend API REST** desarrollado en Python con FastAPI
- **Frontend Web** desarrollado con Streamlit
- **Base de datos MySQL** optimizada
- **Generación de documentos XML** compatibles con el SRI
- **Firma digital XAdES-BES**
- **Generación de RIDE (PDF)**
- **Integración con servicios web del SRI**
- **Sistema de notificaciones por correo electrónico**

---

## ⭐ Características Principales

### Funcionalidades Técnicas
- ✅ Cumple con normativa SRI v2.0.0
- ✅ Firma digital XAdES-BES
- ✅ Generación automática de XML y RIDE (PDF)
- ✅ Integración con servicios web SRI
- ✅ Envío automático por email
- ✅ Base de datos MySQL optimizada
- ✅ Seguridad JWT
- ✅ Validaciones ecuatorianas (RUC, cédula, etc.)

### Funcionalidades de Negocio
- 🧾 **Gestión de Facturas**: Creación, consulta, modificación
- 👥 **Gestión de Clientes**: CRUD completo con validaciones
- 📦 **Catálogo de Productos**: Administración de productos/servicios
- 📊 **Dashboard**: Métricas y estadísticas en tiempo real
- 📈 **Reportes**: Gráficos interactivos con Plotly
- ⚙️ **Configuración**: Sistema completo de configuración
- 🔐 **Autenticación**: Sistema seguro con usuarios y roles
- 📧 **Notificaciones**: Envío automático de documentos

---

## 🏗️ Arquitectura del Sistema

```
Sistema de Facturación Electrónica
├── Backend (FastAPI)
│   ├── API REST
│   ├── ORM (SQLAlchemy)
│   ├── Generación XML
│   ├── Firma Digital
│   ├── Generación PDF (RIDE)
│   └── Integración SRI
├── Frontend (Streamlit)
│   ├── Interfaz Web
│   ├── Dashboard
│   ├── Gestión de Datos
│   └── Reportes
├── Base de Datos (MySQL)
│   ├── Esquema Normalizado
│   ├── Relaciones Optimizadas
│   └── Índices de Rendimiento
└── Utilidades
    ├── Firma Digital (XAdES-BES)
    ├── Generación de Documentos
    ├── Envío de Correos
    └── Validaciones
```

### Tecnologías Utilizadas
- **Backend**: Python 3.10+, FastAPI, SQLAlchemy
- **Frontend**: Streamlit, Plotly, Pandas
- **Base de Datos**: MySQL 8.0+
- **Documentos**: XML (SRI v2.0.0), PDF (ReportLab)
- **Seguridad**: JWT, Bcrypt, XAdES-BES
- **Comunicación**: Requests, SMTP, SRI Web Services

---

## 💻 Requisitos del Sistema

### Requisitos de Hardware
- **RAM**: Mínimo 4GB (recomendado 8GB)
- **Disco**: Mínimo 10GB de espacio libre
- **Procesador**: Intel i3 o equivalente
- **Conexión a Internet**: Requerida para integración con SRI

### Requisitos de Software
- **Sistema Operativo**: Windows 10+, Linux, macOS
- **Python**: Versión 3.10.11
- **Base de Datos**: MySQL 8.0 o superior
- **Dependencias Python**: Ver `requirements.txt`
- **Certificado Digital**: Archivo .p12 del SRI

### Dependencias Principales
```
fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==2.0.23
pymysql==1.1.0
cryptography==3.4.8
lxml==5.0.0
reportlab==4.0.7
streamlit>=1.37.0
plotly==5.17.0
requests==2.31.0
```

---

## 🚀 Instalación y Configuración

### 1. Preparación del Entorno

#### Crear Entorno Virtual
```bash
# Linux/Mac
python -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

#### Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 2. Configuración de Base de Datos

#### Crear Base de Datos
```sql
CREATE DATABASE facturacion_electronica CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

#### Configurar Credenciales
Editar `config/settings.py`:
```python
# Configuración de Base de Datos MySQL
DB_HOST: str = "localhost"
DB_PORT: int = 3306
DB_NAME: str = "facturacion_electronica"
DB_USER: str = "tu_usuario"
DB_PASSWORD: str = "tu_contraseña"
```

### 3. Configuración de Empresa

Editar `config/settings.py`:
```python
# Configuración de la Empresa
EMPRESA_RUC: str = "1234567890001"
EMPRESA_RAZON_SOCIAL: str = "Mi Empresa S.A."
EMPRESA_NOMBRE_COMERCIAL: str = "Mi Empresa"
EMPRESA_DIRECCION: str = "Av. Principal 123"
EMPRESA_TELEFONO: str = "02-2345678"
EMPRESA_EMAIL: str = "info@miempresa.com"
```

### 4. Configuración de Certificado Digital

1. Colocar certificado .p12 en `certificados/certificado.p12`
2. Configurar contraseña en `config/settings.py`:
```python
CERT_PATH: str = "certificados/certificado.p12"
CERT_PASSWORD: str = "tu_contraseña"
```

### 5. Configuración de Correo

Editar `config/settings.py`:
```python
# Configuración de Correo
SMTP_SERVER: str = "smtp.gmail.com"
SMTP_PORT: int = 587
SMTP_USERNAME: str = "tu_email@gmail.com"
SMTP_PASSWORD: str = "tu_contraseña"
SMTP_FROM_EMAIL: str = "facturacion@miempresa.com"
```

### 6. Ejecución del Sistema

#### Inicialización Completa
```bash
# Linux/Mac
bash init.sh

# Windows
init.bat
```

#### Ejecutar Backend
```bash
cd backend
python main.py
```

#### Ejecutar Frontend
```bash
cd frontend
streamlit run app.py
```

---

## 📁 Estructura del Proyecto

```
facturacion-electronica-ecuador/
├── backend/              # API FastAPI
│   ├── main.py           # Punto de entrada API
│   ├── database.py        # Conexión y repositorios
│   └── models.py         # Modelos de datos
├── frontend/             # Interfaz Streamlit
│   ├── app.py            # Aplicación principal
│   ├── config.py         # Configuración frontend
│   ├── pages.py          # Páginas de la aplicación
│   ├── utils.py          # Utilidades frontend
│   └── README.md         # Documentación frontend
├── config/               # Configuración del sistema
│   └── settings.py       # Configuración principal
├── database/             # Esquema de base de datos
│   └── schema.sql        # Esquema MySQL
├── utils/                # Utilidades del sistema
│   ├── xml_generator.py  # Generador XML SRI
│   ├── firma_digital.py   # Firma digital XAdES-BES
│   ├── ride_generator.py  # Generador PDF RIDE
│   └── email_sender.py   # Envío de correos
├── schemas/              # Esquemas XSD del SRI
├── certificados/         # Certificados digitales
├── uploads/              # Archivos subidos
├── output/               # Documentos generados
├── temp/                 # Archivos temporales
├── .streamlit/           # Configuración Streamlit
├── requirements.txt      # Dependencias
└── README.md             # Documentación principal
```

---

## 🧩 Componentes Principales

### 1. Backend API (FastAPI)

**Rutas Principales:**
- `GET /` - Estado del sistema
- `POST /clientes/` - Crear cliente
- `GET /clientes/{id}` - Obtener cliente
- `POST /productos/` - Crear producto
- `POST /facturas/` - Crear factura
- `POST /facturas/{id}/generar-xml` - Generar XML
- `POST /facturas/{id}/firmar` - Firmar factura
- `POST /facturas/{id}/generar-ride` - Generar PDF
- `POST /facturas/{id}/enviar-email` - Enviar por email
- `GET /health` - Verificación de salud

### 2. Frontend Web (Streamlit)

**Páginas Principales:**
- **Dashboard**: Métricas y estadísticas
- **Facturas**: Gestión de facturas electrónicas
- **Clientes**: Administración de clientes
- **Productos**: Catálogo de productos/servicios
- **Reportes**: Gráficos y análisis
- **Configuración**: Ajustes del sistema

### 3. Base de Datos

**Entidades Principales:**
- **Empresas**: Datos fiscales del emisor
- **Establecimientos**: Sucursales
- **Puntos de Emisión**: Cajas emisoras
- **Clientes**: Clientes del sistema
- **Productos**: Catálogo de productos/servicios
- **Facturas**: Documentos electrónicos
- **Usuarios**: Usuarios del sistema

---

## 🗄️ Base de Datos

### Esquema Principal

#### Tabla `empresas`
```sql
CREATE TABLE empresas (
    id INT PRIMARY KEY AUTO_INCREMENT,
    ruc VARCHAR(13) NOT NULL UNIQUE,
    razon_social VARCHAR(300) NOT NULL,
    nombre_comercial VARCHAR(300),
    direccion_matriz VARCHAR(300) NOT NULL,
    telefono VARCHAR(20),
    email VARCHAR(100),
    obligado_contabilidad ENUM('SI', 'NO') DEFAULT 'NO',
    contribuyente_especial VARCHAR(10),
    logo_path VARCHAR(255),
    cert_path VARCHAR(255),
    cert_password VARCHAR(255),
    ambiente ENUM('1', '2') DEFAULT '1',
    tipo_emision ENUM('1', '2') DEFAULT '1',
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

#### Tabla `facturas`
```sql
CREATE TABLE facturas (
    id INT PRIMARY KEY AUTO_INCREMENT,
    empresa_id INT NOT NULL,
    establecimiento_id INT NOT NULL,
    punto_emision_id INT NOT NULL,
    cliente_id INT NOT NULL,
    
    -- Información del comprobante
    tipo_comprobante VARCHAR(2) DEFAULT '01',
    numero_comprobante VARCHAR(17) NOT NULL,
    fecha_emision DATETIME NOT NULL,
    ambiente VARCHAR(1) NOT NULL,
    tipo_emision VARCHAR(1) NOT NULL,
    clave_acceso VARCHAR(49) NOT NULL UNIQUE,
    
    -- Información tributaria
    subtotal_sin_impuestos DECIMAL(12,2) NOT NULL,
    subtotal_0 DECIMAL(12,2) DEFAULT 0,
    subtotal_12 DECIMAL(12,2) DEFAULT 0,
    subtotal_no_objeto_iva DECIMAL(12,2) DEFAULT 0,
    subtotal_exento_iva DECIMAL(12,2) DEFAULT 0,
    total_descuento DECIMAL(12,2) DEFAULT 0,
    ice DECIMAL(12,2) DEFAULT 0,
    iva_12 DECIMAL(12,2) DEFAULT 0,
    irbpnr DECIMAL(12,2) DEFAULT 0,
    propina DECIMAL(12,2) DEFAULT 0,
    valor_total DECIMAL(12,2) NOT NULL,
    
    -- Estados del documento
    estado_sri ENUM('GENERADO', 'FIRMADO', 'AUTORIZADO', 'RECHAZADO', 'DEVUELTO') DEFAULT 'GENERADO',
    numero_autorizacion VARCHAR(49),
    fecha_autorizacion DATETIME,
    
    -- Archivos generados
    xml_path VARCHAR(500),
    xml_firmado_path VARCHAR(500),
    pdf_path VARCHAR(500),
    
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (establecimiento_id) REFERENCES establecimientos(id),
    FOREIGN KEY (punto_emision_id) REFERENCES puntos_emision(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);
```

---

## 🌐 API REST

### Autenticación
La API utiliza autenticación JWT Bearer Token:

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

### Endpoints Principales

#### Gestión de Clientes
```bash
# Crear cliente
POST /clientes/
{
  "tipo_identificacion": "04",
  "identificacion": "1234567890001",
  "razon_social": "Empresa Ejemplo S.A.",
  "direccion": "Av. Principal 123",
  "telefono": "02-2345678",
  "email": "info@ejemplo.com"
}

# Obtener cliente
GET /clientes/{id}
```

#### Gestión de Productos
```bash
# Crear producto
POST /productos/
{
  "codigo_principal": "PROD001",
  "descripcion": "Producto de ejemplo",
  "precio_unitario": 100.00,
  "tipo": "BIEN",
  "codigo_impuesto": "2",
  "porcentaje_iva": 0.12
}
```

#### Gestión de Facturas
```bash
# Crear factura
POST /facturas/
{
  "cliente_id": 1,
  "detalles": [
    {
      "codigo_principal": "PROD001",
      "cantidad": 1.00,
      "precio_unitario": 100.00,
      "descuento": 0.00
    }
  ],
  "observaciones": "Factura de ejemplo"
}

# Generar XML
POST /facturas/{id}/generar-xml

# Firmar factura
POST /facturas/{id}/firmar

# Generar RIDE (PDF)
POST /facturas/{id}/generar-ride

# Enviar por email
POST /facturas/{id}/enviar-email
```

---

## 🖥️ Frontend Web

### Acceso al Sistema
- **URL**: http://localhost:8501
- **Usuario por defecto**: admin
- **Contraseña por defecto**: admin123

### Páginas y Funcionalidades

#### 1. Dashboard
- Métricas de ventas en tiempo real
- Gráficos de tendencias
- Estado de documentos pendientes
- Alertas del sistema

#### 2. Gestión de Facturas
- Creación de nuevas facturas
- Listado y búsqueda de facturas
- Visualización de detalles
- Descarga de documentos (XML, PDF)
- Envío por email

#### 3. Gestión de Clientes
- Registro de nuevos clientes
- Validación de identificaciones ecuatorianas
- Listado con filtros
- Edición de datos

#### 4. Catálogo de Productos
- Administración de productos/servicios
- Precios y tasas de impuestos
- Categorización
- Búsqueda y filtrado

#### 5. Reportes
- Gráficos interactivos
- Exportación de datos
- Análisis por períodos
- Estadísticas de ventas

---

## 📄 Generación de Documentos

### XML (SRI v2.0.0)

#### Estructura Principal
```xml
<factura id="comprobante" version="2.0.0">
  <infoTributaria>
    <ambiente>1</ambiente>
    <tipoEmision>1</tipoEmision>
    <razonSocial>EMPRESA EJEMPLO S.A.</razonSocial>
    <nombreComercial>EMPRESA EJEMPLO</nombreComercial>
    <ruc>1234567890001</ruc>
    <claveAcceso>0101202301123456789000110010010000000011234567890</claveAcceso>
    <codDoc>01</codDoc>
    <estab>001</estab>
    <ptoEmi>001</ptoEmi>
    <secuencial>000000001</secuencial>
    <dirMatriz>AV. EJEMPLO 123 Y CALLE PRINCIPAL</dirMatriz>
  </infoTributaria>
  <infoFactura>
    <fechaEmision>01/01/2023</fechaEmision>
    <obligadoContabilidad>SI</obligadoContabilidad>
    <tipoIdentificacionComprador>04</tipoIdentificacionComprador>
    <razonSocialComprador>CLIENTE EJEMPLO S.A.</razonSocialComprador>
    <identificacionComprador>0987654321001</identificacionComprador>
    <totalSinImpuestos>100.00</totalSinImpuestos>
    <totalDescuento>0.00</totalDescuento>
    <totalConImpuestos>
      <totalImpuesto>
        <codigo>2</codigo>
        <codigoPorcentaje>2</codigoPorcentaje>
        <baseImponible>100.00</baseImponible>
        <tarifa>12</tarifa>
        <valor>12.00</valor>
      </totalImpuesto>
    </totalConImpuestos>
    <propina>0.00</propina>
    <importeTotal>112.00</importeTotal>
    <moneda>DOLAR</moneda>
  </infoFactura>
  <detalles>
    <detalle>
      <codigoPrincipal>PROD001</codigoPrincipal>
      <descripcion>Producto de ejemplo</descripcion>
      <cantidad>1.00</cantidad>
      <precioUnitario>100.00</precioUnitario>
      <descuento>0.00</descuento>
      <precioTotalSinImpuesto>100.00</precioTotalSinImpuesto>
      <impuestos>
        <impuesto>
          <codigo>2</codigo>
          <codigoPorcentaje>2</codigoPorcentaje>
          <tarifa>12</tarifa>
          <baseImponible>100.00</baseImponible>
          <valor>12.00</valor>
        </impuesto>
      </impuestos>
    </detalle>
  </detalles>
</factura>
```

### Generación de Clave de Acceso

Algoritmo: Módulo 11
Formato: `ddmmaaaatipcomprucrubambserienumdígito verificador`

### RIDE (PDF)

Características:
- Diseño profesional
- Información completa del documento
- Códigos QR
- Logotipo de la empresa
- Detalles de impuestos
- Información de autorización

---

## 🔏 Firma Digital

### Estándar XAdES-BES

#### Componentes de la Firma
1. **Certificado Digital**: Archivo .p12 del SRI
2. **Clave Privada**: Para firmar documentos
3. **Clave Pública**: Para verificar firma
4. **Información del Firmante**: Datos del emisor

#### Proceso de Firma
1. Cálculo de digest del documento
2. Creación de estructura XAdES-BES
3. Firma con clave privada
4. Incrustación en documento XML
5. Validación de la firma

### Validación de Firma
- Verificación de integridad
- Autenticidad del certificado
- Caducidad del certificado
- Revocación del certificado

---

## 🌐 Integración con SRI

### Servicios Web

#### 1. Recepción de Comprobantes
- **Pruebas**: https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl
- **Producción**: https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl

#### 2. Autorización de Comprobantes
- **Pruebas**: https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl
- **Producción**: https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl

### Proceso de Envío

1. **Generar XML** conforme a esquema SRI
2. **Firmar digitalmente** con certificado válido
3. **Enviar a SRI** mediante web service
4. **Recibir respuesta** de recepción
5. **Consultar autorización** periódicamente
6. **Actualizar estado** en base de datos

### Estados de Documentos

| Estado | Descripción |
|--------|-------------|
| GENERADO | Documento creado en sistema |
| FIRMADO | Documento firmado digitalmente |
| AUTORIZADO | Aprobado por el SRI |
| RECHAZADO | Rechazado por el SRI |
| DEVUELTO | Devuelto por inconsistencias |

---

## 📧 Envío de Correos

### Plantillas de Email

#### Factura Electrónica
- Asunto personalizable
- Cuerpo HTML con información del documento
- Adjuntos: PDF (RIDE) y XML firmado
- Información de validación en SRI

#### Notificaciones del SRI
- Actualización de estados
- Mensajes de error o advertencia
- Instrucciones de seguimiento

### Configuración SMTP

Formatos soportados:
- Gmail (con App Password)
- Outlook/Hotmail
- Servidores empresariales
- Servicios de terceros (SendGrid, etc.)

---

## 🔐 Seguridad

### Autenticación
- **JWT Tokens**: Sesiones seguras con expiración
- **Password Hashing**: Bcrypt para contraseñas
- **Validación de Roles**: Administrador y usuarios

### Protección de Datos
- **Encriptación en Tránsito**: HTTPS/TLS
- **Encriptación en Reposo**: Base de datos
- **Protección CSRF**: Tokens de seguridad
- **Validación de Entradas**: Prevención de inyecciones

### Auditoría
- Registro de acciones de usuarios
- Seguimiento de cambios en datos
- Logs de acceso y errores
- Auditoría de documentos generados

---

## 🧪 Pruebas y Validación

### Pruebas Unitarias
- Validación de generación de XML
- Verificación de cálculos fiscales
- Pruebas de firma digital
- Comprobación de integración con SRI

### Pruebas de Integración
- Flujo completo de facturación
- Comunicación con base de datos
- Envío de correos electrónicos
- Integración con servicios web

### Validación SRI
- Verificación de esquema XML
- Comprobación de clave de acceso
- Validación de estructura de documentos
- Pruebas en ambiente de pruebas

---

## 🛠️ Mantenimiento

### Tareas Programadas
- **Limpieza de archivos temporales**
- **Rotación de logs**
- **Actualización de certificados**
- **Backup de base de datos**

### Monitoreo
- **Estado de servicios**
- **Rendimiento del sistema**
- **Errores y excepciones**
- **Uso de recursos**

### Actualizaciones
- **Versiones de dependencias**
- **Normativas del SRI**
- **Parches de seguridad**
- **Mejoras de rendimiento**

---

## ❓ Solución de Problemas

### Problemas Comunes

#### 1. Error de Conexión a Base de Datos
**Causas:**
- Credenciales incorrectas
- Servidor MySQL no iniciado
- Firewall bloqueando conexión

**Solución:**
```bash
# Verificar conexión
mysql -h localhost -u usuario -p

# Reiniciar servicio MySQL
sudo service mysql restart
```

#### 2. Error en Firma Digital
**Causas:**
- Certificado no encontrado
- Contraseña incorrecta
- Certificado expirado

**Solución:**
- Verificar ruta del certificado
- Confirmar contraseña
- Renovar certificado en SRI

#### 3. Error de Envío a SRI
**Causas:**
- XML no válido
- Problemas de conectividad
- Certificado no autorizado

**Solución:**
- Validar estructura XML
- Verificar conexión a internet
- Confirmar certificado en SRI

#### 4. Error de Envío de Email
**Causas:**
- Configuración SMTP incorrecta
- Credenciales inválidas
- Problemas con servidor

**Solución:**
- Verificar configuración en settings.py
- Probar credenciales
- Contactar proveedor de correo

---

## 📜 Licencia

Este sistema de facturación electrónica es de código abierto y se distribuye bajo la licencia MIT.

**Derechos:**
- Uso comercial
- Modificación
- Distribución
- Uso privado

**Limitaciones:**
- Sin garantía
- Sin responsabilidad por daños
- Atribución requerida

**Condiciones:**
- Incluir aviso de copyright
- Incluir texto de licencia

---

## 📞 Soporte y Contacto

Para soporte técnico, consultoría o personalización del sistema:

- **Email**: soporte@empresa.com
- **Teléfono**: +593 XX XXX XXXX
- **Sitio Web**: https://www.empresa.com

---

## 🔄 Historial de Versiones

### v1.0.0 (Fecha de lanzamiento)
- Versión inicial del sistema
- Implementación completa de funcionalidades
- Cumplimiento normativo SRI v2.0.0
- Integración con servicios web del SRI
- Sistema de notificaciones por email

---

--

*Este documento es parte del Sistema de Facturación Electrónica para Ecuador y está sujeto a actualizaciones periódicas para mantener su relevancia y precisión.*

