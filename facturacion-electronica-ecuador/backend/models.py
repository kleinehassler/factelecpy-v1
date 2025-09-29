"""
Modelos de base de datos para el sistema de facturación electrónica del SRI Ecuador
"""
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, Integer, String, DateTime, Date, Boolean, Text, 
    DECIMAL, ForeignKey, UniqueConstraint, Index, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.dialects.mysql import ENUM


Base = declarative_base()


class TipoIdentificacion(str, PyEnum):
    """Tipos de identificación según SRI"""
    RUC = "04"
    CEDULA = "05" 
    PASAPORTE = "06"
    VENTA_CONSUMIDOR_FINAL = "07"
    IDENTIFICACION_EXTERIOR = "08"


class TipoComprobante(str, PyEnum):
    """Tipos de comprobantes electrónicos"""
    FACTURA = "01"
    LIQUIDACION_COMPRA = "03"
    NOTA_CREDITO = "04"
    NOTA_DEBITO = "05"
    GUIA_REMISION = "06"
    COMPROBANTE_RETENCION = "07"


class EstadoSRI(str, PyEnum):
    """Estados de documentos en el SRI"""
    GENERADO = "GENERADO"
    FIRMADO = "FIRMADO"
    AUTORIZADO = "AUTORIZADO"
    RECHAZADO = "RECHAZADO"
    DEVUELTO = "DEVUELTO"


class Empresa(Base):
    """Modelo de empresas emisoras"""
    __tablename__ = "empresas"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ruc = Column(String(13), nullable=False, unique=True)
    razon_social = Column(String(300), nullable=False)
    nombre_comercial = Column(String(300))
    direccion_matriz = Column(String(300), nullable=False)
    telefono = Column(String(20))
    email = Column(String(100))
    obligado_contabilidad = Column(ENUM('SI', 'NO'), default='NO')
    contribuyente_especial = Column(String(10))
    logo_path = Column(String(255))
    cert_path = Column(String(255))
    cert_password = Column(String(255))
    ambiente = Column(ENUM('1', '2'), default='1')  # 1=Pruebas, 2=Producción
    tipo_emision = Column(ENUM('1', '2'), default='1')  # 1=Normal, 2=Contingencia
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    establecimientos = relationship("Establecimiento", back_populates="empresa")
    facturas = relationship("Factura", back_populates="empresa")
    proformas = relationship("Proforma", back_populates="empresa")


class Establecimiento(Base):
    """Modelo de establecimientos"""
    __tablename__ = "establecimientos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    codigo = Column(String(3), nullable=False)
    direccion = Column(String(300), nullable=False)
    nombre = Column(String(300))
    telefono = Column(String(20))
    email = Column(String(100))
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    empresa = relationship("Empresa", back_populates="establecimientos")
    puntos_emision = relationship("PuntoEmision", back_populates="establecimiento")
    facturas = relationship("Factura", back_populates="establecimiento")
    proformas = relationship("Proforma", back_populates="establecimiento")
    
    __table_args__ = (
        UniqueConstraint('empresa_id', 'codigo', name='uk_empresa_codigo'),
    )


class PuntoEmision(Base):
    """Modelo de puntos de emisión"""
    __tablename__ = "puntos_emision"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    establecimiento_id = Column(Integer, ForeignKey("establecimientos.id"), nullable=False)
    codigo = Column(String(3), nullable=False)
    descripcion = Column(String(300))
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    establecimiento = relationship("Establecimiento", back_populates="puntos_emision")
    secuencias = relationship("Secuencia", back_populates="punto_emision")
    facturas = relationship("Factura", back_populates="punto_emision")
    proformas = relationship("Proforma", back_populates="punto_emision")
    
    __table_args__ = (
        UniqueConstraint('establecimiento_id', 'codigo', name='uk_establecimiento_codigo'),
    )


class Cliente(Base):
    """Modelo de clientes"""
    __tablename__ = "clientes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tipo_identificacion = Column(ENUM('04', '05', '06', '07', '08'), nullable=False)
    identificacion = Column(String(20), nullable=False)
    razon_social = Column(String(300), nullable=False)
    direccion = Column(String(300))
    telefono = Column(String(20))
    email = Column(String(100))
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    facturas = relationship("Factura", back_populates="cliente")
    proformas = relationship("Proforma", back_populates="cliente")
    
    __table_args__ = (
        UniqueConstraint('tipo_identificacion', 'identificacion', name='uk_tipo_identificacion'),
        Index('idx_clientes_identificacion', 'identificacion'),
    )


