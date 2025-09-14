#!/usr/bin/env python3
"""
HTTP Forward Proxy Implementation

A forward proxy sits between clients and the internet, forwarding requests
on behalf of clients. Clients configure their HTTP client to use this proxy.

Features:
- HTTP/HTTPS support
- Request/response logging
- Basic authentication
- Content filtering capabilities
- Connection pooling

Usage:
    python forward_proxy.py --port 8080 --log-level DEBUG
"""

import argparse
import asyncio
import json
import logging
import ssl
import sys
import time
from typing import Dict, Optional
from urllib.parse import urlparse, urlunparse

import aiohttp
from aiohttp import web, ClientSession, ClientError
from aiohttp.web import Request, Response, StreamResponse

# Add parent directory to path for common utilities
sys.path.append('../common')
from utils import ProxyLogger, PerformanceMonitor, ConfigManager, NetworkUtils


class HTTPForwardProxy:
    """HTTP Forward Proxy server implementation."""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.logger = ProxyLogger("forward-proxy", 
                                 getattr(logging, config.get("log_level", "INFO")))
        self.monitor = PerformanceMonitor()
        self.session: Optional[ClientSession] = None
        
        # Track active connections
        self.active_connections = 0
        
        # Basic authentication (if enabled)
        self.auth_enabled = config.get("auth_enabled", False)
        self.auth_users = config.get("auth_users", {})
        
        # Content filtering
        self.blocked_domains = set(config.get("blocked_domains", []))
        self.blocked_keywords = set(config.get("blocked_keywords", []))
    
    async def start(self):
        """Start the proxy server."""
        # Create HTTP client session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=self.config.get("max_connections", 100),
            limit_per_host=self.config.get("max_connections_per_host", 30),
            ttl_dns_cache=300,
            use_dns_cache=True
        )
        
        timeout = aiohttp.ClientTimeout(
            total=self.config.get("timeout_seconds", 30)
        )
        
        self.session = ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'HTTPForwardProxy/1.0'}
        )
        
        # Create web application
        app = web.Application()
        
        # Add routes for different HTTP methods
        app.router.add_route('*', '/{path:.*}', self.handle_request)
        
        # Add CONNECT method handler for HTTPS tunneling
        app.router.add_route('CONNECT', '/{path:.*}', self.handle_connect)
        
        # Start server
        host = self.config.get("bind_host", "0.0.0.0")
        port = self.config.get("bind_port", 8080)
        
        self.logger.logger.info(f"Starting HTTP Forward Proxy on {host}:{port}")
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        self.logger.logger.info("Forward proxy started successfully")
        return runner
    
    async def stop(self):
        """Stop the proxy server."""
        if self.session:
            await self.session.close()
    
    def check_authentication(self, request: Request) -> bool:
        """Check if request has valid authentication."""
        if not self.auth_enabled:
            return True
        
        auth_header = request.headers.get('Proxy-Authorization', '')
        if not auth_header.startswith('Basic '):
            return False
        
        try:
            import base64
            credentials = base64.b64decode(auth_header[6:]).decode('utf-8')
            username, password = credentials.split(':', 1)
            return self.auth_users.get(username) == password
        except Exception:
            return False
    
    def is_request_blocked(self, url: str) -> tuple[bool, str]:
        """Check if request should be blocked."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Check blocked domains
        for blocked_domain in self.blocked_domains:
            if blocked_domain in domain:
                return True, f"Domain {domain} is blocked"
        
        # Check blocked keywords in URL
        full_url = url.lower()
        for keyword in self.blocked_keywords:
            if keyword in full_url:
                return True, f"URL contains blocked keyword: {keyword}"
        
        return False, ""
    
    async def handle_request(self, request: Request) -> Response:
        """Handle HTTP requests (GET, POST, PUT, DELETE, etc.)."""
        start_time = time.time()
        client_ip = request.remote
        
        # Check authentication
        if not self.check_authentication(request):
            self.logger.error("Authentication failed", client_ip)
            return web.Response(
                status=407,
                text="Proxy Authentication Required",
                headers={"Proxy-Authenticate": "Basic realm='Proxy'"}
            )
        
        # Build target URL
        target_url = str(request.url)
        if not target_url.startswith(('http://', 'https://')):
            # Handle relative URLs by reconstructing from headers
            host = request.headers.get('Host')
            if host:
                scheme = 'https' if request.secure else 'http'
                target_url = f"{scheme}://{host}{request.path_qs}"
            else:
                return web.Response(status=400, text="Bad Request: Invalid URL")
        
        self.logger.request(request.method, target_url, client_ip)
        
        # Check if request is blocked
        is_blocked, block_reason = self.is_request_blocked(target_url)
        if is_blocked:
            self.logger.error(f"Request blocked: {block_reason}")
            duration = (time.time() - start_time) * 1000
            self.monitor.record_request(False, duration)
            return web.Response(status=403, text=f"Forbidden: {block_reason}")
        
        try:
            self.active_connections += 1
            
            # Prepare headers (remove hop-by-hop headers)
            headers = dict(request.headers)
            hop_by_hop_headers = {
                'connection', 'keep-alive', 'proxy-authenticate',
                'proxy-authorization', 'te', 'trailers', 'upgrade'
            }
            for header in hop_by_hop_headers:
                headers.pop(header, None)
            
            # Add forwarded headers
            headers['X-Forwarded-For'] = client_ip
            headers['X-Forwarded-Proto'] = request.scheme
            
            # Read request body
            body = None
            if request.can_read_body:
                body = await request.read()
            
            # Make request to target server
            async with self.session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=body,
                allow_redirects=False
            ) as response:
                
                # Create response
                resp_headers = dict(response.headers)
                
                # Remove hop-by-hop headers from response
                for header in hop_by_hop_headers:
                    resp_headers.pop(header, None)
                
                # Create streaming response for large content
                if int(resp_headers.get('content-length', 0)) > 1024 * 1024:  # 1MB
                    return await self.stream_response(response, resp_headers)
                else:
                    content = await response.read()
                    
                    duration = (time.time() - start_time) * 1000
                    self.logger.response(response.status, target_url, duration)
                    self.monitor.record_request(True, duration, len(content))
                    
                    return web.Response(
                        body=content,
                        status=response.status,
                        headers=resp_headers
                    )
        
        except ClientError as e:
            duration = (time.time() - start_time) * 1000
            self.logger.error(f"Client error: {str(e)}")
            self.monitor.record_request(False, duration)
            return web.Response(status=502, text=f"Bad Gateway: {str(e)}")
        
        except asyncio.TimeoutError:
            duration = (time.time() - start_time) * 1000
            self.logger.error("Request timeout")
            self.monitor.record_request(False, duration)
            return web.Response(status=504, text="Gateway Timeout")
        
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            self.logger.error(f"Unexpected error: {str(e)}")
            self.monitor.record_request(False, duration)
            return web.Response(status=500, text="Internal Server Error")
        
        finally:
            self.active_connections -= 1
    
    async def stream_response(self, response, headers) -> StreamResponse:
        """Stream large responses to avoid memory issues."""
        stream_response = web.StreamResponse(
            status=response.status,
            headers=headers
        )
        
        await stream_response.prepare()
        
        async for chunk in response.content.iter_chunked(8192):
            await stream_response.write(chunk)
        
        return stream_response
    
    async def handle_connect(self, request: Request) -> Response:
        """Handle CONNECT method for HTTPS tunneling."""
        # CONNECT method is used for HTTPS tunneling
        # This is a simplified implementation
        
        if not self.check_authentication(request):
            return web.Response(
                status=407,
                text="Proxy Authentication Required",
                headers={"Proxy-Authenticate": "Basic realm='Proxy'"}
            )
        
        target = request.path.lstrip('/')
        self.logger.request("CONNECT", target, request.remote)
        
        try:
            host, port = target.split(':')
            port = int(port)
        except ValueError:
            return web.Response(status=400, text="Bad Request: Invalid CONNECT target")
        
        # Check if HTTPS tunneling is blocked
        is_blocked, block_reason = self.is_request_blocked(f"https://{target}")
        if is_blocked:
            self.logger.error(f"CONNECT blocked: {block_reason}")
            return web.Response(status=403, text=f"Forbidden: {block_reason}")
        
        # For simplicity, we'll reject CONNECT requests
        # Full HTTPS tunneling requires more complex implementation
        return web.Response(
            status=501,
            text="CONNECT method not implemented in this example"
        )
    
    def get_stats(self) -> Dict:
        """Get proxy statistics."""
        stats = self.monitor.get_stats()
        stats.update({
            "active_connections": self.active_connections,
            "blocked_domains": len(self.blocked_domains),
            "blocked_keywords": len(self.blocked_keywords),
            "auth_enabled": self.auth_enabled
        })
        return stats


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="HTTP Forward Proxy Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--log-level", default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Load configuration
    config = ConfigManager(args.config) if args.config else ConfigManager()
    config.set("bind_host", args.host)
    config.set("bind_port", args.port)
    config.set("log_level", args.log_level)
    
    # Example configuration for testing
    config.set("blocked_domains", ["example-blocked.com", "malware.example"])
    config.set("blocked_keywords", ["malware", "phishing"])
    config.set("auth_enabled", False)  # Set to True to require authentication
    config.set("auth_users", {"user": "password", "admin": "secret"})
    
    proxy = HTTPForwardProxy(config)
    
    try:
        runner = await proxy.start()
        
        print(f"HTTP Forward Proxy running on {args.host}:{args.port}")
        print("\nUsage examples:")
        print(f"  curl -x http://{args.host}:{args.port} http://httpbin.org/ip")
        print(f"  curl -x http://{args.host}:{args.port} http://httpbin.org/headers")
        print("\nTo test blocking:")
        print(f"  curl -x http://{args.host}:{args.port} http://example-blocked.com")
        print("\nPress Ctrl+C to stop")
        
        # Keep server running
        while True:
            await asyncio.sleep(1)
            
            # Print stats every 30 seconds
            if int(time.time()) % 30 == 0:
                stats = proxy.get_stats()
                print(f"\nProxy Stats: {stats['requests_total']} requests, "
                      f"{stats['success_rate']:.1f}% success rate, "
                      f"{stats['active_connections']} active connections")
    
    except KeyboardInterrupt:
        print("\nShutting down proxy...")
    finally:
        await proxy.stop()
        if 'runner' in locals():
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
