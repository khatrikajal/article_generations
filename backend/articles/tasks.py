import logging
import time
from datetime import timedelta
from typing import Tuple, Dict, Any

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction

from .models import ArticleRequest, Article, ArticleHistory, UrlCache
from data_pipeline.services.scraping import crawl_webpage
from data_pipeline.services.preprocessing import clean_text
from data_pipeline.services.chunking import recursive_chunk_text
from generation_pipeline.services.generation import build_graph, render_article
from generation_pipeline.services.validation import validate
from core.exceptions import ScrapingError, GenerationError
from core.cache import get_cached_article, set_cached_article

logger = logging.getLogger(__name__)


def _scrape_url_internal(url: str, instruction: str = "") -> Dict[str, Any]:
    """
    Internal function for URL scraping (not a Celery task)
    """
    try:
        logger.info(f"Starting scraping for URL: {url}")

        # Check cache first
        cached_entry = UrlCache.get_cached_content(url)
        if cached_entry and cached_entry.status == "success":
            logger.info(f"Using cached content for URL: {url}")
            return {
                'success': True,
                'url': url,
                'content': cached_entry.cleaned_text,
                'from_cache': True
            }

        # Scrape fresh content
        success, raw_content, scraped_url = crawl_webpage(
            url, max_crawl_pages=1, max_crawl_depth=1, dynamic_wait=1
        )

        if not success:
            logger.error(f"Scraping failed for {url}: {raw_content}")
            UrlCache.objects.update_or_create(
                url=url,
                defaults={
                    "cleaned_text": "",
                    "status": "failed",
                    "error_message": str(raw_content),
                    "expires_at": timezone.now() + timedelta(hours=1),
                },
            )
            return {"success": False, "url": url, "error": str(raw_content)}

        # Clean text
        content = clean_text(raw_content)
        if not content.strip():
            error_msg = "No meaningful content after cleaning"
            logger.error(f"{error_msg} for URL: {url}")
            UrlCache.objects.update_or_create(
                url=url,
                defaults={
                    "cleaned_text": "",
                    "status": "failed",
                    "error_message": error_msg,
                    "expires_at": timezone.now() + timedelta(hours=1),
                },
            )
            return {"success": False, "url": url, "error": error_msg}

        # Cache result
        UrlCache.objects.update_or_create(
            url=url,
            defaults={
                "cleaned_text": content,
                "status": "success",
                "error_message": None,
                "expires_at": timezone.now() + timedelta(hours=24),
            },
        )
        logger.info(f"Successfully scraped and cached URL: {url}")

        return {
            'success': True,
            'url': url,
            'content': content,
            'from_cache': False
        }

    except Exception as exc:
        logger.error(f"Exception in scraping for {url}: {str(exc)}")
        return {"success": False, "url": url, "error": str(exc)}


def _generate_article_internal(text_data: str, instruction: str = "") -> Dict[str, Any]:
    """
    Internal function for article generation (not a Celery task)
    """
    try:
        start_time = time.time()
        logger.info("Starting article generation")

        # Chunk text
        text_chunks = recursive_chunk_text(text_data, max_chunk_size=1500)

        # Build + run generation graph
        graph = build_graph()
        init_state = {
            "raw_text": text_data,
            "chunks": text_chunks,
            "sections": {},
            "validation": "",
            "user_feedback": {},
            "instruction": instruction or "",
        }

        result_state = graph.invoke(init_state)
        result_state = validate(result_state)
        final_article = render_article(result_state)

        generation_time = time.time() - start_time
        logger.info(f"Article generation completed in {generation_time:.2f} seconds")

        return {
            "success": True,
            "result_state": result_state,
            "final_article": final_article,
            "generation_time": generation_time,
        }

    except Exception as exc:
        logger.error(f"Exception in article generation: {str(exc)}")
        return {"success": False, "error": str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_url_task(self, url: str, instruction: str = "") -> Dict[str, Any]:
    """
    Celery task wrapper for URL scraping
    """
    try:
        return _scrape_url_internal(url, instruction)
    except Exception as exc:
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying scraping task for {url} (attempt {self.request.retries + 1})")
            raise self.retry(exc=exc)
        return {"success": False, "url": url, "error": str(exc)}


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_article_task(self, text_data: str, instruction: str = "") -> Dict[str, Any]:
    """
    Celery task wrapper for article generation
    """
    try:
        return _generate_article_internal(text_data, instruction)
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"success": False, "error": str(exc)}


