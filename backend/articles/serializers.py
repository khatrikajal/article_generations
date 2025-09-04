from rest_framework import serializers
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import ArticleRequest, Article, ArticleHistory, UrlCache


class ArticleRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for ArticleRequest with validation
    """
    
    class Meta:
        model = ArticleRequest
        fields = [
            "id",
            "input_request",
            "instruction",
            "content_hash",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "content_hash"]

    def validate_input_request(self, value):
        """Validate input request type"""
        if value not in ['url', 'text']:
            raise serializers.ValidationError("input_request must be either 'url' or 'text'")
        return value

    def validate_instruction(self, value):
        """Validate instruction length"""
        if value and len(value) > 5000:  # Reasonable limit
            raise serializers.ValidationError("Instruction is too long (max 5000 characters)")
        return value


class ArticleRequestCreateSerializer(serializers.Serializer):
    """
    Serializer for creating article requests via API
    """
    input_type = serializers.ChoiceField(choices=['url', 'text'])
    input_value = serializers.CharField(max_length=10000)
    instruction = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    force_refresh = serializers.BooleanField(default=False)
    async_processing = serializers.BooleanField(default=True, source='async')

    def validate_input_value(self, value):
        """Validate input value based on type"""
        input_type = self.initial_data.get('input_type')
        
        if input_type == 'url':
            # Validate URL format
            validator = URLValidator()
            urls = [value] if isinstance(value, str) else value
            
            for url in urls:
                try:
                    validator(url)
                except DjangoValidationError:
                    raise serializers.ValidationError(f"Invalid URL format: {url}")
        
        elif input_type == 'text':
            if len(value.strip()) < 10:
                raise serializers.ValidationError("Text input is too short (minimum 10 characters)")
            if len(value) > 50000:  # 50KB limit for text input
                raise serializers.ValidationError("Text input is too long (max 50,000 characters)")
        
        return value


class ArticleSerializer(serializers.ModelSerializer):
    """
    Enhanced Article serializer with computed fields
    """
    article_request = ArticleRequestSerializer(read_only=True)
    sections_summary = serializers.SerializerMethodField()
    processing_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Article
        fields = [
            "id",
            "article_request",
            "headline",
            "project_details",
            "participants",
            "lots",
            "organizations",
            "final_render",
            "is_final",
            "generation_time",
            "word_count",
            "validation_status",
            "sections_summary",
            "processing_info",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at", "generation_time", 
            "word_count", "sections_summary", "processing_info"
        ]

    def get_sections_summary(self, obj):
        """Get summary of which sections have content"""
        sections = {
            'headline': bool(obj.headline and obj.headline.strip()),
            'project_details': bool(obj.project_details and obj.project_details.strip()),
            'participants': bool(obj.participants and obj.participants.strip()),
            'lots': bool(obj.lots and obj.lots.strip()),
            'organizations': bool(obj.organizations and obj.organizations.strip()),
        }
        
        completed = sum(sections.values())
        return {
            'sections': sections,
            'completed_count': completed,
            'total_count': len(sections),
            'completion_percentage': (completed / len(sections)) * 100
        }

    def get_processing_info(self, obj):
        """Get processing information"""
        return {
            'generation_time_formatted': f"{obj.generation_time:.2f}s" if obj.generation_time else "N/A",
            'word_count': obj.word_count,
            'validation_status': obj.validation_status,
            'is_final': obj.is_final,
        }

    def validate_headline(self, value):
        """Validate headline"""
        if value and len(value) > 500:
            raise serializers.ValidationError("Headline is too long (max 500 characters)")
        return value


class ArticleHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for ArticleHistory with nested data
    """
    article_request = ArticleRequestSerializer(read_only=True)
    article_summary = serializers.SerializerMethodField()
    changes_summary = serializers.SerializerMethodField()

    class Meta:
        model = ArticleHistory
        fields = [
            "id",
            "article_request",
            "article_summary",
            "changes",
            "changes_summary",
            "action_type",
            "user_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_article_summary(self, obj):
        """Get basic article info"""
        return {
            'id': str(obj.article.id),
            'headline': obj.article.headline[:100] + '...' if len(obj.article.headline) > 100 else obj.article.headline,
            'is_final': obj.article.is_final,
            'validation_status': obj.article.validation_status,
        }

    def get_changes_summary(self, obj):
        """Get summary of changes made"""
        if not obj.changes:
            return None
            
        if isinstance(obj.changes, dict):
            return {
                'sections_modified': list(obj.changes.keys()),
                'modification_count': len(obj.changes),
                'action_type': obj.action_type
            }
        
        return {'raw_changes': obj.changes}


class UrlCacheSerializer(serializers.ModelSerializer):
    """
    Serializer for URL cache entries
    """
    cache_age = serializers.SerializerMethodField()
    
    class Meta:
        model = UrlCache
        fields = [
            "id",
            "url",
            "status",
            "error_message",
            "access_count",
            "cache_age",
            "expires_at",
            "last_accessed",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "url_hash"]

    def get_cache_age(self, obj):
        """Get cache age in hours"""
        from django.utils import timezone
        age = timezone.now() - obj.created_at
        return round(age.total_seconds() / 3600, 2)


class FeedbackApplicationSerializer(serializers.Serializer):
    """
    Serializer for feedback application
    """
    article_id = serializers.UUIDField()
    feedback = serializers.DictField()
    async_processing = serializers.BooleanField(default=True, source='async')

    def validate_feedback(self, value):
        """Validate feedback structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Feedback must be a dictionary")
        
        valid_sections = ['headline', 'details', 'participants', 'lots', 'organizations']
        
        for section, feedback_text in value.items():
            if section not in valid_sections:
                raise serializers.ValidationError(f"Invalid section '{section}'. Valid sections: {valid_sections}")
            
            if not isinstance(feedback_text, str):
                raise serializers.ValidationError(f"Feedback for '{section}' must be a string")
            
            if len(feedback_text.strip()) == 0:
                raise serializers.ValidationError(f"Feedback for '{section}' cannot be empty")
            
            if len(feedback_text) > 2000:
                raise serializers.ValidationError(f"Feedback for '{section}' is too long (max 2000 characters)")
        
        return value


class TaskStatusSerializer(serializers.Serializer):
    """
    Serializer for task status responses
    """
    task_id = serializers.CharField()
    status = serializers.ChoiceField(choices=['processing', 'completed', 'failed'])
    result = serializers.DictField(required=False)
    error = serializers.CharField(required=False)
    progress = serializers.IntegerField(required=False, min_value=0, max_value=100)


class ArticleStatsSerializer(serializers.Serializer):
    """
    Serializer for article statistics
    """
    total_articles = serializers.IntegerField()
    finalized_articles = serializers.IntegerField()
    pending_articles = serializers.IntegerField()
    total_requests = serializers.IntegerField()
    avg_generation_time = serializers.FloatField()
    avg_word_count = serializers.FloatField()
    cache_hit_rate = serializers.FloatField()
    recent_activity = serializers.DictField()


class BulkOperationSerializer(serializers.Serializer):
    """
    Serializer for bulk operations
    """
    article_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100
    )
    operation = serializers.ChoiceField(choices=['delete', 'finalize', 'export'])
    async_processing = serializers.BooleanField(default=True)

    def validate_article_ids(self, value):
        """Validate that all article IDs exist"""
        from .models import Article
        
        existing_ids = set(
            Article.objects.filter(id__in=value).values_list('id', flat=True)
        )
        
        missing_ids = set(value) - existing_ids
        if missing_ids:
            raise serializers.ValidationError(f"Articles not found: {list(missing_ids)}")
        
        return value