"""
Custom exception classes for the article generation system
"""


class ArticleGenerationBaseException(Exception):
    """Base exception for article generation system"""
    
    def __init__(self, message, code=None, details=None):
        self.message = message
        self.code = code or 'UNKNOWN_ERROR'
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(ArticleGenerationBaseException):
    """Raised when input validation fails"""
    
    def __init__(self, message, field=None, details=None):
        self.field = field
        super().__init__(
            message,
            code='VALIDATION_ERROR',
            details=details or {'field': field}
        )


class ScrapingError(ArticleGenerationBaseException):
    """Raised when web scraping fails"""
    
    def __init__(self, message, url=None, status_code=None, details=None):
        self.url = url
        self.status_code = status_code
        super().__init__(
            message,
            code='SCRAPING_ERROR',
            details=details or {'url': url, 'status_code': status_code}
        )


class GenerationError(ArticleGenerationBaseException):
    """Raised when article generation fails"""
    
    def __init__(self, message, stage=None, details=None):
        self.stage = stage
        super().__init__(
            message,
            code='GENERATION_ERROR',
            details=details or {'stage': stage}
        )


class CacheError(ArticleGenerationBaseException):
    """Raised when cache operations fail"""
    
    def __init__(self, message, key=None, operation=None, details=None):
        self.key = key
        self.operation = operation
        super().__init__(
            message,
            code='CACHE_ERROR',
            details=details or {'key': key, 'operation': operation}
        )


class TaskError(ArticleGenerationBaseException):
    """Raised when background task fails"""
    
    def __init__(self, message, task_id=None, task_name=None, details=None):
        self.task_id = task_id
        self.task_name = task_name
        super().__init__(
            message,
            code='TASK_ERROR',
            details=details or {'task_id': task_id, 'task_name': task_name}
        )


class DatabaseError(ArticleGenerationBaseException):
    """Raised when database operations fail"""
    
    def __init__(self, message, model=None, operation=None, details=None):
        self.model = model
        self.operation = operation
        super().__init__(
            message,
            code='DATABASE_ERROR',
            details=details or {'model': model, 'operation': operation}
        )


class RateLimitError(ArticleGenerationBaseException):
    """Raised when rate limits are exceeded"""
    
    def __init__(self, message, limit=None, window=None, details=None):
        self.limit = limit
        self.window = window
        super().__init__(
            message,
            code='RATE_LIMIT_ERROR',
            details=details or {'limit': limit, 'window': window}
        )


class ConfigurationError(ArticleGenerationBaseException):
    """Raised when system configuration is invalid"""
    
    def __init__(self, message, setting=None, details=None):
        self.setting = setting
        super().__init__(
            message,
            code='CONFIGURATION_ERROR',
            details=details or {'setting': setting}
        )