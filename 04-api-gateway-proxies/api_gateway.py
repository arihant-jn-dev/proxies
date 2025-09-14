#!/usr/bin/env python3
"""
API Gateway Proxy Implementation

An API gateway that provides:
- Request routing based on paths and methods
- Rate limiting per client/API key
- Authentication and authorization
- Request/response transformation
- API versioning
- Circuit breaker pattern
- Request/response logging
"""

import asyncio
import json
import logging
import time
import hashlib
import re
from collections import defaultdict, deque
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import urllib.request
import urllib.parse
import http.server
import socketserver


@dataclass
class APIEndpoint:
    """Represents an API endpoint configuration."""
    path_pattern: str  # regex pattern for matching paths
    backend_url: str
    methods: List[str] = None  # allowed HTTP methods
    rate_limit: int = 100  # requests per minute
    auth_required: bool = False
    version: str = "v1"
    transform_request: Callable = None
    transform_response: Callable = None


@dataclass
class APIKey:
    """Represents an API key with permissions."""
    key: str
    name: str
    rate_limit: int = 1000  # requests per hour
    allowed_endpoints: List[str] = None  # endpoint patterns
    created_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self):
        # Track requests per client/API key
        self.requests = defaultdict(deque)  # client_id -> deque of timestamps
        self.buckets = {}  # client_id -> token count
    
    def is_allowed(self, client_id: str, limit: int, window: int = 60) -> bool:
        """Check if request is allowed within rate limit."""
        now = time.time()
        
        # Clean old requests outside window
        if client_id in self.requests:
            while (self.requests[client_id] and 
                   self.requests[client_id][0] < now - window):
                self.requests[client_id].popleft()
        
        # Check if under limit
        if len(self.requests[client_id]) < limit:
            self.requests[client_id].append(now)
            return True
        
        return False
    
    def get_stats(self, client_id: str) -> Dict:
        """Get rate limit stats for client."""
        now = time.time()
        recent_requests = [
            req for req in self.requests.get(client_id, [])
            if req > now - 60  # last minute
        ]
        
        return {
            "client_id": client_id,
            "requests_last_minute": len(recent_requests),
            "last_request": max(recent_requests) if recent_requests else None
        }


