from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

@require_http_methods(["GET"])
@csrf_exempt
def api_root(request):
    """API root endpoint with available endpoints"""
    return JsonResponse({
        "message": "Article Generation API",
        "version": "1.0",
        "endpoints": {
            "admin": "/admin/",
            "articles": {
                "generate": "/api/generate/",
                "list": "/api/articles/",
                "detail": "/api/articles/{id}/",
                "feedback": "/api/feedback/",
                "history": "/api/history/",
                "health": "/api/health/",
                "export": "/api/articles/{id}/export-pdf/"
            },
            "tasks": "/api/tasks/{task_id}/status/",
            "documentation": "/api/docs/" if settings.DEBUG else None
        },
        "status": "active",
        "timestamp": "2025-09-02T00:00:00Z"
    })

@require_http_methods(["GET"])
@csrf_exempt  
def health_check(request):
    """Dedicated health check endpoint"""
    return JsonResponse({
        "status": "healthy",
        "service": "article-generation-api",
        "timestamp": "2025-09-02T00:00:00Z"
    })

urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),
    
    # API root
    path('api/', api_root, name='api-root'),
    
    # Articles API - this includes all your article endpoints
    path('api/', include('articles.urls')),
    
    # Dedicated health check for load balancers
    path('health/', health_check, name='health-check'),
    
    # Alternative health endpoint
    path('', health_check, name='root-health'),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error handlers
handler400 = 'articles.views.custom_bad_request'
handler403 = 'articles.views.custom_permission_denied'
handler404 = 'articles.views.custom_page_not_found'
handler500 = 'articles.views.custom_server_error'