"""
Configuración de logging para el sistema de facturación electrónica
"""
import logging
import logging.handlers
import os
from datetime import datetime
import json
from typing import Dict, Any


class JSONFormatter(logging.Formatter):
    """Formateador JSON para logs estructurados"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Agregar información adicional si existe
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'client_ip'):
            log_entry['client_ip'] = record.client_ip
        if hasattr(record, 'duration'):
            log_entry['duration'] = record.duration
            
        # Agregar información de excepción si existe
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(log_level: str = "INFO", log_dir: str = "logs"):
    """
    Configurar el sistema de logging
    
    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directorio donde guardar los logs
    """
    # Crear directorio de logs si no existe
    os.makedirs(log_dir, exist_ok=True)
    
    # Configurar el logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Limpiar handlers existentes
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Handler para archivo de logs generales (JSON)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(JSONFormatter())
    file_handler.setLevel(logging.INFO)
    
    # Handler para archivo de errores
    error_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'errors.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setFormatter(JSONFormatter())
    error_handler.setLevel(logging.ERROR)
    
    # Handler para consola (desarrollo)
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # Agregar handlers al logger raíz
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)
    
    # Configurar loggers específicos
    
    # Logger para requests HTTP
    http_logger = logging.getLogger('http')
    http_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'http.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    http_handler.setFormatter(JSONFormatter())
    http_logger.addHandler(http_handler)
    http_logger.setLevel(logging.INFO)
    
    # Logger para base de datos
    db_logger = logging.getLogger('database')
    db_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'database.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    db_handler.setFormatter(JSONFormatter())
    db_logger.addHandler(db_handler)
    db_logger.setLevel(logging.INFO)
    
    # Logger para SRI
    sri_logger = logging.getLogger('sri')
    sri_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'sri.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    sri_handler.setFormatter(JSONFormatter())
    sri_logger.addHandler(sri_handler)
    sri_logger.setLevel(logging.INFO)
    
    # Silenciar logs muy verbosos de librerías externas
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    logging.info("Sistema de logging configurado correctamente")


def get_logger(name: str) -> logging.Logger:
    """
    Obtener un logger configurado
    
    Args:
        name: Nombre del logger
        
    Returns:
        logging.Logger: Logger configurado
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """Adaptador para agregar contexto adicional a los logs"""
    
    def process(self, msg, kwargs):
        # Agregar información de contexto al record
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        
        # Agregar información del adaptador
        kwargs['extra'].update(self.extra)
        
        return msg, kwargs


def create_request_logger(request_id: str, client_ip: str, user_id: str = None) -> LoggerAdapter:
    """
    Crear un logger con contexto de request
    
    Args:
        request_id: ID único del request
        client_ip: IP del cliente
        user_id: ID del usuario (opcional)
        
    Returns:
        LoggerAdapter: Logger con contexto
    """
    logger = logging.getLogger('http')
    extra = {
        'request_id': request_id,
        'client_ip': client_ip
    }
    
    if user_id:
        extra['user_id'] = user_id
        
    return LoggerAdapter(logger, extra)