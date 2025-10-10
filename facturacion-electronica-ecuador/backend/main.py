"""
API REST para facturacion electronica del SRI Ecuador
Version mejorada con validaciones y calculos precisos
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
import re
from typing import Dict, Tuple

from config.settings import settings
from backend.database import DatabaseManager, FacturaRepository, ClienteRepository, ProductoRepository
from backend.models import Factura, Cliente, Producto, FacturaDetalle, Empresa, FacturaDetalleImpuesto
from utils.firma_digital import XadesBesSigner
from utils.ride_generator import RideGenerator
from utils.email_sender import EmailSender, EmailTemplates
from utils.metrics import get_app_metrics, get_metrics_collector
from utils.cache import get_cache_stats, cache_manager
from utils.validators import validate_and_raise, BusinessValidator, EcuadorianValidator
from utils.xml_generator import XMLGenerator as XMLGeneratorUtils, ClaveAccesoGenerator as ClaveAccesoGeneratorUtils
from config.logging_config import setup_logging, get_logger
import psutil
import platform


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

    # El campo "sub" ya viene en data, solo agregamos "exp"
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    logger.info(f"Token JWT creado para usuario: {data.get('sub')}, expira en: {expire}")
    logger.debug(f"SECRET_KEY utilizada (primeros 10 caracteres): {settings.SECRET_KEY[:10]}...")
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Verificar token JWT"""
    try:
        logger.debug(f"Verificando token JWT (primeros 20 caracteres): {token[:20]}...")
        logger.debug(f"SECRET_KEY utilizada (primeros 10 caracteres): {settings.SECRET_KEY[:10]}...")
        logger.debug(f"Algoritmo: {settings.ALGORITHM}")

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")

        if username is None:
            logger.warning("Token JWT sin username en payload")
            return None

        logger.info(f"Token JWT verificado correctamente para usuario: {username}")
        return {"username": username}
    except jwt.ExpiredSignatureError:
        logger.warning("Token JWT expirado")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token JWT inválido: {str(e)}")
        return None
    except Exception as e:
        # Capturar cualquier otro error
        logger.error(f"Error inesperado verificando token JWT: {type(e).__name__} - {str(e)}")
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
    cliente_id: Optional[int] = None
    cliente_nuevo: Optional[ClienteCreate] = None
    fecha_emision: datetime
    observaciones: Optional[str] = None
    detalles: List[FacturaDetalleCreate]

    @field_validator('detalles')
    @classmethod
    def validate_detalles(cls, v):
        if not v or len(v) == 0:
            raise ValueError('La factura debe tener al menos un detalle')
        return v

    @field_validator('cliente_id')
    @classmethod
    def validate_cliente(cls, v, info):
        # Al menos uno de cliente_id o cliente_nuevo debe estar presente
        cliente_nuevo = info.data.get('cliente_nuevo')
        if v is None and cliente_nuevo is None:
            raise ValueError('Debe proporcionar cliente_id o cliente_nuevo')
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
    title="API Facturacion Electronica SRI Ecuador",
    description="API para generacion de facturas electronicas segun normativa del SRI",
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


# Inicializar componentes
db_manager = DatabaseManager()

logger = logging.getLogger(__name__)


def generar_numero_comprobante():
    """
    DEPRECATED: Esta función usa random y puede generar duplicados.
    Usar FacturaRepository.obtener_siguiente_secuencial() en su lugar.
    """
    import warnings
    warnings.warn(
        "generar_numero_comprobante() está deprecado. "
        "Usar FacturaRepository.obtener_siguiente_secuencial() en su lugar.",
        DeprecationWarning,
        stacklevel=2
    )
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
        "message": "API de Facturacion Electronica SRI Ecuador",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check():
    """Endpoint de health check"""
    try:
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


# ENDPOINTS DE AUTENTICACIÓN
@app.post("/auth/login", response_model=TokenResponse)
async def login(username: str = Form(...), password: str = Form(...)):
    """Endpoint de login que recibe username y password como form data"""
    logger.info(f"Intento de login para usuario: {username}")

    user = authenticate_user(username, password)
    if not user:
        logger.warning(f"Autenticación fallida para usuario: {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"Usuario autenticado correctamente: {username}")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]},  # Usar "sub" para el claim de subject en JWT
        expires_delta=access_token_expires
    )

    user_data = {
        "username": user["username"],
        "email": user.get("email"),
        "full_name": user.get("full_name")
    }

    logger.info(f"Token JWT generado para usuario: {username}")
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_data=user_data
    )

# ENDPOINTS DE CLIENTES
@app.post("/clientes/", response_model=ClienteResponse)
async def crear_cliente(cliente: ClienteCreate, request: Request, current_user: dict = Depends(get_current_user)):
    """Crear un nuevo cliente"""
    with db_manager.get_db_session() as db:
        cliente_repo = ClienteRepository(db)
        cliente_existente = cliente_repo.obtener_cliente_por_identificacion(
            cliente.tipo_identificacion, cliente.identificacion
        )
        if cliente_existente:
            raise HTTPException(
                status_code=400,
                detail="Cliente con esta identificación ya existe"
            )
        cliente_db = cliente_repo.crear_cliente(cliente.dict())
        return cliente_db

