"""
Sistema de base de datos para facturación electrónica del SRI Ecuador
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
import logging
from typing import Optional, List
import os

from config.settings import settings
from backend.models import Base, Empresa, Establecimiento, PuntoEmision, Cliente, Producto, Secuencia, Factura, Proforma, Usuario


class DatabaseManager:
    """Gestor de base de datos para el sistema de facturación electrónica"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._setup_database()
    
    def _setup_database(self):
        """Configurar conexión a la base de datos"""
        try:
            # Crear motor de base de datos
            self.engine = create_engine(
                settings.DATABASE_URL,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=settings.DEBUG
            )
            
            # Crear sesión
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            # Crear tablas si no existen
            Base.metadata.create_all(bind=self.engine)
            
        except Exception as e:
            raise Exception(f"Error al configurar base de datos: {str(e)}")
    
    @contextmanager
    def get_db_session(self):
        """Obtener sesión de base de datos con contexto"""
        db = self.SessionLocal()
        try:
            yield db
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def test_connection(self) -> bool:
        """Probar conexión a la base de datos"""
        try:
            with self.get_db_session() as db:
                db.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logging.error(f"Error de conexión a la base de datos: {str(e)}")
            return False
    
    def crear_empresa_base(self):
        """Crear empresa base de ejemplo si no existe"""
        with self.get_db_session() as db:
            empresa = db.query(Empresa).filter(Empresa.ruc == settings.EMPRESA_RUC).first()
            if not empresa:
                empresa = Empresa(
                    ruc=settings.EMPRESA_RUC,
                    razon_social=settings.EMPRESA_RAZON_SOCIAL,
                    nombre_comercial=settings.EMPRESA_NOMBRE_COMERCIAL,
                    direccion_matriz=settings.EMPRESA_DIRECCION,
                    telefono=settings.EMPRESA_TELEFONO,
                    email=settings.EMPRESA_EMAIL,
                    obligado_contabilidad="SI",
                    ambiente=settings.SRI_AMBIENTE,
                    tipo_emision=settings.SRI_TIPO_EMISION
                )
                db.add(empresa)
                db.commit()
                
                # Crear establecimiento matriz
                establecimiento = Establecimiento(
                    empresa_id=empresa.id,
                    codigo="001",
                    direccion=settings.EMPRESA_DIRECCION,
                    nombre="MATRIZ"
                )
                db.add(establecimiento)
                db.commit()
                
                # Crear punto de emisión
                punto_emision = PuntoEmision(
                    establecimiento_id=establecimiento.id,
                    codigo="001",
                    descripcion="CAJA PRINCIPAL"
                )
                db.add(punto_emision)
                db.commit()
                
                # Crear secuencias iniciales
                secuencia_factura = Secuencia(
                    punto_emision_id=punto_emision.id,
                    tipo_comprobante="01",  # Factura
                    secuencia_actual=0
                )
                db.add(secuencia_factura)
                db.commit()
                
                print("Empresa base creada exitosamente")
    
    def crear_usuario_admin(self):
        """Crear usuario administrador si no existe"""
        from passlib.context import CryptContext
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        with self.get_db_session() as db:
            usuario = db.query(Usuario).filter(Usuario.username == "admin").first()
            if not usuario:
                hashed_password = pwd_context.hash("admin123")
                usuario = Usuario(
                    username="admin",
                    email="admin@ejemplo.com",
                    password_hash=hashed_password,
                    nombre="Administrador",
                    apellido="Sistema",
                    es_admin=True
                )
                db.add(usuario)
                db.commit()
                print("Usuario administrador creado (usuario: admin, contraseña: admin123)")


