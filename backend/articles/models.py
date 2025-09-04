from django.db import models
from django.core.cache import cache
from django.utils import timezone
import uuid
import hashlib


class BaseModel(models.Model):
    """
    Abstract base model for UUID primary key and timestamps
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ArticleRequestManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related().prefetch_related('articles', 'history')
    
    def get_cached_request(self, input_type, input_value):
        """Get cached request with optimized queries"""
        cache_key = f"article_request_{input_type}_{hashlib.md5(str(input_value).encode()).hexdigest()}"
        cached = cache.get(cache_key)
        
        if cached:
            return cached
            
        if input_type == "text":
            request_obj = self.filter(
                input_request="text", 
                raw_content=input_value
            ).prefetch_related('articles').first()
        elif input_type == "url":
            request_obj = self.filter(
                input_request="url", 
                raw_content__icontains=input_value
            ).prefetch_related('articles').first()
        else:
            return None
            
        if request_obj:
            cache.set(cache_key, request_obj, timeout=3600)  # 1 hour
            
        return request_obj


class ArticleRequest(BaseModel):
    """
    Stores the original request from the user (URL(s) or raw text)
    """
    INPUT_CHOICES = [
        ('url', 'URL'),
        ('text', 'Text'),
    ]

    input_request = models.CharField(max_length=10, choices=INPUT_CHOICES, db_index=True)
    instruction = models.TextField(blank=True, null=True)
    raw_content = models.TextField(blank=True, null=True)
    content_hash = models.CharField(max_length=64, db_index=True, blank=True)  # For deduplication
    
    objects = ArticleRequestManager()

    def save(self, *args, **kwargs):
        # Generate content hash for deduplication
        if self.raw_content:
            self.content_hash = hashlib.sha256(
                f"{self.input_request}:{self.raw_content}".encode()
            ).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Request {self.id} - {self.input_request}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['input_request']),
            models.Index(fields=['content_hash']),
            models.Index(fields=['input_request', 'created_at']),
        ]


class UrlCache(BaseModel):
    """
    Cache for scraped & cleaned webpage text
    """
    url = models.URLField(unique=True, db_index=True)
    url_hash = models.CharField(max_length=64, unique=True, db_index=True)
    cleaned_text = models.TextField()
    status = models.CharField(max_length=20, default='success')
    error_message = models.TextField(blank=True, null=True)
    access_count = models.PositiveIntegerField(default=0)
    last_accessed = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # Generate URL hash for faster lookups
        self.url_hash = hashlib.md5(self.url.encode()).hexdigest()
        # Set expiration (24 hours from now)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Cache for {self.url[:60]}"

    @classmethod
    def get_cached_content(cls, url):
        """Get cached content with access tracking - returns serializable data"""
        cache_key = f"url_cache_{hashlib.md5(url.encode()).hexdigest()}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return type('CachedUrlData', (), {
                'cleaned_text': cached_data.get('cleaned_text', ''),
                'status': cached_data.get('status', 'unknown'),
                'error_message': cached_data.get('error_message'),
            })()
            
        try:
            url_cache = cls.objects.get(url=url, expires_at__gt=timezone.now())
            url_cache.access_count += 1
            url_cache.save(update_fields=['access_count', 'last_accessed'])
            
            cache_data = {
                'cleaned_text': url_cache.cleaned_text,
                'status': url_cache.status,
                'error_message': url_cache.error_message,
                'created_at': url_cache.created_at.isoformat(),
                'expires_at': url_cache.expires_at.isoformat(),
            }
            cache.set(cache_key, cache_data, timeout=1800)  # 30 minutes
            
            return type('CachedUrlData', (), {
                'cleaned_text': url_cache.cleaned_text,
                'status': url_cache.status,
                'error_message': url_cache.error_message,
            })()
            
        except cls.DoesNotExist:
            return None

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=["url_hash"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["last_accessed"]),
        ]


class ArticleManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related('article_request')
    
    def with_full_relations(self):
        return self.get_queryset().select_related(
            'article_request'
        ).prefetch_related('history')


# In your models.py file, find this section and update it:

class ValidationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PASS = "pass", "Pass"
    FAIL = "fail", "Fail"
    PARTIAL = "partial", "Partial"


class Article(BaseModel):
    """
    Stores generated + validated articles
    """
    article_request = models.ForeignKey(
        ArticleRequest, 
        on_delete=models.CASCADE, 
        related_name='articles',
        db_index=True
    )

    headline = models.CharField(max_length=500)
    project_details = models.TextField()
    participants = models.TextField(blank=True, null=True)
    lots = models.TextField(blank=True, null=True)
    organizations = models.TextField(blank=True, null=True)
    is_final = models.BooleanField(default=False, db_index=True)
    final_render = models.TextField()
    
    # Additional metadata
    generation_time = models.FloatField(default=0.0)
    word_count = models.PositiveIntegerField(default=0)
    
    # FIX: Increase the max_length for validation_status from 20 to 50
    validation_status = models.CharField(
        max_length=50,  # Changed from 20 to 50
        choices=ValidationStatus.choices,
        default=ValidationStatus.PENDING,
        db_index=True
    )
    validation_message = models.TextField(blank=True, null=True)
    
    objects = ArticleManager()

    def save(self, *args, **kwargs):
        total_text = f"{self.headline} {self.project_details} {self.participants or ''} {self.lots or ''} {self.organizations or ''}"
        self.word_count = len(total_text.split())
        super().save(*args, **kwargs)
        
        # Clear related caches
        cache_key = f"article_{self.id}"
        cache.delete(cache_key)

    def get_cached(self):
        """
        Returns a serializable dictionary representation of the article
        for caching and API responses
        """
        return {
            'id': str(self.id),
            'headline': self.headline,
            'project_details': self.project_details,
            'participants': self.participants,
            'lots': self.lots,
            'organizations': self.organizations,
            'is_final': self.is_final,
            'final_render': self.final_render,
            'generation_time': self.generation_time,
            'word_count': self.word_count,
            'validation_status': self.validation_status,
            'validation_message': self.validation_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'article_request_id': str(self.article_request_id) if self.article_request_id else None,
        }

    def __str__(self):
        return f"Article {self.id} - {self.headline[:50]}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['is_final']),
            models.Index(fields=['validation_status']),
            models.Index(fields=['article_request']),
            models.Index(fields=['is_final', 'created_at']),
            models.Index(fields=['validation_status', 'created_at']),
        ]

    # ... rest of the model remains the same
class ArticleHistory(BaseModel):
    """
    Stores history of changes (feedback loop, edits, regenerations)
    """
    article_request = models.ForeignKey(
        ArticleRequest, 
        on_delete=models.CASCADE, 
        related_name='history',
        db_index=True
    )
    article = models.ForeignKey(
        Article, 
        on_delete=models.CASCADE, 
        related_name='history',
        db_index=True
    )

    changes = models.JSONField(blank=True, null=True)
    action_type = models.CharField(max_length=50, default='created')
    user_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['article']),
            models.Index(fields=['article_request']),
            models.Index(fields=['action_type']),
            models.Index(fields=['article', 'created_at']),
        ]

    def __str__(self):
        return f"History {self.id} - {self.article.headline[:30]} ({self.action_type})"


# Custom queryset extensions
class ArticleQuerySet(models.QuerySet):
    def with_word_count_range(self, min_words=None, max_words=None):
        queryset = self
        if min_words:
            queryset = queryset.filter(word_count__gte=min_words)
        if max_words:
            queryset = queryset.filter(word_count__lte=max_words)
        return queryset
    
    def recent(self, hours=24):
        cutoff_time = timezone.now() - timezone.timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff_time)
    
    def finalized(self):
        return self.filter(is_final=True)


# Update Article manager to use custom queryset
ArticleManager = ArticleManager.from_queryset(ArticleQuerySet)