@shared_task(bind=True)
def process_complete_article_generation(self, input_type: str, input_value: str, instruction: str = "", force_refresh: bool = False) -> Dict[str, Any]:
    """
    Complete article generation pipeline task
    """
    try:
        logger.info(f"Starting complete article generation: {input_type}")
        
        # Check cache first
        if not force_refresh:
            cached_request, cached_article = get_cached_article(input_type, input_value)
            if cached_article:
                return {
                    'success': True,
                    'from_cache': True,
                    'request_id': str(cached_request.id),
                    'article_id': str(cached_article.id),
                    'article_data': cached_article.get_cached()
                }

        # Process input based on type
        if input_type == "url":
            urls = input_value if isinstance(input_value, list) else [input_value]
            contents = []
            
            for url in urls:
                # Call the internal function directly
                scrape_result = _scrape_url_internal(url, instruction)
                
                if not scrape_result['success']:
                    return {
                        'success': False,
                        'error': f"Scraping failed for {url}: {scrape_result['error']}"
                    }
                
                contents.append({
                    'url': url,
                    'text': scrape_result['content']
                })
            
            combined_text = "\n\n".join([content['text'] for content in contents])
            raw_text_data = contents
            
        else:  # text input
            combined_text = str(input_value)
            raw_text_data = [{"url": "text_input", "text": combined_text}]

        # Call the internal generation function directly
        generation_result = _generate_article_internal(combined_text, instruction)
        
        if not generation_result['success']:
            return {
                'success': False,
                'error': f"Article generation failed: {generation_result['error']}"
            }

        # Save to DB
        with transaction.atomic():
            article_request = ArticleRequest.objects.create(
                input_request=input_type,
                instruction=instruction,
                raw_content=str(raw_text_data),
            )

            sections = generation_result['result_state'].get('sections', {})
            article = Article.objects.create(
                article_request=article_request,
                headline=sections.get('headline', ''),
                project_details=sections.get('details', ''),
                participants=sections.get('participants', ''),
                lots=sections.get('lots', ''),
                organizations=sections.get('organizations', ''),
                final_render=generation_result['final_article'],
                generation_time=generation_result['generation_time'],
                validation_status=generation_result['result_state'].get('validation', 'pending')
            )

            ArticleHistory.objects.create(
                article_request=article_request,
                article=article,
                changes=None,
                action_type='created'
            )

        set_cached_article(input_type, input_value, article_request, article)
        
        logger.info(f"Article generation completed successfully: {article.id}")
        
        return {
            'success': True,
            'from_cache': False,
            'request_id': str(article_request.id),
            'article_id': str(article.id),
            'article_data': article.get_cached(),
            'validation': generation_result['result_state'].get('validation', ''),
            'generation_time': generation_result['generation_time']
        }
        
    except Exception as exc:
        logger.error(f"Exception in complete article generation: {str(exc)}")
        return {
            'success': False,
            'error': str(exc)
        }