class FacturaRepository:
    """Repositorio para operaciones con facturas"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def crear_factura(self, factura_data: dict) -> Factura:
        """Crear nueva factura de forma transaccional y segura.

        - Usa flush() para forzar la validación a nivel de base de datos antes del commit.
        - En caso de error realiza rollback para dejar la sesión en estado consistente.
        - Devuelve la instancia persistida (refrescada) si la operación es exitosa.
        """
        try:
            factura = Factura(**factura_data)
            self.db.add(factura)
            # flush para enviar cambios a la BD y obtener valores generados (p. ej. id)
            self.db.flush()
            self.db.commit()
            # refrescar la instancia para asegurar que tiene los valores actuales de la BD
            self.db.refresh(factura)
            return factura
        except Exception:
            # Asegurar que la sesión queda en un estado limpio en caso de fallo
            try:
                self.db.rollback()
            except Exception:
                pass
            # Re-lanzar la excepción para que el llamador pueda manejarla/loguearla
            raise
    
    def obtener_factura_por_id(self, factura_id: int) -> Optional[Factura]:
        """Obtener factura por ID"""
        return self.db.query(Factura).filter(Factura.id == factura_id).first()
    
    def obtener_factura_por_clave_acceso(self, clave_acceso: str) -> Optional[Factura]:
        """Obtener factura por clave de acceso"""
        return self.db.query(Factura).filter(Factura.clave_acceso == clave_acceso).first()
    
    def obtener_factura_por_numero(self, numero_comprobante: str) -> Optional[Factura]:
        """Obtener factura por número de comprobante"""
        return self.db.query(Factura).filter(Factura.numero_comprobante == numero_comprobante).first()
    
    def listar_facturas(self, skip: int = 0, limit: int = 100) -> List[Factura]:
        """Listar facturas con paginación"""
        return self.db.query(Factura).offset(skip).limit(limit).all()
    
    def actualizar_estado_factura(self, factura_id: int, estado: str, 
                                numero_autorizacion: str = None, 
                                fecha_autorizacion: str = None) -> bool:
        """Actualizar estado de factura"""
        factura = self.obtener_factura_por_id(factura_id)
        if factura:
            factura.estado_sri = estado
            if numero_autorizacion:
                factura.numero_autorizacion = numero_autorizacion
            if fecha_autorizacion:
                factura.fecha_autorizacion = fecha_autorizacion
            self.db.commit()
            return True
        return False
    
    def actualizar_rutas_archivos(self, factura_id: int, xml_path: str = None,
                                 xml_firmado_path: str = None, pdf_path: str = None) -> bool:
        """Actualizar rutas de archivos de la factura"""
        factura = self.obtener_factura_por_id(factura_id)
        if factura:
            if xml_path:
                factura.xml_path = xml_path
            if xml_firmado_path:
                factura.xml_firmado_path = xml_firmado_path
            if pdf_path:
                factura.pdf_path = pdf_path
            self.db.commit()
            return True
        return False


class ProformaRepository:
    """Repositorio para operaciones con proformas"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def crear_proforma(self, proforma_data: dict) -> Proforma:
        """Crear nueva proforma"""
        proforma = Proforma(**proforma_data)
        self.db.add(proforma)
        self.db.commit()
        self.db.refresh(proforma)
        return proforma
    
    def obtener_proforma_por_id(self, proforma_id: int) -> Optional[Proforma]:
        """Obtener proforma por ID"""
        return self.db.query(Proforma).filter(Proforma.id == proforma_id).first()
    
    def listar_proformas(self, skip: int = 0, limit: int = 100) -> List[Proforma]:
        """Listar proformas con paginación"""
        return self.db.query(Proforma).offset(skip).limit(limit).all()


