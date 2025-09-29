# 🚀 Guía Paso a Paso para Ejecutar el Sistema de Facturación Electrónica

## 📋 Índice
1. [Requisitos Previos](#requisitos-previos)
2. [Instalación en Windows](#instalación-en-windows)
3. [Instalación en Linux](#instalación-en-linux)
4. [Configuración Inicial](#configuración-inicial)
5. [Ejecución del Sistema](#ejecución-del-sistema)
6. [Primer Uso del Sistema](#primer-uso-del-sistema)
7. [Solución de Problemas Comunes](#solución-de-problemas-comunes)

---

## ⚠️ Importante Antes de Comenzar

Esta guía está diseñada para usuarios sin conocimientos técnicos avanzados. Sigue cada paso cuidadosamente y en orden. Si encuentras algún problema, consulta la sección de [Solución de Problemas Comunes](#solución-de-problemas-comunes).

---

## 1️⃣ REQUISITOS PREVIOS

### 🔧 Software Necesario

#### Para Ambos Sistemas (Windows y Linux):
1. **Python 3.10.11** - Lenguaje de programación del sistema
2. **MySQL 8.0 o superior** - Base de datos donde se guardarán las facturas
3. **Certificado Digital .p12 del SRI** - Para firmar electrónicamente las facturas
4. **Cuenta de correo electrónico** - Para enviar facturas a clientes
5. **Acceso a Internet** - Para comunicarse con el SRI

#### Información Requerida:
- Datos de tu empresa (RUC, razón social, dirección, etc.)
- Contraseña del certificado digital
- Credenciales del correo electrónico
- Datos de acceso a la base de datos MySQL

---

## 2️⃣ INSTALACIÓN EN WINDOWS

### 📥 Paso 1: Instalar Python
1. Visita https://www.python.org/downloads/
2. Descarga "Python 3.10.11"
3. Ejecuta el instalador
4. ⚠️ IMPORTANTE: Marca la casilla "Add Python to PATH"
5. Selecciona "Install Now"

### 🗄️ Paso 2: Instalar MySQL
1. Visita https://dev.mysql.com/downloads/installer/
3. Ejecuta el instalador
4. Selecciona "Developer Default"
5. Sigue las instrucciones del instalador
6. Durante la instalación, configura una contraseña para el usuario root

### 📁 Paso 3: Preparar el Sistema de Facturación
3. Ejecuta el instalador del sistema de facturación y sigue el asistente.
4. Abre PowerShell o CMD y navega a la carpeta del proyecto (por ejemplo C:\facturacion-electronica).
5. Crea y activa el entorno virtual:
   - python -m venv env
   - .\env\Scripts\activate
6. Instala las dependencias:
   - pip install -r requirements.txt
7. Configura la base de datos (ajusta según tu configuración MySQL):
   - Edita el archivo .env o config/settings.py con las credenciales de MySQL.
   - Ejecuta las migraciones:
     - python manage.py migrate
8. Inicia el backend usando los scripts incluidos:
   - .\scripts\start-backend.bat — inicia el backend en modo producción utilizando las variables definidas en .env.
   - .\scripts\start-backend-dev.bat — inicia el backend en modo desarrollo (auto-reload y logs).
   - Si prefieres no usar los scripts, puedes iniciar manualmente:
     - Para una aplicación Flask: set FLASK_ENV=production && python -m app.main
     - Para una aplicación Django: set DJANGO_SETTINGS_MODULE=project.settings && python manage.py runserver 0.0.0.0:8000
9. Verifica que el backend esté corriendo accediendo a http://localhost:8000 (ajusta el puerto si es necesario).
4. Selecciona "Developer Default"
5. Sigue las instrucciones del instalador
6. Durante la instalación, configura una contraseña para el usuario root

### 📁 Paso 3: Preparar el Sistema de Facturación
1. Extrae el sistema de facturación en una carpeta (por ejemplo: `C:\facturacion`)
2. Abre "Símbolo del sistema" (Presiona Win + R, escribe "cmd", presiona Enter)
3. Navega a la carpeta del sistema:
   ```cmd
   cd C:\facturacion
   ```

### 🐍 Paso 4: Crear Entorno Virtual
```cmd
python -m venv venv
```

### 🔌 Paso 5: Activar Entorno Virtual
```cmd
venv\Scripts\activate
```
Verás que aparece `(venv)` al inicio de la línea.

### 📦 Paso 6: Instalar Dependencias
```cmd
pip install -r requirements.txt
```

---

## 3️⃣ INSTALACIÓN EN LINUX

### 📥 Paso 1: Instalar Python
La mayoría de distribuciones Linux vienen con Python preinstalado. Verifica:
```bash
python3 --version
```
Si no está instalado:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev

# CentOS/RHEL/Fedora
sudo yum install python3.10
```

### 🗄️ Paso 2: Instalar MySQL
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install mysql-server

# Iniciar MySQL
sudo systemctl start mysql
sudo systemctl enable mysql

# Configurar seguridad
sudo mysql_secure_installation
```

### 📁 Paso 3: Preparar el Sistema de Facturación
```bash
# Navegar a la carpeta del sistema
cd /ruta/a/tu/sistema/facturacion
```

### 🐍 Paso 4: Crear Entorno Virtual
```bash
python3 -m venv venv
```

### 🔌 Paso 5: Activar Entorno Virtual
```bash
source venv/bin/activate
```
Verás que aparece `(venv)` al inicio de la línea.

### 📦 Paso 6: Instalar Dependencias
```bash
pip install -r requirements.txt
```

---

## 4️⃣ CONFIGURACIÓN INICIAL

### ⚙️ Paso 1: Configurar la Base de Datos

#### Crear Base de Datos
1. Abre una terminal/consola
2. Conéctate a MySQL:
   ```bash
   # Windows
   mysql -u root -p
   
   # Linux
   sudo mysql -u root -p
   ```
3. Ingresa la contraseña de MySQL
4. Crea la base de datos:
   ```sql
   CREATE DATABASE facturacion_electronica CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
5. Crea un usuario para la aplicación:
   ```sql
   CREATE USER 'facturacion_user'@'localhost' IDENTIFIED BY 'tu_contrasena_segura';
   GRANT ALL PRIVILEGES ON facturacion_electronica.* TO 'facturacion_user'@'localhost';
   FLUSH PRIVILEGES;
   EXIT;
   ```

### ⚙️ Paso 2: Configurar el Sistema

#### Editar archivo de configuración
1. Abre el archivo `config/settings.py` en un editor de texto
2. Modifica los siguientes valores:

```python
# Configuración de Base de Datos MySQL
DB_HOST: str = "localhost"
DB_PORT: int = 3306
DB_NAME: str = "facturacion_electronica"
DB_USER: str = "facturacion_user"
DB_PASSWORD: str = "tu_contrasena_segura"

# Configuración de la Empresa
EMPRESA_RUC: str = "TU_RUC_AQUI"
EMPRESA_RAZON_SOCIAL: str = "RAZON_SOCIAL_DE_TU_EMPRESA"
EMPRESA_NOMBRE_COMERCIAL: str = "NOMBRE_COMERCIAL"
EMPRESA_DIRECCION: str = "DIRECCION_DE_TU_EMPRESA"
EMPRESA_TELEFONO: str = "TELEFONO_DE_TU_EMPRESA"
EMPRESA_EMAIL: str = "EMAIL_DE_TU_EMPRESA"

# Configuración del Certificado Digital
CERT_PATH: str = "ruta/a/tu/certificado.p12"
CERT_PASSWORD: str = "contraseña_de_tu_certificado"

# Configuración de Correo
SMTP_SERVER: str = "servidor_smtp"
SMTP_PORT: int = 587
SMTP_USERNAME: str = "tu_email@dominio.com"
SMTP_PASSWORD: str = "tu_contraseña_de_email"
SMTP_FROM_EMAIL: str = "facturacion@tuempresa.com"
```

### ⚙️ Paso 3: Inicializar la Base de Datos
1. Asegúrate que el entorno virtual está activado
2. Navega a la carpeta backend:
   ```bash
   # Windows
   cd backend
   
   # Linux
   cd backend
   ```
3. Ejecuta el script de inicialización:
   ```bash
   # Windows
   python main.py --init-db
   
   # Linux
   python3 main.py --init-db
   ```

---

## 5️⃣ EJECUCIÓN DEL SISTEMA

### ▶️ Paso 1: Iniciar el Backend (API)
1. Abre una terminal/consola
2. Activa el entorno virtual:
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Linux
   source venv/bin/activate
   ```
3. Navega a la carpeta backend:
   ```bash
   cd backend
   ```
4. Inicia el servidor:
   ```bash
   # Windows
   python main.py
   
   # Linux
   python3 main.py
   ```
5. Verás mensajes como:
   ```
   Iniciando API de Facturación Electrónica SRI Ecuador...
   ✓ Conexión a base de datos exitosa
   ✓ Directorio output listo
   INFO:     Uvicorn running on http://127.0.0.1:8000
   ```

### ▶️ Paso 2: Iniciar el Frontend (Interfaz Web)
1. Abre OTRA terminal/consola (no cierres la primera)
2. Activa el entorno virtual:
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Linux
   source venv/bin/activate
   ```
3. Navega a la carpeta frontend:
   ```bash
   cd frontend
   ```
4. Inicia la aplicación web:
   ```bash
   # Windows
   streamlit run app.py
   
   # Linux
   streamlit run app.py
   ```
5. Automáticamente se abrirá el navegador en:
   ```
   http://localhost:8501
   ```

---

## 6️⃣ PRIMER USO DEL SISTEMA

### 🔐 Acceder al Sistema
1. Abre tu navegador web
2. Ve a: http://localhost:8501
3. Inicia sesión con:
   - Usuario: `admin`
   - Contraseña: `admin123`

### 🏢 Configurar tu Empresa
1. En el menú lateral, haz clic en "Configuración"
2. Verifica que los datos de tu empresa estén correctos
3. Sube el logo de tu empresa (opcional)

### 👥 Registrar Clientes
1. En el menú lateral, haz clic en "Clientes"
2. Haz clic en "Nuevo Cliente"
3. Completa los datos requeridos:
   - Tipo de identificación (RUC, Cédula, etc.)
   - Número de identificación
   - Razón social
   - Dirección, teléfono y email

### 📦 Registrar Productos
1. En el menú lateral, haz clic en "Productos"
2. Haz clic en "Nuevo Producto"
3. Completa los datos:
   - Código del producto
   - Descripción
   - Precio unitario
   - Tasa de IVA (normalmente 12%)

### 🧾 Crear tu Primera Factura
1. En el menú lateral, haz clic en "Facturas"
2. Haz clic en "Nueva Factura"
3. Selecciona un cliente
4. Agrega productos al detalle
5. Revisa los cálculos
6. Haz clic en "Guardar Factura"
7. Genera el XML: Haz clic en "Generar XML"
8. Firma la factura: Haz clic en "Firmar"
9. Genera el PDF: Haz clic en "Generar RIDE"
10. Envía por email: Haz clic en "Enviar Email"

---

## 7️⃣ SOLUCIÓN DE PROBLEMAS COMUNES

### ❌ Problema: "No se puede conectar a la base de datos"
**Causas posibles:**
- MySQL no está iniciado
- Credenciales incorrectas
- Base de datos no creada

**Soluciones:**
1. Verificar que MySQL esté corriendo:
   ```bash
   # Windows: Iniciar servicio desde Panel de Control
   # Linux:
   sudo systemctl status mysql
   sudo systemctl start mysql
   ```
2. Verificar credenciales en `config/settings.py`
3. Verificar que la base de datos exista

### ❌ Problema: "Certificado digital no encontrado"
**Causas posibles:**
- Ruta del certificado incorrecta
- Archivo no existe
- Contraseña incorrecta

**Soluciones:**
1. Verificar ruta en `config/settings.py`
2. Asegurarse que el archivo .p12 esté en la ubicación correcta
3. Verificar contraseña del certificado

### ❌ Problema: "Error al enviar correo"
**Causas posibles:**
- Configuración SMTP incorrecta
- Credenciales inválidas
- Problemas con el proveedor de correo

**Soluciones:**
1. Verificar configuración en `config/settings.py`
2. Probar credenciales en cliente de correo
3. Para Gmail, usar "App Password" en lugar de contraseña principal

### ❌ Problema: "Puerto ocupado" al iniciar
**Causas posibles:**
- Otra instancia del sistema ya está corriendo
- Otro programa usando los puertos

**Soluciones:**
1. Cerrar otras terminales del sistema
2. Cambiar puertos en configuración
3. Reiniciar computadora

### ❌ Problema: "Módulo no encontrado" al ejecutar
**Causas posibles:**
- Dependencias no instaladas
- Entorno virtual no activado

**Soluciones:**
1. Asegurarse que entorno virtual esté activado
2. Ejecutar: `pip install -r requirements.txt`
3. Verificar que estés en la carpeta correcta

---

## 📞 Soporte y Contacto

Para soporte técnico, consultoría o personalización del sistema:

- **Email**: soporte@empresa.com
- **Teléfono**: +593 XX XXX XXXX
- **Sitio Web**: https://www.empresa.com

---

## 🔄 Actualizaciones

Esta guía corresponde a la versión 1.0.0 del sistema. Para obtener actualizaciones, visita el repositorio oficial.

---

*Esta guía es parte del Sistema de Facturación Electrónica para Ecuador y está sujeto a actualizaciones periódicas para mantener su relevancia y precisión.*