class CircuitBreaker:
    """Circuit breaker pattern for backend failures."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = defaultdict(int)  # backend -> failure count
        self.last_failure = defaultdict(float)  # backend -> timestamp
        self.state = defaultdict(str)  # backend -> state (closed/open/half-open)
    
    def call_allowed(self, backend: str) -> bool:
        """Check if call to backend is allowed."""
        now = time.time()
        
        if self.state[backend] == "open":
            # Check if timeout period has passed
            if now - self.last_failure[backend] > self.timeout:
                self.state[backend] = "half-open"
                return True
            return False
        
        return True  # closed or half-open
    
    def record_success(self, backend: str):
        """Record successful request."""
        self.failures[backend] = 0
        self.state[backend] = "closed"
    
    def record_failure(self, backend: str):
        """Record failed request."""
        self.failures[backend] += 1
        self.last_failure[backend] = time.time()
        
        if self.failures[backend] >= self.failure_threshold:
            self.state[backend] = "open"
    
    def get_state(self, backend: str) -> str:
        """Get current circuit breaker state."""
        return self.state.get(backend, "closed")


class APIGateway:
    """API Gateway with routing, rate limiting, and authentication."""
    
    def __init__(self):
        self.endpoints: List[APIEndpoint] = []
        self.api_keys: Dict[str, APIKey] = {}
        self.rate_limiter = RateLimiter()
        self.circuit_breaker = CircuitBreaker()
        self.logger = logging.getLogger("api_gateway")
        
        # Request/response statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "rate_limited": 0,
            "unauthorized": 0,
            "circuit_breaker_open": 0
        }
    
    def add_endpoint(self, endpoint: APIEndpoint):
        """Add API endpoint configuration."""
        self.endpoints.append(endpoint)
        self.logger.info(f"Added endpoint: {endpoint.path_pattern} -> {endpoint.backend_url}")
    
    def add_api_key(self, api_key: APIKey):
        """Add API key."""
        self.api_keys[api_key.key] = api_key
        self.logger.info(f"Added API key: {api_key.name}")
    
    def find_endpoint(self, path: str, method: str) -> Optional[APIEndpoint]:
        """Find matching endpoint for request."""
        for endpoint in self.endpoints:
            if re.match(endpoint.path_pattern, path):
                if endpoint.methods is None or method in endpoint.methods:
                    return endpoint
        return None
    
    def authenticate(self, request_headers: Dict[str, str]) -> Optional[APIKey]:
        """Authenticate request using API key."""
        auth_header = request_headers.get('authorization', '')
        api_key_header = request_headers.get('x-api-key', '')
        
        # Check Authorization header (Bearer token)
        if auth_header.startswith('Bearer '):
            api_key = auth_header[7:]  # Remove "Bearer "
            return self.api_keys.get(api_key)
        
        # Check X-API-Key header
        if api_key_header:
            return self.api_keys.get(api_key_header)
        
        return None
    
    def check_rate_limit(self, client_id: str, limit: int) -> bool:
        """Check if request is within rate limit."""
        return self.rate_limiter.is_allowed(client_id, limit)
    
    def transform_request(self, endpoint: APIEndpoint, headers: Dict, body: bytes) -> tuple:
        """Apply request transformations."""
        if endpoint.transform_request:
            return endpoint.transform_request(headers, body)
        return headers, body
    
    def transform_response(self, endpoint: APIEndpoint, headers: Dict, body: bytes) -> tuple:
        """Apply response transformations."""
        if endpoint.transform_response:
            return endpoint.transform_response(headers, body)
        return headers, body


class APIGatewayHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for API Gateway."""
    
    def do_GET(self):
        self.handle_request()
    
    def do_POST(self):
        self.handle_request()
    
    def do_PUT(self):
        self.handle_request()
    
    def do_DELETE(self):
        self.handle_request()
    
    def handle_request(self):
        """Handle incoming API request."""
        gateway = self.server.gateway
        gateway.stats["total_requests"] += 1
        
        # Parse request
        path = self.path
        method = self.command
        headers = dict(self.headers)
        
        # Read body
        body = b""
        if 'content-length' in headers:
            content_length = int(headers['content-length'])
            body = self.rfile.read(content_length)
        
        # Log request
        client_ip = self.client_address[0]
        gateway.logger.info(f"{method} {path} from {client_ip}")
        
        # Handle management endpoints
        if path.startswith('/_gateway/'):
            self.handle_management_endpoint(path)
            return
        
        # Find matching endpoint
        endpoint = gateway.find_endpoint(path, method)
        if not endpoint:
            self.send_error_response(404, "Endpoint not found")
            return
        
        # Authenticate if required
        api_key = None
        if endpoint.auth_required:
            api_key = gateway.authenticate(headers)
            if not api_key:
                gateway.stats["unauthorized"] += 1
                self.send_error_response(401, "Authentication required")
                return
        
        # Rate limiting
        client_id = api_key.key if api_key else client_ip
        rate_limit = api_key.rate_limit if api_key else endpoint.rate_limit
        
        if not gateway.check_rate_limit(client_id, rate_limit):
            gateway.stats["rate_limited"] += 1
            self.send_error_response(429, "Rate limit exceeded")
            return
        
        # Check circuit breaker
        if not gateway.circuit_breaker.call_allowed(endpoint.backend_url):
            gateway.stats["circuit_breaker_open"] += 1
            self.send_error_response(503, "Service temporarily unavailable")
            return
        
        # Transform request
        headers, body = gateway.transform_request(endpoint, headers, body)
        
        # Forward to backend
        try:
            backend_url = endpoint.backend_url.rstrip('/') + path
            
            # Remove hop-by-hop headers
            headers.pop('host', None)
            headers.pop('connection', None)
            
            # Add gateway headers
            headers['X-Gateway'] = 'APIGateway/1.0'
            headers['X-Client-IP'] = client_ip
            if api_key:
                headers['X-API-Key-Name'] = api_key.name
            
            # Create request
            req = urllib.request.Request(backend_url, data=body, method=method)
            for key, value in headers.items():
                req.add_header(key, value)
            
            # Make request
            with urllib.request.urlopen(req, timeout=30) as response:
                # Read response
                response_body = response.read()
                response_headers = dict(response.headers)
                
                # Transform response
                response_headers, response_body = gateway.transform_response(
                    endpoint, response_headers, response_body
                )
                
                # Send response
                self.send_response(response.status)
                
                # Add gateway headers
                response_headers['X-Gateway'] = 'APIGateway/1.0'
                response_headers['X-Backend'] = endpoint.backend_url
                
                for key, value in response_headers.items():
                    if key.lower() not in ['connection', 'transfer-encoding']:
                        self.send_header(key, value)
                
                self.end_headers()
                self.wfile.write(response_body)
                
                # Record success
                gateway.circuit_breaker.record_success(endpoint.backend_url)
                gateway.stats["successful_requests"] += 1
                
        except Exception as e:
            gateway.circuit_breaker.record_failure(endpoint.backend_url)
            gateway.stats["failed_requests"] += 1
            gateway.logger.error(f"Backend error: {e}")
            self.send_error_response(502, f"Backend error: {str(e)}")
    
    def handle_management_endpoint(self, path: str):
        """Handle gateway management endpoints."""
        gateway = self.server.gateway
        
        if path == '/_gateway/stats':
            self.send_json_response(gateway.stats)
        elif path == '/_gateway/endpoints':
            endpoints = [
                {
                    "pattern": ep.path_pattern,
                    "backend": ep.backend_url,
                    "methods": ep.methods,
                    "rate_limit": ep.rate_limit,
                    "auth_required": ep.auth_required
                }
                for ep in gateway.endpoints
            ]
            self.send_json_response({"endpoints": endpoints})
        elif path == '/_gateway/health':
            healthy_backends = 0
            total_backends = len(gateway.endpoints)
            
            for endpoint in gateway.endpoints:
                if gateway.circuit_breaker.get_state(endpoint.backend_url) == "closed":
                    healthy_backends += 1
            
            self.send_json_response({
                "status": "healthy" if healthy_backends > 0 else "unhealthy",
                "healthy_backends": healthy_backends,
                "total_backends": total_backends
            })
        else:
            self.send_error_response(404, "Management endpoint not found")
    
    def send_json_response(self, data: Any):
        """Send JSON response."""
        response_body = json.dumps(data, indent=2).encode()
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)
    
    def send_error_response(self, status: int, message: str):
        """Send error response."""
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(message.encode())
    
    def log_message(self, format, *args):
        """Custom log format."""
        self.server.gateway.logger.debug(format % args)


def create_sample_config() -> APIGateway:
    """Create sample API gateway configuration."""
    gateway = APIGateway()
    
    # Add endpoints
    gateway.add_endpoint(APIEndpoint(
        path_pattern=r"/api/v1/users.*",
        backend_url="http://jsonplaceholder.typicode.com",
        methods=["GET", "POST"],
        rate_limit=50,
        auth_required=True
    ))
    
    gateway.add_endpoint(APIEndpoint(
        path_pattern=r"/api/v1/posts.*",
        backend_url="http://jsonplaceholder.typicode.com",
        methods=["GET", "POST", "PUT", "DELETE"],
        rate_limit=100,
        auth_required=False
    ))
    
    gateway.add_endpoint(APIEndpoint(
        path_pattern=r"/test.*",
        backend_url="http://httpbin.org",
        methods=None,  # all methods
        rate_limit=200,
        auth_required=False
    ))
    
    # Add API keys
    gateway.add_api_key(APIKey(
        key="demo-key-12345",
        name="Demo Application",
        rate_limit=1000
    ))
    
    gateway.add_api_key(APIKey(
        key="admin-key-67890",
        name="Admin Access",
        rate_limit=5000
    ))
    
    return gateway


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="API Gateway Proxy")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create gateway with sample configuration
    gateway = create_sample_config()
    
    # Create server
    class APIGatewayServer(socketserver.TCPServer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.gateway = gateway
    
    server = APIGatewayServer((args.host, args.port), APIGatewayHandler)
    server.allow_reuse_address = True
    
    print(f"API Gateway running on {args.host}:{args.port}")
    print("\nSample endpoints:")
    print(f"  GET  {args.host}:{args.port}/api/v1/posts (no auth)")
    print(f"  GET  {args.host}:{args.port}/api/v1/users (requires auth)")
    print(f"  GET  {args.host}:{args.port}/test/get (no auth)")
    print("\nManagement endpoints:")
    print(f"  Stats: http://{args.host}:{args.port}/_gateway/stats")
    print(f"  Health: http://{args.host}:{args.port}/_gateway/health")
    print(f"  Endpoints: http://{args.host}:{args.port}/_gateway/endpoints")
    print("\nAPI Keys:")
    print("  demo-key-12345 (Demo Application)")
    print("  admin-key-67890 (Admin Access)")
    print("\nUsage with auth:")
    print(f"  curl -H 'X-API-Key: demo-key-12345' http://{args.host}:{args.port}/api/v1/users")
    print("\nPress Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down API Gateway...")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
