import os
import requests
import logging
from typing import Tuple, Dict, Any, Optional
from urllib.parse import urlparse, urljoin
from core.exceptions import ScrapingError
from core.utils import retry_decorator, timing_decorator

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_TIMEOUT = 60
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

@retry_decorator(max_retries=2, delay=2.0)
@timing_decorator
def crawl_webpage(
    scrap_url: str,
    max_crawl_pages: Optional[int] = None,
    max_crawl_depth: Optional[int] = None,
    dynamic_wait: Optional[int] = None,
) -> Tuple[bool, str, str]:
    """
    Enhanced webpage crawling with multiple fallback methods
    Returns: (success, content_or_error_message, url)
    """
    try:
        # Validate URL
        if not _is_valid_url(scrap_url):
            raise ScrapingError("Invalid URL format", url=scrap_url)
        
        logger.info(f"Starting crawl for URL: {scrap_url}")
        
        # Try Firecrawl first (if available)
        firecrawl_result = _crawl_with_firecrawl(scrap_url, max_crawl_pages, max_crawl_depth, dynamic_wait)
        if firecrawl_result[0]:
            return firecrawl_result
        
        logger.warning(f"Firecrawl failed for {scrap_url}, trying direct scraping")
        
        # Fallback to direct scraping
        direct_result = _crawl_direct(scrap_url)
        if direct_result[0]:
            return direct_result
        
        # If both methods fail, return the more informative error
        firecrawl_error = firecrawl_result[1]
        direct_error = direct_result[1]
        
        combined_error = f"All scraping methods failed. Firecrawl: {firecrawl_error}; Direct: {direct_error}"
        return False, combined_error, scrap_url
        
    except Exception as e:
        logger.error(f"Unexpected error during crawling: {str(e)}")
        return False, f"Unexpected crawling error: {str(e)}", scrap_url


def _crawl_with_firecrawl(
    scrap_url: str,
    max_crawl_pages: Optional[int],
    max_crawl_depth: Optional[int],
    dynamic_wait: Optional[int]
) -> Tuple[bool, str, str]:
    """
    Crawl using Firecrawl API service
    """
    try:
        CRAWLER_API_URL = "https://api.firecrawl.dev/v0/scrape"
        FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

        if not FIRECRAWL_API_KEY:
            return False, "Firecrawl API key not configured", scrap_url

        headers = {
            "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        wait_time = int(dynamic_wait) if dynamic_wait is not None else 1

        payload: Dict[str, Any] = {
            "url": scrap_url,
            "crawlerOptions": {
                "maxPages": int(max_crawl_pages or 10),
                "maxDepth": int(max_crawl_depth or 2),
                "waitBetweenRequests": wait_time * 1000,
                "onlyMainContent": True,
                "includeSelectors": [".ecl-u-type-long", "article", "main", ".content"],
                "render": True,
            },
        }

        logger.debug(f"Sending Firecrawl request with payload: {payload}")

        resp = requests.post(
            CRAWLER_API_URL, 
            json=payload, 
            headers=headers, 
            timeout=DEFAULT_TIMEOUT
        )

        if resp.status_code != 200:
            error_msg = f"Firecrawl API error (HTTP {resp.status_code})"
            if resp.text:
                error_msg += f": {resp.text[:500]}"
            return False, error_msg, scrap_url

        # Check content type
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" not in content_type.lower():
            return False, f"Unexpected content type from Firecrawl: {content_type}", scrap_url

        try:
            data = resp.json()
        except ValueError as e:
            return False, f"Invalid JSON response from Firecrawl: {str(e)}", scrap_url

        # Check response structure
        if not isinstance(data, dict):
            return False, "Invalid response format from Firecrawl", scrap_url

        if data.get("success") and isinstance(data.get("data"), dict):
            extracted_text = data["data"].get("content", "")
            
            if not extracted_text or not extracted_text.strip():
                return False, "No meaningful content extracted by Firecrawl", scrap_url
            
            logger.info(f"Successfully extracted {len(extracted_text)} characters with Firecrawl")
            return True, extracted_text, scrap_url

        error_message = data.get("error", "Unknown Firecrawl error")
        return False, f"Firecrawl extraction failed: {error_message}", scrap_url

    except requests.exceptions.Timeout:
        return False, "Firecrawl request timeout", scrap_url
    except requests.exceptions.ConnectionError:
        return False, "Connection error with Firecrawl service", scrap_url
    except requests.exceptions.RequestException as e:
        return False, f"Firecrawl request failed: {str(e)}", scrap_url
    except Exception as e:
        return False, f"Unexpected Firecrawl error: {str(e)}", scrap_url


def _crawl_direct(scrap_url: str) -> Tuple[bool, str, str]:
    """
    Direct webpage scraping as fallback method
    """
    try:
        logger.info(f"Attempting direct scraping for: {scrap_url}")
        
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        # Make request with streaming to check content length
        with requests.get(
            scrap_url, 
            headers=headers, 
            timeout=DEFAULT_TIMEOUT, 
            stream=True,
            allow_redirects=True
        ) as response:
            
            # Check status code
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}: {response.reason}", scrap_url
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if not any(ct in content_type for ct in ['text/html', 'application/xhtml']):
                return False, f"Unsupported content type: {content_type}", scrap_url
            
            # Check content length
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > MAX_CONTENT_LENGTH:
                return False, f"Content too large: {content_length} bytes", scrap_url
            
            # Read content
            content = response.content
            
            # Check actual content size
            if len(content) > MAX_CONTENT_LENGTH:
                return False, f"Content too large: {len(content)} bytes", scrap_url
            
            # Decode content
            try:
                # Try to get encoding from response
                encoding = response.encoding or 'utf-8'
                text_content = content.decode(encoding)
            except UnicodeDecodeError:
                # Fallback to utf-8 with error handling
                text_content = content.decode('utf-8', errors='ignore')
            
            # Extract text content using simple HTML parsing
            extracted_text = _extract_text_from_html(text_content)
            
            if not extracted_text or len(extracted_text.strip()) < 50:
                return False, "Insufficient content extracted from webpage", scrap_url
            
            logger.info(f"Successfully extracted {len(extracted_text)} characters with direct scraping")
            return True, extracted_text, scrap_url

    except requests.exceptions.Timeout:
        return False, "Request timeout during direct scraping", scrap_url
    except requests.exceptions.ConnectionError:
        return False, "Connection error during direct scraping", scrap_url
    except requests.exceptions.TooManyRedirects:
        return False, "Too many redirects", scrap_url
    except requests.exceptions.RequestException as e:
        return False, f"Request failed during direct scraping: {str(e)}", scrap_url
    except Exception as e:
        return False, f"Unexpected error during direct scraping: {str(e)}", scrap_url


