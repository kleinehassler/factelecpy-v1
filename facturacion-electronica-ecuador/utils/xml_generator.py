"""
Generador de XML para facturación electrónica del SRI Ecuador
Versión 2.0.0 del esquema
"""
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
import os
from xml.dom import minidom
import html

from config.settings import settings
from backend.models import Factura, FacturaDetalle, Cliente, Empresa


class XMLGenerator:
    """Generador de XML para documentos electrónicos del SRI"""

    def __init__(self):
        self.namespace = ""
        self.version = "2.0.0"

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """
        Sanitizar texto para XML (escapar caracteres especiales)

        Args:
            text: Texto a sanitizar

        Returns:
            str: Texto sanitizado para XML
        """
        if not text:
            return text

        # Escapar caracteres especiales XML usando html.escape
        # que maneja &, <, >, y opcionalmente " y '
        return html.escape(str(text), quote=True)
    
    def generar_xml_factura(self, factura: Factura, empresa: Empresa, cliente: Cliente, 
                           detalles: List[FacturaDetalle]) -> str:
        """
        Genera el XML de una factura según el esquema del SRI v2.0.0
        
        Args:
            factura: Objeto factura con datos principales
            empresa: Datos de la empresa emisora
            cliente: Datos del cliente
            detalles: Lista de detalles de la factura
            
        Returns:
            str: XML generado como string
        """
        # Crear elemento raíz
        root = ET.Element("factura")
        root.set("id", "comprobante")
        root.set("version", self.version)
        
        # Información tributaria
        info_tributaria = self._crear_info_tributaria(factura, empresa)
        root.append(info_tributaria)
        
        # Información de la factura
        info_factura = self._crear_info_factura(factura, cliente)
        root.append(info_factura)
        
        # Detalles
        detalles_elem = self._crear_detalles(detalles)
        root.append(detalles_elem)
        
        # Información adicional (opcional)
        if factura.info_adicional:
            info_adicional = self._crear_info_adicional(factura.info_adicional)
            root.append(info_adicional)
        
        # Convertir a string XML con formato
        return self._formatear_xml(root)
    
    def _crear_info_tributaria(self, factura: Factura, empresa: Empresa) -> ET.Element:
        """Crear sección de información tributaria"""
        info_trib = ET.Element("infoTributaria")

        ET.SubElement(info_trib, "ambiente").text = factura.ambiente
        ET.SubElement(info_trib, "tipoEmision").text = factura.tipo_emision
        ET.SubElement(info_trib, "razonSocial").text = self._sanitize_text(empresa.razon_social)

        if empresa.nombre_comercial:
            ET.SubElement(info_trib, "nombreComercial").text = self._sanitize_text(empresa.nombre_comercial)

        ET.SubElement(info_trib, "ruc").text = empresa.ruc
        ET.SubElement(info_trib, "claveAcceso").text = factura.clave_acceso
        ET.SubElement(info_trib, "codDoc").text = factura.tipo_comprobante

        # Extraer establecimiento y punto emisión del número de comprobante
        # Formato: XXX-XXX-XXXXXXXXX
        partes = factura.numero_comprobante.split('-')
        ET.SubElement(info_trib, "estab").text = partes[0]
        ET.SubElement(info_trib, "ptoEmi").text = partes[1]
        ET.SubElement(info_trib, "secuencial").text = partes[2]

        ET.SubElement(info_trib, "dirMatriz").text = self._sanitize_text(empresa.direccion_matriz)

        # Contribuyente especial (opcional)
        if empresa.contribuyente_especial:
            ET.SubElement(info_trib, "contribuyenteEspecial").text = empresa.contribuyente_especial

        return info_trib
    
    def _crear_info_factura(self, factura: Factura, cliente: Cliente) -> ET.Element:
        """Crear sección de información de la factura"""
        info_fact = ET.Element("infoFactura")

        # Fecha en formato dd/mm/yyyy
        fecha_str = factura.fecha_emision.strftime("%d/%m/%Y")
        ET.SubElement(info_fact, "fechaEmision").text = fecha_str

        # Datos del cliente (sanitizados)
        ET.SubElement(info_fact, "tipoIdentificacionComprador").text = cliente.tipo_identificacion
        ET.SubElement(info_fact, "razonSocialComprador").text = self._sanitize_text(cliente.razon_social)
        ET.SubElement(info_fact, "identificacionComprador").text = cliente.identificacion

        if cliente.direccion:
            ET.SubElement(info_fact, "direccionComprador").text = self._sanitize_text(cliente.direccion)
        
        # Obligado a llevar contabilidad
        empresa = factura.empresa
        ET.SubElement(info_fact, "obligadoContabilidad").text = empresa.obligado_contabilidad
        
        # Totales
        ET.SubElement(info_fact, "totalSinImpuestos").text = str(factura.subtotal_sin_impuestos)
        ET.SubElement(info_fact, "totalDescuento").text = str(factura.total_descuento)
        
        # Total con impuestos
        total_con_impuestos = self._crear_total_con_impuestos(factura)
        info_fact.append(total_con_impuestos)
        
        ET.SubElement(info_fact, "propina").text = str(factura.propina)
        ET.SubElement(info_fact, "importeTotal").text = str(factura.valor_total)
        ET.SubElement(info_fact, "moneda").text = factura.moneda
        
        # Pagos (opcional - por defecto sin utilización sistema financiero)
        pagos = ET.SubElement(info_fact, "pagos")
        pago = ET.SubElement(pagos, "pago")
        ET.SubElement(pago, "formaPago").text = "01"  # Sin utilización sistema financiero
        ET.SubElement(pago, "total").text = str(factura.valor_total)
        
        return info_fact
    
    def _crear_total_con_impuestos(self, factura: Factura) -> ET.Element:
        """Crear sección de total con impuestos"""
        total_con_impuestos = ET.Element("totalConImpuestos")

        # IVA 0%
        if factura.subtotal_0 > 0:
            total_impuesto = ET.SubElement(total_con_impuestos, "totalImpuesto")
            ET.SubElement(total_impuesto, "codigo").text = "2"
            ET.SubElement(total_impuesto, "codigoPorcentaje").text = "0"
            ET.SubElement(total_impuesto, "baseImponible").text = str(factura.subtotal_0)
            ET.SubElement(total_impuesto, "tarifa").text = "0"
            ET.SubElement(total_impuesto, "valor").text = "0.00"

        # IVA 8% (zonas especiales)
        if hasattr(factura, 'subtotal_8') and factura.subtotal_8 > 0:
            total_impuesto = ET.SubElement(total_con_impuestos, "totalImpuesto")
            ET.SubElement(total_impuesto, "codigo").text = "2"
            ET.SubElement(total_impuesto, "codigoPorcentaje").text = "3"
            ET.SubElement(total_impuesto, "baseImponible").text = str(factura.subtotal_8)
            ET.SubElement(total_impuesto, "tarifa").text = "0.08"
            ET.SubElement(total_impuesto, "valor").text = str(factura.iva_8)

        # IVA 12% (para facturas históricas)
        if factura.subtotal_12 > 0:
            total_impuesto = ET.SubElement(total_con_impuestos, "totalImpuesto")
            ET.SubElement(total_impuesto, "codigo").text = "2"
            ET.SubElement(total_impuesto, "codigoPorcentaje").text = "2"
            ET.SubElement(total_impuesto, "baseImponible").text = str(factura.subtotal_12)
            ET.SubElement(total_impuesto, "tarifa").text = "0.12"
            ET.SubElement(total_impuesto, "valor").text = str(factura.iva_12)

        # IVA 15% (tarifa actual 2024)
        if hasattr(factura, 'subtotal_15') and factura.subtotal_15 > 0:
            total_impuesto = ET.SubElement(total_con_impuestos, "totalImpuesto")
            ET.SubElement(total_impuesto, "codigo").text = "2"
            ET.SubElement(total_impuesto, "codigoPorcentaje").text = "4"
            ET.SubElement(total_impuesto, "baseImponible").text = str(factura.subtotal_15)
            ET.SubElement(total_impuesto, "tarifa").text = "0.15"
            ET.SubElement(total_impuesto, "valor").text = str(factura.iva_15)
        
        # No objeto de IVA
        if factura.subtotal_no_objeto_iva > 0:
            total_impuesto = ET.SubElement(total_con_impuestos, "totalImpuesto")
            ET.SubElement(total_impuesto, "codigo").text = "2"
            ET.SubElement(total_impuesto, "codigoPorcentaje").text = "6"
            ET.SubElement(total_impuesto, "baseImponible").text = str(factura.subtotal_no_objeto_iva)
            ET.SubElement(total_impuesto, "valor").text = "0.00"
        
        # Exento de IVA
        if factura.subtotal_exento_iva > 0:
            total_impuesto = ET.SubElement(total_con_impuestos, "totalImpuesto")
            ET.SubElement(total_impuesto, "codigo").text = "2"
            ET.SubElement(total_impuesto, "codigePorcentaje").text = "7"
            ET.SubElement(total_impuesto, "baseImponible").text = str(factura.subtotal_exento_iva)
            ET.SubElement(total_impuesto, "valor").text = "0.00"
        
        # ICE (si aplica)
        if factura.ice > 0:
            total_impuesto = ET.SubElement(total_con_impuestos, "totalImpuesto")
            ET.SubElement(total_impuesto, "codigo").text = "3"
            ET.SubElement(total_impuesto, "baseImponible").text = str(factura.subtotal_sin_impuestos)
            ET.SubElement(total_impuesto, "valor").text = str(factura.ice)
        
        return total_con_impuestos
    
    def _crear_detalles(self, detalles: List[FacturaDetalle]) -> ET.Element:
        """Crear sección de detalles de la factura"""
        detalles_elem = ET.Element("detalles")

        for detalle in detalles:
            detalle_elem = ET.SubElement(detalles_elem, "detalle")

            ET.SubElement(detalle_elem, "codigoPrincipal").text = self._sanitize_text(detalle.codigo_principal)

            if detalle.codigo_auxiliar:
                ET.SubElement(detalle_elem, "codigoAuxiliar").text = self._sanitize_text(detalle.codigo_auxiliar)

            ET.SubElement(detalle_elem, "descripcion").text = self._sanitize_text(detalle.descripcion)
            ET.SubElement(detalle_elem, "cantidad").text = str(detalle.cantidad)
            ET.SubElement(detalle_elem, "precioUnitario").text = str(detalle.precio_unitario)
            ET.SubElement(detalle_elem, "descuento").text = str(detalle.descuento)
            ET.SubElement(detalle_elem, "precioTotalSinImpuesto").text = str(detalle.precio_total_sin_impuesto)
            
            # Impuestos del detalle
            impuestos_elem = self._crear_impuestos_detalle(detalle)
            detalle_elem.append(impuestos_elem)
        
        return detalles_elem
    
    def _crear_impuestos_detalle(self, detalle: FacturaDetalle) -> ET.Element:
        """Crear impuestos para un detalle específico"""
        impuestos_elem = ET.Element("impuestos")
        
        # Por cada impuesto del detalle
        for impuesto_detalle in detalle.impuestos:
            impuesto_elem = ET.SubElement(impuestos_elem, "impuesto")
            
            ET.SubElement(impuesto_elem, "codigo").text = impuesto_detalle.codigo
            ET.SubElement(impuesto_elem, "codigoPorcentaje").text = impuesto_detalle.codigo_porcentaje
            ET.SubElement(impuesto_elem, "tarifa").text = str(impuesto_detalle.tarifa)
            ET.SubElement(impuesto_elem, "baseImponible").text = str(impuesto_detalle.base_imponible)
            ET.SubElement(impuesto_elem, "valor").text = str(impuesto_detalle.valor)
        
        return impuestos_elem
    
    def _crear_info_adicional(self, info_adicional: List) -> ET.Element:
        """Crear sección de información adicional"""
        info_adic_elem = ET.Element("infoAdicional")

        for info in info_adicional:
            campo = ET.SubElement(info_adic_elem, "campoAdicional")
            campo.set("nombre", self._sanitize_text(info.nombre))
            campo.text = self._sanitize_text(info.valor)

        return info_adic_elem
    
    def _formatear_xml(self, element: ET.Element) -> str:
        """Formatear XML con indentación"""
        rough_string = ET.tostring(element, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
    
    def validar_xml_contra_xsd(self, xml_content: str) -> tuple[bool, Optional[str]]:
        """
        Validar XML contra el esquema XSD del SRI
        
        Args:
            xml_content: Contenido XML a validar
            
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        try:
            from lxml import etree
            
            # Cargar esquema XSD
            xsd_path = os.path.join("schemas", "factura_v2.0.0.xsd")
            with open(xsd_path, 'r', encoding='utf-8') as xsd_file:
                xsd_doc = etree.parse(xsd_file)
                xsd_schema = etree.XMLSchema(xsd_doc)
            
            # Validar XML
            xml_doc = etree.fromstring(xml_content.encode('utf-8'))
            
            if xsd_schema.validate(xml_doc):
                return True, None
            else:
                errors = []
                for error in xsd_schema.error_log:
                    errors.append(f"Línea {error.line}: {error.message}")
                return False, "; ".join(errors)
                
        except Exception as e:
            return False, f"Error en validación: {str(e)}"
    
    def guardar_xml(self, xml_content: str, ruta_archivo: str) -> bool:
        """
        Guardar XML en archivo
        
        Args:
            xml_content: Contenido XML
            ruta_archivo: Ruta donde guardar el archivo
            
        Returns:
            bool: True si se guardó correctamente
        """
        try:
            # Crear directorio si no existe
            directorio = os.path.dirname(ruta_archivo)
            if directorio and not os.path.exists(directorio):
                os.makedirs(directorio, exist_ok=True)
            
            with open(ruta_archivo, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            return True
            
        except Exception as e:
            print(f"Error al guardar XML: {str(e)}")
            return False


class ClaveAccesoGenerator:
    """Generador de clave de acceso para documentos electrónicos del SRI"""
    
    @staticmethod
    def generar_clave_acceso(fecha_emision: datetime, tipo_comprobante: str,
                           ruc: str, ambiente: str, serie: str, numero: str,
                           codigo_numerico: str = None, tipo_emision: str = "1") -> str:
        """
        Genera la clave de acceso de 49 dígitos según algoritmo del SRI
        
        Formato: ddmmaaaatipcomprucrubambserienumdígito verificador
        
        Args:
            fecha_emision: Fecha de emisión del documento
            tipo_comprobante: Código tipo comprobante (01=Factura)
            ruc: RUC del emisor
            ambiente: Ambiente (1=Pruebas, 2=Producción)
            serie: Serie del comprobante (establecimiento + punto emisión)
            numero: Número secuencial del comprobante
            codigo_numerico: Código numérico (8 dígitos)
            tipo_emision: Tipo emisión (1=Normal, 2=Contingencia)
            
        Returns:
            str: Clave de acceso de 49 dígitos
        """
        # Generar código numérico aleatorio si no se proporciona
        import random
        if codigo_numerico is None:
            codigo_numerico = str(random.randint(10000000, 99999999))

        # Fecha: ddmmaaaa
        fecha_str = fecha_emision.strftime("%d%m%Y")

        # Asegurar que todos los parámetros sean strings antes de concatenar
        # Construir clave sin dígito verificador (48 dígitos)
        clave_base = (
            str(fecha_str) +                # 8 dígitos
            str(tipo_comprobante) +         # 2 dígitos
            str(ruc) +                      # 13 dígitos
            str(ambiente) +                 # 1 dígito
            str(serie) +                    # 6 dígitos (estab + pto emi)
            str(numero).zfill(9) +          # 9 dígitos
            str(codigo_numerico) +          # 8 dígitos
            str(tipo_emision)               # 1 dígito
        )
        
        # Calcular dígito verificador
        digito_verificador = ClaveAccesoGenerator._calcular_digito_verificador(clave_base)
        
        return clave_base + str(digito_verificador)
    
    @staticmethod
    def _calcular_digito_verificador(clave_base: str) -> int:
        """
        Calcula el dígito verificador usando el algoritmo módulo 11
        
        Args:
            clave_base: Clave de 48 dígitos sin verificador
            
        Returns:
            int: Dígito verificador
        """
        # Multiplicadores del algoritmo módulo 11
        multiplicadores = [2, 3, 4, 5, 6, 7] * 8  # Repetir secuencia
        
        suma = 0
        for i, digito in enumerate(reversed(clave_base)):
            suma += int(digito) * multiplicadores[i % 6]
        
        residuo = suma % 11
        
        if residuo == 0:
            return 0
        elif residuo == 1:
            return 1
        else:
            return 11 - residuo


def calcular_totales_factura(detalles: List[FacturaDetalle]) -> Dict:
    """
    Calcular totales de una factura basado en sus detalles
    
    Args:
        detalles: Lista de detalles de la factura
        
    Returns:
        Dict: Diccionario con los totales calculados
    """
    totales = {
        'subtotal_sin_impuestos': Decimal('0.00'),
        'subtotal_0': Decimal('0.00'),
        'subtotal_12': Decimal('0.00'),
        'subtotal_no_objeto_iva': Decimal('0.00'),
        'subtotal_exento_iva': Decimal('0.00'),
        'total_descuento': Decimal('0.00'),
        'iva_12': Decimal('0.00'),
        'ice': Decimal('0.00'),
        'irbpnr': Decimal('0.00'),
        'valor_total': Decimal('0.00')
    }
    
    for detalle in detalles:
        # Sumar subtotales
        totales['subtotal_sin_impuestos'] += detalle.precio_total_sin_impuesto
        totales['total_descuento'] += detalle.descuento
        
        # Calcular impuestos por detalle
        for impuesto in detalle.impuestos:
            if impuesto.codigo == '2':  # IVA
                if impuesto.codigo_porcentaje == '0':
                    totales['subtotal_0'] += impuesto.base_imponible
                elif impuesto.codigo_porcentaje == '2':
                    totales['subtotal_12'] += impuesto.base_imponible
                    totales['iva_12'] += impuesto.valor
                elif impuesto.codigo_porcentaje == '6':
                    totales['subtotal_no_objeto_iva'] += impuesto.base_imponible
                elif impuesto.codigo_porcentaje == '7':
                    totales['subtotal_exento_iva'] += impuesto.base_imponible
            elif impuesto.codigo == '3':  # ICE
                totales['ice'] += impuesto.valor
            elif impuesto.codigo == '5':  # IRBPNR
                totales['irbpnr'] += impuesto.valor
    
    # Calcular total final
    totales['valor_total'] = (
        totales['subtotal_sin_impuestos'] +
        totales['iva_12'] +
        totales['ice'] +
        totales['irbpnr']
    )
    
    return totales


if __name__ == "__main__":
    # Ejemplo de uso
    generator = XMLGenerator()
    
    # Ejemplo de clave de acceso
    fecha = datetime.now()
    clave = ClaveAccesoGenerator.generar_clave_acceso(
        fecha_emision=fecha,
        tipo_comprobante="01",
        ruc="1234567890001",
        ambiente="1",
        serie="001001",
        numero="1"
    )
    print(f"Clave de acceso generada: {clave}")
    print(f"Longitud: {len(clave)} dígitos")