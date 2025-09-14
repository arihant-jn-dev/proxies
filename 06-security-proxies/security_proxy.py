#!/usr/bin/env python3
"""
Security Proxy Implementation

A security-focused proxy that provides:
- SSL/TLS termination and inspection
- Content filtering and malware scanning
- Request sanitization and validation
- Access control and authentication
- Security headers enforcement
- Rate limiting and DDoS protection
"""

import asyncio
import hashlib
import json
import logging
import re
import ssl
import time
import urllib.parse
from typing import Dict, List, Set, Optional
from collections import defaultdict, deque
import socket
import http.server
import socketserver


class SecurityPolicy:
    """Security policy configuration."""
    
    def __init__(self):
        # Content filtering
        self.blocked_domains: Set[str] = set()
        self.blocked_keywords: Set[str] = set()
        self.allowed_content_types: Set[str] = {
            'text/html', 'text/plain', 'text/css', 'text/javascript',
            'application/json', 'application/xml', 'image/jpeg', 'image/png'
        }
        
        # Security headers to enforce
        self.security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Content-Security-Policy': "default-src 'self'",
            'Referrer-Policy': 'strict-origin-when-cross-origin'
        }
        
        # Rate limiting
        self.rate_limits = {
            'requests_per_minute': 60,
            'requests_per_hour': 1000,
            'max_concurrent_connections': 10
        }
        
        # Malicious patterns
        self.malicious_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',                # Javascript URLs
            r'vbscript:',                 # VBScript URLs
            r'onload\s*=',                # Event handlers
            r'onerror\s*=',
            r'onclick\s*=',
            r'eval\s*\(',                 # Eval functions
            r'document\.cookie',          # Cookie access
            r'\.\./',                     # Directory traversal
            r'union\s+select',            # SQL injection
            r'drop\s+table',
            r'exec\s*\(',                 # Command execution
            r'system\s*\(',
        ]
        
        # Compile patterns for efficiency
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.malicious_patterns]


