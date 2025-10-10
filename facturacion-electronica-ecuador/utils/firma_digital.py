"""
Sistema de firma digital XAdES-BES para documentos electrónicos del SRI Ecuador
"""
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography import x509
from cryptography.x509.oid import NameOID
import datetime
import base64
import hashlib
from lxml import etree
import os
from typing import Optional, Tuple
import xml.etree.ElementTree as ET
from OpenSSL import crypto

from config.settings import settings


class XadesBesSigner:
    """Firmador XAdES-BES para documentos electrónicos del SRI"""
    
    def __init__(self, cert_path: str, cert_password: str):
        """
        Inicializar el firmador con certificado digital
        
        Args:
            cert_path: Ruta al archivo .p12 del certificado
            cert_password: Contraseña del certificado
        """
        self.cert_path = cert_path
        self.cert_password = cert_password
        self.cert = None
        self.private_key = None
        self.load_certificate()
    
    def load_certificate(self):
        """Cargar certificado desde archivo .p12"""
        try:
            with open(self.cert_path, 'rb') as f:
                p12_data = f.read()
            
            # Cargar certificado PKCS#12
            p12 = crypto.load_pkcs12(p12_data, self.cert_password.encode())
            
            # Extraer certificado y clave privada
            self.cert = p12.get_certificate()
            self.private_key = p12.get_privatekey()
            
            # Convertir a formato cryptography para operaciones
            cert_pem = crypto.dump_certificate(crypto.FILETYPE_PEM, self.cert)
            key_pem = crypto.dump_privatekey(crypto.FILETYPE_PEM, self.private_key)
            
            # Cargar con cryptography
            self.cert_crypto = x509.load_pem_x509_certificate(cert_pem, default_backend())
            self.private_key_crypto = serialization.load_pem_private_key(
                key_pem, password=None, backend=default_backend()
            )
            
        except Exception as e:
            raise Exception(f"Error al cargar certificado: {str(e)}")
    
    def sign_xml(self, xml_content: str) -> str:
        """
        Firmar XML con XAdES-BES
        
        Args:
            xml_content: Contenido XML a firmar
            
        Returns:
            str: XML firmado
        """
        try:
            # Parsear el XML
            root = etree.fromstring(xml_content.encode('utf-8'))
            
            # Crear firma digital
            signed_xml = self._create_xades_bes_signature(root)
            
            return etree.tostring(signed_xml, encoding='unicode', pretty_print=True)
            
        except Exception as e:
            raise Exception(f"Error al firmar XML: {str(e)}")
    
    def _create_xades_bes_signature(self, root_element) -> etree.Element:
        """
        Crear firma XAdES-BES para el elemento raíz
        
        Args:
            root_element: Elemento raíz del XML
            
        Returns:
            etree.Element: Elemento con firma XAdES-BES
        """
        # Crear namespaces
        NSMAP = {
            None: "http://www.w3.org/2000/09/xmldsig#",
            'xades': 'http://uri.etsi.org/01903/v1.3.2#',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }
        
        # Crear elemento Signature
        signature = etree.Element("{" + NSMAP[None] + "}Signature", nsmap=NSMAP)
        
        # Referencia al documento
        signed_info = etree.SubElement(signature, "SignedInfo")
        
        # Canonicalization method
        canon_method = etree.SubElement(signed_info, "CanonicalizationMethod")
        canon_method.set("Algorithm", "http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
        
        # Signature method (SHA-256)
        sig_method = etree.SubElement(signed_info, "SignatureMethod")
        sig_method.set("Algorithm", "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256")
        
        # Reference
        reference = etree.SubElement(signed_info, "Reference")
        reference.set("URI", "")
        
        # Transformaciones
        transforms = etree.SubElement(reference, "Transforms")
        
        # Transformación Enveloped Signature
        transform1 = etree.SubElement(transforms, "Transform")
        transform1.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#enveloped-signature")
        
        # Transformación C14N
        transform2 = etree.SubElement(transforms, "Transform")
        transform2.set("Algorithm", "http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
        
        # Digest method (SHA-256)
        digest_method = etree.SubElement(reference, "DigestMethod")
        digest_method.set("Algorithm", "http://www.w3.org/2001/04/xmlenc#sha256")
        
        # Calcular digest del documento
        digest_value = etree.SubElement(reference, "DigestValue")
        digest_value.text = self._calculate_digest(root_element)
        
        # Signature value
        signature_value = etree.SubElement(signature, "SignatureValue")
        
        # Firmar SignedInfo con SHA-256
        signed_info_canon = etree.tostring(signed_info, method="c14n", exclusive=False)
        signature_bytes = self.private_key_crypto.sign(
            signed_info_canon,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        signature_value.text = base64.b64encode(signature_bytes).decode()
        
        # Key info
        key_info = etree.SubElement(signature, "KeyInfo")
        
        # X509 data
        x509_data = etree.SubElement(key_info, "X509Data")
        
        # Certificado X509
        cert_pem = crypto.dump_certificate(crypto.FILETYPE_PEM, self.cert)
        cert_der = crypto.dump_certificate(crypto.FILETYPE_ASN1, self.cert)
        x509_certificate = etree.SubElement(x509_data, "X509Certificate")
        x509_certificate.text = base64.b64encode(cert_der).decode()
        
        # Agregar firma al documento
        root_element.append(signature)
        
        return root_element
    
    def _calculate_digest(self, element) -> str:
        """
        Calcular digest SHA-256 del elemento

        Args:
            element: Elemento XML

        Returns:
            str: Digest en base64
        """
        # Canonicalizar el elemento sin la firma
        canon_xml = etree.tostring(element, method="c14n", exclusive=False)

        # Calcular hash SHA-256
        sha256_hash = hashlib.sha256(canon_xml).digest()

        # Convertir a base64
        return base64.b64encode(sha256_hash).decode()
    
    def verify_signature(self, signed_xml: str) -> bool:
        """
        Verificar firma digital del XML
        
        Args:
            signed_xml: XML firmado
            
        Returns:
            bool: True si la firma es válida
        """
        try:
            # Parsear XML firmado
            root = etree.fromstring(signed_xml.encode('utf-8'))
            
            # Encontrar elemento Signature
            signature = root.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature")
            if signature is None:
                return False
            
            # Verificar firma usando la librería signxml
            from signxml import XMLVerifier
            
            # Extraer certificado del XML
            cert_elem = root.find(".//{http://www.w3.org/2000/09/xmldsig#}X509Certificate")
            if cert_elem is not None:
                cert_der = base64.b64decode(cert_elem.text)
                cert = x509.load_der_x509_certificate(cert_der, default_backend())
                
                # Verificar firma
                verified_data = XMLVerifier().verify(
                    signed_xml.encode('utf-8'),
                    x509_cert=cert
                )
                
                return True
            
            return False
            
        except Exception as e:
            print(f"Error al verificar firma: {str(e)}")
            return False


class SRIWebServiceClient:
    """Cliente para comunicación con servicios web del SRI"""
    
    def __init__(self):
        self.recepcion_url = settings.SRI_URL_RECEPCION
        self.autorizacion_url = settings.SRI_URL_AUTORIZACION
    
    def enviar_comprobante(self, xml_firmado: str) -> dict:
        """
        Enviar comprobante al SRI
        
        Args:
            xml_firmado: XML firmado del comprobante
            
        Returns:
            dict: Respuesta del SRI
        """
        try:
            # Importar suds-jurko para llamadas SOAP
            from suds.client import Client
            from suds.transport.http import HttpAuthenticated
            
            # Crear cliente SOAP
            transport = HttpAuthenticated()
            client = Client(self.recepcion_url, transport=transport)
            
            # Codificar XML en base64
            import base64
            xml_base64 = base64.b64encode(xml_firmado.encode('utf-8')).decode('utf-8')
            
            # Enviar comprobante
            response = client.service.validarComprobante(xml_base64)
            
            return {
                'estado': response.estado,
                'comprobantes': response.comprobantes if hasattr(response, 'comprobantes') else None,
                'mensaje': str(response)
            }
            
        except Exception as e:
            return {
                'estado': 'ERROR',
                'mensaje': f"Error al enviar comprobante: {str(e)}"
            }
    
    def autorizar_comprobante(self, clave_acceso: str) -> dict:
        """
        Consultar autorización de comprobante
        
        Args:
            clave_acceso: Clave de acceso del comprobante
            
        Returns:
            dict: Respuesta de autorización del SRI
        """
        try:
            # Importar suds-jurko para llamadas SOAP
            from suds.client import Client
            from suds.transport.http import HttpAuthenticated
            
            # Crear cliente SOAP
            transport = HttpAuthenticated()
            client = Client(self.autorizacion_url, transport=transport)
            
            # Consultar autorización
            response = client.service.autorizacionComprobante(clave_acceso)
            
            if hasattr(response, 'autorizaciones') and response.autorizaciones:
                autorizacion = response.autorizaciones[0] if isinstance(response.autorizaciones, list) else response.autorizaciones.autorizacion
                
                return {
                    'estado': autorizacion.estado,
                    'numeroAutorizacion': getattr(autorizacion, 'numeroAutorizacion', None),
                    'fechaAutorizacion': getattr(autorizacion, 'fechaAutorizacion', None),
                    'ambiente': getattr(autorizacion, 'ambiente', None),
                    'comprobante': getattr(autorizacion, 'comprobante', None),
                    'mensajes': getattr(autorizacion, 'mensajes', None)
                }
            
            return {
                'estado': 'NO_AUTORIZADO',
                'mensaje': 'No se encontró autorización'
            }
            
        except Exception as e:
            return {
                'estado': 'ERROR',
                'mensaje': f"Error al consultar autorización: {str(e)}"
            }


def create_test_certificate() -> Tuple[str, str]:
    """
    Crear certificado de prueba para desarrollo
    
    Returns:
        Tuple[str, str]: Ruta del certificado y contraseña
    """
    try:
        # Generar clave privada
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Generar certificado autofirmado
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u"EC"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Pichincha"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, u"Quito"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Empresa de Prueba S.A."),
            x509.NameAttribute(NameOID.COMMON_NAME, u"test@example.com"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.now(datetime.timezone.utc)
        ).not_valid_after(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
        ).sign(private_key, hashes.SHA256(), default_backend())
        
        # Guardar en formato PEM
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Guardar archivos
        cert_path = os.path.join(settings.CERTIFICADOS_FOLDER, "test_cert.pem")
        key_path = os.path.join(settings.CERTIFICADOS_FOLDER, "test_key.pem")
        
        with open(cert_path, 'wb') as f:
            f.write(cert_pem)
        
        with open(key_path, 'wb') as f:
            f.write(key_pem)
        
        return cert_path, ""
        
    except Exception as e:
        print(f"Error al crear certificado de prueba: {str(e)}")
        return None, None


if __name__ == "__main__":
    # Ejemplo de uso
    try:
        # Para pruebas, crear certificado temporal
        if not os.path.exists(settings.CERT_PATH):
            print("Creando certificado de prueba...")
            cert_path, cert_pass = create_test_certificate()
            if cert_path:
                signer = XadesBesSigner(cert_path, cert_pass)
                print("Certificado de prueba creado exitosamente")
            else:
                print("Error al crear certificado de prueba")
        else:
            # Usar certificado real
            signer = XadesBesSigner(settings.CERT_PATH, settings.CERT_PASSWORD)
            print("Certificado cargado exitosamente")
            
    except Exception as e:
        print(f"Error: {str(e)}")