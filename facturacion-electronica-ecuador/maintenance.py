#!/usr/bin/env python3
"""
Script de mantenimiento para el sistema de facturación electrónica
"""
import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
import schedule
import time
import json

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from config.logging_config import setup_logging, get_logger
from backend.database import DatabaseManager
from utils.metrics import get_metrics_collector
from utils.cache import cache_manager


def setup_maintenance_logging():
    """Configurar logging para mantenimiento"""
    setup_logging(log_level="INFO", log_dir="logs")
    return get_logger("maintenance")


def cleanup_old_logs(days: int = 30):
    """Limpiar logs antiguos"""
    logger = get_logger("maintenance")
    log_dir = "logs"
    
    if not os.path.exists(log_dir):
        return
    
    cutoff_date = datetime.now() - timedelta(days=days)
    cleaned_files = 0
    
    for filename in os.listdir(log_dir):
        filepath = os.path.join(log_dir, filename)
        
        if os.path.isfile(filepath):
            file_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            if file_modified < cutoff_date:
                try:
                    os.remove(filepath)
                    cleaned_files += 1
                    logger.info(f"Archivo de log eliminado: {filename}")
                except Exception as e:
                    logger.error(f"Error al eliminar {filename}: {str(e)}")
    
    logger.info(f"Limpieza de logs completada. {cleaned_files} archivos eliminados.")


def cleanup_old_metrics(days: int = 7):
    """Limpiar métricas antiguas"""
    logger = get_logger("maintenance")
    
    try:
        metrics_collector = get_metrics_collector()
        metrics_collector.cleanup_old_metrics(timedelta(days=days))
        logger.info(f"Métricas anteriores a {days} días limpiadas")
    except Exception as e:
        logger.error(f"Error al limpiar métricas: {str(e)}")


def cleanup_temp_files():
    """Limpiar archivos temporales"""
    logger = get_logger("maintenance")
    temp_dirs = ["temp", "uploads", "output"]
    cleaned_files = 0
    
    for temp_dir in temp_dirs:
        if not os.path.exists(temp_dir):
            continue
        
        try:
            for filename in os.listdir(temp_dir):
                filepath = os.path.join(temp_dir, filename)
                
                if os.path.isfile(filepath):
                    # Eliminar archivos más antiguos de 1 día
                    file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(filepath))
                    
                    if file_age > timedelta(days=1):
                        os.remove(filepath)
                        cleaned_files += 1
                        logger.debug(f"Archivo temporal eliminado: {filepath}")
        
        except Exception as e:
            logger.error(f"Error al limpiar directorio {temp_dir}: {str(e)}")
    
    logger.info(f"Limpieza de archivos temporales completada. {cleaned_files} archivos eliminados.")


def optimize_database():
    """Optimizar base de datos"""
    logger = get_logger("maintenance")
    
    try:
        db_manager = DatabaseManager()
        
        with db_manager.get_db_session() as db:
            # Obtener estadísticas de tablas
            tables = [
                'empresas', 'establecimientos', 'puntos_emision', 
                'clientes', 'productos', 'facturas', 'facturas_detalles'
            ]
            
            for table in tables:
                try:
                    # Optimizar tabla
                    db.execute(f"OPTIMIZE TABLE {table}")
                    logger.info(f"Tabla {table} optimizada")
                except Exception as e:
                    logger.warning(f"No se pudo optimizar tabla {table}: {str(e)}")
            
            db.commit()
        
        logger.info("Optimización de base de datos completada")
        
    except Exception as e:
        logger.error(f"Error al optimizar base de datos: {str(e)}")


def backup_database():
    """Crear backup de la base de datos"""
    logger = get_logger("maintenance")
    
    try:
        import subprocess
        
        # Crear directorio de backup si no existe
        backup_dir = "backup"
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generar nombre de archivo con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"backup_{timestamp}.sql")
        
        # Comando mysqldump
        cmd = [
            "mysqldump",
            f"--host={settings.DB_HOST}",
            f"--port={settings.DB_PORT}",
            f"--user={settings.DB_USER}",
            f"--password={settings.DB_PASSWORD}",
            "--single-transaction",
            "--routines",
            "--triggers",
            settings.DB_NAME
        ]
        
        # Ejecutar backup
        with open(backup_file, 'w') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
        
        if result.returncode == 0:
            logger.info(f"Backup creado exitosamente: {backup_file}")
            
            # Limpiar backups antiguos (mantener solo los últimos 7)
            cleanup_old_backups(backup_dir, keep_count=7)
            
        else:
            logger.error(f"Error al crear backup: {result.stderr}")
            
    except Exception as e:
        logger.error(f"Error al crear backup: {str(e)}")


def cleanup_old_backups(backup_dir: str, keep_count: int = 7):
    """Limpiar backups antiguos"""
    logger = get_logger("maintenance")
    
    try:
        backup_files = []
        
        for filename in os.listdir(backup_dir):
            if filename.startswith("backup_") and filename.endswith(".sql"):
                filepath = os.path.join(backup_dir, filename)
                backup_files.append((filepath, os.path.getmtime(filepath)))
        
        # Ordenar por fecha de modificación (más reciente primero)
        backup_files.sort(key=lambda x: x[1], reverse=True)
        
        # Eliminar backups antiguos
        for filepath, _ in backup_files[keep_count:]:
            os.remove(filepath)
            logger.info(f"Backup antiguo eliminado: {os.path.basename(filepath)}")
            
    except Exception as e:
        logger.error(f"Error al limpiar backups antiguos: {str(e)}")


def export_metrics_report():
    """Exportar reporte de métricas"""
    logger = get_logger("maintenance")
    
    try:
        # Crear directorio de reportes si no existe
        reports_dir = "reports"
        os.makedirs(reports_dir, exist_ok=True)
        
        # Generar reporte
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(reports_dir, f"metrics_report_{timestamp}.json")
        
        metrics_collector = get_metrics_collector()
        metrics_data = metrics_collector.get_summary()
        
        # Agregar información adicional
        report_data = {
            "generated_at": datetime.now().isoformat(),
            "period": "daily",
            "metrics": metrics_data,
            "cache_stats": cache_manager.get_all_stats()
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Reporte de métricas exportado: {report_file}")
        
    except Exception as e:
        logger.error(f"Error al exportar reporte de métricas: {str(e)}")


def run_daily_maintenance():
    """Ejecutar mantenimiento diario"""
    logger = get_logger("maintenance")
    logger.info("=== Iniciando mantenimiento diario ===")
    
    start_time = time.time()
    
    try:
        # Limpiar logs antiguos (30 días)
        cleanup_old_logs(30)
        
        # Limpiar métricas antiguas (7 días)
        cleanup_old_metrics(7)
        
        # Limpiar archivos temporales
        cleanup_temp_files()
        
        # Optimizar base de datos
        optimize_database()
        
        # Crear backup
        backup_database()
        
        # Exportar reporte de métricas
        export_metrics_report()
        
        # Limpiar cache
        cache_manager.clear_all()
        
        duration = time.time() - start_time
        logger.info(f"=== Mantenimiento diario completado en {duration:.2f} segundos ===")
        
    except Exception as e:
        logger.error(f"Error durante mantenimiento diario: {str(e)}")


def run_weekly_maintenance():
    """Ejecutar mantenimiento semanal"""
    logger = get_logger("maintenance")
    logger.info("=== Iniciando mantenimiento semanal ===")
    
    try:
        # Mantenimiento diario
        run_daily_maintenance()
        
        # Tareas adicionales semanales
        logger.info("Mantenimiento semanal completado")
        
    except Exception as e:
        logger.error(f"Error durante mantenimiento semanal: {str(e)}")


def schedule_maintenance():
    """Programar tareas de mantenimiento"""
    logger = get_logger("maintenance")
    
    # Programar mantenimiento diario a las 2:00 AM
    schedule.every().day.at("02:00").do(run_daily_maintenance)
    
    # Programar mantenimiento semanal los domingos a las 3:00 AM
    schedule.every().sunday.at("03:00").do(run_weekly_maintenance)
    
    logger.info("Tareas de mantenimiento programadas:")
    logger.info("- Mantenimiento diario: 02:00 AM")
    logger.info("- Mantenimiento semanal: Domingos 03:00 AM")
    
    # Ejecutar scheduler
    while True:
        schedule.run_pending()
        time.sleep(60)  # Verificar cada minuto


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description="Script de mantenimiento del sistema")
    parser.add_argument("--task", choices=[
        "daily", "weekly", "schedule", "cleanup-logs", "cleanup-metrics", 
        "cleanup-temp", "optimize-db", "backup", "export-metrics"
    ], help="Tarea a ejecutar")
    parser.add_argument("--days", type=int, default=30, help="Días para limpieza (default: 30)")
    
    args = parser.parse_args()
    
    # Configurar logging
    logger = setup_maintenance_logging()
    
    if not args.task:
        logger.info("Iniciando scheduler de mantenimiento...")
        schedule_maintenance()
    elif args.task == "daily":
        run_daily_maintenance()
    elif args.task == "weekly":
        run_weekly_maintenance()
    elif args.task == "cleanup-logs":
        cleanup_old_logs(args.days)
    elif args.task == "cleanup-metrics":
        cleanup_old_metrics(args.days)
    elif args.task == "cleanup-temp":
        cleanup_temp_files()
    elif args.task == "optimize-db":
        optimize_database()
    elif args.task == "backup":
        backup_database()
    elif args.task == "export-metrics":
        export_metrics_report()
    elif args.task == "schedule":
        schedule_maintenance()


if __name__ == "__main__":
    main()