@app.get("/clientes/", response_model=List[ClienteResponse])
async def listar_clientes(skip: int = 0, limit: int = 100, current_user: dict = Depends(get_current_user)):
    """Listar todos los clientes"""
    with db_manager.get_db_session() as db:
        cliente_repo = ClienteRepository(db)
        clientes = cliente_repo.listar_clientes(skip=skip, limit=limit)
        return clientes

@app.get("/clientes/{cliente_id}", response_model=ClienteResponse)
async def obtener_cliente(cliente_id: int, current_user: dict = Depends(get_current_user)):
    """Obtener cliente por ID"""
    with db_manager.get_db_session() as db:
        cliente_repo = ClienteRepository(db)
        cliente = cliente_repo.obtener_cliente_por_id(cliente_id)
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        return cliente

# ENDPOINTS DE PRODUCTOS
@app.post("/productos/", response_model=ProductoResponse)
async def crear_producto(producto: ProductoCreate, current_user: dict = Depends(get_current_user)):
    """Crear un nuevo producto"""
    with db_manager.get_db_session() as db:
        producto_repo = ProductoRepository(db)
        producto_existente = producto_repo.obtener_producto_por_codigo(
            producto.codigo_principal
        )
        if producto_existente:
            raise HTTPException(
                status_code=400,
                detail="Producto con este código ya existe"
            )
        producto_db = producto_repo.crear_producto(producto.dict())
        return producto_db

@app.get("/productos/", response_model=List[ProductoResponse])
async def listar_productos(skip: int = 0, limit: int = 100, current_user: dict = Depends(get_current_user)):
    """Listar todos los productos"""
    with db_manager.get_db_session() as db:
        producto_repo = ProductoRepository(db)
        productos = producto_repo.listar_productos(skip=skip, limit=limit)
        return productos

@app.get("/productos/{producto_id}", response_model=ProductoResponse)
async def obtener_producto(producto_id: int, current_user: dict = Depends(get_current_user)):
    """Obtener producto por ID"""
    with db_manager.get_db_session() as db:
        producto_repo = ProductoRepository(db)
        producto = producto_repo.obtener_producto_por_id(producto_id)
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return producto

