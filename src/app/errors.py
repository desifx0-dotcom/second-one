"""
Error handlers for the Video AI SaaS Platform
"""
import logging
from flask import jsonify, render_template, request, current_app
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

def register_error_handlers(app):
    """Register error handlers for the application"""
    
    # ========== HTTP ERRORS ==========
    
    @app.errorhandler(400)
    def bad_request(error):
        """400 Bad Request"""
        logger.warning(f"Bad Request: {request.path} - {error.description if hasattr(error, 'description') else str(error)}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Bad Request',
                'message': error.description if hasattr(error, 'description') else 'Invalid request format or parameters',
                'code': 400
            }), 400
        
        return render_template('errors/400.html', error=error), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        """401 Unauthorized"""
        logger.warning(f"Unauthorized: {request.path} - User: {request.remote_addr}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Authentication required',
                'code': 401
            }), 401
        
        return render_template('errors/401.html', error=error), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        """403 Forbidden"""
        logger.warning(f"Forbidden: {request.path} - User: {request.remote_addr}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Forbidden',
                'message': 'You do not have permission to access this resource',
                'code': 403
            }), 403
        
        return render_template('errors/403.html', error=error), 403
    
    @app.errorhandler(404)
    def not_found(error):
        """404 Not Found"""
        logger.info(f"Not Found: {request.path}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Not Found',
                'message': 'The requested resource was not found',
                'path': request.path,
                'code': 404
            }), 404
        
        return render_template('errors/404.html', error=error), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """405 Method Not Allowed"""
        logger.warning(f"Method Not Allowed: {request.method} {request.path}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Method Not Allowed',
                'message': f'The {request.method} method is not allowed for this endpoint',
                'allowed_methods': error.valid_methods if hasattr(error, 'valid_methods') else [],
                'code': 405
            }), 405
        
        return render_template('errors/405.html', error=error), 405
    
    @app.errorhandler(409)
    def conflict(error):
        """409 Conflict"""
        logger.warning(f"Conflict: {request.path} - {error.description if hasattr(error, 'description') else str(error)}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Conflict',
                'message': error.description if hasattr(error, 'description') else 'Resource conflict occurred',
                'code': 409
            }), 409
        
        return render_template('errors/409.html', error=error), 409
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        """413 Request Entity Too Large"""
        max_size_mb = current_app.config.get('MAX_CONTENT_LENGTH', 0) // (1024 * 1024)
        
        logger.warning(f"Request Too Large: {request.path} - Size: {request.content_length or 0} bytes")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'File Too Large',
                'message': f'Maximum file size is {max_size_mb}MB',
                'max_size_mb': max_size_mb,
                'code': 413
            }), 413
        
        return render_template('errors/413.html', error=error, max_size_mb=max_size_mb), 413
    
    @app.errorhandler(429)
    def too_many_requests(error):
        """429 Too Many Requests"""
        logger.warning(f"Rate Limit Exceeded: {request.path} - IP: {request.remote_addr}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Too Many Requests',
                'message': 'Rate limit exceeded. Please try again later.',
                'code': 429
            }), 429
        
        return render_template('errors/429.html', error=error), 429
    
    # ========== SERVER ERRORS ==========
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """500 Internal Server Error"""
        logger.error(f"Internal Server Error: {request.path}", exc_info=True)
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred. Our team has been notified.',
                'code': 500,
                'request_id': request.environ.get('REQUEST_ID', 'unknown') if hasattr(request, 'environ') else 'unknown'
            }), 500
        
        return render_template('errors/500.html', error=error), 500
    
    @app.errorhandler(502)
    def bad_gateway(error):
        """502 Bad Gateway"""
        logger.error(f"Bad Gateway: {request.path}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Bad Gateway',
                'message': 'The server received an invalid response from an upstream server',
                'code': 502
            }), 502
        
        return render_template('errors/502.html', error=error), 502
    
    @app.errorhandler(503)
    def service_unavailable(error):
        """503 Service Unavailable"""
        logger.error(f"Service Unavailable: {request.path}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Service Unavailable',
                'message': 'The server is temporarily unavailable. Please try again later.',
                'code': 503
            }), 503
        
        return render_template('errors/503.html', error=error), 503
    
    @app.errorhandler(504)
    def gateway_timeout(error):
        """504 Gateway Timeout"""
        logger.error(f"Gateway Timeout: {request.path}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Gateway Timeout',
                'message': 'The server did not receive a timely response from an upstream server',
                'code': 504
            }), 504
        
        return render_template('errors/504.html', error=error), 504
    
    # ========== DATABASE ERRORS ==========
    
    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        """Handle database errors"""
        logger.error(f"Database Error: {str(error)}", exc_info=True)
        
        # Rollback session if needed
        from src.app.extensions import db
        if db.session.is_active:
            db.session.rollback()
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Database Error',
                'message': 'A database error occurred. Our team has been notified.',
                'code': 500
            }), 500
        
        return render_template('errors/500.html', error=error), 500
    
    # ========== VALIDATION ERRORS ==========
    
    @app.errorhandler(422)
    def handle_validation_error(error):
        """Handle validation errors (usually from webargs or similar)"""
        logger.warning(f"Validation Error: {request.path} - {str(error)}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Validation Error',
                'message': error.description if hasattr(error, 'description') else 'Invalid input data',
                'details': getattr(error, 'data', {}).get('messages', {}),
                'code': 422
            }), 422
        
        return render_template('errors/422.html', error=error), 422
    
    # ========== CSRF ERRORS ==========
    
    @app.errorhandler(400)  # CSRF returns 400
    def handle_csrf_error(error):
        """Handle CSRF errors"""
        from flask_wtf.csrf import CSRFError
        
        if isinstance(error, CSRFError):
            logger.warning(f"CSRF Error: {request.path} - IP: {request.remote_addr}")
            
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({
                    'error': 'CSRF Error',
                    'message': 'CSRF token missing or invalid',
                    'code': 400
                }), 400
            
            return render_template('errors/csrf.html', error=error), 400
        
        # Not a CSRF error, continue with normal 400 handling
        return bad_request(error)
    
    # ========== GENERIC EXCEPTION HANDLER ==========
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Catch-all for unhandled exceptions"""
        logger.critical(f"Unhandled Exception: {type(error).__name__}: {str(error)}", exc_info=True)
        
        # Check if it's an HTTP exception (already handled)
        if isinstance(error, HTTPException):
            return error
        
        if request.is_json or request.path.startswith('/api/'):
            # Don't expose internal details in production
            if current_app.debug or current_app.testing:
                import traceback
                return jsonify({
                    'error': 'Unexpected Error',
                    'message': str(error),
                    'type': type(error).__name__,
                    'traceback': traceback.format_exception(type(error), error, error.__traceback__),
                    'code': 500
                }), 500
            else:
                return jsonify({
                    'error': 'Internal Server Error',
                    'message': 'An unexpected error occurred. Our team has been notified.',
                    'code': 500
                }), 500
        
        return render_template('errors/500.html', error=error), 500
    
    # ========== REQUEST LOGGING MIDDLEWARE ==========
    
    @app.after_request
    def log_response(response):
        """Log response information"""
        if not app.debug and response.status_code >= 400:
            logger.info(
                f"Response: {response.status_code} {request.method} {request.path} "
                f"IP: {request.remote_addr} "
                f"Size: {response.content_length or 0} bytes"
            )
        return response
    
    logger.info("✓ Error handlers registered")