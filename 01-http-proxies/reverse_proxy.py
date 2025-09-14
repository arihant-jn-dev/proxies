#!/usr/bin/env python3
"""
HTTP Reverse Proxy Implementation

A reverse proxy sits in front of web servers and forwards client requests
to backend servers. It acts on behalf of the server, not the client.

Features:
- Load balancing across multiple backends
- Health checking
- SSL termination
- Request/response modification
- Caching capabilities
- Rate limiting

Usage:
    python reverse_proxy.py --port 8080 --backend http://localhost:3000
"""

import argparse
import asyncio
import json
import logging
import random
import sys
import time
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from aiohttp import web, ClientSession, ClientError
from aiohttp.web import Request, Response

# Add parent directory to path for common utilities
sys.path.append('../common')
from utils import ProxyLogger, PerformanceMonitor, ConfigManager


class BackendServer:
    """Represents a backend server with health status."""
    
    def __init__(self, url: str, weight: int = 1):
        self.url = url.rstrip('/')
        self.weight = weight
        self.healthy = True
        self.last_check = 0
        self.response_times = []
        self.error_count = 0
        
        parsed = urlparse(url)
        self.host = parsed.hostname
        self.port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        self.scheme = parsed.scheme
    
    def record_response_time(self, response_time: float):
        """Record a response time for this backend."""
        self.response_times.append(response_time)
        # Keep only last 100 response times
        if len(self.response_times) > 100:
            self.response_times.pop(0)
    
    def record_error(self):
        """Record an error for this backend."""
        self.error_count += 1
    
    def get_avg_response_time(self) -> float:
        """Get average response time."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def __str__(self):
        return f"Backend({self.url}, healthy={self.healthy}, weight={self.weight})"


class LoadBalancer:
    """Load balancer with multiple algorithms."""
    
    def __init__(self, algorithm: str = "round_robin"):
        self.algorithm = algorithm
        self.backends: List[BackendServer] = []
        self.current_index = 0
    
    def add_backend(self, backend: BackendServer):
        """Add a backend server."""
        self.backends.append(backend)
    
    def get_healthy_backends(self) -> List[BackendServer]:
        """Get list of healthy backends."""
        return [b for b in self.backends if b.healthy]
    
    def select_backend(self) -> Optional[BackendServer]:
        """Select a backend using the configured algorithm."""
        healthy_backends = self.get_healthy_backends()
        if not healthy_backends:
            return None
        
        if self.algorithm == "round_robin":
            return self._round_robin(healthy_backends)
        elif self.algorithm == "least_connections":
            return self._least_connections(healthy_backends)
        elif self.algorithm == "weighted_round_robin":
            return self._weighted_round_robin(healthy_backends)
        elif self.algorithm == "random":
            return random.choice(healthy_backends)
        else:
            return healthy_backends[0]
    
    def _round_robin(self, backends: List[BackendServer]) -> BackendServer:
        """Round-robin selection."""
        backend = backends[self.current_index % len(backends)]
        self.current_index += 1
        return backend
    
    def _least_connections(self, backends: List[BackendServer]) -> BackendServer:
        """Select backend with fastest average response time."""
        return min(backends, key=lambda b: b.get_avg_response_time())
    
    def _weighted_round_robin(self, backends: List[BackendServer]) -> BackendServer:
        """Weighted round-robin selection."""
        total_weight = sum(b.weight for b in backends)
        random_weight = random.randint(1, total_weight)
        
        current_weight = 0
        for backend in backends:
            current_weight += backend.weight
            if random_weight <= current_weight:
                return backend
        
        return backends[0]


class HTTPReverseProxy:
    """HTTP Reverse Proxy server implementation."""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.logger = ProxyLogger("reverse-proxy", 
                                 getattr(logging, config.get("log_level", "INFO")))
        self.monitor = PerformanceMonitor()
        self.session: Optional[ClientSession] = None
        
        # Load balancer setup
        algorithm = config.get("load_balancer_algorithm", "round_robin")
        self.load_balancer = LoadBalancer(algorithm)
        
        # Initialize backends
        backend_urls = config.get("backend_servers", [])
        for url in backend_urls:
            backend = BackendServer(url)
            self.load_balancer.add_backend(backend)
        
        # Health check settings
        self.health_check_enabled = config.get("health_check_enabled", True)
        self.health_check_interval = config.get("health_check_interval", 30)
        self.health_check_path = config.get("health_check_path", "/health")
        
        # Rate limiting
        self.rate_limit_enabled = config.get("rate_limit_enabled", False)
        self.rate_limit_requests = config.get("rate_limit_requests", 100)
        self.rate_limit_window = config.get("rate_limit_window", 60)
        self.client_requests = {}  # Track requests per client
        
        # Request modification
        self.add_headers = config.get("add_headers", {})
        self.remove_headers = config.get("remove_headers", [])
    
    async def start(self):
        """Start the reverse proxy server."""
        # Create HTTP client session
        connector = aiohttp.TCPConnector(
            limit=self.config.get("max_connections", 100),
            limit_per_host=30,
            ttl_dns_cache=300,
            use_dns_cache=True
        )
        
        timeout = aiohttp.ClientTimeout(
            total=self.config.get("timeout_seconds", 30)
        )
        
        self.session = ClientSession(
            connector=connector,
            timeout=timeout
        )
        
        # Start health checks
        if self.health_check_enabled:
            asyncio.create_task(self.health_check_loop())
        
        # Create web application
        app = web.Application()
        
        # Add middleware
        app.middlewares.append(self.logging_middleware)
        if self.rate_limit_enabled:
            app.middlewares.append(self.rate_limit_middleware)
        
        # Add routes
        app.router.add_route('*', '/{path:.*}', self.handle_request)
        
        # Add health endpoint for the proxy itself
        app.router.add_get('/_proxy/health', self.proxy_health)
        app.router.add_get('/_proxy/stats', self.proxy_stats)
        
        # Start server
        host = self.config.get("bind_host", "0.0.0.0")
        port = self.config.get("bind_port", 8080)
        
        self.logger.logger.info(f"Starting HTTP Reverse Proxy on {host}:{port}")
        self.logger.logger.info(f"Backend servers: {[b.url for b in self.load_balancer.backends]}")
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        self.logger.logger.info("Reverse proxy started successfully")
        return runner
    
    async def stop(self):
        """Stop the reverse proxy server."""
        if self.session:
            await self.session.close()
    
    @web.middleware
    async def logging_middleware(self, request: Request, handler):
        """Middleware to log requests and responses."""
        start_time = time.time()
        
        try:
            response = await handler(request)
            duration = (time.time() - start_time) * 1000
            
            self.logger.request(request.method, str(request.url), request.remote)
            self.logger.response(response.status, str(request.url), duration)
            
            return response
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            self.logger.error(f"Request failed: {str(e)}")
            raise
    
    @web.middleware
    async def rate_limit_middleware(self, request: Request, handler):
        """Middleware to implement rate limiting."""
        client_ip = request.remote
        current_time = time.time()
        
        # Clean old entries
        cutoff_time = current_time - self.rate_limit_window
        if client_ip in self.client_requests:
            self.client_requests[client_ip] = [
                req_time for req_time in self.client_requests[client_ip]
                if req_time > cutoff_time
            ]
        else:
            self.client_requests[client_ip] = []
        
        # Check rate limit
        if len(self.client_requests[client_ip]) >= self.rate_limit_requests:
            self.logger.error(f"Rate limit exceeded for {client_ip}")
            return web.Response(
                status=429,
                text="Too Many Requests",
                headers={"Retry-After": str(self.rate_limit_window)}
            )
        
        # Record this request
        self.client_requests[client_ip].append(current_time)
        
        return await handler(request)
    
    async def handle_request(self, request: Request) -> Response:
        """Handle incoming requests and forward to backend."""
        start_time = time.time()
        
        # Select backend server
        backend = self.load_balancer.select_backend()
        if not backend:
            self.logger.error("No healthy backend servers available")
            self.monitor.record_request(False, (time.time() - start_time) * 1000)
            return web.Response(status=503, text="Service Unavailable")
        
        try:
            # Build backend URL
            backend_url = backend.url + request.path_qs
            
            # Prepare headers
            headers = dict(request.headers)
            
            # Remove hop-by-hop headers
            hop_by_hop = {'connection', 'keep-alive', 'proxy-authenticate',
                         'proxy-authorization', 'te', 'trailers', 'upgrade'}
            for header in hop_by_hop:
                headers.pop(header, None)
            
            # Add/remove custom headers
            for key, value in self.add_headers.items():
                headers[key] = value
            
            for header in self.remove_headers:
                headers.pop(header, None)
            
            # Add forwarding headers
            headers['X-Forwarded-For'] = request.remote
            headers['X-Forwarded-Proto'] = request.scheme
            headers['X-Forwarded-Host'] = request.host
            
            # Read request body
            body = None
            if request.can_read_body:
                body = await request.read()
            
            # Forward request to backend
            async with self.session.request(
                method=request.method,
                url=backend_url,
                headers=headers,
                data=body,
                allow_redirects=False
            ) as response:
                
                # Record backend response time
                backend_response_time = (time.time() - start_time) * 1000
                backend.record_response_time(backend_response_time)
                
                # Prepare response headers
                resp_headers = dict(response.headers)
                
                # Remove hop-by-hop headers
                for header in hop_by_hop:
                    resp_headers.pop(header, None)
                
                # Read response content
                content = await response.read()
                
                duration = (time.time() - start_time) * 1000
                self.monitor.record_request(True, duration, len(content))
                
                return web.Response(
                    body=content,
                    status=response.status,
                    headers=resp_headers
                )
        
        except ClientError as e:
            backend.record_error()
            duration = (time.time() - start_time) * 1000
            self.logger.error(f"Backend error ({backend.url}): {str(e)}")
            self.monitor.record_request(False, duration)
            return web.Response(status=502, text=f"Bad Gateway: {str(e)}")
        
        except asyncio.TimeoutError:
            backend.record_error()
            duration = (time.time() - start_time) * 1000
            self.logger.error(f"Backend timeout ({backend.url})")
            self.monitor.record_request(False, duration)
            return web.Response(status=504, text="Gateway Timeout")
        
        except Exception as e:
            backend.record_error()
            duration = (time.time() - start_time) * 1000
            self.logger.error(f"Unexpected error: {str(e)}")
            self.monitor.record_request(False, duration)
            return web.Response(status=500, text="Internal Server Error")
    
    async def health_check_loop(self):
        """Periodically check backend health."""
        while True:
            await asyncio.sleep(self.health_check_interval)
            await self.check_backend_health()
    
    async def check_backend_health(self):
        """Check health of all backend servers."""
        for backend in self.load_balancer.backends:
            try:
                health_url = backend.url + self.health_check_path
                async with self.session.get(health_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        if not backend.healthy:
                            self.logger.logger.info(f"Backend {backend.url} is now healthy")
                        backend.healthy = True
                    else:
                        if backend.healthy:
                            self.logger.logger.warning(f"Backend {backend.url} health check failed: {response.status}")
                        backend.healthy = False
            except Exception as e:
                if backend.healthy:
                    self.logger.logger.warning(f"Backend {backend.url} health check failed: {str(e)}")
                backend.healthy = False
            
            backend.last_check = time.time()
    
    async def proxy_health(self, request: Request) -> Response:
        """Health endpoint for the proxy itself."""
        healthy_backends = self.load_balancer.get_healthy_backends()
        total_backends = len(self.load_balancer.backends)
        
        health_data = {
            "status": "healthy" if healthy_backends else "unhealthy",
            "backends": {
                "total": total_backends,
                "healthy": len(healthy_backends),
                "unhealthy": total_backends - len(healthy_backends)
            },
            "timestamp": time.time()
        }
        
        status = 200 if healthy_backends else 503
        return web.json_response(health_data, status=status)
    
    async def proxy_stats(self, request: Request) -> Response:
        """Statistics endpoint for the proxy."""
        stats = self.monitor.get_stats()
        
        # Add backend information
        backend_stats = []
        for backend in self.load_balancer.backends:
            backend_stats.append({
                "url": backend.url,
                "healthy": backend.healthy,
                "weight": backend.weight,
                "avg_response_time_ms": backend.get_avg_response_time(),
                "error_count": backend.error_count,
                "last_check": backend.last_check
            })
        
        stats["backends"] = backend_stats
        stats["load_balancer_algorithm"] = self.load_balancer.algorithm
        
        return web.json_response(stats)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="HTTP Reverse Proxy Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--backend", action="append", help="Backend server URL(s)")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--log-level", default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--algorithm", default="round_robin",
                       choices=["round_robin", "least_connections", "weighted_round_robin", "random"],
                       help="Load balancing algorithm")
    
    args = parser.parse_args()
    
    # Load configuration
    config = ConfigManager(args.config) if args.config else ConfigManager()
    config.set("bind_host", args.host)
    config.set("bind_port", args.port)
    config.set("log_level", args.log_level)
    config.set("load_balancer_algorithm", args.algorithm)
    
    # Set backend servers
    if args.backend:
        config.set("backend_servers", args.backend)
    elif not config.get("backend_servers"):
        config.set("backend_servers", ["http://localhost:3000"])
    
    # Example configuration
    config.set("health_check_enabled", True)
    config.set("health_check_interval", 30)
    config.set("rate_limit_enabled", False)
    config.set("add_headers", {"X-Proxy": "HTTPReverseProxy/1.0"})
    config.set("remove_headers", ["Server"])
    
    proxy = HTTPReverseProxy(config)
    
    try:
        runner = await proxy.start()
        
        print(f"HTTP Reverse Proxy running on {args.host}:{args.port}")
        print(f"Backend servers: {config.get('backend_servers')}")
        print(f"Load balancing: {args.algorithm}")
        print("\nEndpoints:")
        print(f"  Health: http://{args.host}:{args.port}/_proxy/health")
        print(f"  Stats:  http://{args.host}:{args.port}/_proxy/stats")
        print("\nPress Ctrl+C to stop")
        
        # Keep server running
        while True:
            await asyncio.sleep(10)
            
            # Print basic stats
            stats = proxy.monitor.get_stats()
            if stats['requests_total'] > 0:
                print(f"Stats: {stats['requests_total']} requests, "
                      f"{stats['success_rate']:.1f}% success, "
                      f"{stats['avg_response_time_ms']:.1f}ms avg")
    
    except KeyboardInterrupt:
        print("\nShutting down proxy...")
    finally:
        await proxy.stop()
        if 'runner' in locals():
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
