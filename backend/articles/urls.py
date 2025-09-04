# 

from django.urls import path
from .views import (
    GenerateArticleView,
    TaskStatusView,
    ApplyFeedbackView,
    ArticleHistoryListView,
    ArticleListView,
    ArticleDetailView,
    FinalizeArticleView,
    ExportArticlePDFView,
    HealthCheckView,
)

app_name = 'articles'

urlpatterns = [
    # Article generation - POST to generate new articles
    path("generate/", GenerateArticleView.as_view(), name="generate-article"),
    
    # Task management - GET to check task status
    path("tasks/<str:task_id>/status/", TaskStatusView.as_view(), name="task-status"),
    
    # Feedback - POST to apply feedback to existing article
    path("feedback/", ApplyFeedbackView.as_view(), name="apply-feedback"),
    
    # Article management
    path("articles/", ArticleListView.as_view(), name="article-list"),  # GET - list articles
    path("articles/<uuid:id>/", ArticleDetailView.as_view(), name="article-detail"),  # GET - get article, DELETE - delete article
    path("articles/<uuid:id>/finalize/", FinalizeArticleView.as_view(), name="finalize-article"),  # POST - finalize article
    path("articles/<uuid:article_id>/export-pdf/", ExportArticlePDFView.as_view(), name="export-pdf"),  # GET - export as PDF
    
    # History - GET to view article history
    path("history/", ArticleHistoryListView.as_view(), name="article-history"),
    
    # Health check - GET for system health
    path("health/", HealthCheckView.as_view(), name="health-check"),
]