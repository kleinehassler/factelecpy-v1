"""
API REST para facturación electrónica del SRI Ecuador
Versión mejorada con validaciones y cálculos precisos
"""
from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
import os
import uuid
from decimal import Decimal
import logging
import random

from config.settings import settings
from backend.database import DatabaseManager, FacturaRepository, ClienteRepository, ProductoRepository
from backend.models import Factura, Cliente, Producto, FacturaDetalle, Empresa
from utils.xml_generator import XMLGenerator, ClaveAccesoGenerator
from utils.firma_digital import XadesBesSigner
from utils.ride_generator import RideGenerator
from utils.email_sender import EmailSender, EmailTemplates


# Modelos Pydantic para la API
class ClienteCreate(BaseModel):
    tipo_identificacion: str
    identificacion: str
    razon_social: str
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None


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


class ProductoResponse(ProductoCreate):
    id: int
    activo: bool
    created_at: datetime
    updated_at: datetime


class DetalleFacturaCreate(BaseModel):
    codigo_principal: str
    codigo_auxiliar: Optional[str] = None
    descripcion: Optional[str] = None
    cantidad: Decimal
    precio_unitario: Decimal
    descuento: Decimal = Decimal("0.00")


class FacturaCreate(BaseModel):
    cliente_id: int
    detalles: List[DetalleFacturaCreate]
    observaciones: Optional[str] = None


class FacturaResponse(BaseModel):
    id: int
    numero_comprobante: str
    fecha_emision: datetime
    clave_acceso: str
    subtotal_sin_impuestos: Decimal
    iva_12: Decimal
    valor_total: Decimal
    estado_sri: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# Inicializar aplicación FastAPI
app = FastAPI(
    title="API Facturación Electrónica SRI Ecuador",
    description="API para generación de facturas electrónicas según normativa del SRI",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar autenticación OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Inicializar componentes
db_manager = DatabaseManager()


def generar_numero_comprobante():
    """Generar número de comprobante único"""
    # En una implementación real, esto debería obtener el siguiente número de la base de datos
    # basado en la secuencia del punto de emisión
    numero = str(random.randint(1, 999999999)).zfill(9)
    return f"001-001-{numero}"


# Rutas de la API
@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "API de Facturación Electrónica SRI Ecuador",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/clientes/", response_model=ClienteResponse)
async def crear_cliente(cliente: ClienteCreate):
    """Crear un nuevo cliente"""
    try:
        with db_manager.get_db_session() as db:
            cliente_repo = ClienteRepository(db)

            # Verificar si el cliente ya existe
            cliente_existente = cliente_repo.obtener_cliente_por_identificacion(
                cliente.tipo_identificacion, cliente.identificacion
            )

            if cliente_existente:
                raise HTTPException(
                    status_code=400,
                    detail="Cliente con esta identificación ya existe"
                )

            # Crear cliente
            cliente_db = cliente_repo.crear_cliente(cliente.dict())

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
        logging.error(f"Error al crear cliente: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


@app.get("/clientes/{cliente_id}", response_model=ClienteResponse)
async def obtener_cliente(cliente_id: int):
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
async def crear_producto(producto: ProductoCreate):
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


@app.post("/facturas/", response_model=FacturaResponse)
async def crear_factura(factura_data: FacturaCreate):
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
                "content": xml_content[:1000] + "..." if len(xml_content) > 1000 else xml_content
            }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error al generar XML de factura {factura_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar XML: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"Error al generar RIDE: {str(e)}")


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
        logging.error(f"Error general al enviar email para factura {factura_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al enviar email: {str(e)}")


@app.get("/health")
async def health_check():
    """Verificación de salud del sistema"""
    db_ok = db_manager.test_connection()

    # Verificar existencia de directorios importantes
    directories = [settings.OUTPUT_FOLDER, settings.UPLOAD_FOLDER, settings.TEMP_FOLDER]
    dirs_ok = all(os.path.exists(dir_path) for dir_path in directories)

    # Crear directorios que no existen
    if not dirs_ok:
        for dir_path in directories:
            os.makedirs(dir_path, exist_ok=True)
        dirs_ok = True

    return {
        "status": "healthy" if db_ok and dirs_ok else "unhealthy",
        "database": "connected" if db_ok else "disconnected",
        "directories": "accessible" if dirs_ok else "inaccessible",
        "timestamp": datetime.now()
    }


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
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )