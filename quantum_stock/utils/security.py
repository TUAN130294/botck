# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    SECURITY MIDDLEWARE                                       ║
║                    CSRF, Rate Limiting, Security Headers                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

P0 Implementation - Security hardening for production
"""

import os
import time
import hashlib
import secrets
import logging
from functools import wraps
from typing import Dict, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# RATE LIMITER
# ============================================

class RateLimiter:
    """
    In-memory rate limiter
    For production, use Redis-backed rate limiting
    """
    
    def __init__(self, default_limit: int = 100, default_window: int = 60):
        self.default_limit = default_limit
        self.default_window = default_window
        self.requests: Dict[str, list] = defaultdict(list)
        self.blocked: Dict[str, datetime] = {}
        self.block_duration = 300  # 5 minutes
    
    def is_allowed(self, key: str, limit: int = None, window: int = None) -> bool:
        """Check if request is allowed"""
        limit = limit or self.default_limit
        window = window or self.default_window
        now = time.time()
        
        # Check if blocked
        if key in self.blocked:
            if datetime.now() < self.blocked[key]:
                return False
            else:
                del self.blocked[key]
        
        # Clean old requests
        self.requests[key] = [t for t in self.requests[key] if now - t < window]
        
        # Check limit
        if len(self.requests[key]) >= limit:
            # Block for excessive requests
            self.blocked[key] = datetime.now() + timedelta(seconds=self.block_duration)
            logger.warning(f"Rate limit exceeded for {key}, blocking for {self.block_duration}s")
            return False
        
        # Record request
        self.requests[key].append(now)
        return True
    
    def get_remaining(self, key: str, limit: int = None, window: int = None) -> int:
        """Get remaining requests"""
        limit = limit or self.default_limit
        window = window or self.default_window
        now = time.time()
        
        self.requests[key] = [t for t in self.requests[key] if now - t < window]
        return max(0, limit - len(self.requests[key]))
    
    def reset(self, key: str):
        """Reset rate limit for key"""
        self.requests.pop(key, None)
        self.blocked.pop(key, None)


# Global rate limiter
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def rate_limit(limit: int = 100, window: int = 60, key_func: Callable = None):
    """
    Rate limiting decorator
    
    Usage:
        @rate_limit(limit=10, window=60)
        def my_api_endpoint():
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter = get_rate_limiter()
            
            # Get rate limit key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # Default: use function name
                key = func.__name__
            
            if not limiter.is_allowed(key, limit, window):
                raise RateLimitExceeded(
                    f"Rate limit exceeded. Try again in {window} seconds."
                )
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


class RateLimitExceeded(Exception):
    """Rate limit exceeded exception"""
    pass


# ============================================
# CSRF PROTECTION
# ============================================

class CSRFProtection:
    """
    CSRF Token manager
    """
    
    def __init__(self, secret_key: str = None, token_expiry: int = 3600):
        self.secret_key = secret_key or os.getenv('SECRET_KEY', secrets.token_hex(32))
        self.token_expiry = token_expiry
        self.tokens: Dict[str, datetime] = {}
    
    def generate_token(self, session_id: str = None) -> str:
        """Generate a CSRF token"""
        # Create unique token
        data = f"{session_id or ''}{time.time()}{secrets.token_hex(16)}"
        token = hashlib.sha256(
            f"{data}{self.secret_key}".encode()
        ).hexdigest()
        
        # Store with expiry
        self.tokens[token] = datetime.now() + timedelta(seconds=self.token_expiry)
        
        # Clean expired tokens
        self._cleanup()
        
        return token
    
    def validate_token(self, token: str) -> bool:
        """Validate a CSRF token"""
        if not token:
            return False
        
        if token not in self.tokens:
            return False
        
        if datetime.now() > self.tokens[token]:
            del self.tokens[token]
            return False
        
        return True
    
    def invalidate_token(self, token: str):
        """Invalidate a token after use"""
        self.tokens.pop(token, None)
    
    def _cleanup(self):
        """Remove expired tokens"""
        now = datetime.now()
        expired = [t for t, exp in self.tokens.items() if now > exp]
        for token in expired:
            del self.tokens[token]


# Global CSRF protection
_csrf: Optional[CSRFProtection] = None


def get_csrf() -> CSRFProtection:
    """Get global CSRF protection"""
    global _csrf
    if _csrf is None:
        _csrf = CSRFProtection()
    return _csrf


