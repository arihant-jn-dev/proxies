#!/usr/bin/env python3
"""
Simple Reverse Proxy Demo

A basic HTTP reverse proxy that forwards requests to backend servers.
"""

import asyncio
import aiohttp
import argparse
import logging
from aiohttp import web

class SimpleReverseProxy:
    """Simple reverse proxy implementation."""
    
    def __init__(self, backend_url, host='localhost', port=8081):
        self.backend_url = backend_url.rstrip('/')
        self.host = host
        self.port = port
        self.logger = logging.getLogger('reverse-proxy')
        self.session = None
    
    async def start(self):
        """Start the reverse proxy."""
        # Create HTTP client session
        self.session = aiohttp.ClientSession()
        
        # Create web application
        app = web.Application()
        app.router.add_route('*', '/{path:.*}', self.handle_request)
        
        # Add health endpoint
        app.router.add_get('/_proxy/health', self.health_check)
        
        # Start server
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        self.logger.info(f"Reverse proxy started on {self.host}:{self.port}")
        self.logger.info(f"Backend: {self.backend_url}")
        
        return runner
    
    async def handle_request(self, request):
        """Handle incoming requests and forward to backend."""
        try:
            # Build backend URL
            backend_url = self.backend_url + request.path_qs
            
            # Prepare headers
            headers = dict(request.headers)
            headers.pop('host', None)  # Remove original host header
            
            # Add proxy headers
            headers['X-Forwarded-For'] = request.remote
            headers['X-Forwarded-Proto'] = request.scheme
            headers['X-Proxy'] = 'SimpleReverseProxy/1.0'
            
            # Read request body
            body = await request.read() if request.can_read_body else None
            
            self.logger.info(f"{request.method} {request.path} -> {backend_url}")
            
            # Forward request to backend
            async with self.session.request(
                method=request.method,
                url=backend_url,
                headers=headers,
                data=body,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                # Prepare response headers
                resp_headers = dict(response.headers)
                resp_headers['X-Proxy'] = 'SimpleReverseProxy/1.0'
                
                # Read response content
                content = await response.read()
                
                return web.Response(
                    body=content,
                    status=response.status,
                    headers=resp_headers
                )
                
        except Exception as e:
            self.logger.error(f"Error forwarding request: {e}")
            return web.Response(
                status=502,
                text=f"Bad Gateway: {str(e)}"
            )
    
    async def health_check(self, request):
        """Health check endpoint."""
        return web.json_response({
            "status": "healthy",
            "backend": self.backend_url,
            "proxy": "SimpleReverseProxy/1.0"
        })
    
    async def stop(self):
        """Stop the reverse proxy."""
        if self.session:
            await self.session.close()

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Simple Reverse Proxy")
    parser.add_argument("--port", type=int, default=8081, help="Port to bind to")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--backend", default="http://httpbin.org", help="Backend server URL")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    proxy = SimpleReverseProxy(args.backend, args.host, args.port)
    
    try:
        runner = await proxy.start()
        
        print(f"Reverse proxy running on {args.host}:{args.port}")
        print(f"Backend: {args.backend}")
        print(f"Health check: http://{args.host}:{args.port}/_proxy/health")
        print("Press Ctrl+C to stop")
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\nProxy stopped by user")
    finally:
        await proxy.stop()
        if 'runner' in locals():
            await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