class ClienteRepository:
    """Repositorio para operaciones con clientes"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def crear_cliente(self, cliente_data: dict) -> Cliente:
        """Crear nuevo cliente"""
        cliente = Cliente(**cliente_data)
        self.db.add(cliente)
        self.db.commit()
        self.db.refresh(cliente)
        return cliente
    
    def obtener_cliente_por_id(self, cliente_id: int) -> Optional[Cliente]:
        """Obtener cliente por ID"""
        return self.db.query(Cliente).filter(Cliente.id == cliente_id).first()
    
    def obtener_cliente_por_identificacion(self, tipo_identificacion: str, 
                                         identificacion: str) -> Optional[Cliente]:
        """Obtener cliente por tipo e identificación"""
        return self.db.query(Cliente).filter(
            Cliente.tipo_identificacion == tipo_identificacion,
            Cliente.identificacion == identificacion
        ).first()
    
    def listar_clientes(self, skip: int = 0, limit: int = 100) -> List[Cliente]:
        """Listar clientes con paginación"""
        return self.db.query(Cliente).offset(skip).limit(limit).all()


class ProductoRepository:
    """Repositorio para operaciones con productos"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def crear_producto(self, producto_data: dict) -> Producto:
        """Crear nuevo producto"""
        producto = Producto(**producto_data)
        self.db.add(producto)
        self.db.commit()
        self.db.refresh(producto)
        return producto
    
    def obtener_producto_por_id(self, producto_id: int) -> Optional[Producto]:
        """Obtener producto por ID"""
        return self.db.query(Producto).filter(Producto.id == producto_id).first()
    
    def obtener_producto_por_codigo(self, codigo_principal: str) -> Optional[Producto]:
        """Obtener producto por código principal"""
        return self.db.query(Producto).filter(Producto.codigo_principal == codigo_principal).first()
    
    def listar_productos(self, skip: int = 0, limit: int = 100) -> List[Producto]:
        """Listar productos con paginación"""
        return self.db.query(Producto).offset(skip).limit(limit).all()


class SecuenciaManager:
    """Gestor de secuencias de documentos"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def obtener_siguiente_secuencia(self, punto_emision_id: int, 
                                  tipo_comprobante: str) -> tuple[str, str]:
        """
        Obtener siguiente número de secuencia y generar número de comprobante
        
        Returns:
            tuple: (numero_comprobante, secuencia_actualizada)
        """
        # Obtener secuencia
        secuencia = self.db.query(Secuencia).filter(
            Secuencia.punto_emision_id == punto_emision_id,
            Secuencia.tipo_comprobante == tipo_comprobante
        ).first()
        
        if not secuencia:
            raise Exception(f"No se encontró secuencia para tipo {tipo_comprobante}")
        
        # Incrementar secuencia
        secuencia.siguiente_numero = secuencia.siguiente_numero + 1 if hasattr(secuencia, 'siguiente_numero') else secuencia.secuencia_actual + 1
        self.db.commit()
        
        # Formatear número de comprobante
        # Obtener establecimiento y punto de emisión para formar el número completo
        punto_emision = self.db.query(PuntoEmision).filter(
            PuntoEmision.id == punto_emision_id
        ).first()
        
        if not punto_emision:
            raise Exception("No se encontró punto de emisión")
        
        establecimiento = self.db.query(Establecimiento).filter(
            Establecimiento.id == punto_emision.establecimiento_id
        ).first()
        
        if not establecimiento:
            raise Exception("No se encontró establecimiento")
        
        # Formato: XXX-XXX-XXXXXXXXX
        numero_comprobante = f"{establecimiento.codigo}-{punto_emision.codigo}-{secuencia.siguiente_numero:09d}"
        
        return numero_comprobante, str(secuencia.siguiente_numero)


def inicializar_base_datos():
    """Inicializar base de datos con datos básicos"""
    try:
        db_manager = DatabaseManager()
        
        if db_manager.test_connection():
            print("✓ Conexión a base de datos exitosa")
            
            # Crear estructura de base de datos
            Base.metadata.create_all(bind=db_manager.engine)
            print("✓ Estructura de base de datos creada")
            
            # Crear datos base
            db_manager.crear_empresa_base()
            db_manager.crear_usuario_admin()
            
            return True
        else:
            print("✗ Error en conexión a base de datos")
            return False
            
    except Exception as e:
        print(f"✗ Error al inicializar base de datos: {str(e)}")
        return False


if __name__ == "__main__":
    print("Sistema de base de datos para facturación electrónica del SRI Ecuador")
    inicializar_base_datos()