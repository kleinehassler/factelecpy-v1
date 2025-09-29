"""
Sistema de métricas y monitoreo para la aplicación de facturación electrónica
"""
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import os
from dataclasses import dataclass, asdict


@dataclass
class MetricPoint:
    """Punto de métrica individual"""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'value': self.value,
            'labels': self.labels or {}
        }


class MetricsCollector:
    """Recolector de métricas de la aplicación"""
    
    def __init__(self, max_points: int = 1000):
        self.max_points = max_points
        self.metrics = defaultdict(lambda: deque(maxlen=max_points))
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        self.histograms = defaultdict(list)
        self.lock = threading.Lock()
    
    def increment_counter(self, name: str, value: float = 1, labels: Dict[str, str] = None):
        """Incrementar un contador"""
        with self.lock:
            key = self._make_key(name, labels)
            self.counters[key] += value
            self.metrics[name].append(MetricPoint(datetime.utcnow(), self.counters[key], labels))
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Establecer valor de un gauge"""
        with self.lock:
            key = self._make_key(name, labels)
            self.gauges[key] = value
            self.metrics[name].append(MetricPoint(datetime.utcnow(), value, labels))
    
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Registrar valor en histograma"""
        with self.lock:
            key = self._make_key(name, labels)
            self.histograms[key].append(value)
            self.metrics[name].append(MetricPoint(datetime.utcnow(), value, labels))
    
    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """Crear clave única para métrica con labels"""
        if not labels:
            return name
        
        label_str = ','.join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}[{label_str}]"
    
    def get_metrics(self, name: str = None, since: datetime = None) -> Dict[str, List[Dict]]:
        """Obtener métricas"""
        with self.lock:
            result = {}
            
            metrics_to_process = [name] if name else self.metrics.keys()
            
            for metric_name in metrics_to_process:
                if metric_name in self.metrics:
                    points = self.metrics[metric_name]
                    
                    if since:
                        points = [p for p in points if p.timestamp >= since]
                    
                    result[metric_name] = [p.to_dict() for p in points]
            
            return result
    
    def get_summary(self) -> Dict[str, Any]:
        """Obtener resumen de métricas"""
        with self.lock:
            now = datetime.utcnow()
            last_hour = now - timedelta(hours=1)
            
            summary = {
                'timestamp': now.isoformat(),
                'counters': dict(self.counters),
                'gauges': dict(self.gauges),
                'histograms': {}
            }
            
            # Calcular estadísticas de histogramas
            for key, values in self.histograms.items():
                if values:
                    summary['histograms'][key] = {
                        'count': len(values),
                        'min': min(values),
                        'max': max(values),
                        'avg': sum(values) / len(values),
                        'p50': self._percentile(values, 50),
                        'p95': self._percentile(values, 95),
                        'p99': self._percentile(values, 99)
                    }
            
            return summary
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calcular percentil"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def export_to_file(self, filepath: str):
        """Exportar métricas a archivo JSON"""
        summary = self.get_summary()
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
    
    def cleanup_old_metrics(self, older_than: timedelta = timedelta(hours=24)):
        """Limpiar métricas antiguas"""
        cutoff = datetime.utcnow() - older_than
        
        with self.lock:
            for metric_name in self.metrics:
                points = self.metrics[metric_name]
                # Filtrar puntos recientes
                recent_points = deque([p for p in points if p.timestamp >= cutoff], 
                                    maxlen=self.max_points)
                self.metrics[metric_name] = recent_points


class ApplicationMetrics:
    """Métricas específicas de la aplicación"""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Registrar métrica de request HTTP"""
        labels = {
            'method': method,
            'endpoint': endpoint,
            'status_code': str(status_code)
        }
        
        self.collector.increment_counter('http_requests_total', 1, labels)
        self.collector.record_histogram('http_request_duration_seconds', duration, labels)
    
    def record_database_query(self, operation: str, table: str, duration: float, success: bool):
        """Registrar métrica de consulta a base de datos"""
        labels = {
            'operation': operation,
            'table': table,
            'success': str(success)
        }
        
        self.collector.increment_counter('database_queries_total', 1, labels)
        self.collector.record_histogram('database_query_duration_seconds', duration, labels)
    
    def record_factura_created(self, success: bool, sri_status: str = None):
        """Registrar creación de factura"""
        labels = {'success': str(success)}
        if sri_status:
            labels['sri_status'] = sri_status
        
        self.collector.increment_counter('facturas_created_total', 1, labels)
    
    def record_sri_request(self, operation: str, success: bool, duration: float):
        """Registrar request al SRI"""
        labels = {
            'operation': operation,
            'success': str(success)
        }
        
        self.collector.increment_counter('sri_requests_total', 1, labels)
        self.collector.record_histogram('sri_request_duration_seconds', duration, labels)
    
    def set_active_connections(self, count: int):
        """Establecer número de conexiones activas"""
        self.collector.set_gauge('database_connections_active', count)
    
    def set_memory_usage(self, bytes_used: int):
        """Establecer uso de memoria"""
        self.collector.set_gauge('memory_usage_bytes', bytes_used)


# Instancia global del recolector de métricas
metrics_collector = MetricsCollector()
app_metrics = ApplicationMetrics(metrics_collector)


def get_metrics_collector() -> MetricsCollector:
    """Obtener instancia del recolector de métricas"""
    return metrics_collector


def get_app_metrics() -> ApplicationMetrics:
    """Obtener instancia de métricas de aplicación"""
    return app_metrics