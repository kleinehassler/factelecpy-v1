"""
Sistema de envío de correos electrónicos para documentos del SRI
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
from typing import List, Optional
import asyncio
import aiosmtplib
from email.message import EmailMessage

from config.settings import settings


class EmailSender:
    """Sistema de envío de correos electrónicos"""
    
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
    
    def enviar_factura_email(self, destinatario: str, asunto: str, mensaje: str,
                           pdf_ride: bytes = None, xml_firmado: bytes = None,
                           nombre_factura: str = "factura") -> bool:
        """
        Enviar factura por correo electrónico
        
        Args:
            destinatario: Email del destinatario
            asunto: Asunto del correo
            mensaje: Cuerpo del mensaje
            pdf_ride: Contenido del PDF del RIDE (opcional)
            xml_firmado: Contenido del XML firmado (opcional)
            nombre_factura: Nombre base para los archivos adjuntos
            
        Returns:
            bool: True si se envió correctamente
        """
        try:
            # Crear mensaje
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = destinatario
            msg['Subject'] = asunto
            
            # Agregar cuerpo del mensaje
            msg.attach(MIMEText(mensaje, 'html'))
            
            # Adjuntar PDF del RIDE si existe
            if pdf_ride:
                pdf_part = MIMEBase('application', 'octet-stream')
                pdf_part.set_payload(pdf_ride)
                encoders.encode_base64(pdf_part)
                pdf_part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= "{nombre_factura}.pdf"'
                )
                msg.attach(pdf_part)
            
            # Adjuntar XML firmado si existe
            if xml_firmado:
                xml_part = MIMEBase('application', 'octet-stream')
                xml_part.set_payload(xml_firmado)
                encoders.encode_base64(xml_part)
                xml_part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= "{nombre_factura}.xml"'
                )
                msg.attach(xml_part)
            
            # Crear contexto SSL
            context = ssl.create_default_context()
            
            # Conectar y enviar correo
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.username, self.password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            print(f"Error al enviar correo: {str(e)}")
            return False
    
    async def enviar_factura_email_async(self, destinatario: str, asunto: str, mensaje: str,
                                       pdf_ride: bytes = None, xml_firmado: bytes = None,
                                       nombre_factura: str = "factura") -> bool:
        """
        Enviar factura por correo electrónico de forma asíncrona
        
        Args:
            destinatario: Email del destinatario
            asunto: Asunto del correo
            mensaje: Cuerpo del mensaje
            pdf_ride: Contenido del PDF del RIDE (opcional)
            xml_firmado: Contenido del XML firmado (opcional)
            nombre_factura: Nombre base para los archivos adjuntos
            
        Returns:
            bool: True si se envió correctamente
        """
        try:
            # Crear mensaje
            msg = EmailMessage()
            msg['From'] = self.from_email
            msg['To'] = destinatario
            msg['Subject'] = asunto
            msg.set_content(mensaje, subtype='html')
            
            # Adjuntar PDF del RIDE si existe
            if pdf_ride:
                msg.add_attachment(
                    pdf_ride,
                    maintype='application',
                    subtype='pdf',
                    filename=f"{nombre_factura}.pdf"
                )
            
            # Adjuntar XML firmado si existe
            if xml_firmado:
                msg.add_attachment(
                    xml_firmado,
                    maintype='application',
                    subtype='xml',
                    filename=f"{nombre_factura}.xml"
                )
            
            # Enviar correo de forma asíncrona
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_server,
                port=self.smtp_port,
                username=self.username,
                password=self.password,
                start_tls=True
            )
            
            return True
            
        except Exception as e:
            print(f"Error al enviar correo asíncrono: {str(e)}")
            return False
    
    def enviar_proforma_email(self, destinatario: str, asunto: str, mensaje: str,
                            pdf_proforma: bytes = None, nombre_proforma: str = "proforma") -> bool:
        """
        Enviar proforma por correo electrónico
        
        Args:
            destinatario: Email del destinatario
            asunto: Asunto del correo
            mensaje: Cuerpo del mensaje
            pdf_proforma: Contenido del PDF de la proforma (opcional)
            nombre_proforma: Nombre base para el archivo adjunto
            
        Returns:
            bool: True si se envió correctamente
        """
        try:
            # Crear mensaje
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = destinatario
            msg['Subject'] = asunto
            
            # Agregar cuerpo del mensaje
            msg.attach(MIMEText(mensaje, 'html'))
            
            # Adjuntar PDF de la proforma si existe
            if pdf_proforma:
                pdf_part = MIMEBase('application', 'octet-stream')
                pdf_part.set_payload(pdf_proforma)
                encoders.encode_base64(pdf_part)
                pdf_part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= "{nombre_proforma}.pdf"'
                )
                msg.attach(pdf_part)
            
            # Crear contexto SSL
            context = ssl.create_default_context()
            
            # Conectar y enviar correo
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.username, self.password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            print(f"Error al enviar proforma por correo: {str(e)}")
            return False
    
    def enviar_notificacion_masiva(self, destinatarios: List[str], asunto: str, 
                                 mensaje: str) -> dict:
        """
        Enviar notificación masiva a múltiples destinatarios
        
        Args:
            destinatarios: Lista de emails de destinatarios
            asunto: Asunto del correo
            mensaje: Cuerpo del mensaje
            
        Returns:
            dict: Resultado con estadísticas de envío
        """
        resultados = {
            'enviados': 0,
            'fallidos': 0,
            'errores': []
        }
        
        for destinatario in destinatarios:
            try:
                if self.enviar_factura_email(destinatario, asunto, mensaje):
                    resultados['enviados'] += 1
                else:
                    resultados['fallidos'] += 1
                    resultados['errores'].append(f"Falló envío a {destinatario}")
            except Exception as e:
                resultados['fallidos'] += 1
                resultados['errores'].append(f"Error al enviar a {destinatario}: {str(e)}")
        
        return resultados


class EmailTemplates:
    """Plantillas de correos electrónicos"""
    
    @staticmethod
    def factura_template(cliente_nombre: str, numero_factura: str, total: str,
                        fecha_emision: str, clave_acceso: str) -> str:
        """
        Plantilla para envío de factura electrónica
        
        Args:
            cliente_nombre: Nombre del cliente
            numero_factura: Número de la factura
            total: Total de la factura
            fecha_emision: Fecha de emisión
            clave_acceso: Clave de acceso de la factura
            
        Returns:
            str: HTML de la plantilla
        """
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Factura Electrónica {numero_factura}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Factura Electrónica</h2>
                
                <p>Estimado(a) <strong>{cliente_nombre}</strong>,</p>
                
                <p>Le informamos que hemos generado la siguiente factura electrónica:</p>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p><strong>Número de factura:</strong> {numero_factura}</p>
                    <p><strong>Fecha de emisión:</strong> {fecha_emision}</p>
                    <p><strong>Total:</strong> ${total}</p>
                    <p><strong>Clave de acceso:</strong> {clave_acceso}</p>
                </div>
                
                <p>Adjunto a este correo encontrará el documento en formato PDF y XML.</p>
                
                <p>Esta factura ha sido generada conforme a la normativa del SRI (Servicio de Rentas Internas) de Ecuador.</p>
                
                <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Instrucciones de validación</h3>
                    <p>Puede validar esta factura en el portal del SRI utilizando la clave de acceso proporcionada.</p>
                </div>
                
                <p>Si tiene alguna pregunta o necesita más información, no dude en contactarnos.</p>
                
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                
                <p style="font-size: 12px; color: #666;">
                    Este es un mensaje automático. Por favor no responda a este correo.
                </p>
            </div>
        </body>
        </html>
        """
    
    @staticmethod
    def proforma_template(cliente_nombre: str, numero_proforma: str, total: str,
                         fecha_emision: str, fecha_validez: str) -> str:
        """
        Plantilla para envío de proforma
        
        Args:
            cliente_nombre: Nombre del cliente
            numero_proforma: Número de la proforma
            total: Total de la proforma
            fecha_emision: Fecha de emisión
            fecha_validez: Fecha de validez
            
        Returns:
            str: HTML de la plantilla
        """
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Proforma {numero_proforma}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Proforma</h2>
                
                <p>Estimado(a) <strong>{cliente_nombre}</strong>,</p>
                
                <p>Adjunto encontrará nuestra proforma número <strong>{numero_proforma}</strong>.</p>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p><strong>Fecha de emisión:</strong> {fecha_emision}</p>
                    <p><strong>Fecha de validez:</strong> {fecha_validez}</p>
                    <p><strong>Total:</strong> ${total}</p>
                </div>
                
                <p>Esta proforma tiene carácter informativo y no constituye una factura. 
                   Si decide aceptarla, procederemos con la generación de la factura correspondiente.</p>
                
                <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
                    <h3 style="margin-top: 0; color: #856404;">Importante</h3>
                    <p style="color: #856404;">La presente proforma tendrá validez hasta el {fecha_validez}. 
                       Pasada esta fecha, los precios pueden ser modificados.</p>
                </div>
                
                <p>Si tiene alguna pregunta o desea proceder con la aceptación de esta proforma, 
                   por favor contáctenos.</p>
                
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                
                <p style="font-size: 12px; color: #666;">
                    Este es un mensaje automático. Por favor no responda a este correo.
                </p>
            </div>
        </body>
        </html>
        """
    
    @staticmethod
    def notificacion_sri_template(estado: str, numero_factura: str, 
                                mensaje_sri: str = "") -> str:
        """
        Plantilla para notificaciones del SRI
        
        Args:
            estado: Estado de la factura (AUTORIZADA, RECHAZADA, etc.)
            numero_factura: Número de la factura
            mensaje_sri: Mensaje adicional del SRI
            
        Returns:
            str: HTML de la plantilla
        """
        color_estado = {
            'AUTORIZADO': '#28a745',
            'RECHAZADO': '#dc3545',
            'DEVUELTO': '#ffc107',
            'FIRMADO': '#17a2b8'
        }.get(estado.upper(), '#6c757d')
        
        mensaje_sri_html = f'''<div style="background-color: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #dc3545;">
                    <h3 style="margin-top: 0; color: #721c24;">Mensaje del SRI</h3>
                    <p style="color: #721c24;">{mensaje_sri}</p>
                </div>''' if mensaje_sri else ''
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Notificación SRI - Factura {numero_factura}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Notificación del SRI</h2>
                
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; text-align: center; margin: 20px 0;">
                    <h3 style="color: {color_estado}; margin: 0;">ESTADO: {estado.upper()}</h3>
                    <p style="font-size: 18px; margin: 10px 0;">Factura {numero_factura}</p>
                </div>
                
                {mensaje_sri_html}
                
                <p>El estado de su factura ha sido actualizado en el sistema del SRI.</p>
                
                <p>Para más información, puede consultar directamente en el portal del SRI 
                   utilizando la clave de acceso de su factura.</p>
                
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                
                <p style="font-size: 12px; color: #666;">
                    Este es un mensaje automático del sistema de facturación electrónica.
                </p>
            </div>
        </body>
        </html>
        """


def configurar_email_prueba():
    """Configurar y probar conexión de correo"""
    try:
        sender = EmailSender()
        
        # Crear contexto SSL
        context = ssl.create_default_context()
        
        # Probar conexión SMTP
        with smtplib.SMTP(sender.smtp_server, sender.smtp_port) as server:
            server.starttls(context=context)
            server.login(sender.username, sender.password)
        
        print("✓ Configuración de correo verificada correctamente")
        return True
        
    except Exception as e:
        print(f"✗ Error en configuración de correo: {str(e)}")
        return False


if __name__ == "__main__":
    # Probar configuración de correo
    print("Sistema de envío de correos electrónicos para documentos del SRI")
    configurar_email_prueba()