def csrf_required(func: Callable):
    """
    CSRF validation decorator for Flask
    
    Usage:
        @app.route('/api/submit', methods=['POST'])
        @csrf_required
        def submit():
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            from flask import request, abort
        except ImportError:
            return func(*args, **kwargs)
        
        csrf = get_csrf()
        
        # Get token from header or form
        token = request.headers.get('X-CSRF-Token') or \
                request.form.get('csrf_token') or \
                request.json.get('csrf_token') if request.is_json else None
        
        if not csrf.validate_token(token):
            abort(403, description="CSRF validation failed")
        
        return func(*args, **kwargs)
    
    return wrapper


# ============================================
# SECURITY HEADERS
# ============================================

def add_security_headers(response):
    """
    Add security headers to response
    
    Usage in Flask:
        @app.after_request
        def after_request(response):
            return add_security_headers(response)
    """
    # Content Security Policy
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.plot.ly; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' wss: https:;"
    )
    
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    
    # XSS protection
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # Referrer policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Permissions policy
    response.headers['Permissions-Policy'] = (
        'geolocation=(), microphone=(), camera=()'
    )
    
    # HSTS (only in production with HTTPS)
    if os.getenv('FLASK_ENV') == 'production':
        response.headers['Strict-Transport-Security'] = (
            'max-age=31536000; includeSubDomains'
        )
    
    return response


# ============================================
# INPUT VALIDATION
# ============================================

class InputValidator:
    """
    Input validation utilities
    """
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 255) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            value = str(value)
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # Truncate
        return value[:max_length]
    
    @staticmethod
    def validate_symbol(symbol: str) -> bool:
        """Validate stock symbol"""
        if not symbol or not isinstance(symbol, str):
            return False
        
        # Vietnamese stock symbols: 3 uppercase letters
        symbol = symbol.strip().upper()
        if len(symbol) != 3:
            return False
        
        return symbol.isalpha()
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Basic email validation"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_quantity(quantity: int) -> bool:
        """Validate trading quantity (must be multiple of 100 for VN market)"""
        if not isinstance(quantity, int):
            return False
        return quantity > 0 and quantity % 100 == 0
    
    @staticmethod
    def validate_price(price: float, min_price: float = 0.01) -> bool:
        """Validate price"""
        if not isinstance(price, (int, float)):
            return False
        return price >= min_price


def validate_input(validators: Dict[str, Callable]):
    """
    Input validation decorator
    
    Usage:
        @validate_input({
            'symbol': InputValidator.validate_symbol,
            'quantity': InputValidator.validate_quantity
        })
        def place_order(symbol, quantity, price):
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for param, validator in validators.items():
                if param in kwargs:
                    if not validator(kwargs[param]):
                        raise ValueError(f"Invalid {param}: {kwargs[param]}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================
# AUDIT LOGGING
# ============================================

class AuditLogger:
    """
    Audit logging for security events
    """
    
    def __init__(self, log_file: str = 'audit.log'):
        self.logger = logging.getLogger('audit')
        self.logger.setLevel(logging.INFO)
        
        # File handler
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(handler)
    
    def log_login(self, user_id: str, ip: str, success: bool):
        """Log login attempt"""
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(f"LOGIN {status} | user={user_id} | ip={ip}")
    
    def log_trade(self, user_id: str, action: str, symbol: str, quantity: int, price: float):
        """Log trade attempt"""
        self.logger.info(
            f"TRADE | user={user_id} | action={action} | "
            f"symbol={symbol} | qty={quantity} | price={price}"
        )
    
    def log_api_call(self, endpoint: str, method: str, user_id: str, ip: str):
        """Log API call"""
        self.logger.info(f"API | {method} {endpoint} | user={user_id} | ip={ip}")
    
    def log_security_event(self, event_type: str, details: str, severity: str = 'WARNING'):
        """Log security event"""
        log_func = getattr(self.logger, severity.lower(), self.logger.warning)
        log_func(f"SECURITY | {event_type} | {details}")


# Global audit logger
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# ============================================
# FLASK MIDDLEWARE
# ============================================

def init_security_flask(app):
    """
    Initialize security middleware for Flask app
    
    Usage:
        from quantum_stock.utils.security import init_security_flask
        init_security_flask(app)
    """
    from flask import request, g
    
    # Add security headers to all responses
    @app.after_request
    def add_headers(response):
        return add_security_headers(response)
    
    # Rate limiting middleware
    @app.before_request
    def check_rate_limit():
        limiter = get_rate_limiter()
        
        # Use IP address as rate limit key
        key = request.remote_addr
        
        if not limiter.is_allowed(key, limit=100, window=60):
            from flask import abort
            abort(429, description="Too many requests")
        
        # Store remaining requests
        g.rate_limit_remaining = limiter.get_remaining(key)
    
    # Add rate limit headers
    @app.after_request  
    def add_rate_limit_headers(response):
        if hasattr(g, 'rate_limit_remaining'):
            response.headers['X-RateLimit-Remaining'] = str(g.rate_limit_remaining)
            response.headers['X-RateLimit-Limit'] = '100'
        return response
    
    # CSRF token endpoint
    @app.route('/api/csrf-token', methods=['GET'])
    def get_csrf_token():
        from flask import jsonify, session
        csrf = get_csrf()
        token = csrf.generate_token(session.get('session_id'))
        return jsonify({'csrf_token': token})
    
    logger.info("Flask security middleware initialized")


# ============================================
# TESTING
# ============================================

def test_security():
    """Test security module"""
    print("Testing Security Module...")
    print("=" * 50)
    
    # Test rate limiter
    limiter = RateLimiter(default_limit=5, default_window=10)
    
    for i in range(7):
        allowed = limiter.is_allowed('test_user')
        print(f"Request {i+1}: {'✅ Allowed' if allowed else '❌ Blocked'}")
    
    # Test CSRF
    csrf = CSRFProtection()
    token = csrf.generate_token('session123')
    print(f"\nCSRF Token: {token[:20]}...")
    print(f"Token valid: {csrf.validate_token(token)}")
    print(f"Invalid token valid: {csrf.validate_token('fake_token')}")
    
    # Test input validation
    validator = InputValidator()
    print(f"\nSymbol 'HPG' valid: {validator.validate_symbol('HPG')}")
    print(f"Symbol 'ABCD' valid: {validator.validate_symbol('ABCD')}")
    print(f"Quantity 1000 valid: {validator.validate_quantity(1000)}")
    print(f"Quantity 99 valid: {validator.validate_quantity(99)}")
    
    print("\n✅ Security tests completed!")


if __name__ == "__main__":
    test_security()