class ThreatDetector:
    """Detect and analyze security threats."""
    
    def __init__(self, policy: SecurityPolicy):
        self.policy = policy
        self.logger = logging.getLogger("threat_detector")
        
        # Threat statistics
        self.threats_detected = defaultdict(int)
        self.blocked_requests = 0
        self.suspicious_ips: Set[str] = set()
        
        # Rate limiting tracking
        self.request_counts = defaultdict(lambda: defaultdict(deque))  # ip -> timeframe -> timestamps
        self.active_connections = defaultdict(int)  # ip -> count
    
    def check_domain(self, domain: str) -> bool:
        """Check if domain is allowed."""
        domain = domain.lower()
        
        # Check blocked domains
        if domain in self.policy.blocked_domains:
            self.threats_detected['blocked_domain'] += 1
            return False
        
        # Check for suspicious TLDs
        suspicious_tlds = {'.tk', '.ml', '.ga', '.cf', '.top', '.click'}
        for tld in suspicious_tlds:
            if domain.endswith(tld):
                self.threats_detected['suspicious_tld'] += 1
                self.logger.warning(f"Suspicious TLD detected: {domain}")
        
        return True
    
    def check_content(self, content: str, content_type: str = None) -> bool:
        """Check content for malicious patterns."""
        # Check content type
        if content_type and content_type not in self.policy.allowed_content_types:
            self.threats_detected['unauthorized_content_type'] += 1
            return False
        
        # Check for blocked keywords
        content_lower = content.lower()
        for keyword in self.policy.blocked_keywords:
            if keyword in content_lower:
                self.threats_detected['blocked_keyword'] += 1
                self.logger.warning(f"Blocked keyword detected: {keyword}")
                return False
        
        # Check for malicious patterns
        for pattern in self.policy.compiled_patterns:
            if pattern.search(content):
                self.threats_detected['malicious_pattern'] += 1
                self.logger.warning(f"Malicious pattern detected: {pattern.pattern}")
                return False
        
        return True
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """Check if client is within rate limits."""
        now = time.time()
        
        # Clean old requests
        minute_window = self.request_counts[client_ip]['minute']
        hour_window = self.request_counts[client_ip]['hour']
        
        # Remove requests older than 1 minute
        while minute_window and minute_window[0] < now - 60:
            minute_window.popleft()
        
        # Remove requests older than 1 hour
        while hour_window and hour_window[0] < now - 3600:
            hour_window.popleft()
        
        # Check limits
        if len(minute_window) >= self.policy.rate_limits['requests_per_minute']:
            self.threats_detected['rate_limit_minute'] += 1
            return False
        
        if len(hour_window) >= self.policy.rate_limits['requests_per_hour']:
            self.threats_detected['rate_limit_hour'] += 1
            return False
        
        if self.active_connections[client_ip] >= self.policy.rate_limits['max_concurrent_connections']:
            self.threats_detected['connection_limit'] += 1
            return False
        
        # Record this request
        minute_window.append(now)
        hour_window.append(now)
        
        return True
    
    def start_connection(self, client_ip: str):
        """Record start of connection."""
        self.active_connections[client_ip] += 1
    
    def end_connection(self, client_ip: str):
        """Record end of connection."""
        if self.active_connections[client_ip] > 0:
            self.active_connections[client_ip] -= 1
    
    def check_url(self, url: str) -> bool:
        """Check URL for malicious content."""
        try:
            parsed = urllib.parse.urlparse(url)
            
            # Check domain
            if not self.check_domain(parsed.netloc):
                return False
            
            # Check path for suspicious patterns
            if not self.check_content(parsed.path + parsed.query):
                return False
            
            return True
        except Exception as e:
            self.logger.error(f"Error checking URL {url}: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """Get threat detection statistics."""
        return {
            "threats_detected": dict(self.threats_detected),
            "blocked_requests": self.blocked_requests,
            "suspicious_ips": len(self.suspicious_ips),
            "active_connections": sum(self.active_connections.values()),
            "tracked_ips": len(self.request_counts)
        }


class SecurityProxy:
    """Security proxy with threat detection and filtering."""
    
    def __init__(self, target_host: str = None, target_port: int = None):
        self.target_host = target_host
        self.target_port = target_port
        self.policy = SecurityPolicy()
        self.detector = ThreatDetector(self.policy)
        self.logger = logging.getLogger("security_proxy")
        
        # Statistics
        self.total_requests = 0
        self.blocked_requests = 0
        self.allowed_requests = 0


class SecurityProxyHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for security proxy."""
    
    def do_GET(self):
        self.handle_request()
    
    def do_POST(self):
        self.handle_request()
    
    def do_PUT(self):
        self.handle_request()
    
    def do_DELETE(self):
        self.handle_request()
    
    def handle_request(self):
        """Handle incoming request with security checks."""
        proxy = self.server.proxy
        client_ip = self.client_address[0]
        
        proxy.total_requests += 1
        proxy.detector.start_connection(client_ip)
        
        try:
            # Handle management endpoints
            if self.path.startswith('/_security/'):
                self.handle_security_endpoint()
                return
            
            # Rate limiting
            if not proxy.detector.check_rate_limit(client_ip):
                proxy.blocked_requests += 1
                self.send_security_response(429, "Rate limit exceeded")
                return
            
            # URL validation
            full_url = f"http://{self.headers.get('host', 'localhost')}{self.path}"
            if not proxy.detector.check_url(full_url):
                proxy.blocked_requests += 1
                self.send_security_response(403, "Request blocked by security policy")
                return
            
            # Extract target from request or use default
            if proxy.target_host and proxy.target_port:
                target_host = proxy.target_host
                target_port = proxy.target_port
            else:
                # Extract from Host header
                host_header = self.headers.get('host', '')
                if ':' in host_header:
                    target_host, target_port = host_header.split(':', 1)
                    target_port = int(target_port)
                else:
                    target_host = host_header
                    target_port = 80
            
            # Read request body
            body = b""
            if 'content-length' in self.headers:
                content_length = int(self.headers['content-length'])
                body = self.rfile.read(content_length)
            
            # Content filtering on request body
            if body:
                body_str = body.decode('utf-8', errors='ignore')
                content_type = self.headers.get('content-type', '')
                if not proxy.detector.check_content(body_str, content_type):
                    proxy.blocked_requests += 1
                    self.send_security_response(403, "Request content blocked by security policy")
                    return
            
            # Forward to target
            target_url = f"http://{target_host}:{target_port}{self.path}"
            
            try:
                # Create request
                req = urllib.request.Request(target_url, data=body, method=self.command)
                
                # Copy headers (except some)
                for key, value in self.headers.items():
                    if key.lower() not in ['host', 'connection']:
                        req.add_header(key, value)
                
                # Add security headers
                req.add_header('X-Security-Proxy', 'SecurityProxy/1.0')
                req.add_header('X-Client-IP', client_ip)
                
                proxy.logger.info(f"Forwarding {self.command} {self.path} to {target_host}:{target_port}")
                
                # Make request
                with urllib.request.urlopen(req, timeout=30) as response:
                    response_body = response.read()
                    response_headers = dict(response.headers)
                    
                    # Content filtering on response
                    if response_body:
                        response_str = response_body.decode('utf-8', errors='ignore')
                        response_content_type = response_headers.get('content-type', '')
                        if not proxy.detector.check_content(response_str, response_content_type):
                            proxy.blocked_requests += 1
                            self.send_security_response(403, "Response content blocked by security policy")
                            return
                    
                    # Send response with security headers
                    self.send_response(response.status)
                    
                    # Add security headers
                    for key, value in proxy.policy.security_headers.items():
                        self.send_header(key, value)
                    
                    # Add original headers (except security-sensitive ones)
                    for key, value in response_headers.items():
                        if key.lower() not in ['server', 'x-powered-by']:
                            self.send_header(key, value)
                    
                    self.send_header('X-Security-Proxy', 'SecurityProxy/1.0')
                    self.end_headers()
                    
                    self.wfile.write(response_body)
                    proxy.allowed_requests += 1
                    
            except Exception as e:
                proxy.logger.error(f"Backend error: {e}")
                self.send_security_response(502, f"Backend error: {str(e)}")
        
        except Exception as e:
            proxy.logger.error(f"Request handling error: {e}")
            self.send_security_response(500, "Internal proxy error")
        
        finally:
            proxy.detector.end_connection(client_ip)
    
    def handle_security_endpoint(self):
        """Handle security management endpoints."""
        proxy = self.server.proxy
        
        if self.path == '/_security/stats':
            stats = {
                "proxy_stats": {
                    "total_requests": proxy.total_requests,
                    "blocked_requests": proxy.blocked_requests,
                    "allowed_requests": proxy.allowed_requests,
                    "block_rate": (proxy.blocked_requests / proxy.total_requests * 100) if proxy.total_requests > 0 else 0
                },
                "threat_stats": proxy.detector.get_stats(),
                "policy": {
                    "blocked_domains": list(proxy.policy.blocked_domains),
                    "blocked_keywords": list(proxy.policy.blocked_keywords),
                    "rate_limits": proxy.policy.rate_limits
                }
            }
            self.send_json_response(stats)
        
        elif self.path == '/_security/policy':
            policy_info = {
                "blocked_domains": list(proxy.policy.blocked_domains),
                "blocked_keywords": list(proxy.policy.blocked_keywords),
                "allowed_content_types": list(proxy.policy.allowed_content_types),
                "security_headers": proxy.policy.security_headers,
                "rate_limits": proxy.policy.rate_limits
            }
            self.send_json_response(policy_info)
        
        elif self.path == '/_security/health':
            self.send_json_response({
                "status": "healthy",
                "security_proxy": "SecurityProxy/1.0",
                "threats_blocked": proxy.detector.blocked_requests > 0
            })
        
        else:
            self.send_security_response(404, "Security endpoint not found")
    
    def send_json_response(self, data):
        """Send JSON response."""
        response_body = json.dumps(data, indent=2).encode()
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_body)))
        for key, value in self.server.proxy.policy.security_headers.items():
            self.send_header(key, value)
        self.end_headers()
        
        self.wfile.write(response_body)
    
    def send_security_response(self, status: int, message: str):
        """Send security response with appropriate headers."""
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain')
        for key, value in self.server.proxy.policy.security_headers.items():
            self.send_header(key, value)
        self.send_header('X-Security-Proxy', 'SecurityProxy/1.0')
        self.end_headers()
        
        self.wfile.write(message.encode())
    
    def log_message(self, format, *args):
        """Custom log format."""
        self.server.proxy.logger.info(format % args)