class Producto(Base):
    """Modelo de productos/servicios"""
    __tablename__ = "productos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo_principal = Column(String(25), nullable=False, unique=True)
    codigo_auxiliar = Column(String(25))
    descripcion = Column(String(300), nullable=False)
    precio_unitario = Column(DECIMAL(12, 6), nullable=False)
    tipo = Column(ENUM('BIEN', 'SERVICIO'), default='BIEN')
    codigo_impuesto = Column(String(2), default='2')  # 2=IVA
    porcentaje_iva = Column(DECIMAL(5, 4), default=0.12)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_productos_codigo', 'codigo_principal'),
    )


class Secuencia(Base):
    """Modelo de secuencias de documentos"""
    __tablename__ = "secuencias"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    punto_emision_id = Column(Integer, ForeignKey("puntos_emision.id"), nullable=False)
    tipo_comprobante = Column(ENUM('01', '03', '04', '05', '06', '07'), nullable=False)
    secuencia_actual = Column(Integer, nullable=False, default=0)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    punto_emision = relationship("PuntoEmision", back_populates="secuencias")
    
    __table_args__ = (
        UniqueConstraint('punto_emision_id', 'tipo_comprobante', name='uk_punto_tipo'),
    )


class Factura(Base):
    """Modelo de facturas electrónicas"""
    __tablename__ = "facturas"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Referencias
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    establecimiento_id = Column(Integer, ForeignKey("establecimientos.id"), nullable=False)
    punto_emision_id = Column(Integer, ForeignKey("puntos_emision.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    
    # Información del comprobante
    tipo_comprobante = Column(String(2), default='01')
    numero_comprobante = Column(String(17), nullable=False)
    fecha_emision = Column(DateTime, nullable=False)
    ambiente = Column(String(1), nullable=False)
    tipo_emision = Column(String(1), nullable=False)
    clave_acceso = Column(String(49), nullable=False, unique=True)
    
    # Información tributaria
    subtotal_sin_impuestos = Column(DECIMAL(12, 2), nullable=False)
    subtotal_0 = Column(DECIMAL(12, 2), default=0)
    subtotal_12 = Column(DECIMAL(12, 2), default=0)
    subtotal_no_objeto_iva = Column(DECIMAL(12, 2), default=0)
    subtotal_exento_iva = Column(DECIMAL(12, 2), default=0)
    total_descuento = Column(DECIMAL(12, 2), default=0)
    ice = Column(DECIMAL(12, 2), default=0)
    iva_12 = Column(DECIMAL(12, 2), default=0)
    irbpnr = Column(DECIMAL(12, 2), default=0)
    propina = Column(DECIMAL(12, 2), default=0)
    valor_total = Column(DECIMAL(12, 2), nullable=False)
    
    # Información adicional
    moneda = Column(String(3), default='DOLAR')
    observaciones = Column(Text)
    
    # Estados del documento
    estado_sri = Column(ENUM('GENERADO', 'FIRMADO', 'AUTORIZADO', 'RECHAZADO', 'DEVUELTO'), default='GENERADO')
    numero_autorizacion = Column(String(49))
    fecha_autorizacion = Column(DateTime)
    
    # Archivos generados
    xml_path = Column(String(500))
    xml_firmado_path = Column(String(500))
    pdf_path = Column(String(500))
    
    # Envío por correo
    email_enviado = Column(Boolean, default=False)
    fecha_email = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    empresa = relationship("Empresa", back_populates="facturas")
    establecimiento = relationship("Establecimiento", back_populates="facturas")
    punto_emision = relationship("PuntoEmision", back_populates="facturas")
    cliente = relationship("Cliente", back_populates="facturas")
    detalles = relationship("FacturaDetalle", back_populates="factura", cascade="all, delete-orphan")
    info_adicional = relationship("FacturaInfoAdicional", back_populates="factura", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_numero_comprobante', 'numero_comprobante'),
        Index('idx_clave_acceso', 'clave_acceso'),
        Index('idx_fecha_emision', 'fecha_emision'),
        Index('idx_estado_sri', 'estado_sri'),
        Index('idx_facturas_fecha', 'fecha_emision'),
        Index('idx_facturas_cliente', 'cliente_id'),
    )


class FacturaDetalle(Base):
    """Modelo de detalles de factura"""
    __tablename__ = "factura_detalles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    factura_id = Column(Integer, ForeignKey("facturas.id"), nullable=False)
    codigo_principal = Column(String(25), nullable=False)
    codigo_auxiliar = Column(String(25))
    descripcion = Column(String(300), nullable=False)
    cantidad = Column(DECIMAL(12, 6), nullable=False)
    precio_unitario = Column(DECIMAL(12, 6), nullable=False)
    descuento = Column(DECIMAL(12, 2), default=0)
    precio_total_sin_impuesto = Column(DECIMAL(12, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    factura = relationship("Factura", back_populates="detalles")
    impuestos = relationship("FacturaDetalleImpuesto", back_populates="detalle", cascade="all, delete-orphan")


class FacturaDetalleImpuesto(Base):
    """Modelo de impuestos por detalle de factura"""
    __tablename__ = "factura_detalle_impuestos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    detalle_id = Column(Integer, ForeignKey("factura_detalles.id"), nullable=False)
    codigo = Column(String(2), nullable=False)  # 2=IVA, 3=ICE, 5=IRBPNR
    codigo_porcentaje = Column(String(4), nullable=False)
    tarifa = Column(DECIMAL(5, 4), nullable=False)
    base_imponible = Column(DECIMAL(12, 2), nullable=False)
    valor = Column(DECIMAL(12, 2), nullable=False)
    
    # Relaciones
    detalle = relationship("FacturaDetalle", back_populates="impuestos")


class FacturaInfoAdicional(Base):
    """Modelo de información adicional de factura"""
    __tablename__ = "factura_info_adicional"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    factura_id = Column(Integer, ForeignKey("facturas.id"), nullable=False)
    nombre = Column(String(50), nullable=False)
    valor = Column(String(300), nullable=False)
    
    # Relaciones
    factura = relationship("Factura", back_populates="info_adicional")


class Proforma(Base):
    """Modelo de proformas"""
    __tablename__ = "proformas"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Referencias
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    establecimiento_id = Column(Integer, ForeignKey("establecimientos.id"), nullable=False)
    punto_emision_id = Column(Integer, ForeignKey("puntos_emision.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    
    numero_proforma = Column(String(17), nullable=False)
    fecha_emision = Column(DateTime, nullable=False)
    fecha_validez = Column(Date)
    
    # Valores
    subtotal_sin_impuestos = Column(DECIMAL(12, 2), nullable=False)
    subtotal_0 = Column(DECIMAL(12, 2), default=0)
    subtotal_12 = Column(DECIMAL(12, 2), default=0)
    total_descuento = Column(DECIMAL(12, 2), default=0)
    iva_12 = Column(DECIMAL(12, 2), default=0)
    valor_total = Column(DECIMAL(12, 2), nullable=False)
    
    observaciones = Column(Text)
    estado = Column(ENUM('ACTIVA', 'FACTURADA', 'VENCIDA', 'CANCELADA'), default='ACTIVA')
    
    # Archivos
    pdf_path = Column(String(500))
    email_enviado = Column(Boolean, default=False)
    fecha_email = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    empresa = relationship("Empresa", back_populates="proformas")
    establecimiento = relationship("Establecimiento", back_populates="proformas")
    punto_emision = relationship("PuntoEmision", back_populates="proformas")
    cliente = relationship("Cliente", back_populates="proformas")
    detalles = relationship("ProformaDetalle", back_populates="proforma", cascade="all, delete-orphan")


class ProformaDetalle(Base):
    """Modelo de detalles de proforma"""
    __tablename__ = "proforma_detalles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    proforma_id = Column(Integer, ForeignKey("proformas.id"), nullable=False)
    codigo_principal = Column(String(25), nullable=False)
    codigo_auxiliar = Column(String(25))
    descripcion = Column(String(300), nullable=False)
    cantidad = Column(DECIMAL(12, 6), nullable=False)
    precio_unitario = Column(DECIMAL(12, 6), nullable=False)
    descuento = Column(DECIMAL(12, 2), default=0)
    precio_total_sin_impuesto = Column(DECIMAL(12, 2), nullable=False)
    codigo_impuesto = Column(String(2), default='2')
    porcentaje_iva = Column(DECIMAL(5, 4), default=0.12)
    
    # Relaciones
    proforma = relationship("Proforma", back_populates="detalles")


class LogSistema(Base):
    """Modelo de logs del sistema"""
    __tablename__ = "logs_sistema"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tipo = Column(ENUM('INFO', 'WARNING', 'ERROR', 'DEBUG'), nullable=False)
    modulo = Column(String(50), nullable=False)
    mensaje = Column(Text, nullable=False)
    detalle = Column(JSON)
    usuario = Column(String(50))
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=datetime.utcnow)


class Usuario(Base):
    """Modelo de usuarios del sistema"""
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(100), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    activo = Column(Boolean, default=True)
    es_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)