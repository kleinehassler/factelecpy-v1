"""
API REST para facturación electrónica del SRI Ecuador
Versión mejorada con validaciones y cálculos precisos
"""
from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator, EmailStr
from typing import List, Optional
from datetime import datetime, date, timedelta
import os
import uuid
from decimal import Decimal
import logging
import random
import time
from collections import defaultdict
import asyncio
import jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt

from config.settings import settings
from backend.database import DatabaseManager, FacturaRepository, ClienteRepository, ProductoRepository
from backend.models import Factura, Cliente, Producto, FacturaDetalle, Empresa
from utils.firma_digital import XadesBesSigner
from utils.ride_generator import RideGenerator
from utils.email_sender import EmailSender, EmailTemplates
from utils.metrics import get_app_metrics, get_metrics_collector
from utils.cache import get_cache_stats
from utils.validators import validate_and_raise, BusinessValidator
from config.logging_config import setup_logging, get_logger
from utils.email_sender import EmailSender, EmailTemplates
from utils.metrics import get_app_metrics, get_metrics_collector
from utils.cache import get_cache_stats
from utils.validators import validate_and_raise, BusinessValidator
from config.logging_config import setup_logging, get_logger


# Rate Limiting simple
class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)

    def is_allowed(self, client_ip: str, max_requests: int = 100, window: int = 3600) -> bool:
        now = time.time()
        # Limpiar requests antiguos
        self.requests[client_ip] = [req_time for req_time in self.requests[client_ip]
                                   if now - req_time < window]

        if len(self.requests[client_ip]) >= max_requests:
            return False

        self.requests[client_ip].append(now)
        return True

rate_limiter = RateLimiter()

# Configuración de autenticación
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Usuarios de prueba (en producción esto debería estar en base de datos)
USERS_DB = {
    "admin": {
        "username": "admin",
        "email": "admin@empresa.com",
        "full_name": "Administrador",
        "hashed_password": pwd_context.hash("admin123"),  # Contraseña: admin123
    },
    "usuario": {
        "username": "usuario",
        "email": "usuario@empresa.com",
        "full_name": "Usuario",
        "hashed_password": pwd_context.hash("usuario123"),  # Contraseña: usuario123
    }
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar contraseña"""
    return pwd_context.verify(plain_password, hashed_password)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Autenticar usuario"""
    user = USERS_DB.get(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crear token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "sub": data.get("username")})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Verificar token JWT"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return {"username": username}
    except jwt.PyJWTError:
        return None


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Obtener usuario actual desde token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = verify_token(token)
    if token_data is None:
        raise credentials_exception

    user = USERS_DB.get(token_data["username"])
    if user is None:
        raise credentials_exception

    return user


# Configurar logging
import os
import logging

os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Modelos Pydantic para la API con validaciones mejoradas
class ClienteCreate(BaseModel):
    tipo_identificacion: str
    identificacion: str
    razon_social: str
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[EmailStr] = None

    @field_validator('tipo_identificacion')
    @classmethod
    def validate_tipo_identificacion(cls, v):
        valid_types = ['04', '05', '06', '07', '08']
        if v not in valid_types:
            raise ValueError(f'Tipo de identificación debe ser uno de: {valid_types}')
        return v

    @field_validator('identificacion')
    @classmethod
    def validate_identificacion(cls, v, info):
        if not v or len(v.strip()) == 0:
            raise ValueError('Identificación es requerida')

        # Validar según tipo de identificación
        # Nota: En Pydantic V2, necesitamos acceder a otros campos de manera diferente
        # Por ahora, validaremos solo el formato básico
        v = v.strip()
        if len(v) == 13 and v.isdigit():  # Probablemente RUC
            return v
        elif len(v) == 10 and v.isdigit():  # Probablemente Cédula
            return v
        elif len(v) >= 5:  # Otros tipos de identificación
            return v
        else:
            raise ValueError('Formato de identificación inválido')

    @field_validator('razon_social')
    @classmethod
    def validate_razon_social(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Razón social es requerida')
        if len(v.strip()) > 300:
            raise ValueError('Razón social no puede exceder 300 caracteres')
        return v.strip()


class ClienteResponse(ClienteCreate):
    id: int
    activo: bool
    created_at: datetime


class ProductoCreate(BaseModel):
    codigo_principal: str
    codigo_auxiliar: Optional[str] = None
    descripcion: str
    precio_unitario: Decimal
    tipo: str = "BIEN"
    codigo_impuesto: str = "2"
    porcentaje_iva: Decimal = Decimal("0.12")

    @field_validator('codigo_principal')
    @classmethod
    def validate_codigo_principal(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Código principal es requerido')
        if len(v.strip()) > 25:
            raise ValueError('Código principal no puede exceder 25 caracteres')
        return v.strip()

    @field_validator('descripcion')
    @classmethod
    def validate_descripcion(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Descripción es requerida')
        if len(v.strip()) > 300:
            raise ValueError('Descripción no puede exceder 300 caracteres')
        return v.strip()

    @field_validator('precio_unitario')
    @classmethod
    def validate_precio_unitario(cls, v):
        if v <= 0:
            raise ValueError('Precio unitario debe ser mayor a 0')
        return v

    @field_validator('tipo')
    @classmethod
    def validate_tipo(cls, v):
        if v not in ['BIEN', 'SERVICIO']:
            raise ValueError('Tipo debe ser BIEN o SERVICIO')
        return v


class FacturaDetalleCreate(BaseModel):
    codigo_principal: str
    codigo_auxiliar: Optional[str] = None
    descripcion: str
    cantidad: Decimal
    precio_unitario: Decimal
    descuento: Decimal = Decimal("0.00")

    @field_validator('codigo_principal')
    @classmethod
    def validate_codigo_principal(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Código principal es requerido')
        if len(v.strip()) > 25:
            raise ValueError('Código principal no puede exceder 25 caracteres')
        return v.strip()

    @field_validator('descripcion')
    @classmethod
    def validate_descripcion(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Descripción es requerida')
        if len(v.strip()) > 300:
            raise ValueError('Descripción no puede exceder 300 caracteres')
        return v.strip()

    @field_validator('cantidad')
    @classmethod
    def validate_cantidad(cls, v):
        if v <= 0:
            raise ValueError('Cantidad debe ser mayor a 0')
        return v

    @field_validator('precio_unitario')
    @classmethod
    def validate_precio_unitario(cls, v):
        if v <= 0:
            raise ValueError('Precio unitario debe ser mayor a 0')
        return v


class FacturaCreate(BaseModel):
    cliente_id: int
    fecha_emision: datetime
    observaciones: Optional[str] = None
    detalles: List[FacturaDetalleCreate]

    @field_validator('detalles')
    @classmethod
    def validate_detalles(cls, v):
        if not v or len(v) == 0:
            raise ValueError('La factura debe tener al menos un detalle')
        return v


class FacturaResponse(BaseModel):
    id: int
    numero_comprobante: str
    fecha_emision: datetime
    clave_acceso: str
    subtotal_sin_impuestos: Decimal
    subtotal_0: Decimal = Decimal("0.00")
    subtotal_12: Decimal = Decimal("0.00")
    iva_12: Decimal = Decimal("0.00")
    valor_total: Decimal
    estado_sri: str = "PENDIENTE"
    created_at: datetime


# Modelos para autenticación
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_data: Optional[dict] = None


class UserData(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None


class ProductoResponse(ProductoCreate):
    id: int
    activo: bool
    created_at: datetime

# Inicializar aplicación FastAPI
app = FastAPI(
    title="API Facturación Electrónica SRI Ecuador",
    description="API para generación de facturas electrónicas según normativa del SRI",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)

# Middleware de seguridad
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.localhost"]
)

# Configurar CORS de manera más segura
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],  # Solo frontend específico
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Middleware de Rate Limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host

    # Excluir endpoints de documentación del rate limiting
    if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
        response = await call_next(request)
        return response

    if not rate_limiter.is_allowed(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."}
        )

    response = await call_next(request)
    return response

# Configurar autenticación OAuth2 (ya está definido arriba, eliminando duplicado)

# Inicializar componentes
db_manager = DatabaseManager()

# Configurar logging (ya está configurado arriba, eliminando duplicado)
logger = logging.getLogger(__name__)


def generar_numero_comprobante():
    """Generar número de comprobante único"""
    # En una implementación real, esto debería obtener el siguiente número de la base de datos
    # basado en la secuencia del punto de emisión
    numero = str(random.randint(1, 999999999)).zfill(9)
    return f"001-001-{numero}"


# Middleware de logging de requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.4f}s - "
        f"Client: {request.client.host}"
    )

    return response


# Rutas de la API
@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "API de Facturación Electrónica SRI Ecuador",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check():
    """Endpoint de health check"""
    try:
        # Verificar conexión a base de datos
        with db_manager.get_db_session() as db:
            db.execute("SELECT 1")

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": "Database connection failed"
            }
        )


# ============================================================================
# ENDPOINTS DE AUTENTICACIÓN
# ============================================================================

@app.post("/auth/login", response_model=TokenResponse)
async def login(username: str = Form(...), password: str = Form(...)):
    """Endpoint de login que recibe username y password como form data"""
    try:
        # Autenticar usuario
        user = authenticate_user(username, password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Crear token de acceso
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"]},
            expires_delta=access_token_expires
        )

        # Preparar datos del usuario (sin contraseña)
        user_data = {
            "username": user["username"],
            "email": user.get("email"),
            "full_name": user.get("full_name")
        }

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user_data=user_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error en login: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )


# ============================================================================
# ENDPOINTS DE CLIENTES
# ============================================================================


@app.post("/clientes/", response_model=ClienteResponse)
async def crear_cliente(cliente: ClienteCreate, request: Request, current_user: dict = Depends(get_current_user)):
    """Crear un nuevo cliente"""
    try:
        logger.info(f"Creando cliente: {cliente.identificacion} desde IP: {request.client.host}")

        with db_manager.get_db_session() as db:
            cliente_repo = ClienteRepository(db)

            # Verificar si el cliente ya existe
            cliente_existente = cliente_repo.obtener_cliente_por_identificacion(
                cliente.tipo_identificacion, cliente.identificacion
            )

            if cliente_existente:
                logger.warning(f"Intento de crear cliente duplicado: {cliente.identificacion}")
                raise HTTPException(
                    status_code=400,
                    detail="Cliente con esta identificación ya existe"
                )

            # Crear cliente
            cliente_db = cliente_repo.crear_cliente(cliente.dict())

            logger.info(f"Cliente creado exitosamente: ID {cliente_db.id}")

            return ClienteResponse(
                id=cliente_db.id,
                tipo_identificacion=cliente_db.tipo_identificacion,
                identificacion=cliente_db.identificacion,
                razon_social=cliente_db.razon_social,
                direccion=cliente_db.direccion,
                telefono=cliente_db.telefono,
                email=cliente_db.email,
                activo=cliente_db.activo,
                created_at=cliente_db.created_at
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al crear cliente: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor. Por favor, intente más tarde."
        )


# Endpoint POST /clientes/ removed (duplicate)


@app.get("/clientes/{cliente_id}", response_model=ClienteResponse)
async def obtener_cliente(cliente_id: int, current_user: dict = Depends(get_current_user)):
    """Obtener cliente por ID"""
    try:
        with db_manager.get_db_session() as db:
            cliente_repo = ClienteRepository(db)
            cliente = cliente_repo.obtener_cliente_por_id(cliente_id)

            if not cliente:
                raise HTTPException(status_code=404, detail="Cliente no encontrado")

            return ClienteResponse(
                id=cliente.id,
                tipo_identificacion=cliente.tipo_identificacion,
                identificacion=cliente.identificacion,
                razon_social=cliente.razon_social,
                direccion=cliente.direccion,
                telefono=cliente.telefono,
                email=cliente.email,
                activo=cliente.activo,
                created_at=cliente.created_at
            )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error al obtener cliente {cliente_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


@app.post("/productos/", response_model=ProductoResponse)
async def crear_producto(producto: ProductoCreate, current_user: dict = Depends(get_current_user)):
    """Crear un nuevo producto"""
    try:
        with db_manager.get_db_session() as db:
            producto_repo = ProductoRepository(db)

            # Verificar si el producto ya existe
            producto_existente = producto_repo.obtener_producto_por_codigo(
                producto.codigo_principal
            )

            if producto_existente:
                raise HTTPException(
                    status_code=400,
                    detail="Producto con este código ya existe"
                )

            # Crear producto
            producto_db = producto_repo.crear_producto(producto.dict())

            return ProductoResponse(
                id=producto_db.id,
                codigo_principal=producto_db.codigo_principal,
                codigo_auxiliar=producto_db.codigo_auxiliar,
                descripcion=producto_db.descripcion,
                precio_unitario=producto_db.precio_unitario,
                tipo=producto_db.tipo,
                codigo_impuesto=producto_db.codigo_impuesto,
                porcentaje_iva=producto_db.porcentaje_iva,
                activo=producto_db.activo,
                created_at=producto_db.created_at,
                updated_at=producto_db.updated_at
            )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error al crear producto: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


@app.get("/productos/", response_model=List[ProductoResponse])
async def listar_productos(skip: int = 0, limit: int = 100, current_user: dict = Depends(get_current_user)):
    """Listar todos los productos"""
    try:
        with db_manager.get_db_session() as db:
            producto_repo = ProductoRepository(db)
            productos = producto_repo.listar_productos(skip=skip, limit=limit)

            return [
                ProductoResponse(
                    id=producto.id,
                    codigo_principal=producto.codigo_principal,
                    codigo_auxiliar=producto.codigo_auxiliar,
                    descripcion=producto.descripcion,
                    precio_unitario=producto.precio_unitario,
                    tipo=producto.tipo,
                    codigo_impuesto=producto.codigo_impuesto,
                    porcentaje_iva=producto.porcentaje_iva,
                    activo=producto.activo,
                    created_at=producto.created_at
                ) for producto in productos
            ]
    except Exception as e:
        logging.error(f"Error al listar productos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


@app.get("/productos/{producto_id}", response_model=ProductoResponse)
async def obtener_producto(producto_id: int, current_user: dict = Depends(get_current_user)):
    """Obtener producto por ID"""
    try:
        with db_manager.get_db_session() as db:
            producto_repo = ProductoRepository(db)
            producto = producto_repo.obtener_producto_por_id(producto_id)

            if not producto:
                raise HTTPException(status_code=404, detail="Producto no encontrado")

            return ProductoResponse(
                id=producto.id,
                codigo_principal=producto.codigo_principal,
                codigo_auxiliar=producto.codigo_auxiliar,
                descripcion=producto.descripcion,
                precio_unitario=producto.precio_unitario,
                tipo=producto.tipo,
                codigo_impuesto=producto.codigo_impuesto,
                porcentaje_iva=producto.porcentaje_iva,
                activo=producto.activo,
                created_at=producto.created_at
            )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error al obtener producto {producto_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


# ============================================================================
# ENDPOINTS DE FACTURAS
# ============================================================================


@app.post("/facturas/", response_model=FacturaResponse)
async def crear_factura(factura_data: FacturaCreate, current_user: dict = Depends(get_current_user)):
    """Crear una nueva factura electrónica"""
    try:
        with db_manager.get_db_session() as db:
            # Obtener repositorios
            cliente_repo = ClienteRepository(db)
            producto_repo = ProductoRepository(db)
            factura_repo = FacturaRepository(db)

            # Verificar cliente
            cliente = cliente_repo.obtener_cliente_por_id(factura_data.cliente_id)
            if not cliente:
                raise HTTPException(status_code=404, detail="Cliente no encontrado")

            # Validar que haya al menos un detalle
            if not factura_data.detalles:
                raise HTTPException(status_code=400, detail="La factura debe tener al menos un detalle")

            # Crear detalles de factura con cálculos precisos
            detalles_factura = []
            subtotal_sin_impuestos = Decimal("0.00")
            subtotal_12 = Decimal("0.00")
            subtotal_0 = Decimal("0.00")
            iva_12 = Decimal("0.00")
            total_descuento = Decimal("0.00")

            for detalle_data in factura_data.detalles:
                # Obtener producto
                producto = producto_repo.obtener_producto_por_codigo(detalle_data.codigo_principal)
                if not producto:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Producto {detalle_data.codigo_principal} no encontrado"
                    )

                # Validar cantidades y precios positivos
                if detalle_data.cantidad <= 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"La cantidad del producto {detalle_data.codigo_principal} debe ser mayor a cero"
                    )

                if detalle_data.precio_unitario <= 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"El precio unitario del producto {detalle_data.codigo_principal} debe ser mayor a cero"
                    )

                # Calcular valores
                precio_total_sin_impuesto = detalle_data.cantidad * detalle_data.precio_unitario

                # Aplicar descuento si existe
                descuento = detalle_data.descuento if detalle_data.descuento > 0 else Decimal("0.00")
                if descuento > 0:
                    if descuento >= precio_total_sin_impuesto:
                        raise HTTPException(
                            status_code=400,
                            detail=f"El descuento del producto {detalle_data.codigo_principal} no puede ser mayor o igual al total"
                        )
                    precio_total_sin_impuesto -= descuento

                # Clasificar por tipo de impuesto
                if producto.porcentaje_iva > 0:
                    subtotal_12 += precio_total_sin_impuesto
                    iva_12 += precio_total_sin_impuesto * producto.porcentaje_iva
                else:
                    subtotal_0 += precio_total_sin_impuesto

                subtotal_sin_impuestos += precio_total_sin_impuesto
                total_descuento += descuento

                # Crear detalle completo
                detalle = {
                    "codigo_principal": detalle_data.codigo_principal,
                    "codigo_auxiliar": detalle_data.codigo_auxiliar or producto.codigo_auxiliar,
                    "descripcion": detalle_data.descripcion or producto.descripcion,
                    "cantidad": detalle_data.cantidad,
                    "precio_unitario": detalle_data.precio_unitario,
                    "descuento": descuento,
                    "precio_total_sin_impuesto": precio_total_sin_impuesto
                }
                detalles_factura.append(detalle)

            # Calcular totales finales
            valor_total = subtotal_sin_impuestos + iva_12

            # Generar número de comprobante y clave de acceso
            numero_comprobante = generar_numero_comprobante()
            clave_acceso = ClaveAccesoGenerator.generar_clave_acceso(
                fecha_emision=datetime.now(),
                tipo_comprobante="01",
                ruc=settings.EMPRESA_RUC,
                ambiente=settings.SRI_AMBIENTE,
                serie="001001",
                numero=numero_comprobante.split('-')[2]
            )

            # Crear factura en base de datos
            factura_dict = {
                "empresa_id": 1,  # Empresa por defecto
                "establecimiento_id": 1,  # Establecimiento por defecto
                "punto_emision_id": 1,  # Punto de emisión por defecto
                "cliente_id": factura_data.cliente_id,
                "tipo_comprobante": "01",
                "numero_comprobante": numero_comprobante,
                "fecha_emision": datetime.now(),
                "ambiente": settings.SRI_AMBIENTE,
                "tipo_emision": settings.SRI_TIPO_EMISION,
                "clave_acceso": clave_acceso,
                "subtotal_sin_impuestos": subtotal_sin_impuestos,
                "subtotal_0": subtotal_0,
                "subtotal_12": subtotal_12,
                "iva_12": iva_12,
                "total_descuento": total_descuento,
                "valor_total": valor_total,
                "moneda": "DOLAR",
                "observaciones": factura_data.observaciones
            }

            factura = factura_repo.crear_factura(factura_dict)

            return FacturaResponse(
                id=factura.id,
                numero_comprobante=factura.numero_comprobante,
                fecha_emision=factura.fecha_emision,
                clave_acceso=factura.clave_acceso,
                subtotal_sin_impuestos=factura.subtotal_sin_impuestos,
                subtotal_0=getattr(factura, 'subtotal_0', Decimal("0.00")),
                subtotal_12=getattr(factura, 'subtotal_12', Decimal("0.00")),
                iva_12=factura.iva_12,
                valor_total=factura.valor_total,
                estado_sri=factura.estado_sri,
                created_at=factura.created_at
            )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error al crear factura: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


@app.get("/facturas/", response_model=List[FacturaResponse])
async def listar_facturas(skip: int = 0, limit: int = 100, current_user: dict = Depends(get_current_user)):
    """Listar todas las facturas"""
    try:
        with db_manager.get_db_session() as db:
            factura_repo = FacturaRepository(db)
            facturas = factura_repo.listar_facturas(skip=skip, limit=limit)

            return [
                FacturaResponse(
                    id=factura.id,
                    numero_comprobante=factura.numero_comprobante,
                    fecha_emision=factura.fecha_emision,
                    clave_acceso=factura.clave_acceso,
                    subtotal_sin_impuestos=factura.subtotal_sin_impuestos,
                    subtotal_0=getattr(factura, 'subtotal_0', Decimal("0.00")),
                    subtotal_12=getattr(factura, 'subtotal_12', Decimal("0.00")),
                    iva_12=factura.iva_12,
                    valor_total=factura.valor_total,
                    estado_sri=factura.estado_sri,
                    created_at=factura.created_at
                ) for factura in facturas
            ]
    except Exception as e:
        logging.error(f"Error al listar facturas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


@app.get("/facturas/{factura_id}", response_model=FacturaResponse)
async def obtener_factura(factura_id: int, current_user: dict = Depends(get_current_user)):
    """Obtener factura por ID"""
    try:
        with db_manager.get_db_session() as db:
            factura_repo = FacturaRepository(db)
            factura = factura_repo.obtener_factura_por_id(factura_id)

            if not factura:
                raise HTTPException(status_code=404, detail="Factura no encontrada")

            return FacturaResponse(
                id=factura.id,
                numero_comprobante=factura.numero_comprobante,
                fecha_emision=factura.fecha_emision,
                clave_acceso=factura.clave_acceso,
                subtotal_sin_impuestos=factura.subtotal_sin_impuestos,
                subtotal_0=getattr(factura, 'subtotal_0', Decimal("0.00")),
                subtotal_12=getattr(factura, 'subtotal_12', Decimal("0.00")),
                iva_12=factura.iva_12,
                valor_total=factura.valor_total,
                estado_sri=factura.estado_sri,
                created_at=factura.created_at
            )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error al obtener factura {factura_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


@app.post("/facturas/{factura_id}/generar-xml")
async def generar_xml_factura(factura_id: int):
    """Generar XML de factura"""
    try:
        with db_manager.get_db_session() as db:
            factura_repo = FacturaRepository(db)
            factura = factura_repo.obtener_factura_por_id(factura_id)

            if not factura:
                raise HTTPException(status_code=404, detail="Factura no encontrada")

            # Obtener empresa y cliente
            empresa = db.query(Empresa).filter(Empresa.id == factura.empresa_id).first()
            cliente = db.query(Cliente).filter(Cliente.id == factura.cliente_id).first()

            if not empresa or not cliente:
                raise HTTPException(status_code=500, detail="Error al obtener datos de empresa o cliente")

            # Obtener detalles de la factura
            detalles = db.query(FacturaDetalle).filter(FacturaDetalle.factura_id == factura_id).all()

            # Generar XML completo
            xml_generator = XMLGenerator()
            xml_content = xml_generator.generar_xml_factura(factura, empresa, cliente, detalles)

            # Validar XML contra esquema básico SRI
            valido, mensaje = xml_generator.validar_esquema_sri(xml_content)
            if not valido:
                raise HTTPException(status_code=500, detail=f"XML inválido: {mensaje}")

            # Guardar XML
            xml_filename = f"factura_{factura_id}.xml"
            xml_path = os.path.join(settings.OUTPUT_FOLDER, xml_filename)

            # Crear directorio si no existe
            os.makedirs(settings.OUTPUT_FOLDER, exist_ok=True)

            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)

            # Actualizar ruta en base de datos
            factura_repo.actualizar_rutas_archivos(factura_id, xml_path=xml_path)

            return {
                "message": "XML generado exitosamente",
                "path": xml_path,
                "content": xml_content[:1000] + "..." if len(xml_content) > 1000 else xml_content,
                "valido": True,
                "mensaje_validacion": mensaje
            }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error al generar XML de factura {factura_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar XML: {str(e)}")


@app.post("/facturas/{factura_id}/validar-xml")
async def validar_xml_factura(factura_id: int):
    """Validar XML de factura contra esquema SRI"""
    try:
        with db_manager.get_db_session() as db:
            factura_repo = FacturaRepository(db)
            factura = factura_repo.obtener_factura_por_id(factura_id)

            if not factura:
                raise HTTPException(status_code=404, detail="Factura no encontrada")

            # Verificar que el XML exista
            if not factura.xml_path or not os.path.exists(factura.xml_path):
                raise HTTPException(status_code=400, detail="XML no generado o no encontrado")

            # Leer contenido del XML
            with open(factura.xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()

            # Validar XML contra esquema básico SRI
            xml_generator = XMLGenerator()
            valido, mensaje = xml_generator.validar_esquema_sri(xml_content)

            return {
                "factura_id": factura_id,
                "valido": valido,
                "mensaje": mensaje,
                "xml_path": factura.xml_path
            }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error al validar XML de factura {factura_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al validar XML: {str(e)}")


@app.post("/facturas/{factura_id}/firmar")
async def firmar_factura(factura_id: int):
    """Firmar factura con certificado digital"""
    try:
        with db_manager.get_db_session() as db:
            factura_repo = FacturaRepository(db)
            factura = factura_repo.obtener_factura_por_id(factura_id)

            if not factura:
                raise HTTPException(status_code=404, detail="Factura no encontrada")

            if not factura.xml_path or not os.path.exists(factura.xml_path):
                raise HTTPException(status_code=400, detail="XML no generado")

            # Verificar que exista el certificado
            if not os.path.exists(settings.CERT_PATH):
                raise HTTPException(status_code=500, detail="Certificado digital no encontrado")

            # Firmar XML con certificado digital
            try:
                signer = XadesBesSigner(settings.CERT_PATH, settings.CERT_PASSWORD)
                xml_firmado = signer.sign_xml_file(factura.xml_path)

                # Guardar XML firmado
                xml_firmado_filename = f"factura_{factura_id}_firmada.xml"
                xml_firmado_path = os.path.join(settings.OUTPUT_FOLDER, xml_firmado_filename)

                with open(xml_firmado_path, 'w', encoding='utf-8') as f:
                    f.write(xml_firmado)

                # Actualizar ruta en base de datos
                factura_repo.actualizar_rutas_archivos(factura_id, xml_firmado_path=xml_firmado_path)
                factura_repo.actualizar_estado_factura(factura_id, "FIRMADO")

                return {
                    "message": "Factura firmada exitosamente",
                    "path": xml_firmado_path
                }

            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error al firmar documento: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error al firmar factura {factura_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/facturas/{factura_id}/generar-ride")
async def generar_ride_factura(factura_id: int):
    """Generar RIDE (PDF) de factura"""
    try:
        with db_manager.get_db_session() as db:
            factura_repo = FacturaRepository(db)
            factura = factura_repo.obtener_factura_por_id(factura_id)

            if not factura:
                raise HTTPException(status_code=404, detail="Factura no encontrada")

            # Verificar que exista el XML firmado
            if not factura.xml_firmado_path or not os.path.exists(factura.xml_firmado_path):
                raise HTTPException(status_code=400, detail="XML firmado no encontrado")

            try:
                # Generar PDF usando el generador de RIDE
                ride_generator = RideGenerator()
                pdf_bytes = ride_generator.generar_ride_factura(
                    factura.xml_firmado_path,
                    factura.numero_comprobante
                )

                # Guardar PDF
                pdf_filename = f"factura_{factura_id}.pdf"
                pdf_path = os.path.join(settings.OUTPUT_FOLDER, pdf_filename)

                # Crear directorio si no existe
                os.makedirs(settings.OUTPUT_FOLDER, exist_ok=True)

                with open(pdf_path, 'wb') as f:
                    f.write(pdf_bytes)

                # Actualizar ruta en base de datos
                factura_repo.actualizar_rutas_archivos(factura_id, pdf_path=pdf_path)

                return {
                    "message": "RIDE generado exitosamente",
                    "path": pdf_path
                }

            except Exception as e:
                logging.error(f"Error al generar RIDE para factura {factura_id}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error al generar RIDE: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error general al generar RIDE para factura {factura_id}: {str(e)}")
        # Re-raise as HTTPException for API response
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/facturas/{factura_id}/enviar-email")
async def enviar_factura_email(factura_id: int):
    """Enviar factura por correo electrónico"""
    try:
        with db_manager.get_db_session() as db:
            factura_repo = FacturaRepository(db)
            factura = factura_repo.obtener_factura_por_id(factura_id)

            if not factura:
                raise HTTPException(status_code=404, detail="Factura no encontrada")

            if not factura.cliente.email:
                raise HTTPException(status_code=400, detail="Cliente no tiene email registrado")

            # Verificar que existan los archivos necesarios
            if not factura.pdf_path or not os.path.exists(factura.pdf_path):
                raise HTTPException(status_code=400, detail="PDF de factura no generado")

            if not factura.xml_firmado_path or not os.path.exists(factura.xml_firmado_path):
                raise HTTPException(status_code=400, detail="XML firmado no generado")

            try:
                # Leer archivos
                with open(factura.pdf_path, 'rb') as pdf_file:
                    pdf_content = pdf_file.read()

                with open(factura.xml_firmado_path, 'rb') as xml_file:
                    xml_content = xml_file.read()

                # Crear mensaje
                mensaje = EmailTemplates.factura_template(
                    cliente_nombre=factura.cliente.razon_social,
                    numero_factura=factura.numero_comprobante,
                    total=str(factura.valor_total),
                    fecha_emision=factura.fecha_emision.strftime('%d/%m/%Y'),
                    clave_acceso=factura.clave_acceso
                )

                # Enviar correo
                sender = EmailSender()
                enviado = sender.enviar_factura_email(
                    destinatario=factura.cliente.email,
                    asunto=f"Factura Electrónica {factura.numero_comprobante}",
                    mensaje=mensaje,
                    pdf_ride=pdf_content,
                    xml_firmado=xml_content,
                    nombre_factura=f"factura_{factura.numero_comprobante}"
                )

                if enviado:
                    # Actualizar estado en base de datos
                    factura.email_enviado = True
                    factura.fecha_email = datetime.now()
                    db.commit()

                    return {"message": "Factura enviada por email exitosamente"}
                else:
                    raise HTTPException(status_code=500, detail="Error al enviar email")

            except FileNotFoundError as e:
                logging.error(f"Archivos no encontrados para factura {factura_id}: {str(e)}")
                raise HTTPException(status_code=500, detail="Archivos adjuntos no encontrados")
            except Exception as e:
                logging.error(f"Error al enviar email para factura {factura_id}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error al enviar email: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error al validar factura {factura_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al validar factura: {str(e)}")


# ============================================================================
# ENDPOINT PARA VALIDAR DOCUMENTOS ANTES DE ENVIAR AL SRI
# ============================================================================

@app.post("/facturas/{factura_id}/validar")
async def validar_factura_sri(
    factura_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Valida factura contra reglas SRI antes de enviar"""
    try:
        with db_manager.get_db_session() as db:
            factura_repo = FacturaRepository(db)
            factura = factura_repo.obtener_factura_por_id(factura_id)

            if not factura:
                raise HTTPException(status_code=404, detail="Factura no encontrada")

            errores = []

            # Validar clave de acceso
            valido, mensaje = SRIValidator.validar_clave_acceso(factura.clave_acceso)
            if not valido:
                errores.append(f"Clave de acceso: {mensaje}")

            # Validar número de comprobante
            valido, mensaje = SRIValidator.validar_formato_comprobante(
                factura.numero_comprobante
            )
            if not valido:
                errores.append(f"Número de comprobante: {mensaje}")

            # Validar que tenga detalles
            if not factura.detalles:
                errores.append("La factura no tiene detalles")

            # Validar montos
            total_calculado = factura.subtotal_sin_impuestos + factura.iva_12
            if abs(total_calculado - getattr(factura, "valor_total", Decimal("0.00"))) > Decimal("0.01"):
                errores.append(
                    f"El total no cuadra. Calculado: {total_calculado}, "
                    f"Registrado: {factura.valor_total}"
                )

            # Validar identificación del cliente (si viene en la factura)
            cliente_identificacion = getattr(factura, "cliente_identificacion", None)
            if not cliente_identificacion:
                # intentar extraer desde relación cliente
                cliente = getattr(factura, "cliente", None)
                if cliente:
                    cliente_identificacion = getattr(cliente, "identificacion", None)

            if cliente_identificacion:
                if isinstance(cliente_identificacion, str) and cliente_identificacion.isdigit():
                    if len(cliente_identificacion) == 13:
                        valido, mensaje = SRIValidator.validar_ruc(cliente_identificacion)
                        if not valido:
                            errores.append(f"Identificación cliente: {mensaje}")
                    elif len(cliente_identificacion) == 10:
                        valido, mensaje = SRIValidator._validar_cedula(cliente_identificacion)
                        if not valido:
                            errores.append(f"Identificación cliente: {mensaje}")
                    else:
                        errores.append("Identificación cliente con longitud inválida")
                else:
                    errores.append("Identificación cliente debe ser numérica")

            if errores:
                return {
                    "valido": False,
                    "errores": errores
                }

            return {
                "valido": True,
                "mensaje": "Factura válida para envío al SRI"
            }

    except Exception as e:
        logger.error(f"Error validando factura {factura_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/facturas/{factura_id}/generar-xml")
async def generar_xml_factura(factura_id: int):
    """Generar XML de factura"""
    try:
        with db_manager.get_db_session() as db:
            factura_repo = FacturaRepository(db)
            factura = factura_repo.obtener_factura_por_id(factura_id)

            if not factura:
                raise HTTPException(status_code=404, detail="Factura no encontrada")

            # Obtener empresa y cliente
            empresa = db.query(Empresa).filter(Empresa.id == factura.empresa_id).first()
            cliente = db.query(Cliente).filter(Cliente.id == factura.cliente_id).first()

            if not empresa or not cliente:
                raise HTTPException(status_code=500, detail="Error al obtener datos de empresa o cliente")

            # Obtener detalles de la factura
            detalles = db.query(FacturaDetalle).filter(FacturaDetalle.factura_id == factura_id).all()

            # Generar XML completo
            xml_generator = XMLGenerator()
            xml_content = xml_generator.generar_xml_factura(factura, empresa, cliente, detalles)

            # Validar XML contra esquema básico SRI
            valido, mensaje = xml_generator.validar_esquema_sri(xml_content)
            if not valido:
                raise HTTPException(status_code=500, detail=f"XML inválido: {mensaje}")

            # Guardar XML
            xml_filename = f"factura_{factura_id}.xml"
            xml_path = os.path.join(settings.OUTPUT_FOLDER, xml_filename)

            # Crear directorio si no existe
            os.makedirs(settings.OUTPUT_FOLDER, exist_ok=True)

            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)

            # Actualizar ruta en base de datos
            factura_repo.actualizar_rutas_archivos(factura_id, xml_path=xml_path)

            return {
                "message": "XML generado exitosamente",
                "path": xml_path,
                "content": xml_content[:1000] + "..." if len(xml_content) > 1000 else xml_content,
                "valido": True,
                "mensaje_validacion": mensaje
            }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error al generar XML de factura {factura_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar XML: {str(e)}")
        for dir_path in directories:
            os.makedirs(dir_path, exist_ok=True)
        dirs_ok = True

    return {
        "status": "healthy" if db_ok and dirs_ok else "unhealthy",
        "database": "connected" if db_ok else "disconnected",
        "directories": "accessible" if dirs_ok else "inaccessible",
        "timestamp": datetime.now()
    }

# ============================================================================
# ENDPOINTS DEL DASHBOARD
# ============================================================================

@app.get("/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """Obtener estadísticas del dashboard"""
    try:
        with db_manager.get_db_session() as db:
            from sqlalchemy import func
            from datetime import timedelta
            
            hoy = datetime.now()
            inicio_mes = hoy.replace(day=1)
            mes_anterior = (inicio_mes - timedelta(days=1)).replace(day=1)
            
            # Facturas del mes
            facturas_mes = db.query(func.count(Factura.id)).filter(
                Factura.fecha_emision >= inicio_mes
            ).scalar() or 0
            
            facturas_mes_anterior = db.query(func.count(Factura.id)).filter(
                Factura.fecha_emision >= mes_anterior,
                Factura.fecha_emision < inicio_mes
            ).scalar() or 0
            
            # Ventas del mes
            ventas_mes = db.query(func.sum(Factura.valor_total)).filter(
                Factura.fecha_emision >= inicio_mes
            ).scalar() or Decimal("0")
            
            ventas_mes_anterior = db.query(func.sum(Factura.valor_total)).filter(
                Factura.fecha_emision >= mes_anterior,
                Factura.fecha_emision < inicio_mes
            ).scalar() or Decimal("0")
            
            # Clientes y productos activos
            clientes_activos = db.query(func.count(Cliente.id)).filter(
                Cliente.activo == True
            ).scalar() or 0
            
            productos_activos = db.query(func.count(Producto.id)).filter(
                Producto.activo == True
            ).scalar() or 0
            
            return {
                "facturas_mes": facturas_mes,
                "delta_facturas": facturas_mes - facturas_mes_anterior,
                "ventas_mes": float(ventas_mes),
                "delta_ventas": float(ventas_mes - ventas_mes_anterior),
                "clientes_activos": clientes_activos,
                "delta_clientes": 0,
                "productos_activos": productos_activos
            }
            
    except Exception as e:
        logger.error(f"Error en dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard/ventas-mensuales")
async def get_ventas_mensuales(current_user: dict = Depends(get_current_user)):
    """Ventas mensuales"""
    try:
        with db_manager.get_db_session() as db:
            from sqlalchemy import func, extract
            
            seis_meses_atras = datetime.now() - timedelta(days=180)
            
            ventas = db.query(
                extract('month', Factura.fecha_emision).label('month'),
                func.sum(Factura.valor_total).label('total')
            ).filter(
                Factura.fecha_emision >= seis_meses_atras
            ).group_by('month').all()
            
            meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            
            return [{"mes": meses[int(v.month)-1], "total": float(v.total)} for v in ventas]
            
    except Exception as e:
        logger.error(f"Error ventas mensuales: {str(e)}")
        return []


@app.get("/dashboard/facturas-estado")
async def get_facturas_estado(current_user: dict = Depends(get_current_user)):
    """Facturas por estado"""
    try:
        with db_manager.get_db_session() as db:
            from sqlalchemy import func
            
            estados = db.query(
                Factura.estado_sri,
                func.count(Factura.id).label('cantidad')
            ).group_by(Factura.estado_sri).all()
            
            return [{"estado": e.estado_sri or "PENDIENTE", "cantidad": e.cantidad} for e in estados]
            
    except Exception as e:
        logger.error(f"Error facturas estado: {str(e)}")
        return []


@app.get("/dashboard/alertas")
async def get_alertas(current_user: dict = Depends(get_current_user)):
    """Alertas del sistema"""
    return []

## fin endpoints

if __name__ == "__main__":
    import uvicorn

    print("Iniciando API de Facturación Electrónica SRI Ecuador...")
    print(f"Entorno: {'Producción' if settings.SRI_AMBIENTE == '2' else 'Pruebas'}")
    print(f"Empresa: {settings.EMPRESA_RAZON_SOCIAL}")

    # Verificar conexión a base de datos
    if db_manager.test_connection():
        print("✓ Conexión a base de datos exitosa")
    else:
        print("✗ Error en conexión a base de datos")

    # Crear directorios necesarios
    directories = [settings.OUTPUT_FOLDER, settings.UPLOAD_FOLDER, settings.TEMP_FOLDER, settings.CERTIFICADOS_FOLDER]
    for dir_path in directories:
        os.makedirs(dir_path, exist_ok=True)
        print(f"✓ Directorio {dir_path} listo")

    # Iniciar servidor

    # Obtener instancias de métricas
    app_metrics = get_app_metrics()

# Endpoints de monitoreo y métricas
@app.get("/metrics")
async def get_metrics():
    """Endpoint para obtener métricas de la aplicación"""
    try:
        metrics_data = get_metrics_collector().get_summary()
        cache_stats = get_cache_stats()
        db_info = db_manager.get_connection_info()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": metrics_data,
            "cache": cache_stats,
            "database": db_info
        }
    except Exception as e:
        logger.error(f"Error al obtener métricas: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al obtener métricas")


@app.get("/metrics/export")
async def export_metrics():
    """Exportar métricas a archivo"""
    try:
        import os
        from datetime import datetime

        # Crear directorio si no existe
        os.makedirs("metrics", exist_ok=True)

        # Generar nombre de archivo con timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filepath = f"metrics/metrics_{timestamp}.json"

        # Exportar métricas
        get_metrics_collector().export_to_file(filepath)

        return {
            "message": "Métricas exportadas exitosamente",
            "filepath": filepath,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error al exportar métricas: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al exportar métricas")


@app.post("/cache/clear")
async def clear_cache():
    """Limpiar todos los caches"""
    try:
        from utils.cache import cache_manager

        cache_manager.clear_all()

        return {
            "message": "Todos los caches han sido limpiados",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error al limpiar cache: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al limpiar cache")


@app.get("/system/info")
async def get_system_info():
    """Obtener información del sistema"""
    try:
        import psutil
        import platform

        # Información del sistema
        system_info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "free": psutil.disk_usage('/').free,
                "percent": psutil.disk_usage('/').percent
            }
        }

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system": system_info,
            "application": {
                "name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "debug": settings.DEBUG
            }
        }
    except Exception as e:
        logger.error(f"Error al obtener información del sistema: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al obtener información del sistema")


# Middleware mejorado para métricas
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware para recopilar métricas de requests"""
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time

    # Registrar métricas
    try:
        app_metrics.record_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
            duration=duration
        )
    except Exception as e:
        logger.debug(f"No se pudo registrar métrica de request: {e}")

    return response


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Iniciando {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Modo debug: {settings.DEBUG}")

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug"
    )

# ============================================================================
# VALIDADORES MEJORADOS PARA CUMPLIMIENTO SRI ECUADOR
# ============================================================================

from decimal import Decimal
import re
from typing import Dict, Tuple
from fastapi import HTTPException

# Duplicate SRIValidator removed — the primary SRIValidator implementation is used elsewhere.
# Se reemplaza la clase duplicada por una función local para validar montos de factura,
# de modo que las validaciones específicas queden disponibles sin duplicar la clase.
def validar_montos_factura(detalles: list) -> Tuple[bool, str]:
        """Valida que los cálculos de la factura sean correctos (reemplazo del duplicado SRIValidator)"""
        subtotal = Decimal("0.00")

        for detalle in detalles:
            cantidad = Decimal(str(detalle.get('cantidad', 0)))
            precio = Decimal(str(detalle.get('precio_unitario', 0)))
            descuento = Decimal(str(detalle.get('descuento', 0)))

            if cantidad <= 0:
                return False, "La cantidad debe ser mayor a cero"

            if precio <= 0:
                return False, "El precio unitario debe ser mayor a cero"

            if descuento < 0:
                return False, "El descuento no puede ser negativo"

            total_item = (cantidad * precio) - descuento

            if total_item < 0:
                return False, "El descuento no puede ser mayor al subtotal del ítem"

            subtotal += total_item

        return True, "Montos válidos"


# ============================================================================
# ENDPOINT CORREGIDO PARA CREAR FACTURAS
# ============================================================================

@app.post("/facturas/", response_model=FacturaResponse)
async def crear_factura(
    factura_data: FacturaCreate,
    current_user: dict = Depends(get_current_user)
):
    """Crear factura con validaciones completas SRI"""
    try:
        with db_manager.get_db_session() as db:
            # 1. VALIDACIONES PREVIAS
            cliente_repo = ClienteRepository(db)
            producto_repo = ProductoRepository(db)
            factura_repo = FacturaRepository(db)

            cliente = cliente_repo.obtener_cliente_por_id(factura_data.cliente_id)
            if not cliente:
                raise HTTPException(status_code=404, detail="Cliente no encontrado")

            # Validar identificación del cliente
            if cliente.tipo_identificacion == "04":  # RUC
                if not SRIValidator.validar_ruc(cliente.identificacion):
                    raise HTTPException(
                        status_code=400,
                        detail=f"RUC del cliente inválido: {cliente.identificacion}"
                    )
            elif cliente.tipo_identificacion == "05":  # Cédula
                if not SRIValidator._validar_cedula(cliente.identificacion):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cédula del cliente inválida: {cliente.identificacion}"
                    )

            # Validar montos
            valido, mensaje = SRIValidator.validar_montos_factura(
                [d.dict() for d in factura_data.detalles]
            )
            if not valido:
                raise HTTPException(status_code=400, detail=mensaje)

            # 2. PROCESAR DETALLES Y CALCULAR TOTALES
            detalles_procesados = []
            subtotal_sin_impuestos = Decimal("0.00")
            subtotal_12 = Decimal("0.00")
            subtotal_0 = Decimal("0.00")
            iva_12 = Decimal("0.00")
            total_descuento = Decimal("0.00")

            for detalle_data in factura_data.detalles:
                producto = producto_repo.obtener_producto_por_codigo(
                    detalle_data.codigo_principal
                )
                if not producto:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Producto no encontrado: {detalle_data.codigo_principal}"
                    )

                cantidad = detalle_data.cantidad
                precio_unitario = detalle_data.precio_unitario
                descuento = detalle_data.descuento or Decimal("0.00")

                precio_total_sin_impuesto = (cantidad * precio_unitario) - descuento

                # Clasificar por tarifa IVA
                if producto.porcentaje_iva > 0:
                    subtotal_12 += precio_total_sin_impuesto
                    iva_item = precio_total_sin_impuesto * producto.porcentaje_iva
                    iva_12 += iva_item
                else:
                    subtotal_0 += precio_total_sin_impuesto

                subtotal_sin_impuestos += precio_total_sin_impuesto
                total_descuento += descuento

                # Crear detalle completo
                detalle_completo = {
                    "codigo_principal": detalle_data.codigo_principal,
                    "codigo_auxiliar": detalle_data.codigo_auxiliar or producto.codigo_auxiliar,
                    "descripcion": detalle_data.descripcion or producto.descripcion,
                    "cantidad": cantidad,
                    "precio_unitario": precio_unitario,
                    "descuento": descuento,
                    "precio_total_sin_impuesto": precio_total_sin_impuesto,
                    "codigo_impuesto": producto.codigo_impuesto,
                    "porcentaje_iva": producto.porcentaje_iva,
                    "base_imponible": precio_total_sin_impuesto,
                    "valor_iva": precio_total_sin_impuesto * producto.porcentaje_iva if producto.porcentaje_iva > 0 else Decimal("0.00")
                }
                detalles_procesados.append(detalle_completo)

            valor_total = subtotal_sin_impuestos + iva_12

            # 3. GENERAR NÚMERO DE COMPROBANTE Y CLAVE DE ACCESO
            from datetime import datetime
            fecha_emision = datetime.now()

            # Obtener siguiente secuencial
            secuencial = factura_repo.obtener_siguiente_secuencial("01")  # Factura
            numero_comprobante = f"001-001-{str(secuencial).zfill(9)}"

            # Validar formato
            valido, mensaje = SRIValidator.validar_formato_comprobante(numero_comprobante)
            if not valido:
                raise HTTPException(status_code=500, detail=mensaje)

            # Generar clave de acceso
            clave_acceso = ClaveAccesoGenerator.generar_clave_acceso(
                fecha_emision=fecha_emision,
                tipo_comprobante="01",
                ruc=settings.EMPRESA_RUC,
                ambiente=settings.SRI_AMBIENTE,
                serie="001001",
                numero=str(secuencial).zfill(9)
            )

            # Validar clave de acceso
            valido, mensaje = SRIValidator.validar_clave_acceso(clave_acceso)
            if not valido:
                raise HTTPException(status_code=500, detail=f"Clave de acceso inválida: {mensaje}")

            # 4. CREAR FACTURA EN BASE DE DATOS
            factura_dict = {
                "empresa_id": 1,
                "establecimiento_id": 1,
                "punto_emision_id": 1,
                "cliente_id": factura_data.cliente_id,
                "tipo_comprobante": "01",
                "numero_comprobante": numero_comprobante,
                "fecha_emision": fecha_emision,
                "ambiente": settings.SRI_AMBIENTE,
                "tipo_emision": settings.SRI_TIPO_EMISION,
                "clave_acceso": clave_acceso,
                "subtotal_sin_impuestos": subtotal_sin_impuestos,
                "subtotal_0": subtotal_0,
                "subtotal_12": subtotal_12,
                "iva_12": iva_12,
                "total_descuento": total_descuento,
                "valor_total": valor_total,
                "moneda": "DOLAR",
                "observaciones": factura_data.observaciones
            }

            factura = factura_repo.crear_factura(factura_dict)

            # 5. CREAR DETALLES DE FACTURA (ESTO FALTABA)
            for detalle in detalles_procesados:
                detalle_db = FacturaDetalle(
                    factura_id=factura.id,
                    **detalle
                )
                db.add(detalle_db)

                # Crear impuesto del detalle
                impuesto_db = FacturaDetalleImpuesto(
                    detalle_id=detalle_db.id,
                    codigo="2",  # IVA
                    codigo_porcentaje="2" if detalle['porcentaje_iva'] > 0 else "0",
                    tarifa=detalle['porcentaje_iva'],
                    base_imponible=detalle['base_imponible'],
                    valor=detalle['valor_iva']
                )
                db.add(impuesto_db)

            db.commit()
            db.refresh(factura)

            logger.info(f"Factura creada: {numero_comprobante} - Total: ${valor_total}")

            return FacturaResponse(
                id=factura.id,
                numero_comprobante=factura.numero_comprobante,
                fecha_emision=factura.fecha_emision,
                clave_acceso=factura.clave_acceso,
                subtotal_sin_impuestos=factura.subtotal_sin_impuestos,
                subtotal_0=factura.subtotal_0,
                subtotal_12=factura.subtotal_12,
                iva_12=factura.iva_12,
                valor_total=factura.valor_total,
                estado_sri=factura.estado_sri,
                created_at=factura.created_at
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al crear factura: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al crear factura: {str(e)}"
        )


# ============================================================================
# ENDPOINT PARA VALIDAR DOCUMENTOS ANTES DE ENVIAR AL SRI
# ============================================================================

@app.post("/facturas/{factura_id}/validar")
async def validar_factura_sri(
    factura_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Endpoint duplicado eliminado. Use la ruta principal para validación."""
    # Esta ruta estaba duplicada en el código. Se mantiene el nombre y la firma
    # para evitar romper rutas existentes, pero se marca como retirada y no
    # Esta ruta ha sido retirada. Use el endpoint principal para validación.
    # Se mantiene la firma para no romper rutas existentes, pero el endpoint
    # responde con 410 Gone indicando que es un duplicado retirado.
    raise HTTPException(
        status_code=410,
        detail="Endpoint duplicado. Esta ruta ha sido retirada; use el endpoint principal de validación."
    )


# ============================================================================
# CLASE PARA VALIDACIONES SRI
# ============================================================================

class SRIValidator:
    """Validaciones específicas para normativas del SRI Ecuador"""

    @staticmethod
    def validar_ruc(ruc: str) -> tuple[bool, str]:
        """Valida RUC ecuatoriano según tipo de contribuyente"""
        if not ruc or not isinstance(ruc, str):
            return False, "RUC no puede estar vacío"
        ruc = ruc.strip()
        if len(ruc) != 13:
            return False, "RUC debe tener 13 dígitos"
        if not ruc.isdigit():
            return False, "RUC solo debe contener dígitos"
        tercer = int(ruc[2])
        if tercer < 6:
            # Persona natural: verificar módulo 10 para cédula
            coef = [2, 1, 2, 1, 2, 1, 2, 1, 2]
            total = 0
            for i in range(9):
                val = int(ruc[i]) * coef[i]
                total += val if val < 10 else (val - 9)
            ver = 10 - (total % 10)
            if ver == 10:
                ver = 0
            if ver == int(ruc[9]):
                return True, "RUC válido"
            return False, "RUC inválido para persona natural"
        elif tercer == 6:
            # Público: módulo 11 con coeficientes
            coef = [3, 2, 7, 6, 5, 4, 3, 2]
            total = sum(int(ruc[i]) * coef[i] for i in range(8))
            ver = 11 - (total % 11)
            if ver == 11:
                ver = 0
            if ver == int(ruc[8]):
                return True, "RUC válido"
            return False, "RUC inválido para entidad pública"
        elif tercer == 9:
            # Sociedad privada: módulo 11 con coeficientes
            coef = [4, 3, 2, 7, 6, 5, 4, 3, 2]
            total = sum(int(ruc[i]) * coef[i] for i in range(9))
            ver = 11 - (total % 11)
            if ver == 11:
                ver = 0
            if ver == int(ruc[9]):
                return True, "RUC válido"
            return False, "RUC inválido para sociedad privada"
        else:
            return False, "Tercer dígito no válido"

    @staticmethod
    def validar_montos(total: float, subtotal: float, impuestos: float) -> tuple[bool, str]:
        """Valida que la suma de componentes coincida con el total"""
        try:
            total = float(total)
            subtotal = float(subtotal)
            impuestos = float(impuestos)
        except (TypeError, ValueError):
            return False, "Montos deben ser numéricos"
        # Tolerancia pequeña por redondeos
        if abs((subtotal + impuestos) - total) > 0.01:
            return False, "Montos no coinciden"
        return True, "Montos válidos"


# ============================================================================
# ENDPOINTS PARA ENVÍO Y AUTORIZACIÓN SRI (SIMULADOS)
# ============================================================================

@app.post("/sri/submit", status_code=200)
async def sri_submit(payload: dict, current_user: dict = Depends(get_current_user)):
    """
    Enviar comprobante al SRI para validación/envío (simulado).
    Realiza validaciones locales básicas y devuelve un estado de envío.
    """
    # Validaciones mínimas
    ruc = payload.get("ruc")
    ok, msg = SRIValidator.validar_ruc(ruc)
    if not ok:
        raise HTTPException(status_code=400, detail=f"RUC inválido: {msg}")

    ok, msg = SRIValidator.validar_montos(payload.get("total"), payload.get("subtotal"), payload.get("impuestos"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    # Simulación de envío: en producción aquí se consumiría la API del SRI
    # Retornamos estructura mínima con estado de envío
    return {
        "status": "submitted",
        "message": "Comprobante enviado (simulado)",
        "ruc": ruc,
        "reference": payload.get("reference_id")
    }


@app.post("/sri/authorize", status_code=200)
async def sri_authorize(reference_id: str, current_user: dict = Depends(get_current_user)):
    """
    Solicitar autorización del comprobante al SRI (simulado).
    Devuelve estado 'authorized' o 'rejected' según referencia.
    """
    if not reference_id:
        raise HTTPException(status_code=400, detail="reference_id es requerido")

    # Simulación de autorización: en producción se consultaría estado real del SRI
    # Para demo retornamos autorizado si referencia no contiene 'fail'
    if "fail" in reference_id.lower():
        return {"status": "rejected", "message": "Autorización denegada por SRI", "reference": reference_id}
    return {"status": "authorized", "message": "Comprobante autorizado (simulado)", "reference": reference_id}

    @staticmethod
    def validar_ruc(ruc: str) -> tuple[bool, str]:
        """Valida RUC ecuatoriano según tipo de contribuyente"""
        if not ruc or not isinstance(ruc, str):
            return False, "RUC no puede estar vacío"

        # Limpiar RUC
        ruc = ruc.strip()

        # Validar longitud
        if len(ruc) != 13:
            return False, "RUC debe tener 13 dígitos"

        # Validar que sean solo números
        if not ruc.isdigit():
            return False, "RUC solo debe contener números"

        # Validar código de establecimiento (últimos 3 dígitos)
        if ruc[10:] != "001":
            return False, "Código de establecimiento debe ser 001"

        # Extraer número base (primeros 10 dígitos)
        numero_base = ruc[:10]

        # Determinar tipo de contribuyente por tercer dígito
        tercer_digito = int(numero_base[2])

        if tercer_digito < 6:
            # Persona natural
            return SRIValidator._validar_cedula(numero_base)
        elif tercer_digito == 6:
            # Sociedad pública
            return SRIValidator._validar_sector_publico(numero_base)
        elif tercer_digito == 9:
            # Persona jurídica (sociedad privada)
            return SRIValidator._validar_sociedad_privada(numero_base)
        else:
            return False, f"Tercer dígito inválido: {tercer_digito}"

    @staticmethod
    def _validar_cedula(cedula: str) -> tuple[bool, str]:
        """Valida cédula ecuatoriana usando algoritmo módulo 10"""
        if len(cedula) != 10:
            return False, "Cédula debe tener 10 dígitos"

        # Validar provincia (primeros 2 dígitos)
        try:
            provincia = int(cedula[:2])
        except ValueError:
            return False, "Cédula contiene caracteres inválidos"

        if provincia < 1 or provincia > 24:
            return False, f"Código de provincia inválido: {provincia}"

        # Algoritmo módulo 10
        coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        suma = 0

        for i in range(9):
            valor = int(cedula[i]) * coeficientes[i]
            if valor >= 10:
                valor = sum(int(d) for d in str(valor))
            suma += valor

        digito_verificador = (10 - (suma % 10)) % 10

        if digito_verificador != int(cedula[9]):
            return False, "Dígito verificador inválido"

        return True, "Cédula válida"

    @staticmethod
    def _validar_sector_publico(ruc: str) -> tuple[bool, str]:
        """Valida RUC de sector público (tercer dígito = 6)"""
        # Para sector público, validar los primeros 9 dígitos + dígito verificador
        coeficientes = [3, 2, 7, 6, 5, 4, 3, 2]
        suma = 0

        for i in range(8):
            suma += int(ruc[i]) * coeficientes[i]

        digito_verificador = (11 - (suma % 11)) % 11

        if digito_verificador == 10:
            # Para sector público, 10 se considera como 0
            digito_verificador = 0

        if digito_verificador != int(ruc[8]):
            return False, "Dígito verificador inválido para entidad pública"

        return True, "RUC de entidad pública válido"

    @staticmethod
    def _validar_sociedad_privada(ruc: str) -> tuple[bool, str]:
        """Valida RUC de sociedad privada (tercer dígito = 9)"""
        # Para sociedad privada, validar con coeficientes diferentes
        coeficientes = [4, 3, 2, 7, 6, 5, 4, 3, 2]
        suma = 0

        for i in range(9):
            suma += int(ruc[i]) * coeficientes[i]

        digito_verificador = (11 - (suma % 11)) % 11

        if digito_verificador == 10:
            # Para sociedad privada, 10 se considera como 0
            digito_verificador = 0

        if digito_verificador != int(ruc[9]):
            return False, "Dígito verificador inválido para sociedad privada"

        return True, "RUC de sociedad privada válido"

    @staticmethod
    def validar_clave_acceso(clave: str) -> tuple[bool, str]:
        """Valida formato de clave de acceso SRI (49 dígitos)"""
        if not clave:
            return False, "Clave de acceso no puede estar vacía"

        # Validar longitud
        if len(clave) != 49:
            return False, f"Clave de acceso debe tener 49 dígitos, tiene {len(clave)}"

        # Validar que sean solo números
        if not clave.isdigit():
            return False, "Clave de acceso solo debe contener números"

        # Validar dígito verificador (último dígito)
        # Usar algoritmo módulo 11 para verificar
        coeficientes = [2, 3, 4, 5, 6, 7]
        suma = 0

        # Aplicar coeficientes a los primeros 48 dígitos en orden inverso
        for i in range(48):
            coeficiente = coeficientes[i % 6]
            suma += int(clave[47 - i]) * coeficiente

        digito_verificador = (11 - (suma % 11)) % 11

        if digito_verificador == 11:
            digito_verificador = 0
        elif digito_verificador == 10:
            # En caso de 10, se considera inválido
            return False, "Clave de acceso inválida (dígito verificador 10 no permitido)"

        if digito_verificador != int(clave[48]):
            return False, f"Clave de acceso inválida (dígito verificador incorrecto)"

        return True, "Clave de acceso válida"

    @staticmethod
    def validar_formato_comprobante(numero: str) -> tuple[bool, str]:
        """Valida formato de número de comprobante (establecimiento-punto-emisión-secuencial)"""
        if not numero:
            return False, "Número de comprobante no puede estar vacío"

        # Formato esperado: XXX-XXX-XXXXXXXXX
        partes = numero.split('-')

        if len(partes) != 3:
            return False, "Formato inválido. Debe ser: Establecimiento-PuntoEmisión-Secuencial"

        # Validar longitudes
        if len(partes[0]) != 3 or len(partes[1]) != 3 or len(partes[2]) != 9:
            return False, "Formato inválido. Longitudes: 3-3-9"

        # Validar que sean números
        if not all(p.isdigit() for p in partes):
            return False, "Todos los componentes deben ser numéricos"

        # Validar establecimiento (001)
        if partes[0] != "001":
            return False, "Código de establecimiento debe ser 001"

        # Validar punto de emisión (001)
        if partes[1] != "001":
            return False, "Código de punto de emisión debe ser 001"

        # Validar secuencial
        if int(partes[2]) == 0:
            return False, "Número secuencial no puede ser 000000000"

        return True, "Formato de comprobante válido"

    @staticmethod
    def validar_montos_factura(detalles: list) -> tuple[bool, str]:
        """Valida montos y cálculos de factura"""
        if not detalles:
            return False, "No hay detalles en la factura"

        subtotal = Decimal("0.00")

        for detalle in detalles:
            cantidad = Decimal(str(detalle.get('cantidad', 0)))
            precio = Decimal(str(detalle.get('precio_unitario', 0)))
            descuento = Decimal(str(detalle.get('descuento', 0)))

            # Validar valores positivos
            if cantidad <= 0:
                return False, f"Cantidad debe ser positiva: {cantidad}"

            if precio <= 0:
                return False, f"Precio debe ser positivo: {precio}"

            if descuento < 0:
                return False, f"Descuento no puede ser negativo: {descuento}"

            # Validar que descuento no exceda el subtotal
            subtotal_item = cantidad * precio
            if descuento > subtotal_item:
                return False, f"Descuento ${descuento} excede subtotal del ítem ${subtotal_item}"

            total_item = subtotal_item - descuento

            if total_item < 0:
                return False, f"El descuento no puede ser mayor al subtotal del ítem"

            subtotal += total_item

        return True, "Montos válidos"


# ============================================================================
# CLASE PARA GENERACIÓN DE XML DE FACTURAS SRI
# ============================================================================

class XMLGenerator:
    """Generador de XML para facturas electrónicas SRI Ecuador"""

    def generar_xml_factura(self, factura, empresa, cliente, detalles) -> str:
        """Genera XML completo de factura según esquema SRI"""
        from datetime import datetime
        import xml.etree.ElementTree as ET
        from xml.dom import minidom

        try:
            # Crear documento XML
            factura_element = ET.Element("factura")
            factura_element.set("id", "comprobante")
            factura_element.set("version", "1.1.0")

            # Información de acceso
            info_acceso = ET.SubElement(factura_element, "infoTributaria")
            self._agregar_info_tributaria(info_acceso, factura, empresa)

            # Información de factura
            info_factura = ET.SubElement(factura_element, "infoFactura")
            # pasar empresa también para campos que pertenecen a la empresa
            self._agregar_info_factura(info_factura, factura, cliente, empresa)

            # Detalles
            detalles_element = ET.SubElement(factura_element, "detalles")
            self._agregar_detalles(detalles_element, detalles)

            # Adicionales (opcional)
            if hasattr(factura, 'observaciones') and factura.observaciones:
                info_adicional = ET.SubElement(factura_element, "infoAdicional")
                self._agregar_info_adicional(info_adicional, factura.observaciones)

            # Convertir a string XML con formato
            rough_string = ET.tostring(factura_element, encoding='utf-8')
            reparsed = minidom.parseString(rough_string)
            xml_formatted = reparsed.toprettyxml(indent="  ", encoding='utf-8')

            # Limpiar líneas vacías
            lines = [line for line in xml_formatted.decode('utf-8').split('\n') if line.strip()]
            return '\n'.join(lines)

        except Exception as e:
            logger.error(f"Error generando XML de factura: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generando XML: {str(e)}")

    def _agregar_info_tributaria(self, parent, factura, empresa):
        """Agrega información tributaria al XML"""
        import xml.etree.ElementTree as ET

        # Datos obligatorios de información tributaria
        ET.SubElement(parent, "ambiente").text = str(getattr(empresa, 'ambiente', '1'))  # 1=Pruebas, 2=Producción
        ET.SubElement(parent, "tipoEmision").text = str(getattr(empresa, 'tipo_emision', '1'))  # 1=Normal
        ET.SubElement(parent, "razonSocial").text = getattr(empresa, 'razon_social', '')
        ET.SubElement(parent, "nombreComercial").text = getattr(empresa, 'nombre_comercial', '')
        ET.SubElement(parent, "ruc").text = getattr(empresa, 'ruc', '')
        ET.SubElement(parent, "claveAcceso").text = getattr(factura, 'clave_acceso', '')
        ET.SubElement(parent, "codDoc").text = "01"  # 01=Factura
        ET.SubElement(parent, "estab").text = getattr(factura, 'establecimiento', '001')
        ET.SubElement(parent, "ptoEmi").text = getattr(factura, 'punto_emision', '001')
        ET.SubElement(parent, "secuencial").text = str(getattr(factura, 'secuencial', '')).zfill(9)
        ET.SubElement(parent, "dirMatriz").text = getattr(empresa, 'direccion_matriz', '')

    def _agregar_info_factura(self, parent, factura, cliente, empresa):
        """Agrega información de factura al XML"""
        import xml.etree.ElementTree as ET
        from datetime import datetime

        # Fechas
        fecha_emision = getattr(factura, 'fecha_emision', datetime.now())
        ET.SubElement(parent, "fechaEmision").text = fecha_emision.strftime("%d/%m/%Y")
        ET.SubElement(parent, "dirEstablecimiento").text = getattr(factura, 'direccion_establecimiento', getattr(empresa, 'direccion_establecimiento', ''))

        # Contribuyente especial (si aplica)
        if hasattr(empresa, 'contribuyente_especial') and getattr(empresa, 'contribuyente_especial'):
            ET.SubElement(parent, "contribuyenteEspecial").text = str(empresa.contribuyente_especial)

        ET.SubElement(parent, "obligadoContabilidad").text = "SI"  # Por defecto

        # Cliente
        ET.SubElement(parent, "tipoIdentificacionComprador").text = getattr(cliente, 'tipo_identificacion', '05')  # 05=Cédula, 04=RUC
        ET.SubElement(parent, "razonSocialComprador").text = getattr(cliente, 'razon_social', getattr(cliente, 'nombres', ''))
        ET.SubElement(parent, "identificacionComprador").text = getattr(cliente, 'identificacion', '')
        ET.SubElement(parent, "direccionComprador").text = getattr(cliente, 'direccion', '')

        # Totales
        ET.SubElement(parent, "totalSinImpuestos").text = str(getattr(factura, 'subtotal_sin_impuestos', '0.00'))
        ET.SubElement(parent, "totalDescuento").text = str(getattr(factura, 'total_descuento', '0.00'))

        # Impuestos
        total_con_impuestos = ET.SubElement(parent, "totalConImpuestos")
        total_impuesto = ET.SubElement(total_con_impuestos, "totalImpuesto")
        ET.SubElement(total_impuesto, "codigo").text = "2"  # IVA
        ET.SubElement(total_impuesto, "codigoPorcentaje").text = "2"  # 12%
        ET.SubElement(total_impuesto, "baseImponible").text = str(getattr(factura, 'subtotal_12', '0.00'))
        ET.SubElement(total_impuesto, "valor").text = str(getattr(factura, 'iva_12', '0.00'))

        # Si hay IVA 0%
        if hasattr(factura, 'subtotal_0') and getattr(factura, 'subtotal_0', 0) and float(getattr(factura, 'subtotal_0', 0)) > 0:
            total_impuesto_0 = ET.SubElement(total_con_impuestos, "totalImpuesto")
            ET.SubElement(total_impuesto_0, "codigo").text = "2"  # IVA
            ET.SubElement(total_impuesto_0, "codigoPorcentaje").text = "0"  # 0%
            ET.SubElement(total_impuesto_0, "baseImponible").text = str(getattr(factura, 'subtotal_0', '0.00'))
            ET.SubElement(total_impuesto_0, "valor").text = "0.00"

        ET.SubElement(parent, "propina").text = "0.00"
        ET.SubElement(parent, "importeTotal").text = str(getattr(factura, 'valor_total', '0.00'))
        ET.SubElement(parent, "moneda").text = "DOLAR"

    def _agregar_detalles(self, parent, detalles):
        """Agrega detalles de factura al XML"""
        import xml.etree.ElementTree as ET

        for detalle in detalles:
            detalle_element = ET.SubElement(parent, "detalle")

            ET.SubElement(detalle_element, "codigoPrincipal").text = getattr(detalle, 'codigo_principal', '')
            ET.SubElement(detalle_element, "codigoAuxiliar").text = getattr(detalle, 'codigo_auxiliar', '') or ''
            ET.SubElement(detalle_element, "descripcion").text = getattr(detalle, 'descripcion', '')
            ET.SubElement(detalle_element, "cantidad").text = str(getattr(detalle, 'cantidad', '0'))
            ET.SubElement(detalle_element, "precioUnitario").text = str(getattr(detalle, 'precio_unitario', '0.00'))
            ET.SubElement(detalle_element, "descuento").text = str(getattr(detalle, 'descuento', '0.00'))
            ET.SubElement(detalle_element, "precioTotalSinImpuesto").text = str(getattr(detalle, 'precio_total_sin_impuesto', '0.00'))

            # Impuestos del detalle
            impuestos = ET.SubElement(detalle_element, "impuestos")
            impuesto = ET.SubElement(impuestos, "impuesto")

            ET.SubElement(impuesto, "codigo").text = str(getattr(detalle, 'codigo_impuesto', '2'))  # IVA
            porcentaje = getattr(detalle, 'porcentaje_iva', 0)
            try:
                codigo_porcentaje = "2" if float(porcentaje) > 0 else "0"
            except Exception:
                codigo_porcentaje = "0"
            ET.SubElement(impuesto, "codigoPorcentaje").text = codigo_porcentaje
            ET.SubElement(impuesto, "tarifa").text = str(getattr(detalle, 'porcentaje_iva', '0.00'))
            ET.SubElement(impuesto, "baseImponible").text = str(getattr(detalle, 'base_imponible', '0.00'))
            ET.SubElement(impuesto, "valor").text = str(getattr(detalle, 'valor_iva', '0.00'))

    def _agregar_info_adicional(self, parent, observaciones):
        """Agrega información adicional al XML"""
        import xml.etree.ElementTree as ET

        campo = ET.SubElement(parent, "campoAdicional")
        campo.set("nombre", "Observaciones")
        campo.text = observaciones

    def validar_esquema_sri(self, xml_content: str) -> tuple[bool, str]:
        """Valida XML contra esquema XSD del SRI"""
        try:
            # Esta es una implementación básica de validación
            # En producción, se debería usar el XSD oficial del SRI

            # Verificar que tenga los elementos obligatorios
            required_elements = [
                'factura', 'infoTributaria', 'infoFactura', 'detalles'
            ]

            # Verificar estructura básica
            if not xml_content.strip().startswith('<?xml') and not xml_content.strip().startswith('<factura'):
                return False, "XML no tiene estructura válida"

            # Verificar elementos obligatorios
            for element in required_elements:
                if f'<{element}' not in xml_content:
                    return False, f"Falta elemento obligatorio: {element}"

            return True, "XML válido según estructura básica"

        except Exception as e:
            return False, f"Error validando XML: {str(e)}"


# ============================================================================
# CLASE PARA GENERACIÓN DE CLAVE DE ACCESO SRI
# ============================================================================

class ClaveAccesoGenerator:
    """Generador de clave de acceso para documentos SRI Ecuador"""

    @staticmethod
    def generar_clave_acceso(fecha_emision, tipo_comprobante, ruc, ambiente,
                             serie, numero) -> str:
        """Genera clave de acceso de 49 dígitos según especificaciones SRI"""
        from datetime import datetime

        # Formato de fecha: DDMMYYYY
        if isinstance(fecha_emision, datetime):
            fecha_str = fecha_emision.strftime("%d%m%Y")
        else:
            fecha_str = fecha_emision

        # Completar serie a 6 dígitos y número a 9 dígitos
        serie_completa = str(serie).zfill(6)
        numero_completo = str(numero).zfill(9)

        # Tipo de emisión (1=Normal, 2=Indisponibilidad)
        tipo_emision = "1"

        # Código numérico (aleatorio de 8 dígitos)
        import random
        codigo_numerico = str(random.randint(10000000, 99999999))

        # Construir cadena de 48 dígitos
        cadena = (
            fecha_str +                    # 8 dígitos (DDMMYYYY)
            str(tipo_comprobante).zfill(2) +    # 2 dígitos (01=Factura)
            str(ruc).zfill(13) +           # 13 dígitos (RUC empresa)
            str(ambiente) +                # 1 dígito (1=Pruebas, 2=Producción)
            serie_completa +               # 6 dígitos (Establecimiento + Punto emisión)
            numero_completo +              # 9 dígitos (Secuencial)
            codigo_numerico +              # 8 dígitos (Código numérico)
            tipo_emision                   # 1 dígito (Tipo emisión)
        )

        # Calcular dígito verificador (módulo 11)
        coeficientes = [2, 3, 4, 5, 6, 7]
        suma = 0

        # Aplicar coeficientes en orden inverso
        for i in range(48):
            coeficiente = coeficientes[i % 6]
            suma += int(cadena[47 - i]) * coeficiente

        digito_verificador = (11 - (suma % 11)) % 11

        if digito_verificador == 11:
            digito_verificador = 0
        elif digito_verificador == 10:
            digito_verificador = 1  # En SRI, 10 se considera como 1

        # Retornar clave de acceso completa (49 dígitos)
        return cadena + str(digito_verificador)


# ============================================================================
# CLASE PARA GENERACIÓN DE XML DE FACTURAS SRI
# ============================================================================

class XMLGenerator:
    """Generador de XML para facturas electrónicas SRI Ecuador"""

    def generar_xml_factura(self, factura, empresa, cliente, detalles) -> str:
        """Genera XML completo de factura según esquema SRI"""
        from datetime import datetime
        import xml.etree.ElementTree as ET
        from xml.dom import minidom

        try:
            # Crear documento XML
            factura_element = ET.Element("factura")
            factura_element.set("id", "comprobante")
            factura_element.set("version", "1.1.0")

            # Información de acceso
            info_acceso = ET.SubElement(factura_element, "infoTributaria")
            self._agregar_info_tributaria(info_acceso, factura, empresa)

            # Información de factura
            info_factura = ET.SubElement(factura_element, "infoFactura")
            # Pasar 'empresa' también para que _agregar_info_factura pueda acceder a datos de la empresa
            self._agregar_info_factura(info_factura, factura, cliente, empresa)

            # Detalles
            detalles_element = ET.SubElement(factura_element, "detalles")
            self._agregar_detalles(detalles_element, detalles)

            # Adicionales (opcional)
            if hasattr(factura, 'observaciones') and factura.observaciones:
                info_adicional = ET.SubElement(factura_element, "infoAdicional")
                self._agregar_info_adicional(info_adicional, factura.observaciones)

            # Convertir a string XML con formato
            rough_string = ET.tostring(factura_element, encoding='utf-8')
            reparsed = minidom.parseString(rough_string)
            xml_formatted = reparsed.toprettyxml(indent="  ", encoding='utf-8')

            # Limpiar líneas vacías
            lines = [line for line in xml_formatted.decode('utf-8').split('\n') if line.strip()]
            return '\n'.join(lines)

        except Exception as e:
            logger.error(f"Error generando XML de factura: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generando XML: {str(e)}")

    def _agregar_info_tributaria(self, parent, factura, empresa):
        """Agrega información tributaria al XML"""
        import xml.etree.ElementTree as ET

        # Datos obligatorios de información tributaria
        ET.SubElement(parent, "ambiente").text = str(getattr(empresa, 'ambiente', '1'))  # 1=Pruebas, 2=Producción
        ET.SubElement(parent, "tipoEmision").text = str(getattr(empresa, 'tipo_emision', '1'))  # 1=Normal
        ET.SubElement(parent, "razonSocial").text = getattr(empresa, 'razon_social', '')
        ET.SubElement(parent, "nombreComercial").text = getattr(empresa, 'nombre_comercial', '')
        ET.SubElement(parent, "ruc").text = getattr(empresa, 'ruc', '')
        ET.SubElement(parent, "claveAcceso").text = getattr(factura, 'clave_acceso', '')
        ET.SubElement(parent, "codDoc").text = "01"  # 01=Factura
        ET.SubElement(parent, "estab").text = getattr(factura, 'establecimiento', '001')
        ET.SubElement(parent, "ptoEmi").text = getattr(factura, 'punto_emision', '001')
        ET.SubElement(parent, "secuencial").text = str(getattr(factura, 'secuencial', '')).zfill(9)
        ET.SubElement(parent, "dirMatriz").text = getattr(empresa, 'direccion_matriz', '')

    def _agregar_info_factura(self, parent, factura, cliente, empresa):
        """Agrega información de factura al XML"""
        import xml.etree.ElementTree as ET
        from datetime import datetime

        # Fechas
        fecha_emision = getattr(factura, 'fecha_emision', datetime.now())
        if isinstance(fecha_emision, datetime):
            fecha_str = fecha_emision.strftime("%d/%m/%Y")
        else:
            fecha_str = str(fecha_emision)
        ET.SubElement(parent, "fechaEmision").text = fecha_str
        ET.SubElement(parent, "dirEstablecimiento").text = getattr(factura, 'direccion_establecimiento', '')

        # Contribuyente especial (si aplica)
        contribuyente_especial = getattr(empresa, 'contribuyente_especial', None)
        if contribuyente_especial:
            ET.SubElement(parent, "contribuyenteEspecial").text = contribuyente_especial

        ET.SubElement(parent, "obligadoContabilidad").text = "SI"  # Por defecto

        # Cliente
        ET.SubElement(parent, "tipoIdentificacionComprador").text = getattr(cliente, 'tipo_identificacion', '05')  # 05=Cédula, 04=RUC
        ET.SubElement(parent, "razonSocialComprador").text = getattr(cliente, 'razon_social', getattr(cliente, 'nombres', ''))
        ET.SubElement(parent, "identificacionComprador").text = getattr(cliente, 'identificacion', '')
        ET.SubElement(parent, "direccionComprador").text = getattr(cliente, 'direccion', '')

        # Totales
        ET.SubElement(parent, "totalSinImpuestos").text = str(getattr(factura, 'subtotal_sin_impuestos', '0.00'))
        ET.SubElement(parent, "totalDescuento").text = str(getattr(factura, 'total_descuento', '0.00'))

        # Impuestos
        total_con_impuestos = ET.SubElement(parent, "totalConImpuestos")
        total_impuesto = ET.SubElement(total_con_impuestos, "totalImpuesto")
        ET.SubElement(total_impuesto, "codigo").text = "2"  # IVA
        ET.SubElement(total_impuesto, "codigoPorcentaje").text = "2"  # 12%
        ET.SubElement(total_impuesto, "baseImponible").text = str(getattr(factura, 'subtotal_12', '0.00'))
        ET.SubElement(total_impuesto, "valor").text = str(getattr(factura, 'iva_12', '0.00'))

        # Si hay IVA 0%
        if hasattr(factura, 'subtotal_0') and getattr(factura, 'subtotal_0', 0) > 0:
            total_impuesto_0 = ET.SubElement(total_con_impuestos, "totalImpuesto")
            ET.SubElement(total_impuesto_0, "codigo").text = "2"  # IVA
            ET.SubElement(total_impuesto_0, "codigoPorcentaje").text = "0"  # 0%
            ET.SubElement(total_impuesto_0, "baseImponible").text = str(getattr(factura, 'subtotal_0', '0.00'))
            ET.SubElement(total_impuesto_0, "valor").text = "0.00"

        ET.SubElement(parent, "propina").text = "0.00"
        ET.SubElement(parent, "importeTotal").text = str(getattr(factura, 'valor_total', '0.00'))
        ET.SubElement(parent, "moneda").text = "DOLAR"

    def _agregar_detalles(self, parent, detalles):
        """Agrega detalles de factura al XML"""
        import xml.etree.ElementTree as ET

        for detalle in detalles:
            detalle_element = ET.SubElement(parent, "detalle")

            ET.SubElement(detalle_element, "codigoPrincipal").text = getattr(detalle, 'codigo_principal', '')
            ET.SubElement(detalle_element, "codigoAuxiliar").text = getattr(detalle, 'codigo_auxiliar', '')
            ET.SubElement(detalle_element, "descripcion").text = getattr(detalle, 'descripcion', '')
            ET.SubElement(detalle_element, "cantidad").text = str(getattr(detalle, 'cantidad', '0'))
            ET.SubElement(detalle_element, "precioUnitario").text = str(getattr(detalle, 'precio_unitario', '0.00'))
            ET.SubElement(detalle_element, "descuento").text = str(getattr(detalle, 'descuento', '0.00'))
            ET.SubElement(detalle_element, "precioTotalSinImpuesto").text = str(getattr(detalle, 'precio_total_sin_impuesto', '0.00'))

            # Impuestos del detalle
            impuestos = ET.SubElement(detalle_element, "impuestos")
            impuesto = ET.SubElement(impuestos, "impuesto")

            ET.SubElement(impuesto, "codigo").text = str(getattr(detalle, 'codigo_impuesto', '2'))  # IVA
            ET.SubElement(impuesto, "codigoPorcentaje").text = "2" if getattr(detalle, 'porcentaje_iva', 0) > 0 else "0"
            ET.SubElement(impuesto, "tarifa").text = str(getattr(detalle, 'porcentaje_iva', '0.00'))
            ET.SubElement(impuesto, "baseImponible").text = str(getattr(detalle, 'base_imponible', '0.00'))
            ET.SubElement(impuesto, "valor").text = str(getattr(detalle, 'valor_iva', '0.00'))

    def _agregar_info_adicional(self, parent, observaciones):
        """Agrega información adicional al XML"""
        import xml.etree.ElementTree as ET

        campo = ET.SubElement(parent, "campoAdicional")
        campo.set("nombre", "Observaciones")
        campo.text = observaciones

    def validar_esquema_sri(self, xml_content: str) -> tuple[bool, str]:
        """Valida XML contra esquema XSD del SRI"""
        try:
            # Esta es una implementación básica de validación
            # En producción, se debería usar el XSD oficial del SRI

            # Verificar que tenga los elementos obligatorios
            required_elements = [
                'factura', 'infoTributaria', 'infoFactura', 'detalles'
            ]

            # Verificar estructura básica
            content = xml_content.lstrip()
            lc = content.lower()
            if not (lc.startswith('<?xml') or lc.startswith('<factura')):
                return False, "XML no tiene estructura válida"

            # Verificar elementos obligatorios (búsqueda case-insensitive)
            for element in required_elements:
                if f'<{element}' not in lc:
                    return False, f"Falta elemento obligatorio: {element}"

            # Verificar que la factura tenga cierre
            if '</factura>' not in lc:
                return False, "Falta cierre del elemento: factura"

            return True, "XML válido según estructura básica"

        except Exception as e:
            logger.error(f"Error validando XML: {str(e)}", exc_info=True)
            return False, f"Error validando XML: {str(e)}"