@shared_task
def apply_feedback_task(article_id: str, feedback: Dict[str, str]) -> Dict[str, Any]:
    """
    Background task to apply user feedback to article
    """
    try:
        logger.info(f"Applying feedback to article: {article_id}")
        
        from generation_pipeline.services.feedback import apply_user_feedback, render_with_feedback
        
        with transaction.atomic():
            article = Article.objects.select_related('article_request').get(id=article_id)
            
            # Build current state
            state = {
                "sections": {
                    "headline": article.headline,
                    "details": article.project_details,
                    "participants": article.participants,
                    "lots": article.lots,
                    "organizations": article.organizations,
                },
                "validation": "PASS",
                "user_feedback": {},
            }

            # Apply feedback
            updated_state = apply_user_feedback(state, feedback)

            # Update article fields
            sections = updated_state["sections"]
            article.headline = sections.get("headline", article.headline)
            article.project_details = sections.get("details", article.project_details)
            article.participants = sections.get("participants", article.participants)
            article.lots = sections.get("lots", article.lots)
            article.organizations = sections.get("organizations", article.organizations)

            # Regenerate final render
            article.final_render = render_with_feedback(updated_state)
            article.save()

            # Save history
            ArticleHistory.objects.create(
                article_request=article.article_request,
                article=article,
                changes=feedback,
                action_type='feedback_applied'
            )

        logger.info(f"Feedback applied successfully to article: {article_id}")
        
        return {
            'success': True,
            'article_id': str(article.id),
            'article_data': article.get_cached(),
            'feedback_applied': feedback
        }
        
    except Article.DoesNotExist:
        return {
            'success': False,
            'error': 'Article not found'
        }
    except Exception as exc:
        logger.error(f"Exception in feedback application: {str(exc)}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task
def cleanup_expired_cache():
    """
    Periodic task to cleanup expired URL cache entries
    """
    try:
        expired_count = UrlCache.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()[0]
        
        logger.info(f"Cleaned up {expired_count} expired cache entries")
        return {'success': True, 'cleaned_count': expired_count}
        
    except Exception as exc:
        logger.error(f"Exception in cache cleanup: {str(exc)}")
        return {'success': False, 'error': str(exc)}


@shared_task
def cleanup_old_articles():
    """
    Periodic task to cleanup old articles (older than 30 days)
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Only delete non-finalized articles older than 30 days
        old_articles = Article.objects.filter(
            created_at__lt=cutoff_date,
            is_final=False
        )
        
        deleted_count = old_articles.count()
        old_articles.delete()
        
        logger.info(f"Cleaned up {deleted_count} old articles")
        return {'success': True, 'cleaned_count': deleted_count}
        
    except Exception as exc:
        logger.error(f"Exception in article cleanup: {str(exc)}")
        return {'success': False, 'error': str(exc)}


@shared_task
def export_article_pdf_task(article_id: str) -> Dict[str, Any]:
    """
    Background task to generate PDF export
    """
    try:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.pagesizes import A4
        from io import BytesIO
        import base64
        
        logger.info(f"Generating PDF for article: {article_id}")
        
        article = Article.objects.select_related('article_request').get(id=article_id)
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        if article.headline:
            elements.append(Paragraph(article.headline, styles["Title"]))
            elements.append(Spacer(1, 12))

        section_map = {
            "Project Details": article.project_details,
            "Participants and Winners": article.participants,
            "Lots and Winners": article.lots,
            "Organizations Involved": article.organizations,
        }

        for title, content in section_map.items():
            if content:
                elements.append(Paragraph(title, styles["Heading2"]))
                for line in content.strip().split("\n"):
                    if line.strip():
                        elements.append(Paragraph(line.strip(), styles["BodyText"]))
                elements.append(Spacer(1, 6))
            elements.append(Spacer(1, 12))

        doc.build(elements)
        pdf_content = buffer.getvalue()
        buffer.close()
        
        # Encode PDF as base64 for JSON serialization
        pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
        
        logger.info(f"PDF generated successfully for article: {article_id}")
        
        return {
            'success': True,
            'pdf_base64': pdf_base64,
            'filename': f'article_{article.id}.pdf'
        }
        
    except Article.DoesNotExist:
        return {
            'success': False,
            'error': 'Article not found'
        }
    except Exception as exc:
        logger.error(f"Exception in PDF generation: {str(exc)}")
        return {
            'success': False,
            'error': str(exc)
        }