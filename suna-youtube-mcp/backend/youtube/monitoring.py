"""
Monitoring and Error Tracking for YouTube MCP
Using Sentry SDK following Suna's tech stack
"""

import os
import logging
from typing import Any, Dict, Optional
from functools import wraps
import time

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from prometheus_client import Counter, Histogram, Gauge
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Initialize Sentry
def init_sentry():
    """Initialize Sentry error tracking"""
    
    sentry_dsn = os.getenv("SENTRY_DSN")
    if not sentry_dsn:
        logger.warning("Sentry DSN not configured, error tracking disabled")
        return
    
    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=os.getenv("ENVIRONMENT", "development"),
        integrations=[
            FastApiIntegration(
                transaction_style="endpoint",
                failed_request_status_codes={400, 401, 403, 404, 405, 409, 410, 422, 429}
            ),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR
            ),
        ],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
        attach_stacktrace=True,
        send_default_pii=False,  # Don't send PII
        before_send=before_send_filter,
    )
    
    logger.info("Sentry initialized", dsn=sentry_dsn[:20] + "...")


def before_send_filter(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Filter sensitive data before sending to Sentry"""
    
    # Remove sensitive headers
    if "request" in event and "headers" in event["request"]:
        sensitive_headers = ["authorization", "cookie", "x-api-key", "x-auth-token"]
        for header in sensitive_headers:
            if header in event["request"]["headers"]:
                event["request"]["headers"][header] = "[FILTERED]"
    
    # Remove access tokens from extra data
    if "extra" in event:
        for key in list(event["extra"].keys()):
            if "token" in key.lower() or "secret" in key.lower() or "password" in key.lower():
                event["extra"][key] = "[FILTERED]"
    
    return event


# Prometheus metrics
youtube_upload_counter = Counter(
    'youtube_uploads_total',
    'Total number of YouTube uploads',
    ['status', 'channel_id']
)

youtube_upload_duration = Histogram(
    'youtube_upload_duration_seconds',
    'Duration of YouTube uploads in seconds',
    ['channel_id']
)

youtube_upload_size = Histogram(
    'youtube_upload_size_bytes',
    'Size of uploaded YouTube videos in bytes',
    ['channel_id'],
    buckets=(
        1024 * 1024,  # 1MB
        10 * 1024 * 1024,  # 10MB
        100 * 1024 * 1024,  # 100MB
        500 * 1024 * 1024,  # 500MB
        1024 * 1024 * 1024,  # 1GB
        5 * 1024 * 1024 * 1024,  # 5GB
    )
)

youtube_api_requests = Counter(
    'youtube_api_requests_total',
    'Total number of YouTube API requests',
    ['endpoint', 'status_code']
)

youtube_api_latency = Histogram(
    'youtube_api_latency_seconds',
    'Latency of YouTube API requests',
    ['endpoint']
)

youtube_channels_connected = Gauge(
    'youtube_channels_connected',
    'Number of connected YouTube channels'
)

youtube_tokens_refreshed = Counter(
    'youtube_tokens_refreshed_total',
    'Total number of YouTube token refreshes',
    ['channel_id', 'success']
)

upload_queue_size = Gauge(
    'youtube_upload_queue_size',
    'Number of videos in upload queue'
)


def track_upload(func):
    """Decorator to track upload metrics"""
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        channel_id = kwargs.get('channel_id', 'unknown')
        
        try:
            result = await func(*args, **kwargs)
            
            # Track success
            youtube_upload_counter.labels(status='success', channel_id=channel_id).inc()
            
            # Track duration
            duration = time.time() - start_time
            youtube_upload_duration.labels(channel_id=channel_id).observe(duration)
            
            # Track size if available
            if 'file_size' in kwargs:
                youtube_upload_size.labels(channel_id=channel_id).observe(kwargs['file_size'])
            
            logger.info(
                "Upload completed",
                channel_id=channel_id,
                duration=duration,
                upload_id=kwargs.get('upload_id')
            )
            
            return result
            
        except Exception as e:
            # Track failure
            youtube_upload_counter.labels(status='failure', channel_id=channel_id).inc()
            
            # Log error with context
            logger.error(
                "Upload failed",
                channel_id=channel_id,
                duration=time.time() - start_time,
                upload_id=kwargs.get('upload_id'),
                error=str(e),
                exc_info=True
            )
            
            # Report to Sentry
            sentry_sdk.capture_exception(e)
            
            raise
    
    return wrapper


def track_api_call(endpoint: str):
    """Decorator to track YouTube API calls"""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                
                # Track success
                youtube_api_requests.labels(endpoint=endpoint, status_code=200).inc()
                
                # Track latency
                latency = time.time() - start_time
                youtube_api_latency.labels(endpoint=endpoint).observe(latency)
                
                logger.debug(
                    "YouTube API call successful",
                    endpoint=endpoint,
                    latency=latency
                )
                
                return result
                
            except Exception as e:
                # Determine status code from exception
                status_code = getattr(e, 'status_code', 500)
                
                # Track failure
                youtube_api_requests.labels(endpoint=endpoint, status_code=status_code).inc()
                
                # Track latency even for failures
                latency = time.time() - start_time
                youtube_api_latency.labels(endpoint=endpoint).observe(latency)
                
                logger.warning(
                    "YouTube API call failed",
                    endpoint=endpoint,
                    status_code=status_code,
                    latency=latency,
                    error=str(e)
                )
                
                raise
        
        return wrapper
    return decorator


def track_token_refresh(channel_id: str, success: bool):
    """Track token refresh attempts"""
    
    youtube_tokens_refreshed.labels(
        channel_id=channel_id,
        success='true' if success else 'false'
    ).inc()
    
    if success:
        logger.info("Token refreshed successfully", channel_id=channel_id)
    else:
        logger.warning("Token refresh failed", channel_id=channel_id)


def update_channel_count(count: int):
    """Update the connected channels gauge"""
    youtube_channels_connected.set(count)
    logger.info("Updated channel count", count=count)


def update_queue_size(size: int):
    """Update the upload queue size gauge"""
    upload_queue_size.set(size)


class YouTubeMonitor:
    """Context manager for monitoring YouTube operations"""
    
    def __init__(self, operation: str, **tags):
        self.operation = operation
        self.tags = tags
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        logger.info(f"Starting {self.operation}", **self.tags)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        if exc_type is None:
            logger.info(
                f"Completed {self.operation}",
                duration=duration,
                **self.tags
            )
        else:
            logger.error(
                f"Failed {self.operation}",
                duration=duration,
                error=str(exc_val),
                exc_info=True,
                **self.tags
            )
            
            # Report to Sentry
            sentry_sdk.capture_exception(exc_val)
        
        return False  # Don't suppress exceptions


# Langfuse integration for LLM tracing
def init_langfuse():
    """Initialize Langfuse for LLM tracing"""
    
    langfuse_key = os.getenv("LANGFUSE_SECRET_KEY")
    langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
    if not langfuse_key or not langfuse_public_key:
        logger.warning("Langfuse credentials not configured, LLM tracing disabled")
        return None
    
    try:
        from langfuse import Langfuse
        
        langfuse = Langfuse(
            secret_key=langfuse_key,
            public_key=langfuse_public_key,
            host=langfuse_host,
            debug=os.getenv("ENVIRONMENT") == "development"
        )
        
        logger.info("Langfuse initialized for LLM tracing")
        return langfuse
        
    except ImportError:
        logger.warning("Langfuse not installed, LLM tracing disabled")
        return None


class LLMTracer:
    """Trace LLM calls for YouTube metadata generation"""
    
    def __init__(self):
        self.langfuse = init_langfuse()
    
    def trace_metadata_generation(
        self,
        prompt: str,
        model: str,
        response: str,
        duration: float,
        tokens_used: Optional[int] = None
    ):
        """Trace metadata generation with LLM"""
        
        if not self.langfuse:
            return
        
        try:
            self.langfuse.generation(
                name="youtube_metadata_generation",
                model=model,
                input=prompt,
                output=response,
                usage={
                    "total_tokens": tokens_used
                } if tokens_used else None,
                metadata={
                    "duration_seconds": duration,
                    "service": "youtube_mcp"
                }
            )
            
            logger.debug(
                "LLM call traced",
                model=model,
                duration=duration,
                tokens=tokens_used
            )
            
        except Exception as e:
            logger.warning(f"Failed to trace LLM call: {e}")


# Initialize monitoring on import
init_sentry()
llm_tracer = LLMTracer()

__all__ = [
    'init_sentry',
    'track_upload',
    'track_api_call',
    'track_token_refresh',
    'update_channel_count',
    'update_queue_size',
    'YouTubeMonitor',
    'llm_tracer',
    'logger'
]