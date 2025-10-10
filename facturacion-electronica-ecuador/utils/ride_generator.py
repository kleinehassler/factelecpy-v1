"""
Generador de RIDE (Representación Impresa Digitalizada Electrónica) para facturas del SRI
"""
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import logging
from datetime import datetime
from decimal import Decimal
from typing import List
import io
import base64

from config.settings import settings
from backend.models import Factura, FacturaDetalle, Cliente, Empresa

logger = logging.getLogger(__name__)


class RideGenerator:
    """Generador de RIDE para facturas electrónicas del SRI"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.page_width, self.page_height = A4
        self.margin = 0.5 * inch
        
        # Registrar fuentes personalizadas si es necesario
        try:
            # Intentar registrar fuentes adicionales
            # pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
            pass
        except:
            pass  # Si no se pueden registrar fuentes, usar las predeterminadas
    
    def generar_ride_factura(self, factura: Factura, empresa: Empresa, cliente: Cliente,
                           detalles: List[FacturaDetalle], output_path: str = None) -> bytes:
        """
        Generar RIDE en formato PDF para una factura
        
        Args:
            factura: Objeto factura
            empresa: Datos de la empresa emisora
            cliente: Datos del cliente
            detalles: Lista de detalles de la factura
            output_path: Ruta donde guardar el PDF (opcional)
            
        Returns:
            bytes: Contenido del PDF generado
        """
        # Crear buffer en memoria
        buffer = io.BytesIO()
        
        # Crear documento PDF
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=self.margin,
            rightMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin
        )
        
        # Construir contenido del PDF
        story = []
        
        # Encabezado de la factura
        self._agregar_encabezado(story, factura, empresa)
        
        # Información del cliente
        self._agregar_info_cliente(story, cliente)
        
        # Detalles de la factura
        self._agregar_detalles(story, detalles)
        
        # Totales
        self._agregar_totales(story, factura)
        
        # Información adicional
        self._agregar_info_adicional(story, factura)
        
        # Información de autorización
        self._agregar_info_autorizacion(story, factura)
        
        # Generar PDF
        doc.build(story)
        
        # Obtener contenido del PDF
        pdf_content = buffer.getvalue()
        buffer.close()
        
        # Guardar en archivo si se especifica
        if output_path:
            self._guardar_pdf(pdf_content, output_path)
        
        return pdf_content
    
    def _agregar_encabezado(self, story: List, factura: Factura, empresa: Empresa):
        """Agregar encabezado de la factura"""
        # Logo de la empresa (si existe)
        if empresa.logo_path and os.path.exists(empresa.logo_path):
            try:
                logo = Image(empresa.logo_path, width=1*inch, height=1*inch)
                story.append(logo)
                story.append(Spacer(1, 12))
            except:
                pass  # Si no se puede cargar el logo, continuar sin él
        
        # Datos de la empresa
        story.append(Paragraph(f"<b>{empresa.razon_social.upper()}</b>", self._get_title_style()))
        if empresa.nombre_comercial:
            story.append(Paragraph(f"<b>{empresa.nombre_comercial}</b>", self._get_subtitle_style()))
        
        story.append(Paragraph(f"RUC: {empresa.ruc}", self._get_normal_style()))
        story.append(Paragraph(f"{empresa.direccion_matriz}", self._get_normal_style()))
        
        if empresa.telefono:
            story.append(Paragraph(f"Teléfono: {empresa.telefono}", self._get_normal_style()))
        
        if empresa.email:
            story.append(Paragraph(f"Email: {empresa.email}", self._get_normal_style()))
        
        story.append(Spacer(1, 12))
        
        # Título de la factura
        story.append(Paragraph("<b>FACTURA ELECTRÓNICA</b>", self._get_title_style()))
        story.append(Spacer(1, 6))
        
        # Información básica de la factura
        story.append(Paragraph(f"<b>NÚMERO:</b> {factura.numero_comprobante}", self._get_normal_style()))
        story.append(Paragraph(f"<b>FECHA:</b> {factura.fecha_emision.strftime('%d/%m/%Y %H:%M:%S')}", self._get_normal_style()))
        story.append(Paragraph(f"<b>AMBIENTE:</b> {'PRODUCCIÓN' if factura.ambiente == '2' else 'PRUEBAS'}", self._get_normal_style()))
        story.append(Paragraph(f"<b>EMISIÓN:</b> {'NORMAL' if factura.tipo_emision == '1' else 'CONTINGENCIA'}", self._get_normal_style()))
        
        # Clave de acceso (mostrar solo los primeros y últimos dígitos por seguridad)
        clave_visible = factura.clave_acceso[:10] + "..." + factura.clave_acceso[-10:] if len(factura.clave_acceso) > 20 else factura.clave_acceso
        story.append(Paragraph(f"<b>CLAVE DE ACCESO:</b> {clave_visible}", self._get_normal_style()))
        
        story.append(Spacer(1, 12))
    
    def _agregar_info_cliente(self, story: List, cliente: Cliente):
        """Agregar información del cliente"""
        story.append(Paragraph("<b>INFORMACIÓN DEL CLIENTE</b>", self._get_subtitle_style()))
        story.append(Spacer(1, 6))
        
        story.append(Paragraph(f"<b>Razón Social:</b> {cliente.razon_social}", self._get_normal_style()))
        story.append(Paragraph(f"<b>Identificación:</b> {cliente.identificacion} ({self._get_tipo_identificacion(cliente.tipo_identificacion)})", self._get_normal_style()))
        
        if cliente.direccion:
            story.append(Paragraph(f"<b>Dirección:</b> {cliente.direccion}", self._get_normal_style()))
        
        if cliente.telefono:
            story.append(Paragraph(f"<b>Teléfono:</b> {cliente.telefono}", self._get_normal_style()))
        
        if cliente.email:
            story.append(Paragraph(f"<b>Email:</b> {cliente.email}", self._get_normal_style()))
        
        story.append(Spacer(1, 12))
    
    def _agregar_detalles(self, story: List, detalles: List[FacturaDetalle]):
        """Agregar tabla de detalles de la factura"""
        story.append(Paragraph("<b>DETALLES DE LA FACTURA</b>", self._get_subtitle_style()))
        story.append(Spacer(1, 6))
        
        # Encabezados de la tabla
        data = [
            ['Código', 'Descripción', 'Cantidad', 'Precio Unit.', 'Descuento', 'Total']
        ]
        
        # Datos de los detalles
        for detalle in detalles:
            data.append([
                detalle.codigo_principal,
                detalle.descripcion[:50] + "..." if len(detalle.descripcion) > 50 else detalle.descripcion,
                f"{float(detalle.cantidad):.2f}",
                f"{float(detalle.precio_unitario):.2f}",
                f"{float(detalle.descuento):.2f}",
                f"{float(detalle.precio_total_sin_impuesto):.2f}"
            ])
        
        # Crear tabla
        table = Table(data, colWidths=[1*inch, 2.5*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch])
        
        # Estilo de la tabla
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 12))
    
    def _agregar_totales(self, story: List, factura: Factura):
        """Agregar sección de totales"""
        story.append(Paragraph("<b>TOTALES</b>", self._get_subtitle_style()))
        story.append(Spacer(1, 6))
        
        # Crear tabla de totales
        data = [
            ['Concepto', 'Valor']
        ]
        
        if factura.subtotal_sin_impuestos > 0:
            data.append(['Subtotal Sin Impuestos', f"${float(factura.subtotal_sin_impuestos):.2f}"])
        
        if factura.subtotal_0 > 0:
            data.append(['Subtotal 0%', f"${float(factura.subtotal_0):.2f}"])
        
        if factura.subtotal_12 > 0:
            data.append(['Subtotal 12%', f"${float(factura.subtotal_12):.2f}"])
        
        if factura.total_descuento > 0:
            data.append(['Total Descuento', f"${float(factura.total_descuento):.2f}"])
        
        if factura.iva_12 > 0:
            data.append(['IVA 12%', f"${float(factura.iva_12):.2f}"])
        
        if factura.ice > 0:
            data.append(['ICE', f"${float(factura.ice):.2f}"])
        
        if factura.irbpnr > 0:
            data.append(['IRBPNR', f"${float(factura.irbpnr):.2f}"])
        
        if factura.propina > 0:
            data.append(['Propina', f"${float(factura.propina):.2f}"])
        
        # Total final
        data.append(['<b>VALOR TOTAL</b>', f"<b>${float(factura.valor_total):.2f}</b>"])
        
        # Crear tabla de totales
        table = Table(data, colWidths=[3*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 12))
    
    def _agregar_info_adicional(self, story: List, factura: Factura):
        """Agregar información adicional"""
        if factura.observaciones or factura.info_adicional:
            story.append(Paragraph("<b>INFORMACIÓN ADICIONAL</b>", self._get_subtitle_style()))
            story.append(Spacer(1, 6))
            
            if factura.observaciones:
                story.append(Paragraph(f"<b>Observaciones:</b> {factura.observaciones}", self._get_normal_style()))
            
            if factura.info_adicional:
                for info in factura.info_adicional:
                    story.append(Paragraph(f"<b>{info.nombre}:</b> {info.valor}", self._get_normal_style()))
            
            story.append(Spacer(1, 12))
    
    def _agregar_info_autorizacion(self, story: List, factura: Factura):
        """Agregar información de autorización"""
        story.append(Paragraph("<b>INFORMACIÓN DE AUTORIZACIÓN</b>", self._get_subtitle_style()))
        story.append(Spacer(1, 6))

        if factura.estado_sri == "AUTORIZADO" and factura.numero_autorizacion:
            story.append(Paragraph(f"<b>ESTADO:</b> AUTORIZADO", self._get_normal_style()))
            story.append(Paragraph(f"<b>NÚMERO DE AUTORIZACIÓN:</b> {factura.numero_autorizacion}", self._get_normal_style()))
            if factura.fecha_autorizacion:
                story.append(Paragraph(f"<b>FECHA DE AUTORIZACIÓN:</b> {factura.fecha_autorizacion.strftime('%d/%m/%Y %H:%M:%S')}", self._get_normal_style()))
        else:
            story.append(Paragraph(f"<b>ESTADO:</b> {factura.estado_sri}", self._get_normal_style()))
            story.append(Paragraph("<b>Nota:</b> Este documento aún no ha sido autorizado por el SRI", self._get_normal_style()))

        story.append(Spacer(1, 12))

        # Información de obligado a llevar contabilidad
        empresa = factura.empresa
        if empresa.obligado_contabilidad == "SI":
            story.append(Paragraph("<b>CONTRIBUYENTE ESPECIAL:</b> " + (empresa.contribuyente_especial or "NO"), self._get_normal_style()))
            story.append(Paragraph("<b>OBLIGADO A LLEVAR CONTABILIDAD:</b> SI", self._get_normal_style()))

        story.append(Spacer(1, 12))

        # Agregar código QR
        self._agregar_qr_code(story, factura)

        story.append(Spacer(1, 12))

        # Pie de página
        story.append(Paragraph("Representación impresa de la factura electrónica", self._get_small_style()))
        story.append(Paragraph("Generado por sistema autorizado por el SRI", self._get_small_style()))

    def _agregar_qr_code(self, story: List, factura: Factura):
        """Agregar código QR de la factura"""
        try:
            import qrcode
            from io import BytesIO

            # URL de consulta según ambiente
            if factura.ambiente == "2":  # Producción
                url = f"https://www.sri.gob.ec/facturacion-internet/#/consultas/comprobantes?clave={factura.clave_acceso}"
            else:  # Pruebas
                url = f"https://celcer.sri.gob.ec/comprobantes-electronicos-ws/consultas/comprobantes?clave={factura.clave_acceso}"

            # Generar código QR
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=4,
                border=2,
            )
            qr.add_data(url)
            qr.make(fit=True)

            # Crear imagen
            img_qr = qr.make_image(fill_color="black", back_color="white")

            # Guardar en buffer
            buffer = BytesIO()
            img_qr.save(buffer, format='PNG')
            buffer.seek(0)

            # Agregar al PDF
            story.append(Paragraph("<b>CÓDIGO QR PARA CONSULTA EN EL SRI</b>", self._get_subtitle_style()))
            story.append(Spacer(1, 6))
            qr_image = Image(buffer, width=1.5*inch, height=1.5*inch)
            story.append(qr_image)
            story.append(Paragraph("Escanee este código para verificar la factura en el portal del SRI", self._get_small_style()))

        except Exception as e:
            # Si falla la generación del QR, continuar sin él
            logger.error(f"Error al generar código QR: {str(e)}")
            story.append(Paragraph("<i>Código QR no disponible</i>", self._get_small_style()))
    
    def _get_title_style(self) -> ParagraphStyle:
        """Obtener estilo para títulos"""
        return ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=12,
            alignment=1,  # Center
        )
    
    def _get_subtitle_style(self) -> ParagraphStyle:
        """Obtener estilo para subtítulos"""
        return ParagraphStyle(
            'CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceAfter=6,
        )
    
    def _get_normal_style(self) -> ParagraphStyle:
        """Obtener estilo normal"""
        return ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=3,
        )
    
    def _get_small_style(self) -> ParagraphStyle:
        """Obtener estilo pequeño"""
        return ParagraphStyle(
            'CustomSmall',
            parent=self.styles['Normal'],
            fontSize=8,
            spaceAfter=2,
        )
    
    def _get_tipo_identificacion(self, codigo: str) -> str:
        """Obtener descripción del tipo de identificación"""
        tipos = {
            "04": "RUC",
            "05": "CÉDULA",
            "06": "PASAPORTE",
            "07": "VENTA A CONSUMIDOR FINAL",
            "08": "IDENTIFICACIÓN DEL EXTERIOR"
        }
        return tipos.get(codigo, "DESCONOCIDO")
    
    def _guardar_pdf(self, pdf_content: bytes, output_path: str):
        """Guardar PDF en archivo"""
        try:
            # Crear directorio si no existe
            directorio = os.path.dirname(output_path)
            if directorio and not os.path.exists(directorio):
                os.makedirs(directorio, exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(pdf_content)
                
        except Exception as e:
            print(f"Error al guardar PDF: {str(e)}")


class QRGenerator:
    """Generador de códigos QR para facturas electrónicas"""
    
    @staticmethod
    def generar_qr_factura(clave_acceso: str, ambiente: str) -> str:
        """
        Generar código QR para una factura
        
        Args:
            clave_acceso: Clave de acceso de la factura
            ambiente: Ambiente (1=Pruebas, 2=Producción)
            
        Returns:
            str: URL del código QR en base64
        """
        try:
            import qrcode
            from io import BytesIO
            import base64
            
            # URL de consulta según ambiente
            if ambiente == "2":  # Producción
                url = f"https://www.sri.gob.ec/web/guest/consulta-comprobantes-electronicos?clave={clave_acceso}"
            else:  # Pruebas
                url = f"https://celcer.sri.gob.ec/comprobantes-electronicos-ws/ConsultarComprobante?clave={clave_acceso}"
            
            # Generar código QR
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(url)
            qr.make(fit=True)
            
            # Crear imagen
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convertir a base64
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            print(f"Error al generar código QR: {str(e)}")
            return ""


def generar_ride_prueba():
    """Generar un RIDE de prueba"""
    # Esta función sería para pruebas, en un entorno real se usarían datos reales
    print("Generador de RIDE para facturas electrónicas del SRI Ecuador")
    print("Para usar este generador, llame al método generar_ride_factura() con los datos apropiados")


if __name__ == "__main__":
    generar_ride_prueba()