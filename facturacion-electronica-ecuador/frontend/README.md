# Frontend - Sistema de Facturación Electrónica SRI Ecuador

Frontend desarrollado en Python con Streamlit para el sistema de facturación electrónica que cumple con la normativa del SRI de Ecuador.

## 🚀 Características del Frontend

- **Interfaz Moderna**: Diseño limpio y profesional con Streamlit
- **Responsive**: Se adapta a diferentes tamaños de pantalla
- **Tiempo Real**: Actualización automática de datos
- **Interactivo**: Gráficos y tablas interactivas con Plotly
- **Validaciones**: Validación en tiempo real de formularios
- **Multiidioma**: Preparado para múltiples idiomas
- **Temas**: Soporte para temas claro y oscuro

## 📋 Funcionalidades Implementadas

### 🏠 Dashboard
- Métricas principales en tiempo real
- Gráficos de ventas y facturación
- Facturas recientes
- Alertas y notificaciones
- Estado del sistema

### 🧾 Gestión de Facturas
- Lista de facturas con filtros avanzados
- Creación de nuevas facturas
- Selección de clientes existentes o creación de nuevos
- Agregado de productos con cálculo automático
- Estadísticas de facturación
- Consultas al SRI
- Envío por email
- Descarga de PDF
- Exportación a Excel

### 👥 Gestión de Clientes
- Lista de clientes con búsqueda
- Creación de nuevos clientes
- Validación de RUC y cédula ecuatoriana
- Estadísticas de clientes
- Filtros por tipo de identificación

### 📦 Gestión de Productos
- Catálogo de productos y servicios
- Creación y edición de productos
- Filtros por tipo y estado
- Estadísticas de productos
- Productos más vendidos

### 📈 Reportes
- Reportes de ventas por período
- Gráficos interactivos
- Exportación de reportes
- Análisis de tendencias

### ⚙️ Configuración
- Configuración de empresa
- Gestión de certificados digitales
- Configuración de email
- Configuración del sistema
- Estado y mantenimiento

## 🛠️ Tecnologías Utilizadas

- **Streamlit 1.28.1**: Framework principal para la interfaz web
- **Plotly 5.17.0**: Gráficos interactivos
- **Pandas 2.1.4**: Manipulación de datos
- **Requests 2.31.0**: Comunicación con la API
- **Pillow 10.1.0**: Procesamiento de imágenes

## 📁 Estructura del Frontend

```
frontend/
├── app.py              # Aplicación principal
├── config.py           # Configuración del frontend
├── utils.py            # Utilidades y componentes reutilizables
├── pages.py            # Páginas específicas
└── README.md           # Este archivo
```

## 🚀 Instalación y Ejecución

### Prerrequisitos
- Python 3.8+
- Backend FastAPI ejecutándose en http://localhost:8000

### Instalación
```bash
# Instalar dependencias
pip install -r requirements.txt
```

### Ejecución

#### Linux/Mac
```bash
# Ejecutar frontend
bash run_frontend.sh

# O directamente con Streamlit
cd frontend
streamlit run app.py
```

#### Windows
```cmd
# Ejecutar frontend
run_frontend.bat

# O directamente con Streamlit
cd frontend
streamlit run app.py
```

### Ejecución en Desarrollo
```bash
# Ejecutar backend y frontend simultáneamente
npm run dev-full
```

## 🌐 Acceso a la Aplicación

Una vez iniciado el servidor, la aplicación estará disponible en:
- **URL**: http://localhost:8501
- **Puerto**: 8501 (configurable)

## 🔐 Autenticación

El frontend se conecta al backend FastAPI para la autenticación. Las credenciales por defecto son:
- **Usuario**: admin
- **Contraseña**: admin123

## 📊 Características Técnicas

### Componentes Principales

#### APIClient
- Manejo de autenticación JWT
- Gestión de sesiones
- Manejo de errores de conexión
- Reintentos automáticos

#### Validaciones
- Validación de RUC ecuatoriano
- Validación de cédula ecuatoriana
- Validación de emails
- Validación de formularios en tiempo real

#### Utilidades
- Formateo de moneda
- Formateo de fechas
- Componentes reutilizables
- Badges de estado
- Métricas personalizadas

### Configuración Personalizable

```python
# config.py
class FrontendConfig:
    API_BASE_URL = "http://localhost:8000"
    APP_TITLE = "Sistema de Facturación Electrónica"
    PAGE_CONFIG = {...}
    CUSTOM_CSS = "..."
```

## 🎨 Personalización

### Temas
El frontend soporta personalización de temas mediante CSS:

```css
/* Tema claro */
--primary-color: #1f77b4;
--background-color: #ffffff;
--secondary-background: #f0f2f6;
--text-color: #262730;
```

### Componentes
Los componentes son modulares y reutilizables:

```python
from utils import create_metric_card, display_factura_table

# Usar componentes
create_metric_card("Ventas", "$1,234.56", "+5%")
display_factura_table(facturas_data)
```

## 🔧 Configuración Avanzada

### Variables de Entorno
```bash
# .env
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=localhost
API_BASE_URL=http://localhost:8000
```

### Configuración de Streamlit
```toml
# .streamlit/config.toml
[server]
port = 8501
address = "localhost"

[theme]
base = "light"
primaryColor = "#1f77b4"
backgroundColor = "#ffffff"
```

## 📱 Responsive Design

El frontend está optimizado para diferentes dispositivos:
- **Desktop**: Diseño completo con sidebar
- **Tablet**: Diseño adaptado con menú colapsible
- **Mobile**: Diseño simplificado y táctil

## 🔍 Debugging

### Logs
Los logs se guardan en:
```
logs/
├── frontend.log
├── api_calls.log
└── errors.log
```

### Modo Debug
```python
# Activar modo debug
DEBUG = True
SHOW_API_RESPONSES = True
```

## 🚀 Despliegue

### Desarrollo
```bash
streamlit run frontend/app.py --server.port 8501
```

### Producción
```bash
streamlit run frontend/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --browser.gatherUsageStats false
```

### Docker
```dockerfile
FROM python:3.9-slim
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY frontend/ /app/frontend/
WORKDIR /app
EXPOSE 8501
CMD ["streamlit", "run", "frontend/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
```

## 🤝 Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📞 Soporte

- **Email**: soporte@empresa.com
- **Teléfono**: +593-2-1234567
- **Documentación**: [docs.empresa.com](https://docs.empresa.com)

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](../LICENSE) para detalles.

## 🙏 Agradecimientos

- Streamlit por el excelente framework
- Plotly por los gráficos interactivos
- Comunidad Python Ecuador
- SRI Ecuador por la documentación técnica