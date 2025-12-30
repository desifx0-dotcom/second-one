"""
Custom middleware for the Video AI SaaS Platform
"""
import time
import uuid
from flask import request, g, current_app
from werkzeug.middleware.proxy_fix import ProxyFix

def setup_middleware(app):
    """Setup all middleware for the application"""
    
    # Trust X-Forwarded-* headers (for reverse proxy)
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,  # Number of trusted proxies
        x_proto=1,
        x_host=1,
        x_port=1,
        x_prefix=1
    )
    
    @app.before_request
    def before_request():
        """Execute before each request"""
        # Start timer
        g.start_time = time.time()
        
        # Generate request ID for tracking
        g.request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        
        # Set request ID in headers for downstream services
        request.environ['REQUEST_ID'] = g.request_id
        
        # Log request (for non-static requests)
        if not request.path.startswith('/static/') and not request.path.startswith('/favicon.ico'):
            current_app.logger.debug(
                f"Request Started: {request.method} {request.path} "
                f"IP: {request.remote_addr} "
                f"Request-ID: {g.request_id}"
            )
    
    @app.after_request
    def after_request(response):
        """Execute after each request"""
        # Calculate request duration
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            
            # Add request ID to response headers
            response.headers['X-Request-ID'] = g.request_id
            
            # Add server timing header
            response.headers['Server-Timing'] = f'dur={duration:.3f}'
            
            # Log slow requests
            if duration > 1.0:  # More than 1 second
                current_app.logger.warning(
                    f"Slow Request: {request.method} {request.path} "
                    f"Duration: {duration:.3f}s "
                    f"Status: {response.status_code} "
                    f"Request-ID: {g.request_id}"
                )
            
            # Log completed request (for non-static requests)
            if not request.path.startswith('/static/') and not request.path.startswith('/favicon.ico'):
                current_app.logger.debug(
                    f"Request Completed: {request.method} {request.path} "
                    f"Status: {response.status_code} "
                    f"Duration: {duration:.3f}s "
                    f"Size: {response.content_length or 0} bytes "
                    f"Request-ID: {g.request_id}"
                )
        
        # Security headers (already in app.py, but kept here for completeness)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # CORS headers for API requests
        if request.path.startswith('/api/'):
            response.headers['Access-Control-Allow-Origin'] = ', '.join(
                current_app.config.get('CORS_ORIGINS', [])
            )
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
        
        return response
    
    @app.teardown_request
    def teardown_request(exception=None):
        """Execute after request is complete, even if an error occurred"""
        if exception:
            current_app.logger.error(
                f"Request Error: {request.method} {request.path} "
                f"Error: {str(exception)} "
                f"Request-ID: {g.request_id if hasattr(g, 'request_id') else 'unknown'}",
                exc_info=True
            )
    
    # Error logging for unhandled exceptions
    @app.errorhandler(Exception)
    def handle_exception(error):
        """Log unhandled exceptions"""
        current_app.logger.error(
            f"Unhandled Exception: {type(error).__name__}: {str(error)} "
            f"Path: {request.path} "
            f"Method: {request.method} "
            f"IP: {request.remote_addr} "
            f"Request-ID: {g.request_id if hasattr(g, 'request_id') else 'unknown'}",
            exc_info=True
        )
        # Re-raise to let Flask's default error handler deal with it
        raise error
    
    # Rate limiting error handler
    from flask_limiter import RateLimitExceeded
    
    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit_exceeded(error):
        """Custom handler for rate limit exceeded"""
        current_app.logger.warning(
            f"Rate Limit Exceeded: {request.path} "
            f"IP: {request.remote_addr} "
            f"Limit: {error.description} "
            f"Request-ID: {g.request_id if hasattr(g, 'request_id') else 'unknown'}"
        )
        
        # Return JSON response for API requests
        if request.path.startswith('/api/'):
            from flask import jsonify
            return jsonify({
                'error': 'Too Many Requests',
                'message': 'Rate limit exceeded. Please try again later.',
                'retry_after': getattr(error, 'retry_after', None),
                'code': 429
            }), 429
        
        # For non-API requests, use default error handler
        from werkzeug.exceptions import TooManyRequests
        return TooManyRequests().get_response()
    
    current_app.logger.info("✓ Middleware setup complete")