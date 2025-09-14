#!/usr/bin/env python3
"""
Advanced Load Balancer Proxy Implementation

🎯 MAIN PURPOSE:
A comprehensive load balancer with multiple algorithms, health checking, and advanced features
for production-grade load balancing scenarios.

🔍 WHAT WE'RE TRYING TO ACCOMPLISH:
1. **Enterprise-Grade Load Balancing**: Multiple algorithms for different scenarios
2. **Intelligent Health Monitoring**: Automatic detection and recovery of failed servers
3. **Session Affinity**: Keep users connected to the same backend (sticky sessions)
4. **Advanced Analytics**: Detailed metrics and performance monitoring
5. **Dynamic Configuration**: Runtime algorithm changes and server management
6. **Production Reliability**: Robust error handling and failover mechanisms

📊 REAL-WORLD USE CASES:

1. **High-Traffic Web Applications**:
   - Netflix, YouTube: Video streaming with global load distribution
   - Amazon, eBay: E-commerce platforms handling millions of transactions
   - Facebook, Twitter: Social media with complex user interactions
   - Banking systems: Financial applications requiring session persistence

2. **Microservices Architecture**:
   - Kubernetes ingress controllers distributing container traffic
   - API gateways routing requests to appropriate microservices
   - Service mesh implementations (Istio, Linkerd)
   - Container orchestration platforms

3. **Database Load Balancing**:
   - MySQL, PostgreSQL read replica distribution
   - MongoDB sharded cluster access
   - Redis cluster connection pooling
   - Database connection load balancing

4. **Enterprise Applications**:
   - SAP, Oracle applications with multiple app servers
   - Microsoft Exchange email server load balancing
   - Citrix virtual desktop infrastructure
   - Corporate intranet applications

🧪 TESTING EXAMPLES:

# 1. Start with multiple algorithms:
python3 load_balancer.py --port 8083 \
  --backends http://httpbin.org http://jsonplaceholder.typicode.com \
  --weights 2 1 \
  --algorithm least_connections

# 2. Test different algorithms:
curl -X POST http://localhost:8083/_lb/algorithm/round_robin
curl -X POST http://localhost:8083/_lb/algorithm/weighted
curl -X POST http://localhost:8083/_lb/algorithm/least_connections
curl -X POST http://localhost:8083/_lb/algorithm/random

# 3. Monitor real-time statistics:
curl http://localhost:8083/_lb/stats | jq '.'
curl http://localhost:8083/_lb/health | jq '.'

# 4. Test sticky sessions:
# Same client IP will be routed to same backend
for i in {1..5}; do
  curl http://localhost:8083/get
done

# 5. Load testing:
# Use multiple concurrent connections to see load distribution
ab -n 1000 -c 10 http://localhost:8083/get

🏗️ ADVANCED FEATURES:

1. **Multiple Load Balancing Algorithms**:
   - Round Robin: Even distribution across all servers
   - Weighted: Distribute based on server capacity weights  
   - Least Connections: Route to server with fewest active connections
   - Random: Random selection for stateless applications

2. **Health Monitoring**:
   - Automatic health checks every 30 seconds
   - Remove failed servers from rotation
   - Automatic recovery when servers come back online
   - Response time monitoring and alerting

3. **Session Affinity (Sticky Sessions)**:
   - Client IP based session persistence
   - Important for applications with server-side state
   - Automatic failover if preferred server fails

4. **Advanced Metrics**:
   - Per-backend request counts and success rates
   - Response time monitoring
   - Active connection tracking
   - Health check status and history

5. **Runtime Management**:
   - Change algorithms without restart
   - View real-time statistics
   - Monitor backend health status
   - Performance analytics

💡 PRODUCTION CONSIDERATIONS:
- SSL termination and certificate management
- Rate limiting and DDoS protection  
- Geographic load balancing
- Auto-scaling integration
- Monitoring and alerting systems

A comprehensive load balancer with multiple algorithms and health checking.
This implementation provides:
- Round Robin load balancing
- Weighted Round Robin
- Least Connections algorithm
- Health monitoring of backend servers
- Session affinity (sticky sessions)
"""