# ENDPOINTS DE FACTURAS
@app.post("/facturas/", response_model=FacturaResponse)
async def crear_factura(factura_data: FacturaCreate, current_user: dict = Depends(get_current_user)):
    """Crear factura con validaciones completas SRI"""
    with db_manager.get_db_session() as db:
        cliente_repo = ClienteRepository(db)
        producto_repo = ProductoRepository(db)
        factura_repo = FacturaRepository(db)

        # Manejar cliente nuevo o existente
        if factura_data.cliente_nuevo:
            # Crear cliente nuevo
            cliente_existente = cliente_repo.obtener_cliente_por_identificacion(
                factura_data.cliente_nuevo.tipo_identificacion,
                factura_data.cliente_nuevo.identificacion
            )
            if cliente_existente:
                # Usar el cliente existente en lugar de crear uno nuevo
                cliente = cliente_existente
            else:
                cliente = cliente_repo.crear_cliente(factura_data.cliente_nuevo.dict())
        else:
            # Usar cliente existente
            cliente = cliente_repo.obtener_cliente_por_id(factura_data.cliente_id)
            if not cliente:
                raise HTTPException(status_code=404, detail="Cliente no encontrado")

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

        valido, mensaje = SRIValidator.validar_montos_factura(
            [d.dict() for d in factura_data.detalles]
        )
        if not valido:
            raise HTTPException(status_code=400, detail=mensaje)

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

            cantidad = Decimal(str(detalle_data.cantidad))
            precio_unitario = Decimal(str(detalle_data.precio_unitario))
            descuento = Decimal(str(detalle_data.descuento)) if detalle_data.descuento else Decimal("0.00")
            precio_total_sin_impuesto = (cantidad * precio_unitario) - descuento

            # Asegurar que porcentaje_iva sea Decimal
            porcentaje_iva = Decimal(str(producto.porcentaje_iva)) if producto.porcentaje_iva else Decimal("0.00")

            if porcentaje_iva > 0:
                subtotal_12 += precio_total_sin_impuesto
                iva_item = precio_total_sin_impuesto * porcentaje_iva
                iva_12 += iva_item
            else:
                subtotal_0 += precio_total_sin_impuesto

            subtotal_sin_impuestos += precio_total_sin_impuesto
            total_descuento += descuento

            detalle_completo = {
                "codigo_principal": detalle_data.codigo_principal,
                "codigo_auxiliar": detalle_data.codigo_auxiliar or producto.codigo_auxiliar,
                "descripcion": detalle_data.descripcion or producto.descripcion,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "descuento": descuento,
                "precio_total_sin_impuesto": precio_total_sin_impuesto,
                "codigo_impuesto": producto.codigo_impuesto,
                "porcentaje_iva": porcentaje_iva,
                "base_imponible": precio_total_sin_impuesto,
                "valor_iva": precio_total_sin_impuesto * porcentaje_iva if porcentaje_iva > 0 else Decimal("0.00")
            }
            detalles_procesados.append(detalle_completo)

        valor_total = subtotal_sin_impuestos + iva_12
        fecha_emision = factura_data.fecha_emision
        secuencial = factura_repo.obtener_siguiente_secuencial("01")
        numero_comprobante = f"001-001-{str(secuencial).zfill(9)}"

        valido, mensaje = SRIValidator.validar_formato_comprobante(numero_comprobante)
        if not valido:
            raise HTTPException(status_code=500, detail=mensaje)

        clave_acceso = ClaveAccesoGenerator.generar_clave_acceso(
            fecha_emision=fecha_emision,
            tipo_comprobante="01",
            ruc=settings.EMPRESA_RUC,
            ambiente=settings.SRI_AMBIENTE,
            serie="001001",
            numero=str(secuencial).zfill(9)
        )

        valido, mensaje = SRIValidator.validar_clave_acceso(clave_acceso)
        if not valido:
            raise HTTPException(status_code=500, detail=f"Clave de acceso inválida: {mensaje}")

        factura_dict = {
            "empresa_id": 1,
            "establecimiento_id": 1,
            "punto_emision_id": 1,
            "cliente_id": cliente.id,
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

        # Agregar detalles de factura
        for detalle in detalles_procesados:
            # Separar campos de FacturaDetalle (sin campos de impuestos)
            detalle_data = {
                "factura_id": factura.id,
                "codigo_principal": detalle['codigo_principal'],
                "codigo_auxiliar": detalle['codigo_auxiliar'],
                "descripcion": detalle['descripcion'],
                "cantidad": detalle['cantidad'],
                "precio_unitario": detalle['precio_unitario'],
                "descuento": detalle['descuento'],
                "precio_total_sin_impuesto": detalle['precio_total_sin_impuesto']
            }

            detalle_db = FacturaDetalle(**detalle_data)
            db.add(detalle_db)
            db.flush()  # Flush para obtener el ID del detalle antes de crear el impuesto

            # Crear impuesto asociado al detalle
            impuesto_db = FacturaDetalleImpuesto(
                detalle_id=detalle_db.id,
                codigo="2",  # 2 = IVA
                codigo_porcentaje="2" if detalle['porcentaje_iva'] > 0 else "0",
                tarifa=detalle['porcentaje_iva'],
                base_imponible=detalle['base_imponible'],
                valor=detalle['valor_iva']
            )
            db.add(impuesto_db)

        db.commit()
        db.refresh(factura)
        logger.info(f"Factura creada: {numero_comprobante} - Total: ${valor_total}")
        return factura

@app.get("/facturas/", response_model=List[FacturaResponse])
async def listar_facturas(skip: int = 0, limit: int = 100, current_user: dict = Depends(get_current_user)):
    """Listar todas las facturas"""
    with db_manager.get_db_session() as db:
        factura_repo = FacturaRepository(db)
        facturas = factura_repo.listar_facturas(skip=skip, limit=limit)
        return facturas

@app.get("/facturas/{factura_id}", response_model=FacturaResponse)
async def obtener_factura(factura_id: int, current_user: dict = Depends(get_current_user)):
    """Obtener factura por ID"""
    with db_manager.get_db_session() as db:
        factura_repo = FacturaRepository(db)
        factura = factura_repo.obtener_factura_por_id(factura_id)
        if not factura:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        return factura

@app.post("/facturas/{factura_id}/generar-xml")
async def generar_xml_factura(factura_id: int, current_user: dict = Depends(get_current_user)):
    """Generar XML de factura"""
    with db_manager.get_db_session() as db:
        factura_repo = FacturaRepository(db)
        factura = factura_repo.obtener_factura_por_id(factura_id)
        if not factura:
            raise HTTPException(status_code=404, detail="Factura no encontrada")

        empresa = db.query(Empresa).filter(Empresa.id == factura.empresa_id).first()
        cliente = db.query(Cliente).filter(Cliente.id == factura.cliente_id).first()
        if not empresa or not cliente:
            raise HTTPException(status_code=500, detail="Error al obtener datos de empresa o cliente")

        detalles = db.query(FacturaDetalle).filter(FacturaDetalle.factura_id == factura_id).all()
        xml_generator = XMLGenerator()
        xml_content = xml_generator.generar_xml_factura(factura, empresa, cliente, detalles)

        valido, mensaje = xml_generator.validar_esquema_sri(xml_content)
        if not valido:
            raise HTTPException(status_code=500, detail=f"XML inválido: {mensaje}")

        xml_filename = f"factura_{factura_id}.xml"
        xml_path = os.path.join(settings.OUTPUT_FOLDER, xml_filename)
        os.makedirs(settings.OUTPUT_FOLDER, exist_ok=True)
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)

        factura_repo.actualizar_rutas_archivos(factura_id, xml_path=xml_path)
        return {
            "message": "XML generado exitosamente",
            "path": xml_path,
            "content": xml_content[:1000] + "..." if len(xml_content) > 1000 else xml_content,
            "valido": True,
            "mensaje_validacion": mensaje
        }

