import logging
import time
import functools
from typing import Any, Callable, Dict, Optional
from django.http import HttpRequest
from django.core.cache import cache
from django.utils import timezone
from .exceptions import RateLimitError

logger = logging.getLogger(__name__)


def get_client_ip(request: HttpRequest) -> str:
    """
    Get client IP address from request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip or 'unknown'


def timing_decorator(func: Callable) -> Callable:
    """
    Decorator to measure function execution time
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} executed in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.3f}s: {str(e)}")
            raise
    return wrapper


def retry_decorator(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator to retry function execution on failure
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(f"{func.__name__} failed after {max_retries} retries: {str(e)}")
                        raise
                    
                    logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {str(e)}, retrying in {current_delay}s")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
        return wrapper
    return decorator


def rate_limit(calls: int, period: int, key_func: Callable = None):
    """
    Rate limiting decorator
    
    Args:
        calls: Number of calls allowed
        period: Time period in seconds
        key_func: Function to generate rate limit key (default: uses function name)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate rate limit key
            if key_func:
                rate_key = key_func(*args, **kwargs)
            else:
                rate_key = f"rate_limit:{func.__name__}"
            
            # Check current count
            current_count = cache.get(rate_key, 0)
            
            if current_count >= calls:
                raise RateLimitError(
                    f"Rate limit exceeded: {calls} calls per {period} seconds",
                    limit=calls,
                    window=period
                )
            
            # Execute function
            try:
                result = func(*args, **kwargs)
                
                # Increment counter
                cache.set(rate_key, current_count + 1, period)
                
                return result
            except Exception:
                # Don't increment counter on failure
                raise
                
        return wrapper
    return decorator


def cache_result(timeout: int = 3600, key_func: Callable = None):
    """
    Cache function result decorator
    
    Args:
        timeout: Cache timeout in seconds
        key_func: Function to generate cache key
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Simple key generation from function name and args
                args_str = str(args) + str(sorted(kwargs.items()))
                cache_key = f"cache:{func.__name__}:{hash(args_str)}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            logger.debug(f"Cached result for {func.__name__}")
            
            return result
            
        return wrapper
    return decorator


def validate_input(validation_rules: Dict[str, Any]):
    """
    Input validation decorator
    
    Args:
        validation_rules: Dictionary of validation rules
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Validate kwargs against rules
            for field, rules in validation_rules.items():
                if field in kwargs:
                    value = kwargs[field]
                    
                    # Required check
                    if rules.get('required', False) and not value:
                        raise ValueError(f"Field '{field}' is required")
                    
                    # Type check
                    if 'type' in rules and value is not None:
                        expected_type = rules['type']
                        if not isinstance(value, expected_type):
                            raise ValueError(f"Field '{field}' must be of type {expected_type.__name__}")
                    
                    # Min/Max length for strings
                    if isinstance(value, str):
                        if 'min_length' in rules and len(value) < rules['min_length']:
                            raise ValueError(f"Field '{field}' must be at least {rules['min_length']} characters")
                        if 'max_length' in rules and len(value) > rules['max_length']:
                            raise ValueError(f"Field '{field}' must be at most {rules['max_length']} characters")
                    
                    # Min/Max value for numbers
                    if isinstance(value, (int, float)):
                        if 'min_value' in rules and value < rules['min_value']:
                            raise ValueError(f"Field '{field}' must be at least {rules['min_value']}")
                        if 'max_value' in rules and value > rules['max_value']:
                            raise ValueError(f"Field '{field}' must be at most {rules['max_value']}")
                    
                    # Custom validator function
                    if 'validator' in rules:
                        validator = rules['validator']
                        if not validator(value):
                            raise ValueError(f"Field '{field}' failed custom validation")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def safe_execute(default_return=None, log_errors=True):
    """
    Safely execute function and return default on error
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"Safe execution failed for {func.__name__}: {str(e)}")
                return default_return
        return wrapper
    return decorator


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human readable format
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to specified length
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe file system usage
    """
    import re
    
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    
    # Ensure it's not empty
    if not filename:
        filename = "untitled"
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_length = 255 - len(ext) - 1 if ext else 255
        filename = name[:max_name_length]
        if ext:
            filename += '.' + ext
    
    return filename


def generate_unique_id() -> str:
    """
    Generate a unique identifier
    """
    import uuid
    return str(uuid.uuid4())


def is_valid_url(url: str) -> bool:
    """
    Check if URL is valid
    """
    from django.core.validators import URLValidator
    from django.core.exceptions import ValidationError as DjangoValidationError
    
    validator = URLValidator()
    try:
        validator(url)
        return True
    except DjangoValidationError:
        return False


def extract_domain(url: str) -> Optional[str]:
    """
    Extract domain from URL
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return None


def calculate_word_count(text: str) -> int:
    """
    Calculate word count in text
    """
    if not text:
        return 0
    
    import re
    # Remove extra whitespace and split by word boundaries
    words = re.findall(r'\b\w+\b', text.lower())
    return len(words)


def estimate_reading_time(text: str, wpm: int = 200) -> int:
    """
    Estimate reading time in minutes
    
    Args:
        text: Text to analyze
        wpm: Words per minute reading speed
    """
    word_count = calculate_word_count(text)
    return max(1, round(word_count / wpm))


def chunk_list(lst: list, chunk_size: int) -> list:
    """
    Split list into chunks of specified size
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def deep_merge_dict(dict1: dict, dict2: dict) -> dict:
    """
    Deep merge two dictionaries
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dict(result[key], value)
        else:
            result[key] = value
    
    return result


def get_system_stats() -> Dict[str, Any]:
    """
    Get basic system statistics
    """
    import psutil
    import os
    
    try:
        stats = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory': {
                'total': psutil.virtual_memory().total,
                'available': psutil.virtual_memory().available,
                'percent': psutil.virtual_memory().percent
            },
            'disk': {
                'total': psutil.disk_usage('/').total,
                'used': psutil.disk_usage('/').used,
                'free': psutil.disk_usage('/').free,
                'percent': psutil.disk_usage('/').percent
            },
            'process_count': len(psutil.pids()),
            'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
        }
        return stats
    except ImportError:
        # psutil not available
        return {'error': 'psutil not available'}
    except Exception as e:
        return {'error': str(e)}


class ContextTimer:
    """
    Context manager for timing operations
    """
    
    def __init__(self, description: str = "Operation"):
        self.description = description
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        
        if exc_type is None:
            logger.info(f"{self.description} completed in {duration:.3f}s")
        else:
            logger.error(f"{self.description} failed after {duration:.3f}s")
    
    @property
    def duration(self) -> Optional[float]:
        """Get duration if timing is complete"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


def batch_process(items: list, batch_size: int, process_func: Callable, **kwargs) -> list:
    """
    Process items in batches
    
    Args:
        items: List of items to process
        batch_size: Size of each batch
        process_func: Function to process each batch
        **kwargs: Additional arguments for process_func
    
    Returns:
        List of results from all batches
    """
    results = []
    batches = chunk_list(items, batch_size)
    
    for i, batch in enumerate(batches):
        logger.info(f"Processing batch {i + 1}/{len(batches)} ({len(batch)} items)")
        
        try:
            batch_result = process_func(batch, **kwargs)
            results.extend(batch_result if isinstance(batch_result, list) else [batch_result])
        except Exception as e:
            logger.error(f"Error processing batch {i + 1}: {str(e)}")
            raise
    
    return results