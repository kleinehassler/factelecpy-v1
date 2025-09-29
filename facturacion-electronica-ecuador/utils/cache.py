"""
Sistema de cache para mejorar el rendimiento de la aplicación
"""
import time
import threading
import json
import hashlib
from typing import Any, Optional, Dict, Callable
from datetime import datetime, timedelta
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class CacheItem:
    """Item individual del cache"""
    
    def __init__(self, value: Any, ttl: int = 3600):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.access_count = 0
        self.last_accessed = time.time()
    
    def is_expired(self) -> bool:
        """Verificar si el item ha expirado"""
        return time.time() - self.created_at > self.ttl
    
    def access(self) -> Any:
        """Acceder al valor y actualizar estadísticas"""
        self.access_count += 1
        self.last_accessed = time.time()
        return self.value


class MemoryCache:
    """Cache en memoria con TTL y estadísticas"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheItem] = {}
        self.lock = threading.RLock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Obtener valor del cache"""
        with self.lock:
            if key not in self.cache:
                self.stats['misses'] += 1
                return None
            
            item = self.cache[key]
            
            if item.is_expired():
                del self.cache[key]
                self.stats['misses'] += 1
                return None
            
            self.stats['hits'] += 1
            return item.access()
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Establecer valor en el cache"""
        with self.lock:
            if ttl is None:
                ttl = self.default_ttl
            
            # Limpiar items expirados si el cache está lleno
            if len(self.cache) >= self.max_size:
                self._evict_expired()
                
                # Si aún está lleno, usar LRU
                if len(self.cache) >= self.max_size:
                    self._evict_lru()
            
            self.cache[key] = CacheItem(value, ttl)
            self.stats['sets'] += 1
    
    def delete(self, key: str) -> bool:
        """Eliminar valor del cache"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                self.stats['deletes'] += 1
                return True
            return False
    
    def clear(self) -> None:
        """Limpiar todo el cache"""
        with self.lock:
            self.cache.clear()
            logger.info("Cache limpiado completamente")
    
    def _evict_expired(self) -> None:
        """Eliminar items expirados"""
        expired_keys = [
            key for key, item in self.cache.items() 
            if item.is_expired()
        ]
        
        for key in expired_keys:
            del self.cache[key]
            self.stats['evictions'] += 1
    
    def _evict_lru(self) -> None:
        """Eliminar el item menos recientemente usado"""
        if not self.cache:
            return
        
        lru_key = min(
            self.cache.keys(), 
            key=lambda k: self.cache[k].last_accessed
        )
        
        del self.cache[lru_key]
        self.stats['evictions'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del cache"""
        with self.lock:
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hit_rate': round(hit_rate, 2),
                'stats': self.stats.copy()
            }
    
    def get_info(self) -> Dict[str, Any]:
        """Obtener información detallada del cache"""
        with self.lock:
            items_info = []
            
            for key, item in self.cache.items():
                items_info.append({
                    'key': key,
                    'size_bytes': len(str(item.value)),
                    'created_at': datetime.fromtimestamp(item.created_at).isoformat(),
                    'last_accessed': datetime.fromtimestamp(item.last_accessed).isoformat(),
                    'access_count': item.access_count,
                    'ttl': item.ttl,
                    'expired': item.is_expired()
                })
            
            return {
                'stats': self.get_stats(),
                'items': items_info
            }


class CacheManager:
    """Gestor de múltiples caches"""
    
    def __init__(self):
        self.caches: Dict[str, MemoryCache] = {}
        self.lock = threading.Lock()
    
    def get_cache(self, name: str, max_size: int = 1000, default_ttl: int = 3600) -> MemoryCache:
        """Obtener o crear un cache"""
        with self.lock:
            if name not in self.caches:
                self.caches[name] = MemoryCache(max_size, default_ttl)
                logger.info(f"Cache '{name}' creado con max_size={max_size}, ttl={default_ttl}")
            
            return self.caches[name]
    
    def clear_all(self) -> None:
        """Limpiar todos los caches"""
        with self.lock:
            for cache in self.caches.values():
                cache.clear()
            logger.info("Todos los caches limpiados")
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Obtener estadísticas de todos los caches"""
        with self.lock:
            return {
                name: cache.get_stats() 
                for name, cache in self.caches.items()
            }


# Instancia global del gestor de cache
cache_manager = CacheManager()


def get_cache(name: str = "default", max_size: int = 1000, default_ttl: int = 3600) -> MemoryCache:
    """Obtener instancia de cache"""
    return cache_manager.get_cache(name, max_size, default_ttl)


def cache_key(*args, **kwargs) -> str:
    """Generar clave de cache a partir de argumentos"""
    # Crear string único a partir de argumentos
    key_data = {
        'args': args,
        'kwargs': sorted(kwargs.items())
    }
    
    key_string = json.dumps(key_data, sort_keys=True, default=str)
    
    # Generar hash MD5
    return hashlib.md5(key_string.encode()).hexdigest()


def cached(cache_name: str = "default", ttl: int = 3600, key_func: Optional[Callable] = None):
    """
    Decorador para cachear resultados de funciones
    
    Args:
        cache_name: Nombre del cache a usar
        ttl: Tiempo de vida en segundos
        key_func: Función para generar la clave (opcional)
    """
    def decorator(func: Callable) -> Callable:
        cache = get_cache(cache_name, default_ttl=ttl)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generar clave
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # Intentar obtener del cache
            result = cache.get(key)
            if result is not None:
                logger.debug(f"Cache hit para {func.__name__}: {key}")
                return result
            
            # Ejecutar función y cachear resultado
            logger.debug(f"Cache miss para {func.__name__}: {key}")
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            
            return result
        
        # Agregar métodos para limpiar cache
        wrapper.cache_clear = lambda: cache.clear()
        wrapper.cache_info = lambda: cache.get_stats()
        
        return wrapper
    
    return decorator


# Caches específicos para la aplicación
clientes_cache = get_cache("clientes", max_size=500, default_ttl=1800)  # 30 minutos
productos_cache = get_cache("productos", max_size=1000, default_ttl=3600)  # 1 hora
facturas_cache = get_cache("facturas", max_size=200, default_ttl=900)  # 15 minutos
sri_cache = get_cache("sri", max_size=100, default_ttl=300)  # 5 minutos


def invalidate_cliente_cache(cliente_id: int = None):
    """Invalidar cache de clientes"""
    if cliente_id:
        # Invalidar cliente específico
        clientes_cache.delete(f"cliente:{cliente_id}")
    else:
        # Invalidar todo el cache de clientes
        clientes_cache.clear()
    
    logger.info(f"Cache de clientes invalidado: {cliente_id or 'todos'}")


def invalidate_producto_cache(producto_id: int = None):
    """Invalidar cache de productos"""
    if producto_id:
        productos_cache.delete(f"producto:{producto_id}")
    else:
        productos_cache.clear()
    
    logger.info(f"Cache de productos invalidado: {producto_id or 'todos'}")


def invalidate_factura_cache(factura_id: int = None):
    """Invalidar cache de facturas"""
    if factura_id:
        facturas_cache.delete(f"factura:{factura_id}")
    else:
        facturas_cache.clear()
    
    logger.info(f"Cache de facturas invalidado: {factura_id or 'todos'}")


def get_cache_stats() -> Dict[str, Any]:
    """Obtener estadísticas de todos los caches"""
    return cache_manager.get_all_stats()