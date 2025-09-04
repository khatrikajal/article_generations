import logging
from django.http import HttpResponse, JsonResponse
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from celery.result import AsyncResult
import base64
from django.utils import timezone
from .models import Article, ArticleHistory, ArticleRequest
from .serializers import ArticleHistorySerializer, ArticleSerializer, ArticleRequestSerializer
from .tasks import (
    process_complete_article_generation,
    apply_feedback_task,
    export_article_pdf_task
)
from core.exceptions import ValidationError, TaskError
from core.utils import get_client_ip

logger = logging.getLogger(__name__)


class StandardResultPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class GenerateArticleView(APIView):
    """
    Generate article with background task processing
    """
    
    def post(self, request, *args, **kwargs):
        try:
            # Validate input
            input_type = request.data.get("input_type")
            input_value = request.data.get("input_value")
            instruction = request.data.get("instruction", "")
            force_refresh = request.data.get("force_refresh", False)
            async_processing = request.data.get("async", True)  # Default to async

            if input_type not in ["url", "text"]:
                return Response({
                    "message": "Invalid input_type. Must be 'url' or 'text'",
                    "success": False,
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)

            if not input_value:
                return Response({
                    "message": "input_value is required",
                    "success": False,
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)

            # Log the request
            client_ip = get_client_ip(request)
            logger.info(f"Article generation request from {client_ip}: {input_type}")

            if async_processing:
                # Start background task
                task = process_complete_article_generation.delay(
                    input_type, input_value, instruction, force_refresh
                )
                
                return Response({
                    "message": "Article generation started",
                    "success": True,
                    "data": {
                        "task_id": task.id,
                        "status": "processing",
                        "async": True
                    }
                }, status=status.HTTP_202_ACCEPTED)
            
            else:
                # Synchronous processing (for testing or immediate results)
                result = process_complete_article_generation(
                    input_type, input_value, instruction, force_refresh
                )
                
                if result['success']:
                    return Response({
                        "message": "Article generated successfully",
                        "success": True,
                        "data": {
                            "request_id": result['request_id'],
                            "article_id": result['article_id'],
                            "article": result['article_data'],
                            "validation": result.get('validation', ''),
                            "from_cache": result.get('from_cache', False),
                            "generation_time": result.get('generation_time', 0),
                            "async": False
                        }
                    }, status=status.HTTP_201_CREATED)
                else:
                    return Response({
                        "message": result['error'],
                        "success": False,
                        "data": None
                    }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        except Exception as e:
            logger.error(f"Exception in GenerateArticleView: {str(e)}")
            return Response({
                "message": f"Internal server error: {str(e)}",
                "success": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TaskStatusView(APIView):
    """
    Check the status of background tasks
    """
    
    def get(self, request, task_id, *args, **kwargs):
        try:
            task_result = AsyncResult(task_id)
            
            if task_result.ready():
                if task_result.successful():
                    result = task_result.result
                    if result.get('success'):
                        return Response({
                            "message": "Task completed successfully",
                            "success": True,
                            "data": {
                                "task_id": task_id,
                                "status": "completed",
                                "result": result
                            }
                        }, status=status.HTTP_200_OK)
                    else:
                        return Response({
                            "message": "Task completed with errors",
                            "success": False,
                            "data": {
                                "task_id": task_id,
                                "status": "failed",
                                "error": result.get('error', 'Unknown error')
                            }
                        }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        "message": "Task failed",
                        "success": False,
                        "data": {
                            "task_id": task_id,
                            "status": "failed",
                            "error": str(task_result.result)
                        }
                    }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "message": "Task is still processing",
                    "success": True,
                    "data": {
                        "task_id": task_id,
                        "status": "processing"
                    }
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Exception in TaskStatusView: {str(e)}")
            return Response({
                "message": f"Error checking task status: {str(e)}",
                "success": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ApplyFeedbackView(APIView):
    """
    Apply user feedback to article with background processing
    """
    
    def post(self, request, *args, **kwargs):
        try:
            article_id = request.data.get("article_id")
            feedback = request.data.get("feedback", {})
            async_processing = request.data.get("async", True)

            if not article_id or not feedback:
                return Response({
                    "message": "article_id and feedback are required",
                    "success": False,
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate feedback structure
            if not isinstance(feedback, dict):
                return Response({
                    "message": "feedback must be a dictionary",
                    "success": False,
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check if article exists
            try:
                Article.objects.get(id=article_id)
            except Article.DoesNotExist:
                return Response({
                    "message": "Article not found",
                    "success": False,
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)

            logger.info(f"Applying feedback to article: {article_id}")

            if async_processing:
                # Start background task
                task = apply_feedback_task.delay(article_id, feedback)
                
                return Response({
                    "message": "Feedback application started",
                    "success": True,
                    "data": {
                        "task_id": task.id,
                        "status": "processing",
                        "async": True
                    }
                }, status=status.HTTP_202_ACCEPTED)
            
            else:
                # Synchronous processing
                result = apply_feedback_task(article_id, feedback)
                
                if result['success']:
                    return Response({
                        "message": "Feedback applied successfully",
                        "success": True,
                        "data": {
                            "article_id": result['article_id'],
                            "article": result['article_data'],
                            "feedback_applied": result['feedback_applied'],
                            "async": False
                        }
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        "message": result['error'],
                        "success": False,
                        "data": None
                    }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        except Exception as e:
            logger.error(f"Exception in ApplyFeedbackView: {str(e)}")
            return Response({
                "message": f"Internal server error: {str(e)}",
                "success": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ArticleHistoryListView(APIView):
    """
    Get article history with optimized queries
    """
    pagination_class = StandardResultPagination
    
    def get(self, request, *args, **kwargs):
        try:
            request_id = request.query_params.get("request_id")
            article_id = request.query_params.get("article_id")
            action_type = request.query_params.get("action_type")

            # Start with optimized queryset
            queryset = ArticleHistory.objects.select_related(
                'article_request', 'article'
            ).prefetch_related('article__history')

            # Apply filters
            if request_id:
                queryset = queryset.filter(article_request_id=request_id)
            if article_id:
                queryset = queryset.filter(article_id=article_id)
            if action_type:
                queryset = queryset.filter(action_type=action_type)

            # Check cache for common queries
            cache_key = f"article_history_{request_id}_{article_id}_{action_type}"
            cached_data = cache.get(cache_key)
            
            if cached_data:
                return Response({
                    "message": "Article history fetched successfully (cached)",
                    "success": True,
                    "data": cached_data
                }, status=status.HTTP_200_OK)

            # Paginate results
            paginator = self.pagination_class()
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            
            serializer = ArticleHistorySerializer(paginated_queryset, many=True)
            
            # Cache the results
            cache.set(cache_key, serializer.data, timeout=1800)  # 30 minutes
            
            return paginator.get_paginated_response({
                "message": "Article history fetched successfully",
                "success": True,
                "data": serializer.data
            })

        except Exception as e:
            logger.error(f"Exception in ArticleHistoryListView: {str(e)}")
            return Response({
                "message": f"Internal server error: {str(e)}",
                "success": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ArticleListView(APIView):
    """
    List articles with filtering and pagination
    """
    pagination_class = StandardResultPagination
    
    def get(self, request, *args, **kwargs):
        try:
            # Query parameters
            is_final = request.query_params.get("is_final")
            request_id = request.query_params.get("request_id")
            search = request.query_params.get("search")
            
            # Optimized queryset
            queryset = Article.objects.with_full_relations()
            
            # Apply filters
            if is_final is not None:
                queryset = queryset.filter(is_final=is_final.lower() == 'true')
            if request_id:
                queryset = queryset.filter(article_request_id=request_id)
            if search:
                queryset = queryset.filter(headline__icontains=search)
            
            # Paginate
            paginator = self.pagination_class()
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            
            serializer = ArticleSerializer(paginated_queryset, many=True)
            
            return paginator.get_paginated_response({
                "message": "Articles fetched successfully",
                "success": True,
                "data": serializer.data
            })
            
        except Exception as e:
            logger.error(f"Exception in ArticleListView: {str(e)}")
            return Response({
                "message": f"Internal server error: {str(e)}",
                "success": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ArticleDetailView(APIView):
    """
    Get, update, or delete a specific article
    """
    
    def get(self, request, id, *args, **kwargs):
        try:
            # Check cache first
            cached_article = cache.get(f"article_detail_{id}")
            if cached_article:
                return Response({
                    "message": "Article fetched successfully (cached)",
                    "success": True,
                    "data": cached_article
                }, status=status.HTTP_200_OK)
            
            # Fetch from database with optimized query
            article = Article.objects.select_related(
                'article_request'
            ).prefetch_related('history').get(id=id)
            
            serializer = ArticleSerializer(article)
            
            # Cache the result
            cache.set(f"article_detail_{id}", serializer.data, timeout=1800)
            
            return Response({
                "message": "Article fetched successfully",
                "success": True,
                "data": serializer.data
            }, status=status.HTTP_200_OK)
            
        except Article.DoesNotExist:
            return Response({
                "message": "Article not found",
                "success": False,
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Exception in ArticleDetailView.get: {str(e)}")
            return Response({
                "message": f"Internal server error: {str(e)}",
                "success": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, id, *args, **kwargs):
        try:
            with transaction.atomic():
                article = Article.objects.select_related('article_request').get(id=id)
                article_request = article.article_request
                
                # Delete the article (this will cascade to history)
                article.delete()
                
                # Clear related caches
                cache.delete(f"article_detail_{id}")
                cache.delete(f"article_{id}")
                
                logger.info(f"Article deleted: {id}")
                
                return Response({
                    "message": f"Article {id} deleted successfully",
                    "success": True,
                    "data": None
                }, status=status.HTTP_200_OK)
                
        except Article.DoesNotExist:
            return Response({
                "message": "Article not found",
                "success": False,
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Exception in ArticleDetailView.delete: {str(e)}")
            return Response({
                "message": f"Internal server error: {str(e)}",
                "success": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FinalizeArticleView(APIView):
    """
    Finalize an article
    """
    
    def post(self, request, id, *args, **kwargs):
        try:
            with transaction.atomic():
                article = Article.objects.select_related('article_request').get(id=id)
                
                if article.is_final:
                    return Response({
                        "message": "Article is already finalized",
                        "success": True,
                        "data": {"article_id": str(article.id)}
                    }, status=status.HTTP_200_OK)

                article.is_final = True
                article.save(update_fields=["is_final", "updated_at"])

                ArticleHistory.objects.create(
                    article_request=article.article_request,
                    article=article,
                    changes={"finalized": True},
                    action_type='finalized'
                )
                
                # Clear caches
                cache.delete(f"article_detail_{id}")
                cache.delete(f"article_{id}")
                
                logger.info(f"Article finalized: {id}")

                return Response({
                    "message": "Article finalized successfully",
                    "success": True,
                    "data": {"article_id": str(article.id)}
                }, status=status.HTTP_200_OK)
                
        except Article.DoesNotExist:
            return Response({
                "message": "Article not found",
                "success": False,
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Exception in FinalizeArticleView: {str(e)}")
            return Response({
                "message": f"Internal server error: {str(e)}",
                "success": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExportArticlePDFView(APIView):
    """
    Export article as PDF with background processing
    """
    
    def get(self, request, article_id, *args, **kwargs):
        try:
            async_processing = request.query_params.get("async", "true").lower() == "true"
            
            # Check if article exists
            try:
                Article.objects.get(id=article_id)
            except Article.DoesNotExist:
                return Response({
                    "message": "Article not found",
                    "success": False,
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)

            if async_processing:
                # Start background task
                task = export_article_pdf_task.delay(article_id)
                
                return Response({
                    "message": "PDF generation started",
                    "success": True,
                    "data": {
                        "task_id": task.id,
                        "status": "processing",
                        "async": True
                    }
                }, status=status.HTTP_202_ACCEPTED)
            
            else:
                # Synchronous processing
                result = export_article_pdf_task(article_id)
                
                if result['success']:
                    # Decode base64 and return as HTTP response
                    pdf_content = base64.b64decode(result['pdf_base64'])
                    
                    response = HttpResponse(pdf_content, content_type="application/pdf")
                    response["Content-Disposition"] = f'attachment; filename="{result["filename"]}"'
                    return response
                else:
                    return Response({
                        "message": result['error'],
                        "success": False,
                        "data": None
                    }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        except Exception as e:
            logger.error(f"Exception in ExportArticlePDFView: {str(e)}")
            return Response({
                "message": f"Internal server error: {str(e)}",
                "success": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HealthCheckView(APIView):
    """
    Health check endpoint
    """
    
    def get(self, request, *args, **kwargs):
        try:
            # Check database
            Article.objects.first()
            
            # Check cache
            cache.set("health_check", "ok", timeout=60)
            cached_value = cache.get("health_check")
            
            # Check Celery
            from celery import current_app
            inspect = current_app.control.inspect()
            stats = inspect.stats()
            
            return Response({
                "message": "System is healthy",
                "success": True,
                "data": {
                    "database": "ok",
                    "cache": "ok" if cached_value == "ok" else "error",
                    "celery": "ok" if stats else "error",
                    "timestamp": timezone.now().isoformat()
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return Response({
                "message": "System health check failed",
                "success": False,
                "data": {"error": str(e)}
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        

@csrf_exempt
def custom_bad_request(request, exception=None):
    """Custom 400 error handler"""
    logger.warning(f"Bad request from {get_client_ip(request)}: {exception}")
    return JsonResponse({
        'error': 'Bad Request',
        'message': 'The request could not be understood by the server.',
        'status_code': 400,
        'timestamp': timezone.now().isoformat()
    }, status=400)

@csrf_exempt
def custom_permission_denied(request, exception=None):
    """Custom 403 error handler"""
    logger.warning(f"Permission denied for {get_client_ip(request)}: {exception}")
    return JsonResponse({
        'error': 'Forbidden',
        'message': 'You do not have permission to access this resource.',
        'status_code': 403,
        'timestamp': timezone.now().isoformat()
    }, status=403)

@csrf_exempt
def custom_page_not_found(request, exception=None):
    """Custom 404 error handler"""
    logger.info(f"Page not found for {get_client_ip(request)}: {request.path}")
    return JsonResponse({
        'error': 'Not Found',
        'message': 'The requested resource was not found.',
        'status_code': 404,
        'timestamp': timezone.now().isoformat(),
        'path': request.path
    }, status=404)

@csrf_exempt
def custom_server_error(request):
    """Custom 500 error handler"""
    logger.error(f"Server error for {get_client_ip(request)}: {request.path}")
    return JsonResponse({
        'error': 'Internal Server Error',
        'message': 'The server encountered an unexpected condition.',
        'status_code': 500,
        'timestamp': timezone.now().isoformat()
    }, status=500)