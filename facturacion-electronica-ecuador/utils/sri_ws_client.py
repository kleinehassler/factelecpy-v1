"""
Cliente para comunicación con los servicios web del SRI Ecuador
"""
import requests
import base64
import logging
from typing import Dict, Any
from config.settings import settings

logger = logging.getLogger(__name__)


class SRIWebServiceClient:
    """Cliente para comunicación con los servicios web del SRI"""
    
    def __init__(self):
        self.ambiente = settings.SRI_AMBIENTE  # 1=Pruebas, 2=Producción
        self.recepcion_url = settings.SRI_URL_RECEPCION
        self.autorizacion_url = settings.SRI_URL_AUTORIZACION
    
    def enviar_comprobante(self, xml_content: str) -> Dict[str, Any]:
        """
        Enviar comprobante electrónico al SRI
        
        Args:
            xml_content: Contenido XML del comprobante firmado
            
        Returns:
            Dict con respuesta del SRI
        """
        try:
            # Codificar XML en base64
            xml_base64 = base64.b64encode(xml_content.encode('utf-8')).decode('utf-8')
            
            # Preparar datos para envío
            soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <ns2:validarComprobante xmlns:ns2="http://ec.gob.sri.ws.recepcion">
            <xml>{xml_base64}</xml>
        </ns2:validarComprobante>
    </soap:Body>
</soap:Envelope>"""
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': '""'
            }
            
            # Enviar solicitud
            response = requests.post(
                self.recepcion_url,
                data=soap_body,
                headers=headers,
                timeout=30
            )
            
            # Procesar respuesta
            if response.status_code == 200:
                return {
                    'success': True,
                    'response': response.text,
                    'status_code': response.status_code
                }
            else:
                return {
                    'success': False,
                    'error': f'Error HTTP {response.status_code}',
                    'response': response.text,
                    'status_code': response.status_code
                }
                
        except Exception as e:
            logger.error(f"Error enviando comprobante al SRI: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response': None
            }
    
    def consultar_autorizacion(self, clave_acceso: str) -> Dict[str, Any]:
        """
        Consultar estado de autorización de un comprobante
        
        Args:
            clave_acceso: Clave de acceso del comprobante
            
        Returns:
            Dict con estado de autorización
        """
        try:
            # Preparar datos para consulta
            soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <ns2:autorizacionComprobante xmlns:ns2="http://ec.gob.sri.ws.autorizacion">
            <claveAccesoComprobante>{clave_acceso}</claveAccesoComprobante>
        </ns2:autorizacionComprobante>
    </soap:Body>
</soap:Envelope>"""
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': '""'
            }
            
            # Enviar consulta
            response = requests.post(
                self.autorizacion_url,
                data=soap_body,
                headers=headers,
                timeout=30
            )
            
            # Procesar respuesta
            if response.status_code == 200:
                return {
                    'success': True,
                    'response': response.text,
                    'status_code': response.status_code
                }
            else:
                return {
                    'success': False,
                    'error': f'Error HTTP {response.status_code}',
                    'response': response.text,
                    'status_code': response.status_code
                }
                
        except Exception as e:
            logger.error(f"Error consultando autorización en SRI: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response': None
            }