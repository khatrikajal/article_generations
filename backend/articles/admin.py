from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import ArticleRequest, Article, ArticleHistory, UrlCache


@admin.register(ArticleRequest)
class ArticleRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'input_request', 'instruction_preview', 
        'article_count', 'created_at', 'updated_at'
    ]
    list_filter = ['input_request', 'created_at']
    search_fields = ['id', 'instruction', 'raw_content']
    readonly_fields = ['id', 'content_hash', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    def instruction_preview(self, obj):
        if obj.instruction:
            return obj.instruction[:100] + '...' if len(obj.instruction) > 100 else obj.instruction
        return '-'
    instruction_preview.short_description = 'Instruction Preview'
    
    def article_count(self, obj):
        count = obj.articles.count()
        if count > 0:
            url = reverse('admin:articles_article_changelist') + f'?article_request__id__exact={obj.id}'
            return format_html('<a href="{}">{} articles</a>', url, count)
        return '0 articles'
    article_count.short_description = 'Articles'


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'headline_preview', 'article_request_link', 
        'is_final', 'validation_status', 'word_count', 
        'generation_time_display', 'created_at'
    ]
    list_filter = [
        'is_final', 'validation_status', 'created_at',
        'article_request__input_request'
    ]
    search_fields = ['headline', 'project_details', 'participants']
    readonly_fields = [
        'id', 'word_count', 'generation_time', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'article_request', 'is_final', 'validation_status')
        }),
        ('Content', {
            'fields': ('headline', 'project_details', 'participants', 'lots', 'organizations')
        }),
        ('Rendered Output', {
            'fields': ('final_render',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('word_count', 'generation_time', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def headline_preview(self, obj):
        return obj.headline[:80] + '...' if len(obj.headline) > 80 else obj.headline
    headline_preview.short_description = 'Headline'
    
    def article_request_link(self, obj):
        url = reverse('admin:articles_articlerequest_change', args=[obj.article_request.id])
        return format_html('<a href="{}">{}</a>', url, str(obj.article_request.id)[:8])
    article_request_link.short_description = 'Request'
    
    def generation_time_display(self, obj):
        if obj.generation_time:
            return f"{obj.generation_time:.2f}s"
        return '-'
    generation_time_display.short_description = 'Gen Time'
    
    actions = ['mark_as_final', 'mark_as_draft', 'regenerate_render']
    
    def mark_as_final(self, request, queryset):
        updated = queryset.update(is_final=True)
        self.message_user(request, f'{updated} articles marked as final.')
    mark_as_final.short_description = 'Mark selected articles as final'
    
    def mark_as_draft(self, request, queryset):
        updated = queryset.update(is_final=False)
        self.message_user(request, f'{updated} articles marked as draft.')
    mark_as_draft.short_description = 'Mark selected articles as draft'


@admin.register(ArticleHistory)
class ArticleHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'article_link', 'action_type', 'changes_summary', 
        'user_id', 'created_at'
    ]
    list_filter = ['action_type', 'created_at']
    search_fields = ['article__headline', 'user_id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    def article_link(self, obj):
        url = reverse('admin:articles_article_change', args=[obj.article.id])
        return format_html('<a href="{}">{}</a>', url, obj.article.headline[:50])
    article_link.short_description = 'Article'
    
    def changes_summary(self, obj):
        if obj.changes:
            if isinstance(obj.changes, dict):
                return ', '.join(obj.changes.keys())
            return str(obj.changes)[:100]
        return '-'
    changes_summary.short_description = 'Changes'


@admin.register(UrlCache)
class UrlCacheAdmin(admin.ModelAdmin):
    list_display = [
        'url_preview', 'status', 'content_length', 
        'access_count', 'cache_age', 'expires_at'
    ]
    list_filter = ['status', 'created_at', 'expires_at']
    search_fields = ['url', 'error_message']
    readonly_fields = [
        'id', 'url_hash', 'access_count', 'last_accessed', 
        'created_at', 'updated_at'
    ]
    ordering = ['-created_at']
    
    def url_preview(self, obj):
        return obj.url[:80] + '...' if len(obj.url) > 80 else obj.url
    url_preview.short_description = 'URL'
    
    def content_length(self, obj):
        if obj.cleaned_text:
            length = len(obj.cleaned_text)
            if length > 1000:
                return f"{length:,} chars"
            return f"{length} chars"
        return "0 chars"
    content_length.short_description = 'Content Size'
    
    def cache_age(self, obj):
        age = timezone.now() - obj.created_at
        hours = age.total_seconds() / 3600
        if hours < 1:
            return f"{int(age.total_seconds() / 60)}min"
        elif hours < 24:
            return f"{hours:.1f}h"
        else:
            return f"{hours / 24:.1f}d"
    cache_age.short_description = 'Age'
    
    actions = ['clear_expired_cache', 'refresh_cache']
    
    def clear_expired_cache(self, request, queryset):
        expired = queryset.filter(expires_at__lt=timezone.now())
        count = expired.count()
        expired.delete()
        self.message_user(request, f'Cleared {count} expired cache entries.')
    clear_expired_cache.short_description = 'Clear expired cache entries'


# Admin site customization
admin.site.site_header = "Article Generation System"
admin.site.site_title = "Article Gen Admin"
admin.site.index_title = "Administration Dashboard"