import asyncio
import aiohttp
import hashlib
import json
import logging
import random
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple
from aiohttp import web
from dataclasses import dataclass


@dataclass
class BackendServer:
    """Represents a backend server with health and load information."""
    url: str
    weight: int = 1
    active_connections: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    last_health_check: float = 0
    is_healthy: bool = True
    response_time: float = 0.0


class LoadBalancer:
    """Advanced load balancer with multiple algorithms."""
    
    def __init__(self):
        self.backends: List[BackendServer] = []
        self.algorithm = "round_robin"  # round_robin, weighted, least_connections, random
        self.current_index = 0
        self.health_check_interval = 30  # seconds
        self.session = None
        self.logger = logging.getLogger("load_balancer")
        
        # Session affinity (sticky sessions)
        self.sticky_sessions: Dict[str, str] = {}  # client_ip -> backend_url
        
        # Health monitoring
        self.health_check_task = None
    
    def add_backend(self, url: str, weight: int = 1):
        """Add a backend server."""
        backend = BackendServer(url=url, weight=weight)
        self.backends.append(backend)
        self.logger.info(f"Added backend: {url} (weight: {weight})")
    
    def get_backend_round_robin(self) -> Optional[BackendServer]:
        """Round robin algorithm - cycles through all healthy backends."""
        if not self.backends:
            return None
        
        healthy_backends = [b for b in self.backends if b.is_healthy]
        if not healthy_backends:
            return None
        
        backend = healthy_backends[self.current_index % len(healthy_backends)]
        self.current_index += 1
        return backend
    
    def get_backend_weighted(self) -> Optional[BackendServer]:
        """Weighted round robin - considers server weights."""
        if not self.backends:
            return None
        
        # Create weighted list
        weighted_backends = []
        for backend in self.backends:
            if backend.is_healthy:
                weighted_backends.extend([backend] * backend.weight)
        
        if not weighted_backends:
            return None
        
        backend = weighted_backends[self.current_index % len(weighted_backends)]
        self.current_index += 1
        return backend
    
    def get_backend_least_connections(self) -> Optional[BackendServer]:
        """Least connections algorithm - routes to server with fewest active connections."""
        healthy_backends = [b for b in self.backends if b.is_healthy]
        if not healthy_backends:
            return None
        
        return min(healthy_backends, key=lambda b: b.active_connections)
    
    def get_backend_random(self) -> Optional[BackendServer]:
        """Random algorithm - randomly selects a healthy backend."""
        healthy_backends = [b for b in self.backends if b.is_healthy]
        if not healthy_backends:
            return None
        
        return random.choice(healthy_backends)
    
    def get_backend(self, client_ip: str = None) -> Optional[BackendServer]:
        """Get next backend based on configured algorithm."""
        # Check for sticky session
        if client_ip and client_ip in self.sticky_sessions:
            backend_url = self.sticky_sessions[client_ip]
            for backend in self.backends:
                if backend.url == backend_url and backend.is_healthy:
                    return backend
        
        # Select based on algorithm
        if self.algorithm == "round_robin":
            backend = self.get_backend_round_robin()
        elif self.algorithm == "weighted":
            backend = self.get_backend_weighted()
        elif self.algorithm == "least_connections":
            backend = self.get_backend_least_connections()
        elif self.algorithm == "random":
            backend = self.get_backend_random()
        else:
            backend = self.get_backend_round_robin()  # fallback
        
        # Set sticky session
        if backend and client_ip:
            self.sticky_sessions[client_ip] = backend.url
        
        return backend
    
    async def health_check(self):
        """Perform health checks on all backends."""
        if not self.session:
            return
        
        for backend in self.backends:
            try:
                start_time = time.time()
                health_url = f"{backend.url.rstrip('/')}/health"
                
                async with self.session.get(
                    health_url, 
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    backend.response_time = time.time() - start_time
                    backend.is_healthy = response.status == 200
                    backend.last_health_check = time.time()
                    
                    if backend.is_healthy:
                        self.logger.debug(f"Health check OK: {backend.url}")
                    else:
                        self.logger.warning(f"Health check failed: {backend.url} (status: {response.status})")
                        
            except Exception as e:
                backend.is_healthy = False
                backend.last_health_check = time.time()
                backend.response_time = 5.0  # timeout
                self.logger.error(f"Health check error for {backend.url}: {e}")
    
    async def start_health_monitoring(self):
        """Start periodic health checking."""
        while True:
            await self.health_check()
            await asyncio.sleep(self.health_check_interval)
    
    def get_stats(self) -> Dict:
        """Get load balancer statistics."""
        total_requests = sum(b.total_requests for b in self.backends)
        total_failed = sum(b.failed_requests for b in self.backends)
        
        backend_stats = []
        for backend in self.backends:
            backend_stats.append({
                "url": backend.url,
                "weight": backend.weight,
                "is_healthy": backend.is_healthy,
                "active_connections": backend.active_connections,
                "total_requests": backend.total_requests,
                "failed_requests": backend.failed_requests,
                "success_rate": (
                    (backend.total_requests - backend.failed_requests) / backend.total_requests * 100
                    if backend.total_requests > 0 else 0
                ),
                "avg_response_time": backend.response_time,
                "last_health_check": backend.last_health_check
            })
        
        return {
            "algorithm": self.algorithm,
            "total_backends": len(self.backends),
            "healthy_backends": len([b for b in self.backends if b.is_healthy]),
            "total_requests": total_requests,
            "total_failed": total_failed,
            "success_rate": (total_requests - total_failed) / total_requests * 100 if total_requests > 0 else 0,
            "active_sessions": len(self.sticky_sessions),
            "backends": backend_stats
        }


class LoadBalancerProxy:
    """Load balancer proxy server."""
    
    def __init__(self, host='localhost', port=8080):
        self.host = host
        self.port = port
        self.load_balancer = LoadBalancer()
        self.logger = logging.getLogger("proxy")
    
    async def start(self):
        """Start the load balancer proxy."""
        # Create HTTP client session
        self.load_balancer.session = aiohttp.ClientSession()
        
        # Start health monitoring
        self.load_balancer.health_check_task = asyncio.create_task(
            self.load_balancer.start_health_monitoring()
        )
        
        # Create web application
        app = web.Application()
        
        # Proxy routes
        app.router.add_route('*', '/{path:.*}', self.handle_request)
        
        # Management endpoints
        app.router.add_get('/_lb/stats', self.get_stats)
        app.router.add_get('/_lb/health', self.get_health)
        app.router.add_post('/_lb/algorithm/{algorithm}', self.set_algorithm)
        
        # Start server
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        self.logger.info(f"Load balancer started on {self.host}:{self.port}")
        return runner
    
    async def handle_request(self, request):
        """Handle incoming request and route to backend."""
        client_ip = request.remote
        backend = self.load_balancer.get_backend(client_ip)
        
        if not backend:
            return web.Response(status=503, text="No healthy backends available")
        
        try:
            # Increment connection count
            backend.active_connections += 1
            backend.total_requests += 1
            
            # Build target URL
            target_url = f"{backend.url.rstrip('/')}{request.path_qs}"
            
            # Prepare headers
            headers = dict(request.headers)
            headers.pop('host', None)
            headers['X-Forwarded-For'] = client_ip
            headers['X-Load-Balancer'] = 'LoadBalancerProxy/1.0'
            headers['X-Backend'] = backend.url
            
            # Read request body
            body = await request.read() if request.can_read_body else None
            
            self.logger.info(f"Routing {request.method} {request.path} to {backend.url}")
            
            # Forward request
            async with self.load_balancer.session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=body,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                # Read response
                content = await response.read()
                
                # Prepare response headers
                resp_headers = dict(response.headers)
                resp_headers['X-Load-Balancer'] = 'LoadBalancerProxy/1.0'
                resp_headers['X-Backend'] = backend.url
                
                return web.Response(
                    body=content,
                    status=response.status,
                    headers=resp_headers
                )
                
        except Exception as e:
            backend.failed_requests += 1
            self.logger.error(f"Error forwarding to {backend.url}: {e}")
            return web.Response(status=502, text=f"Backend error: {str(e)}")
        
        finally:
            backend.active_connections -= 1
    
    async def get_stats(self, request):
        """Get load balancer statistics."""
        stats = self.load_balancer.get_stats()
        return web.json_response(stats)
    
    async def get_health(self, request):
        """Get health status."""
        healthy_backends = [b for b in self.load_balancer.backends if b.is_healthy]
        
        return web.json_response({
            "status": "healthy" if healthy_backends else "unhealthy",
            "healthy_backends": len(healthy_backends),
            "total_backends": len(self.load_balancer.backends),
            "algorithm": self.load_balancer.algorithm
        })
    
    async def set_algorithm(self, request):
        """Change load balancing algorithm."""
        algorithm = request.match_info['algorithm']
        valid_algorithms = ["round_robin", "weighted", "least_connections", "random"]
        
        if algorithm not in valid_algorithms:
            return web.json_response({
                "error": f"Invalid algorithm. Valid options: {valid_algorithms}"
            }, status=400)
        
        self.load_balancer.algorithm = algorithm
        self.logger.info(f"Changed algorithm to: {algorithm}")
        
        return web.json_response({
            "message": f"Algorithm changed to {algorithm}",
            "algorithm": algorithm
        })
    
    async def stop(self):
        """Stop the load balancer."""
        if self.load_balancer.session:
            await self.load_balancer.session.close()
        
        if self.load_balancer.health_check_task:
            self.load_balancer.health_check_task.cancel()


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Advanced Load Balancer Proxy")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--backends", nargs="+", 
                       default=["http://httpbin.org", "http://jsonplaceholder.typicode.com"],
                       help="Backend server URLs")
    parser.add_argument("--weights", nargs="*", type=int, help="Weights for backends")
    parser.add_argument("--algorithm", default="round_robin",
                       choices=["round_robin", "weighted", "least_connections", "random"],
                       help="Load balancing algorithm")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create proxy
    proxy = LoadBalancerProxy(args.host, args.port)
    
    # Add backends
    weights = args.weights if args.weights else [1] * len(args.backends)
    for i, backend in enumerate(args.backends):
        weight = weights[i] if i < len(weights) else 1
        proxy.load_balancer.add_backend(backend, weight)
    
    # Set algorithm
    proxy.load_balancer.algorithm = args.algorithm
    
    try:
        runner = await proxy.start()
        
        print(f"Load Balancer running on {args.host}:{args.port}")
        print(f"Algorithm: {args.algorithm}")
        print(f"Backends: {args.backends}")
        print(f"Weights: {weights}")
        print("\nManagement endpoints:")
        print(f"  Stats: http://{args.host}:{args.port}/_lb/stats")
        print(f"  Health: http://{args.host}:{args.port}/_lb/health")
        print(f"  Change algorithm: curl -X POST http://{args.host}:{args.port}/_lb/algorithm/least_connections")
        print("\nPress Ctrl+C to stop")
        
        # Keep running
        while True:
            await asyncio.sleep(10)
            stats = proxy.load_balancer.get_stats()
            healthy = stats['healthy_backends']
            total = stats['total_backends']
            requests = stats['total_requests']
            print(f"Status: {healthy}/{total} backends healthy, {requests} total requests")
    
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await proxy.stop()
        if 'runner' in locals():
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
