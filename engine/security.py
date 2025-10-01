"""
Security utilities and configurations for Involution Engine
Provides centralized security hardening functions and middleware helpers.
"""

import os
import secrets
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

# Security constants
MAX_REQUEST_SIZE = int(os.getenv("MAX_REQUEST_SIZE", "1048576"))  # 1MB default
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))  # 30 seconds
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "100"))


class SecurityConfig:
    """Centralized security configuration"""

    # Security headers configuration
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": os.getenv("X_FRAME_OPTIONS", "DENY"),
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": os.getenv("REFERRER_POLICY", "strict-origin-when-cross-origin"),
        "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
    }

    # CSP policy
    CSP_POLICY = os.getenv(
        "CSP_POLICY",
        "default-src 'self'; "
        "connect-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    # HSTS configuration
    HSTS_MAX_AGE = int(os.getenv("HSTS_MAX_AGE", "31536000"))  # 1 year

    # Trusted hosts
    TRUSTED_HOSTS = [
        h.strip() for h in os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1,*.yourdomain.com").split(",")
    ]

    # Rate limiting
    RATE_LIMITS = {
        "default": os.getenv("RATE_LIMIT_DEFAULT", "100/minute"),
        "calculate": os.getenv("RATE_LIMIT_CALCULATE", "60/minute"),
        "timesolve": os.getenv("RATE_LIMIT_TIMESOLVE", "30/minute"),
    }


class SecurityMetrics:
    """Track security-related metrics"""

    def __init__(self):
        self.blocked_requests = 0
        self.rate_limited_requests = 0
        self.invalid_hosts = 0
        self.suspicious_requests = 0
        self.start_time = time.time()

    def record_blocked_request(self, reason: str):
        """Record a blocked request"""
        self.blocked_requests += 1
        logging.warning(f"Request blocked: {reason}")

    def record_rate_limited_request(self, client_ip: str):
        """Record a rate-limited request"""
        self.rate_limited_requests += 1
        logging.warning(f"Rate limit exceeded for IP: {client_ip}")

    def record_invalid_host(self, host: str):
        """Record invalid host access attempt"""
        self.invalid_hosts += 1
        logging.warning(f"Invalid host access attempt: {host}")

    def record_suspicious_request(self, details: str):
        """Record suspicious request patterns"""
        self.suspicious_requests += 1
        logging.warning(f"Suspicious request detected: {details}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get security metrics summary"""
        uptime = time.time() - self.start_time
        return {
            "blocked_requests": self.blocked_requests,
            "rate_limited_requests": self.rate_limited_requests,
            "invalid_hosts": self.invalid_hosts,
            "suspicious_requests": self.suspicious_requests,
            "uptime_hours": round(uptime / 3600, 2),
        }


def generate_secure_token(length: int = 32) -> str:
    """Generate cryptographically secure random token"""
    return secrets.token_urlsafe(length)


def is_suspicious_request(headers: dict, path: str) -> Optional[str]:
    """
    Detect potentially suspicious request patterns
    Returns reason if suspicious, None if clean
    """

    # Check for common attack patterns in headers
    user_agent = headers.get("user-agent", "").lower()
    if any(pattern in user_agent for pattern in ["sqlmap", "nikto", "nmap", "dirb", "gobuster"]):
        return f"Suspicious user-agent: {user_agent}"

    # Check for suspicious paths
    suspicious_paths = [
        "/admin", "/wp-admin", "/.env", "/config", "/phpmyadmin",
        "/.git", "/backup", "/test", "/debug", "/api/v1/admin"
    ]
    if any(pattern in path.lower() for pattern in suspicious_paths):
        return f"Suspicious path access: {path}"

    # Check for unusual header combinations
    if "x-forwarded-for" in headers and "x-real-ip" in headers:
        xff = headers["x-forwarded-for"]
        xri = headers["x-real-ip"]
        if xff.count(",") > 5:  # Too many proxy hops
            return f"Suspicious proxy chain: {xff}"

    # Check for missing expected headers
    if not headers.get("user-agent"):
        return "Missing user-agent header"

    return None


def validate_request_size(content_length: Optional[int]) -> bool:
    """Validate request content length"""
    if content_length is None:
        return True
    return content_length <= MAX_REQUEST_SIZE


def get_client_ip(headers: dict, client_host: Optional[str]) -> str:
    """Extract real client IP considering proxy headers"""

    # Check for proxy headers in order of preference
    proxy_headers = [
        "x-forwarded-for",
        "x-real-ip",
        "x-client-ip",
        "cf-connecting-ip",  # Cloudflare
    ]

    for header in proxy_headers:
        if header in headers:
            ip = headers[header].split(",")[0].strip()
            if ip:
                return ip

    return client_host or "unknown"


# Global security metrics instance
security_metrics = SecurityMetrics()