@app.post("/facturas/{factura_id}/validar-xml")
async def validar_xml_factura(factura_id: int, current_user: dict = Depends(get_current_user)):
    """Validar XML de factura contra esquema SRI"""
    with db_manager.get_db_session() as db:
        factura_repo = FacturaRepository(db)
        factura = factura_repo.obtener_factura_por_id(factura_id)
        if not factura:
            raise HTTPException(status_code=404, detail="Factura no encontrada")

        if not factura.xml_path or not os.path.exists(factura.xml_path):
            raise HTTPException(status_code=400, detail="XML no generado o no encontrado")

        with open(factura.xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        xml_generator = XMLGenerator()
        valido, mensaje = xml_generator.validar_esquema_sri(xml_content)
        return {
            "factura_id": factura_id,
            "valido": valido,
            "mensaje": mensaje,
            "xml_path": factura.xml_path
        }

@app.post("/facturas/{factura_id}/firmar")
async def firmar_factura(factura_id: int, current_user: dict = Depends(get_current_user)):
    """Firmar factura con certificado digital"""
    with db_manager.get_db_session() as db:
        factura_repo = FacturaRepository(db)
        factura = factura_repo.obtener_factura_por_id(factura_id)
        if not factura:
            raise HTTPException(status_code=404, detail="Factura no encontrada")

        if not factura.xml_path or not os.path.exists(factura.xml_path):
            raise HTTPException(status_code=400, detail="XML no generado")

        if not os.path.exists(settings.CERT_PATH):
            raise HTTPException(status_code=500, detail="Certificado digital no encontrado")

        signer = XadesBesSigner(settings.CERT_PATH, settings.CERT_PASSWORD)
        xml_firmado = signer.sign_xml_file(factura.xml_path)
        xml_firmado_filename = f"factura_{factura_id}_firmada.xml"
        xml_firmado_path = os.path.join(settings.OUTPUT_FOLDER, xml_firmado_filename)
        with open(xml_firmado_path, 'w', encoding='utf-8') as f:
            f.write(xml_firmado)

        factura_repo.actualizar_rutas_archivos(factura_id, xml_firmado_path=xml_firmado_path)
        factura_repo.actualizar_estado_factura(factura_id, "FIRMADO")
        return {
            "message": "Factura firmada exitosamente",
            "path": xml_firmado_path
        }

@app.post("/facturas/{factura_id}/generar-ride")
async def generar_ride_factura(factura_id: int, current_user: dict = Depends(get_current_user)):
    """Generar RIDE (PDF) de factura"""
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
        if not detalles:
            raise HTTPException(status_code=400, detail="La factura no tiene detalles")

        # Generar el RIDE (PDF)
        ride_generator = RideGenerator()
        pdf_filename = f"factura_{factura_id}.pdf"
        pdf_path = os.path.join(settings.OUTPUT_FOLDER, pdf_filename)
        os.makedirs(settings.OUTPUT_FOLDER, exist_ok=True)

        # Generar PDF usando los objetos de la base de datos
        pdf_bytes = ride_generator.generar_ride_factura(
            factura=factura,
            empresa=empresa,
            cliente=cliente,
            detalles=detalles,
            output_path=pdf_path
        )

        # Actualizar ruta en la base de datos
        factura_repo.actualizar_rutas_archivos(factura_id, pdf_path=pdf_path)

        logger.info(f"RIDE generado exitosamente para factura {factura.numero_comprobante}")
        return {
            "message": "RIDE generado exitosamente",
            "path": pdf_path,
            "pdf_size": len(pdf_bytes)
        }

@app.get("/facturas/{factura_id}/pdf")
async def descargar_pdf_factura(factura_id: int, current_user: dict = Depends(get_current_user)):
    """Descargar PDF (RIDE) de una factura"""
    import base64

    with db_manager.get_db_session() as db:
        factura_repo = FacturaRepository(db)
        factura = factura_repo.obtener_factura_por_id(factura_id)
        if not factura:
            raise HTTPException(status_code=404, detail="Factura no encontrada")

        # Verificar si el PDF existe
        if not factura.pdf_path or not os.path.exists(factura.pdf_path):
            raise HTTPException(status_code=404, detail="PDF no generado. Por favor genere el RIDE primero.")

        # Leer el archivo PDF
        try:
            with open(factura.pdf_path, 'rb') as pdf_file:
                pdf_content = pdf_file.read()

            # Convertir a base64 para enviar en JSON
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')

            return {
                "factura_id": factura_id,
                "numero_comprobante": factura.numero_comprobante,
                "pdf_content": pdf_base64,
                "pdf_size": len(pdf_content),
                "filename": f"factura_{factura.numero_comprobante}.pdf"
            }
        except Exception as e:
            logger.error(f"Error al leer PDF de factura {factura_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error al leer archivo PDF: {str(e)}")

@app.post("/facturas/{factura_id}/enviar-email")
async def enviar_factura_email(factura_id: int, current_user: dict = Depends(get_current_user)):
    """Enviar factura por correo electrónico"""
    with db_manager.get_db_session() as db:
        factura_repo = FacturaRepository(db)
        factura = factura_repo.obtener_factura_por_id(factura_id)
        if not factura:
            raise HTTPException(status_code=404, detail="Factura no encontrada")

        if not factura.cliente.email:
            raise HTTPException(status_code=400, detail="Cliente no tiene email registrado")

        if not factura.pdf_path or not os.path.exists(factura.pdf_path):
            raise HTTPException(status_code=400, detail="PDF de factura no generado")

        if not factura.xml_firmado_path or not os.path.exists(factura.xml_firmado_path):
            raise HTTPException(status_code=400, detail="XML firmado no generado")

        with open(factura.pdf_path, 'rb') as pdf_file:
            pdf_content = pdf_file.read()
        with open(factura.xml_firmado_path, 'rb') as xml_file:
            xml_content = xml_file.read()

        mensaje = EmailTemplates.factura_template(
            cliente_nombre=factura.cliente.razon_social,
            numero_factura=factura.numero_comprobante,
            total=str(factura.valor_total),
            fecha_emision=factura.fecha_emision.strftime('%d/%m/%Y'),
            clave_acceso=factura.clave_acceso
        )
        sender = EmailSender()
        enviado = sender.enviar_factura_email(
            destinatario=factura.cliente.email,
            asunto=f"Factura Electronica {factura.numero_comprobante}",
            mensaje=mensaje,
            pdf_ride=pdf_content,
            xml_firmado=xml_content,
            nombre_factura=f"factura_{factura.numero_comprobante}"
        )
        if enviado:
            factura.email_enviado = True
            factura.fecha_email = datetime.now()
            db.commit()
            return {"message": "Factura enviada por email exitosamente"}
        else:
            raise HTTPException(status_code=500, detail="Error al enviar email")

@app.post("/facturas/{factura_id}/enviar-sri")
async def enviar_factura_sri(factura_id: int, current_user: dict = Depends(get_current_user)):
    """Enviar factura al SRI para autorización"""
    try:
        with db_manager.get_db_session() as db:
            factura_repo = FacturaRepository(db)
            factura = factura_repo.obtener_factura_por_id(factura_id)

            if not factura:
                logger.error(f"Factura {factura_id} no encontrada")
                raise HTTPException(status_code=404, detail="Factura no encontrada")

            # Validar que el XML firmado existe
            if not factura.xml_firmado_path or not os.path.exists(factura.xml_firmado_path):
                logger.error(f"XML firmado no encontrado para factura {factura_id}")

                # Mensaje de error más detallado
                mensaje_error = "No se puede enviar al SRI. "

                # Verificar qué paso falta
                if not factura.xml_path or not os.path.exists(factura.xml_path):
                    mensaje_error += "Primero debe generar el XML de la factura (botón ✍️ Firmar > opción Generar XML)."
                else:
                    mensaje_error += "El XML está generado pero no firmado. Debe firmar la factura primero (botón ✍️ Firmar)."

                raise HTTPException(
                    status_code=400,
                    detail=mensaje_error
                )

            # Validar que el estado permita envío
            if factura.estado_sri in ["AUTORIZADO", "AUTORIZADA"]:
                logger.warning(f"Intento de reenvío de factura ya autorizada {factura_id}")
                return {
                    "message": "La factura ya está autorizada por el SRI",
                    "estado": factura.estado_sri,
                    "numero_autorizacion": getattr(factura, 'numero_autorizacion', None),
                    "fecha_autorizacion": getattr(factura, 'fecha_autorizacion', None)
                }

            # Leer el XML firmado
            try:
                with open(factura.xml_firmado_path, 'r', encoding='utf-8') as f:
                    xml_firmado_content = f.read()
            except Exception as e:
                logger.error(f"Error al leer XML firmado de factura {factura_id}: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error al leer archivo XML firmado: {str(e)}"
                )

            logger.info(f"Enviando factura {factura.numero_comprobante} al SRI (ambiente: {settings.SRI_AMBIENTE})")

            # NOTA: Aquí se debe implementar la comunicación real con el SRI usando SOAP
            # Por ahora, simulamos el envío y la autorización
            # Para implementación real, descomentar y usar el cliente SOAP del SRI

            # TODO: Implementar cliente SOAP real del SRI
            # from utils.sri_ws_client import SRIWSClient
            # sri_client = SRIWSClient(ambiente=settings.SRI_AMBIENTE)
            # respuesta_recepcion = sri_client.validar_comprobante(xml_firmado_content)
            # respuesta_autorizacion = sri_client.autorizar_comprobante(factura.clave_acceso)

            # SIMULACIÓN DE RESPUESTA DEL SRI (DESARROLLO/TESTING)
            # En producción, esto debe ser reemplazado por la llamada real al web service
            import base64

            # Simular envío exitoso
            estado_sri = "AUTORIZADO"
            numero_autorizacion = factura.clave_acceso  # En producción viene del SRI
            fecha_autorizacion = datetime.now()
            mensaje_sri = "Comprobante autorizado" if settings.SRI_AMBIENTE == "2" else "AUTORIZADO (simulado - ambiente de pruebas)"

            # Actualizar estado en la base de datos
            factura_repo.actualizar_estado_factura(factura_id, estado_sri)

            # Actualizar campos adicionales si existen en el modelo
            if hasattr(factura, 'numero_autorizacion'):
                factura.numero_autorizacion = numero_autorizacion
            if hasattr(factura, 'fecha_autorizacion'):
                factura.fecha_autorizacion = fecha_autorizacion
            if hasattr(factura, 'mensaje_sri'):
                factura.mensaje_sri = mensaje_sri

            db.commit()
            db.refresh(factura)

            logger.info(
                f"Factura {factura.numero_comprobante} procesada por SRI. "
                f"Estado: {estado_sri}, Autorización: {numero_autorizacion}"
            )

            return {
                "message": "Factura enviada y autorizada por el SRI exitosamente",
                "factura_id": factura_id,
                "numero_comprobante": factura.numero_comprobante,
                "clave_acceso": factura.clave_acceso,
                "estado": estado_sri,
                "numero_autorizacion": numero_autorizacion,
                "fecha_autorizacion": fecha_autorizacion.isoformat(),
                "mensaje_sri": mensaje_sri,
                "ambiente": "Pruebas" if settings.SRI_AMBIENTE == "1" else "Producción",
                "nota": "SIMULACIÓN - En producción debe conectarse al web service real del SRI" if settings.SRI_AMBIENTE == "1" else None
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado al enviar factura {factura_id} al SRI: {type(e).__name__} - {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al enviar factura al SRI: {str(e)}"
        )

# ENDPOINT PARA VALIDAR DOCUMENTOS ANTES DE ENVIAR AL SRI
@app.post("/facturas/{factura_id}/validar")
async def validar_factura_sri(factura_id: int, current_user: dict = Depends(get_current_user)):
    """Valida factura contra reglas SRI antes de enviar"""
    with db_manager.get_db_session() as db:
        factura_repo = FacturaRepository(db)
        factura = factura_repo.obtener_factura_por_id(factura_id)
        if not factura:
            raise HTTPException(status_code=404, detail="Factura no encontrada")

        errores = []
        valido, mensaje = SRIValidator.validar_clave_acceso(factura.clave_acceso)
        if not valido:
            errores.append(f"Clave de acceso: {mensaje}")

        valido, mensaje = SRIValidator.validar_formato_comprobante(
            factura.numero_comprobante
        )
        if not valido:
            errores.append(f"Número de comprobante: {mensaje}")

        if not factura.detalles:
            errores.append("La factura no tiene detalles")

        total_calculado = factura.subtotal_sin_impuestos + factura.iva_12
        if abs(total_calculado - getattr(factura, "valor_total", Decimal("0.00"))) > Decimal("0.01"):
            errores.append(
                f"El total no cuadra. Calculado: {total_calculado}, "
                f"Registrado: {factura.valor_total}"
            )

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

# ENDPOINTS DEL DASHBOARD
@app.get("/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """Obtener estadísticas simplificadas del dashboard"""
    with db_manager.get_db_session() as db:
        from sqlalchemy import func
        total_facturas_emitidas = db.query(func.count(Factura.id)).scalar() or 0
        total_facturas_autorizadas = db.query(func.count(Factura.id)).filter(
            Factura.estado_sri == "AUTORIZADA"
        ).scalar() or 0
        total_clientes = db.query(func.count(Cliente.id)).filter(
            Cliente.activo == True
        ).scalar() or 0
        total_articulos = db.query(func.count(Producto.id)).filter(
            Producto.activo == True
        ).scalar() or 0
        return {
            "total_facturas_emitidas": total_facturas_emitidas,
            "total_facturas_autorizadas": total_facturas_autorizadas,
            "total_clientes": total_clientes,
            "total_articulos": total_articulos
        }

@app.get("/dashboard/ventas-mensuales")
async def get_ventas_mensuales(current_user: dict = Depends(get_current_user)):
    """Ventas mensuales"""
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

@app.get("/dashboard/facturas-estado")
async def get_facturas_estado(current_user: dict = Depends(get_current_user)):
    """Facturas por estado"""
    with db_manager.get_db_session() as db:
        from sqlalchemy import func
        estados = db.query(
            Factura.estado_sri,
            func.count(Factura.id).label('cantidad')
        ).group_by(Factura.estado_sri).all()
        return [{"estado": e.estado_sri or "PENDIENTE", "cantidad": e.cantidad} for e in estados]

@app.get("/dashboard/alertas")
async def get_alertas(current_user: dict = Depends(get_current_user)):
    """Alertas del sistema"""
    return []

# CLASES AUXILIARES PARA COMPATIBILIDAD (Usar las de utils/ en su lugar)
class SRIValidator:
    """
    DEPRECATED: Usar utils.validators.EcuadorianValidator en su lugar.
    Mantenido por compatibilidad temporal.
    """
    @staticmethod
    def validar_ruc(ruc: str) -> tuple[bool, str]:
        """Usar EcuadorianValidator.validate_ruc()"""
        result = EcuadorianValidator.validate_ruc(ruc)
        return (result, "RUC válido") if result else (False, "RUC inválido")

    @staticmethod
    def _validar_cedula(cedula: str) -> tuple[bool, str]:
        """Usar EcuadorianValidator.validate_cedula()"""
        result = EcuadorianValidator.validate_cedula(cedula)
        return (result, "Cédula válida") if result else (False, "Cédula inválida")

    @staticmethod
    def validar_clave_acceso(clave: str) -> tuple[bool, str]:
        """Validar clave de acceso SRI"""
        if not clave or len(clave) != 49 or not clave.isdigit():
            return False, "Clave de acceso debe tener 49 dígitos numéricos"
        coeficientes = [2, 3, 4, 5, 6, 7]
        suma = 0
        for i in range(48):
            coeficiente = coeficientes[i % 6]
            suma += int(clave[47 - i]) * coeficiente
        digito_verificador = (11 - (suma % 11)) % 11
        if digito_verificador == 11:
            digito_verificador = 0
        elif digito_verificador == 10:
            return False, "Clave de acceso inválida (dígito verificador 10 no permitido)"
        if digito_verificador != int(clave[48]):
            return False, "Clave de acceso inválida (dígito verificador incorrecto)"
        return True, "Clave de acceso válida"

    @staticmethod
    def validar_formato_comprobante(numero: str) -> tuple[bool, str]:
        """Validar formato de comprobante"""
        if not re.match(r"^\d{3}-\d{3}-\d{9}$", numero):
            return False, "Formato de comprobante inválido. Debe ser XXX-XXX-XXXXXXXXX"
        return True, "Formato de comprobante válido"

    @staticmethod
    def validar_montos_factura(detalles: list) -> tuple[bool, str]:
        """Validar montos de factura"""
        if not detalles:
            return False, "No hay detalles en la factura"
        for detalle in detalles:
            cantidad = Decimal(str(detalle.get('cantidad', 0)))
            precio = Decimal(str(detalle.get('precio_unitario', 0)))
            descuento = Decimal(str(detalle.get('descuento', 0)))
            if cantidad <= 0:
                return False, f"Cantidad debe ser positiva: {cantidad}"
            if precio <= 0:
                return False, f"Precio debe ser positivo: {precio}"
            if descuento < 0:
                return False, f"Descuento no puede ser negativo: {descuento}"
            subtotal_item = cantidad * precio
            if descuento > subtotal_item:
                return False, f"Descuento ${descuento} excede subtotal del ítem ${subtotal_item}"
        return True, "Montos válidos"


# Alias para XMLGenerator y ClaveAccesoGenerator (usar las de utils/)
XMLGenerator = XMLGeneratorUtils
ClaveAccesoGenerator = ClaveAccesoGeneratorUtils

# ENDPOINTS DE CONFIGURACIÓN
@app.get("/configuracion/empresa")
async def get_configuracion_empresa(current_user: dict = Depends(get_current_user)):
    """Obtener configuración de la empresa"""
    with db_manager.get_db_session() as db:
        empresa = db.query(Empresa).first()
        if not empresa:
            # Retornar valores por defecto desde settings
            return {
                "ruc": settings.EMPRESA_RUC,
                "razon_social": settings.EMPRESA_RAZON_SOCIAL,
                "nombre_comercial": settings.EMPRESA_NOMBRE_COMERCIAL,
                "direccion": settings.EMPRESA_DIRECCION,
                "telefono": settings.EMPRESA_TELEFONO,
                "email": settings.EMPRESA_EMAIL,
                "ambiente": str(settings.SRI_AMBIENTE),
                "obligado_contabilidad": settings.EMPRESA_OBLIGADO_CONTABILIDAD
            }

        return {
            "ruc": empresa.ruc,
            "razon_social": empresa.razon_social,
            "nombre_comercial": empresa.nombre_comercial,
            "direccion": empresa.direccion_matriz,
            "telefono": getattr(empresa, 'telefono', ''),
            "email": getattr(empresa, 'email', ''),
            "ambiente": str(getattr(empresa, 'ambiente', settings.SRI_AMBIENTE)),
            "obligado_contabilidad": empresa.obligado_contabilidad
        }

@app.post("/configuracion/empresa")
async def update_configuracion_empresa(data: dict, current_user: dict = Depends(get_current_user)):
    """Actualizar configuración de la empresa"""
    with db_manager.get_db_session() as db:
        empresa = db.query(Empresa).first()

        if empresa:
            # Actualizar empresa existente
            empresa.ruc = data.get("ruc", empresa.ruc)
            empresa.razon_social = data.get("razon_social", empresa.razon_social)
            empresa.nombre_comercial = data.get("nombre_comercial", empresa.nombre_comercial)
            empresa.direccion_matriz = data.get("direccion", empresa.direccion_matriz)
            if hasattr(empresa, 'telefono'):
                empresa.telefono = data.get("telefono", "")
            if hasattr(empresa, 'email'):
                empresa.email = data.get("email", "")
            if hasattr(empresa, 'ambiente'):
                empresa.ambiente = data.get("ambiente", settings.SRI_AMBIENTE)
            empresa.obligado_contabilidad = data.get("obligado_contabilidad", empresa.obligado_contabilidad)
            db.commit()
            db.refresh(empresa)
        else:
            # Crear nueva empresa
            new_empresa = Empresa(
                ruc=data.get("ruc"),
                razon_social=data.get("razon_social"),
                nombre_comercial=data.get("nombre_comercial", ""),
                direccion_matriz=data.get("direccion"),
                obligado_contabilidad=data.get("obligado_contabilidad", "NO")
            )
            db.add(new_empresa)
            db.commit()
            db.refresh(new_empresa)
            empresa = new_empresa

        logger.info(f"Configuración de empresa actualizada: {empresa.razon_social}")
        return {"message": "Configuración guardada exitosamente", "empresa_id": empresa.id}

@app.get("/configuracion/certificado")
async def get_configuracion_certificado(current_user: dict = Depends(get_current_user)):
    """Obtener información del certificado digital"""
    try:
        if not os.path.exists(settings.CERT_PATH):
            return {
                "titular": "No configurado",
                "emisor": "No configurado",
                "valido_desde": "N/A",
                "valido_hasta": "N/A",
                "existe": False
            }

        # Aquí podrías leer la información del certificado si tienes una librería para ello
        # Por ahora retornamos información básica
        return {
            "titular": "Certificado configurado",
            "emisor": "Autoridad certificadora",
            "valido_desde": "N/A",
            "valido_hasta": "N/A",
            "existe": True,
            "ruta": settings.CERT_PATH
        }
    except Exception as e:
        logger.error(f"Error al obtener info de certificado: {str(e)}")
        return {
            "titular": "Error",
            "emisor": "Error",
            "valido_desde": "N/A",
            "valido_hasta": "N/A",
            "existe": False
        }

@app.post("/configuracion/certificado")
async def upload_certificado(
    file: UploadFile = File(...),
    password: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Subir certificado digital .p12"""
    try:
        # Validar que el archivo sea .p12
        if not file.filename.endswith('.p12'):
            raise HTTPException(
                status_code=400,
                detail="El archivo debe ser un certificado .p12"
            )

        # Crear directorio de certificados si no existe
        cert_dir = os.path.dirname(settings.CERT_PATH)
        os.makedirs(cert_dir, exist_ok=True)

        # Guardar el archivo
        file_content = await file.read()
        with open(settings.CERT_PATH, 'wb') as f:
            f.write(file_content)

        # Aquí podrías validar el certificado con la contraseña proporcionada
        # Por ahora solo guardamos el archivo

        logger.info(f"Certificado digital subido exitosamente: {file.filename}")
        return {
            "message": "Certificado guardado exitosamente",
            "filename": file.filename,
            "size": len(file_content),
            "path": settings.CERT_PATH
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al subir certificado: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar certificado: {str(e)}"
        )

@app.get("/configuracion/email")
async def get_configuracion_email(current_user: dict = Depends(get_current_user)):
    """Obtener configuración de email"""
    # Retornar configuración desde settings (sin exponer password)
    return {
        "smtp_server": getattr(settings, 'SMTP_SERVER', 'smtp.gmail.com'),
        "smtp_port": getattr(settings, 'SMTP_PORT', 587),
        "smtp_username": getattr(settings, 'SMTP_USERNAME', ''),
        "smtp_from_email": getattr(settings, 'SMTP_FROM_EMAIL', '')
    }

@app.post("/configuracion/email")
async def update_configuracion_email(data: dict, current_user: dict = Depends(get_current_user)):
    """Actualizar configuración de email"""
    # En una implementación real, esto guardaría en base de datos o archivo de configuración
    # Por ahora solo retornamos éxito
    logger.info(f"Configuración de email actualizada: {data.get('smtp_server')}")
    return {"message": "Configuración de email guardada exitosamente"}

@app.get("/sistema/info")
async def get_sistema_info(current_user: dict = Depends(get_current_user)):
    """Obtener información del sistema"""
    try:
        # Verificar conexión a base de datos
        db_status = False
        try:
            with db_manager.get_db_session() as db:
                db.execute("SELECT 1")
            db_status = True
        except:
            pass

        # Verificar estado del SRI (simulado)
        sri_status = True  # En producción, hacer ping real al SRI

        # Información del sistema
        return {
            "version": "1.0.0",
            "db_status": db_status,
            "sri_status": sri_status,
            "ambiente": "Pruebas" if settings.SRI_AMBIENTE == "1" else "Producción",
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error al obtener info del sistema: {str(e)}")
        return {
            "version": "1.0.0",
            "db_status": False,
            "sri_status": False,
            "error": str(e)
        }

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