def _extract_text_from_html(html_content: str) -> str:
    """
    Extract text content from HTML using BeautifulSoup or simple regex
    """
    try:
        # Try BeautifulSoup first (if available)
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "meta", "link"]):
                script.decompose()
            
            # Get text from main content areas
            main_content = (
                soup.find('main') or 
                soup.find('article') or 
                soup.find('div', class_=lambda x: x and 'content' in x.lower()) or
                soup.find('div', id=lambda x: x and 'content' in x.lower()) or
                soup.body or 
                soup
            )
            
            if main_content:
                text = main_content.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)
            
            return text
            
        except ImportError:
            # Fallback to regex-based extraction
            logger.warning("BeautifulSoup not available, using regex extraction")
            return _extract_text_with_regex(html_content)
            
    except Exception as e:
        logger.error(f"HTML text extraction failed: {str(e)}")
        return _extract_text_with_regex(html_content)


def _extract_text_with_regex(html_content: str) -> str:
    """
    Simple regex-based HTML text extraction as fallback
    """
    import re
    
    try:
        # Remove scripts and styles
        html_content = re.sub(r'<script[^>]*>.*?</script>', ' ', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<style[^>]*>.*?</style>', ' ', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove all HTML tags
        html_content = re.sub(r'<[^>]+>', ' ', html_content)
        
        # Decode HTML entities
        html_content = html_content.replace('&nbsp;', ' ')
        html_content = html_content.replace('&amp;', '&')
        html_content = html_content.replace('&lt;', '<')
        html_content = html_content.replace('&gt;', '>')
        html_content = html_content.replace('&quot;', '"')
        html_content = html_content.replace('&#39;', "'")
        
        # Clean up whitespace
        html_content = re.sub(r'\s+', ' ', html_content)
        
        return html_content.strip()
        
    except Exception as e:
        logger.error(f"Regex text extraction failed: {str(e)}")
        return html_content  # Return as-is if all else fails


def _is_valid_url(url: str) -> bool:
    """
    Validate URL format
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def get_scraping_health() -> Dict[str, Any]:
    """
    Check scraping service health
    """
    health_info = {
        'firecrawl_available': bool(os.getenv("FIRECRAWL_API_KEY")),
        'direct_scraping_available': True,
        'test_results': {}
    }
    
    # Test Firecrawl if available
    if health_info['firecrawl_available']:
        try:
            test_url = "https://httpbin.org/html"
            success, message, _ = _crawl_with_firecrawl(test_url, 1, 1, 1)
            health_info['test_results']['firecrawl'] = {
                'status': 'healthy' if success else 'unhealthy',
                'message': message[:100] if not success else 'OK'
            }
        except Exception as e:
            health_info['test_results']['firecrawl'] = {
                'status': 'unhealthy',
                'message': str(e)[:100]
            }
    
    # Test direct scraping
    try:
        test_url = "https://httpbin.org/html"
        success, message, _ = _crawl_direct(test_url)
        health_info['test_results']['direct_scraping'] = {
            'status': 'healthy' if success else 'unhealthy',
            'message': message[:100] if not success else 'OK'
        }
    except Exception as e:
        health_info['test_results']['direct_scraping'] = {
            'status': 'unhealthy',
            'message': str(e)[:100]
        }
    
    # Overall health
    health_info['overall_status'] = (
        'healthy' if any(
            test.get('status') == 'healthy' 
            for test in health_info['test_results'].values()
        ) else 'unhealthy'
    )
    
    return health_info


def estimate_scraping_time(url: str) -> Dict[str, Any]:
    """
    Estimate scraping time based on URL and previous performance
    """
    try:
        domain = urlparse(url).netloc.lower()
        
        # Base estimates (in seconds)
        base_estimates = {
            'firecrawl': 15,
            'direct': 5
        }
        
        # Domain-specific adjustments
        slow_domains = ['europa.eu', 'gov.uk', 'government.ca']
        fast_domains = ['github.com', 'stackoverflow.com']
        
        multiplier = 1.0
        if any(slow_domain in domain for slow_domain in slow_domains):
            multiplier = 2.0
        elif any(fast_domain in domain for fast_domain in fast_domains):
            multiplier = 0.5
        
        estimates = {
            method: int(time * multiplier) 
            for method, time in base_estimates.items()
        }
        
        return {
            'estimates_seconds': estimates,
            'recommended_timeout': max(estimates.values()) + 30,
            'domain_category': (
                'slow' if multiplier > 1.5 else 
                'fast' if multiplier < 0.8 else 
                'normal'
            )
        }
        
    except Exception as e:
        logger.error(f"Failed to estimate scraping time: {str(e)}")
        return {
            'estimates_seconds': {'firecrawl': 30, 'direct': 15},
            'recommended_timeout': 60,
            'domain_category': 'unknown'
        }


def batch_scrape_urls(urls: list, max_concurrent: int = 3) -> Dict[str, Any]:
    """
    Scrape multiple URLs with controlled concurrency
    """
    import concurrent.futures
    import time
    
    results = {
        'successful': [],
        'failed': [],
        'stats': {
            'total_urls': len(urls),
            'success_rate': 0,
            'total_time': 0
        }
    }
    
    start_time = time.time()
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            # Submit all scraping tasks
            future_to_url = {
                executor.submit(crawl_webpage, url): url 
                for url in urls
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    success, content, scraped_url = future.result(timeout=90)
                    
                    if success:
                        results['successful'].append({
                            'url': url,
                            'content_length': len(content),
                            'scraped_url': scraped_url
                        })
                    else:
                        results['failed'].append({
                            'url': url,
                            'error': content,
                            'scraped_url': scraped_url
                        })
                        
                except Exception as e:
                    results['failed'].append({
                        'url': url,
                        'error': str(e),
                        'scraped_url': url
                    })
        
        # Calculate stats
        total_time = time.time() - start_time
        success_count = len(results['successful'])
        
        results['stats'].update({
            'success_count': success_count,
            'failure_count': len(results['failed']),
            'success_rate': (success_count / len(urls)) * 100,
            'total_time': total_time,
            'average_time_per_url': total_time / len(urls)
        })
        
        logger.info(f"Batch scraping completed: {success_count}/{len(urls)} successful in {total_time:.2f}s")
        
        return results
        
    except Exception as e:
        logger.error(f"Batch scraping failed: {str(e)}")
        results['stats']['error'] = str(e)
        return results