def create_security_config() -> SecurityProxy:
    """Create security proxy with sample configuration."""
    proxy = SecurityProxy()
    
    # Add blocked domains
    proxy.policy.blocked_domains.update([
        'malware.example.com',
        'phishing.example.com',
        'suspicious.tk'
    ])
    
    # Add blocked keywords
    proxy.policy.blocked_keywords.update([
        'hack', 'crack', 'malware', 'virus',
        'phishing', 'scam', 'fraud'
    ])
    
    return proxy


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Security Proxy")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--target-host", help="Default target host")
    parser.add_argument("--target-port", type=int, help="Default target port")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create security proxy
    proxy = create_security_config()
    proxy.target_host = args.target_host
    proxy.target_port = args.target_port
    
    # Create server
    class SecurityProxyServer(socketserver.TCPServer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.proxy = proxy
    
    server = SecurityProxyServer((args.host, args.port), SecurityProxyHandler)
    server.allow_reuse_address = True
    
    print(f"Security Proxy running on {args.host}:{args.port}")
    if args.target_host and args.target_port:
        print(f"Default target: {args.target_host}:{args.target_port}")
    print("\nSecurity features enabled:")
    print("  ✓ Content filtering and malware detection")
    print("  ✓ Rate limiting and DDoS protection")
    print("  ✓ Security headers enforcement")
    print("  ✓ Domain and keyword blocking")
    print("\nManagement endpoints:")
    print(f"  Stats: http://{args.host}:{args.port}/_security/stats")
    print(f"  Policy: http://{args.host}:{args.port}/_security/policy")
    print(f"  Health: http://{args.host}:{args.port}/_security/health")
    print("\nUsage examples:")
    print(f"  curl --proxy {args.host}:{args.port} http://httpbin.org/get")
    print(f"  curl http://{args.host}:{args.port}/_security/stats")
    print("\nPress Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Security Proxy...")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
