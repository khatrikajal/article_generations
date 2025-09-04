import hashlib
import logging
from typing import Any, Optional, Tuple, Dict
from django.core.cache import cache
from django.conf import settings
from .exceptions import CacheError

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Enhanced cache management utilities
    """
    
    # Cache key prefixes
    ARTICLE_PREFIX = "article"
    REQUEST_PREFIX = "request" 
    URL_PREFIX = "url"
    TASK_PREFIX = "task"
    STATS_PREFIX = "stats"
    
    # Default timeouts (seconds)
    DEFAULT_TIMEOUT = 3600  # 1 hour
    LONG_TIMEOUT = 24 * 3600  # 24 hours
    SHORT_TIMEOUT = 300  # 5 minutes
    
    @classmethod
    def _generate_key(cls, prefix: str, identifier: str) -> str:
        """Generate cache key with prefix and hash"""
        key_data = f"{prefix}:{identifier}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{settings.CACHES['default']['KEY_PREFIX']}:{prefix}:{key_hash}"
    
    @classmethod
    def get(cls, prefix: str, identifier: str, default=None) -> Any:
        """Get value from cache"""
        try:
            key = cls._generate_key(prefix, identifier)
            value = cache.get(key, default)
            
            if value is not None:
                logger.debug(f"Cache HIT: {key}")
            else:
                logger.debug(f"Cache MISS: {key}")
                
            return value
        except Exception as e:
            logger.error(f"Cache get error for {prefix}:{identifier}: {str(e)}")
            return default
    
    @classmethod
    def set(cls, prefix: str, identifier: str, value: Any, timeout: int = None) -> bool:
        """Set value in cache"""
        try:
            key = cls._generate_key(prefix, identifier)
            timeout = timeout or cls.DEFAULT_TIMEOUT
            
            result = cache.set(key, value, timeout)
            logger.debug(f"Cache SET: {key} (timeout: {timeout}s)")
            return result
        except Exception as e:
            logger.error(f"Cache set error for {prefix}:{identifier}: {str(e)}")
            return False
    
    @classmethod
    def delete(cls, prefix: str, identifier: str) -> bool:
        """Delete value from cache"""
        try:
            key = cls._generate_key(prefix, identifier)
            result = cache.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return result
        except Exception as e:
            logger.error(f"Cache delete error for {prefix}:{identifier}: {str(e)}")
            return False
    
    @classmethod
    def get_many(cls, prefix: str, identifiers: list) -> Dict[str, Any]:
        """Get multiple values from cache"""
        try:
            keys = {cls._generate_key(prefix, ident): ident for ident in identifiers}
            cached_data = cache.get_many(list(keys.keys()))
            
            # Map back to original identifiers
            result = {}
            for cache_key, value in cached_data.items():
                original_key = keys[cache_key]
                result[original_key] = value
                
            return result
        except Exception as e:
            logger.error(f"Cache get_many error for {prefix}: {str(e)}")
            return {}
    
    @classmethod
    def set_many(cls, prefix: str, data: Dict[str, Any], timeout: int = None) -> bool:
        """Set multiple values in cache"""
        try:
            timeout = timeout or cls.DEFAULT_TIMEOUT
            cache_data = {}
            
            for identifier, value in data.items():
                key = cls._generate_key(prefix, identifier)
                cache_data[key] = value
            
            cache.set_many(cache_data, timeout)
            logger.debug(f"Cache SET_MANY: {len(cache_data)} items (timeout: {timeout}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set_many error for {prefix}: {str(e)}")
            return False
    
    @classmethod
    def clear_prefix(cls, prefix: str) -> bool:
        """Clear all cache entries with given prefix"""
        try:
            # This is a simplified version - in production you might want
            # to use Redis SCAN for better performance
            pattern = f"{settings.CACHES['default']['KEY_PREFIX']}:{prefix}:*"
            
            # Note: This requires django-redis and direct Redis access
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            
            keys = redis_conn.keys(pattern)
            if keys:
                deleted = redis_conn.delete(*keys)
                logger.info(f"Cleared {deleted} cache entries with prefix: {prefix}")
                return True
            return True
        except Exception as e:
            logger.error(f"Cache clear_prefix error for {prefix}: {str(e)}")
            return False
    
    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            
            info = redis_conn.info()
            return {
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory_human', 'Unknown'),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate': cls._calculate_hit_rate(
                    info.get('keyspace_hits', 0),
                    info.get('keyspace_misses', 0)
                )
            }
        except Exception as e:
            logger.error(f"Cache stats error: {str(e)}")
            return {}
    
    @staticmethod
    def _calculate_hit_rate(hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage"""
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0


