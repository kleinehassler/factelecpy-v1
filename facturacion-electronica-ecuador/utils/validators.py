"""
Sistema de validaciones para facturación electrónica del SRI Ecuador
"""
import re
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Excepción para errores de validación"""
    def __init__(self, message: str, field: str = None, code: str = None):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)


class EcuadorianValidator:
    """Validador para documentos y datos ecuatorianos"""
    
    @staticmethod
    def validate_cedula(cedula: str) -> bool:
        """
        Validar cédula ecuatoriana
        
        Args:
            cedula: Número de cédula
            
        Returns:
            bool: True si es válida
        """
        if not cedula or len(cedula) != 10:
            return False
        
        if not cedula.isdigit():
            return False
        
        # Validar provincia (primeros 2 dígitos)
        provincia = int(cedula[:2])
        if provincia < 1 or provincia > 24:
            return False
        
        # Validar tercer dígito
        tercer_digito = int(cedula[2])
        if tercer_digito > 6:
            return False
        
        # Algoritmo de validación
        coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        suma = 0
        
        for i in range(9):
            valor = int(cedula[i]) * coeficientes[i]
            if valor > 9:
                valor -= 9
            suma += valor
        
        digito_verificador = (10 - (suma % 10)) % 10
        
        return digito_verificador == int(cedula[9])
    
    @staticmethod
    def validate_ruc(ruc: str) -> bool:
        """
        Validar RUC ecuatoriano
        
        Args:
            ruc: Número de RUC
            
        Returns:
            bool: True si es válido
        """
        if not ruc or len(ruc) != 13:
            return False
        
        if not ruc.isdigit():
            return False
        
        # Validar que termine en 001
        if not ruc.endswith('001'):
            return False
        
        # Validar los primeros 10 dígitos como cédula
        cedula_parte = ruc[:10]
        
        # Para RUC de personas naturales, validar como cédula
        tercer_digito = int(ruc[2])
        if tercer_digito < 6:
            return EcuadorianValidator.validate_cedula(cedula_parte)
        
        # Para RUC de sociedades públicas (tercer dígito = 6)
        elif tercer_digito == 6:
            return EcuadorianValidator._validate_ruc_publico(ruc)
        
        # Para RUC de sociedades privadas (tercer dígito = 9)
        elif tercer_digito == 9:
            return EcuadorianValidator._validate_ruc_privado(ruc)
        
        return False
    
    @staticmethod
    def _validate_ruc_publico(ruc: str) -> bool:
        """Validar RUC de entidad pública (9 dígitos, incluye dígito verificador)"""
        coeficientes = [3, 2, 7, 6, 5, 4, 3, 2]
        suma = 0

        # Usar 8 coeficientes para los primeros 8 dígitos
        for i in range(8):
            suma += int(ruc[i]) * coeficientes[i]

        digito_verificador = 11 - (suma % 11)
        if digito_verificador == 11:
            digito_verificador = 0
        elif digito_verificador == 10:
            digito_verificador = 1

        return digito_verificador == int(ruc[8])
    
    @staticmethod
    def _validate_ruc_privado(ruc: str) -> bool:
        """Validar RUC de sociedad privada"""
        coeficientes = [4, 3, 2, 7, 6, 5, 4, 3, 2]
        suma = 0
        
        for i in range(9):
            suma += int(ruc[i]) * coeficientes[i]
        
        digito_verificador = 11 - (suma % 11)
        if digito_verificador == 11:
            digito_verificador = 0
        elif digito_verificador == 10:
            digito_verificador = 1
        
        return digito_verificador == int(ruc[9])
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validar formato de email"""
        if not email:
            return True  # Email es opcional
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validar formato de teléfono ecuatoriano"""
        if not phone:
            return True  # Teléfono es opcional
        
        # Remover espacios y guiones
        clean_phone = re.sub(r'[\s-]', '', phone)
        
        # Validar formato ecuatoriano
        patterns = [
            r'^0[2-7]\d{7}$',  # Teléfono fijo: 02-2345678
            r'^09\d{8}$',      # Celular: 0987654321
            r'^593[2-7]\d{7}$', # Internacional fijo: 593-2-2345678
            r'^5939\d{8}$'     # Internacional celular: 593-9-87654321
        ]
        
        return any(re.match(pattern, clean_phone) for pattern in patterns)


class BusinessValidator:
    """Validador para reglas de negocio"""
    
    @staticmethod
    def validate_factura_data(data: Dict[str, Any]) -> List[ValidationError]:
        """
        Validar datos de factura
        
        Args:
            data: Datos de la factura
            
        Returns:
            List[ValidationError]: Lista de errores encontrados
        """
        errors = []
        
        # Validar cliente_id
        if not data.get('cliente_id'):
            errors.append(ValidationError("Cliente es requerido", "cliente_id", "REQUIRED"))
        
        # Validar detalles
        detalles = data.get('detalles', [])
        if not detalles:
            errors.append(ValidationError("Debe incluir al menos un detalle", "detalles", "REQUIRED"))
        
        # Validar cada detalle
        for i, detalle in enumerate(detalles):
            detalle_errors = BusinessValidator._validate_detalle(detalle, i)
            errors.extend(detalle_errors)
        
        return errors
    
    @staticmethod
    def _validate_detalle(detalle: Dict[str, Any], index: int) -> List[ValidationError]:
        """Validar detalle de factura"""
        errors = []
        prefix = f"detalles[{index}]"
        
        # Validar código principal
        if not detalle.get('codigo_principal'):
            errors.append(ValidationError(
                "Código principal es requerido", 
                f"{prefix}.codigo_principal", 
                "REQUIRED"
            ))
        
        # Validar cantidad
        cantidad = detalle.get('cantidad')
        if not cantidad or cantidad <= 0:
            errors.append(ValidationError(
                "Cantidad debe ser mayor a 0", 
                f"{prefix}.cantidad", 
                "INVALID_VALUE"
            ))
        
        # Validar precio unitario
        precio = detalle.get('precio_unitario')
        if not precio or precio <= 0:
            errors.append(ValidationError(
                "Precio unitario debe ser mayor a 0", 
                f"{prefix}.precio_unitario", 
                "INVALID_VALUE"
            ))
        
        # Validar descuento
        descuento = detalle.get('descuento', 0)
        if descuento < 0:
            errors.append(ValidationError(
                "Descuento no puede ser negativo", 
                f"{prefix}.descuento", 
                "INVALID_VALUE"
            ))
        
        # Validar que el descuento no sea mayor al subtotal
        if cantidad and precio and descuento:
            subtotal = cantidad * precio
            if descuento > subtotal:
                errors.append(ValidationError(
                    "Descuento no puede ser mayor al subtotal", 
                    f"{prefix}.descuento", 
                    "INVALID_VALUE"
                ))
        
        return errors
    
    @staticmethod
    def validate_cliente_data(data: Dict[str, Any]) -> List[ValidationError]:
        """Validar datos de cliente"""
        errors = []
        
        # Validar tipo de identificación
        tipo_id = data.get('tipo_identificacion')
        if not tipo_id:
            errors.append(ValidationError(
                "Tipo de identificación es requerido", 
                "tipo_identificacion", 
                "REQUIRED"
            ))
        elif tipo_id not in ['04', '05', '06', '07', '08']:
            errors.append(ValidationError(
                "Tipo de identificación inválido", 
                "tipo_identificacion", 
                "INVALID_VALUE"
            ))
        
        # Validar identificación
        identificacion = data.get('identificacion')
        if not identificacion:
            errors.append(ValidationError(
                "Identificación es requerida", 
                "identificacion", 
                "REQUIRED"
            ))
        elif tipo_id == '04' and not EcuadorianValidator.validate_ruc(identificacion):
            errors.append(ValidationError(
                "RUC inválido", 
                "identificacion", 
                "INVALID_FORMAT"
            ))
        elif tipo_id == '05' and not EcuadorianValidator.validate_cedula(identificacion):
            errors.append(ValidationError(
                "Cédula inválida", 
                "identificacion", 
                "INVALID_FORMAT"
            ))
        
        # Validar razón social
        if not data.get('razon_social'):
            errors.append(ValidationError(
                "Razón social es requerida", 
                "razon_social", 
                "REQUIRED"
            ))
        
        # Validar email
        email = data.get('email')
        if email and not EcuadorianValidator.validate_email(email):
            errors.append(ValidationError(
                "Formato de email inválido", 
                "email", 
                "INVALID_FORMAT"
            ))
        
        # Validar teléfono
        telefono = data.get('telefono')
        if telefono and not EcuadorianValidator.validate_phone(telefono):
            errors.append(ValidationError(
                "Formato de teléfono inválido", 
                "telefono", 
                "INVALID_FORMAT"
            ))
        
        return errors
    
    @staticmethod
    def validate_producto_data(data: Dict[str, Any]) -> List[ValidationError]:
        """Validar datos de producto"""
        errors = []
        
        # Validar código principal
        if not data.get('codigo_principal'):
            errors.append(ValidationError(
                "Código principal es requerido", 
                "codigo_principal", 
                "REQUIRED"
            ))
        
        # Validar descripción
        if not data.get('descripcion'):
            errors.append(ValidationError(
                "Descripción es requerida", 
                "descripcion", 
                "REQUIRED"
            ))
        
        # Validar precio unitario
        precio = data.get('precio_unitario')
        if not precio or precio <= 0:
            errors.append(ValidationError(
                "Precio unitario debe ser mayor a 0", 
                "precio_unitario", 
                "INVALID_VALUE"
            ))
        
        # Validar tipo
        tipo = data.get('tipo', 'BIEN')
        if tipo not in ['BIEN', 'SERVICIO']:
            errors.append(ValidationError(
                "Tipo debe ser BIEN o SERVICIO", 
                "tipo", 
                "INVALID_VALUE"
            ))
        
        # Validar porcentaje IVA
        iva = data.get('porcentaje_iva', 0.12)
        if iva < 0 or iva > 1:
            errors.append(ValidationError(
                "Porcentaje de IVA debe estar entre 0 y 1", 
                "porcentaje_iva", 
                "INVALID_VALUE"
            ))
        
        return errors


def validate_and_raise(data: Dict[str, Any], validator_func) -> None:
    """
    Validar datos y lanzar excepción si hay errores
    
    Args:
        data: Datos a validar
        validator_func: Función validadora
        
    Raises:
        ValidationError: Si hay errores de validación
    """
    errors = validator_func(data)
    
    if errors:
        # Tomar el primer error para la excepción
        first_error = errors[0]
        
        # Log todos los errores
        logger.warning(f"Errores de validación encontrados: {[e.message for e in errors]}")
        
        raise first_error


def format_validation_errors(errors: List[ValidationError]) -> Dict[str, Any]:
    """
    Formatear errores de validación para respuesta API

    Args:
        errors: Lista de errores

    Returns:
        Dict: Errores formateados
    """
    return {
        "detail": "Errores de validación",
        "errors": [
            {
                "field": error.field,
                "message": error.message,
                "code": error.code
            }
            for error in errors
        ]
    }


# Longitudes máximas según especificación SRI
class SRIFieldLengths:
    """Longitudes máximas de campos según normativa SRI"""
    RAZON_SOCIAL = 300
    NOMBRE_COMERCIAL = 300
    DIRECCION = 300
    CODIGO_PRINCIPAL = 25
    CODIGO_AUXILIAR = 25
    DESCRIPCION = 300
    EMAIL = 300
    TELEFONO = 20
    OBSERVACIONES = 300


def validate_field_length(value: str, field_name: str, max_length: int) -> None:
    """
    Validar longitud máxima de un campo

    Args:
        value: Valor a validar
        field_name: Nombre del campo
        max_length: Longitud máxima permitida

    Raises:
        ValidationError: Si el valor excede la longitud máxima
    """
    if value and len(value) > max_length:
        raise ValidationError(
            f"{field_name} excede la longitud máxima de {max_length} caracteres (actual: {len(value)})",
            field_name,
            "MAX_LENGTH_EXCEEDED"
        )


def sanitize_xml_content(text: str) -> str:
    """
    Sanitizar contenido para XML (escapar caracteres especiales)

    Args:
        text: Texto a sanitizar

    Returns:
        str: Texto sanitizado
    """
    if not text:
        return text

    # Reemplazar caracteres especiales XML
    replacements = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&apos;'
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def validate_and_sanitize_text(text: str, field_name: str, max_length: int) -> str:
    """
    Validar longitud y sanitizar texto para uso en XML

    Args:
        text: Texto a validar y sanitizar
        field_name: Nombre del campo
        max_length: Longitud máxima

    Returns:
        str: Texto sanitizado

    Raises:
        ValidationError: Si el texto excede la longitud máxima
    """
    validate_field_length(text, field_name, max_length)
    return sanitize_xml_content(text)