# Convenience functions for specific cache types
def get_cached_article(input_type: str, input_value: str) -> Tuple[Optional[Any], Optional[Any]]:
    """Get cached article request and article"""
    try:
        from articles.models import ArticleRequest, Article
        
        # Generate cache key
        cache_identifier = f"{input_type}_{hashlib.md5(str(input_value).encode()).hexdigest()}"
        
        # Try cache first
        cached_data = CacheManager.get(CacheManager.REQUEST_PREFIX, cache_identifier)
        if cached_data:
            request_id = cached_data.get('request_id')
            article_id = cached_data.get('article_id')
            existing_request = ArticleRequest.objects.filter(id=request_id).first() if request_id else None
            existing_article = Article.objects.filter(id=article_id).first() if article_id else None
            return existing_request, existing_article
        
        # Fallback to DB query
        if input_type == "text":
            existing_request = ArticleRequest.objects.filter(
                input_request="text", raw_content=input_value
            ).prefetch_related('articles').first()
        elif input_type == "url":
            existing_request = ArticleRequest.objects.filter(
                input_request="url", raw_content__icontains=input_value
            ).prefetch_related('articles').first()
        else:
            return None, None
        
        if existing_request:
            existing_article = existing_request.articles.first()
            if existing_article:
                # Store only IDs
                cache_data = {
                    'request_id': existing_request.id,
                    'article_id': existing_article.id
                }
                CacheManager.set(CacheManager.REQUEST_PREFIX, cache_identifier, cache_data)
                return existing_request, existing_article
        
        return None, None
        
    except Exception as e:
        logger.error(f"Error getting cached article: {str(e)}")
        return None, None

def set_cached_article(input_type: str, input_value: str, request_obj: Any, article_obj: Any) -> bool:
    """Cache article request and article"""
    try:
        cache_identifier = f"{input_type}_{hashlib.md5(str(input_value).encode()).hexdigest()}"
        cache_data = {
            'request_id': getattr(request_obj, "id", None),
            'article_id': getattr(article_obj, "id", None)
        }
        return CacheManager.set(
            CacheManager.REQUEST_PREFIX, 
            cache_identifier, 
            cache_data,
            CacheManager.LONG_TIMEOUT
        )
    except Exception as e:
        logger.error(f"Error caching article: {str(e)}")
        return False

def get_cached_url_content(url: str) -> Optional[str]:
    """Get cached URL content - returns only text content"""
    try:
        from articles.models import UrlCache
        
        # Try cache first - this should now return only serializable data
        cached_content = CacheManager.get(CacheManager.URL_PREFIX, url)
        if cached_content:
            # If it's a dict (new format), extract the text
            if isinstance(cached_content, dict):
                return cached_content.get('cleaned_text', '')
            # If it's a string (old format), return as is
            elif isinstance(cached_content, str):
                return cached_content
        
        # Fallback to DB - using updated get_cached_content method
        url_cache_data = UrlCache.get_cached_content(url)
        if url_cache_data and url_cache_data.status == 'success':
            # Store only the text content in cache
            CacheManager.set(
                CacheManager.URL_PREFIX, 
                url, 
                {
                    'cleaned_text': url_cache_data.cleaned_text,
                    'status': url_cache_data.status,
                    'error_message': url_cache_data.error_message,
                },
                CacheManager.LONG_TIMEOUT
            )
            return url_cache_data.cleaned_text
        
        return None
    except Exception as e:
        logger.error(f"Error getting cached URL content: {str(e)}")
        return None

def set_cached_url_content(url: str, content: str, timeout: int = None) -> bool:
    """Cache URL content - stores only serializable data"""
    try:
        cache_data = {
            'cleaned_text': content,
            'status': 'success',
            'error_message': None,
        }
        return CacheManager.set(
            CacheManager.URL_PREFIX,
            url,
            cache_data,
            timeout or CacheManager.LONG_TIMEOUT
        )
    except Exception as e:
        logger.error(f"Error caching URL content: {str(e)}")
        return False


def get_cached_task_result(task_id: str) -> Optional[Dict[str, Any]]:
    """Get cached task result"""
    return CacheManager.get(CacheManager.TASK_PREFIX, task_id)


def set_cached_task_result(task_id: str, result: Dict[str, Any], timeout: int = None) -> bool:
    """Cache task result"""
    return CacheManager.set(
        CacheManager.TASK_PREFIX,
        task_id,
        result,
        timeout or CacheManager.SHORT_TIMEOUT
    )


def invalidate_article_cache(article_id: str) -> bool:
    """Invalidate all cache entries related to an article"""
    try:
        # Delete specific article cache
        CacheManager.delete(CacheManager.ARTICLE_PREFIX, str(article_id))
        
        # You might want to add more specific invalidation logic here
        # based on your caching strategy
        
        return True
    except Exception as e:
        logger.error(f"Error invalidating article cache: {str(e)}")
        return False


def get_cache_health() -> Dict[str, Any]:
    """Get cache health information"""
    try:
        # Test basic cache operations
        test_key = "health_check_test"
        test_value = {"timestamp": "test"}
        
        # Test set operation
        set_success = cache.set(test_key, test_value, 60)
        
        # Test get operation  
        get_result = cache.get(test_key)
        get_success = get_result == test_value
        
        # Test delete operation
        delete_success = cache.delete(test_key)
        
        # Get cache stats
        stats = CacheManager.get_stats()
        
        return {
            'status': 'healthy' if all([set_success, get_success, delete_success]) else 'unhealthy',
            'operations': {
                'set': set_success,
                'get': get_success,
                'delete': delete_success
            },
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"Cache health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }