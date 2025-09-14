#!/usr/bin/env python3
"""
Simple Load Balancer Proxy Demo

A basic round-robin load balancer that distributes requests across multiple backend servers.

Load Balancing Concepts:
Load balancing distributes incoming requests across multiple backend servers to:
- Improve application performance and availability
- Prevent any single server from becoming overwhelmed
- Provide redundancy in case a server fails
- Scale horizontally by adding more servers

Load Balancing Algorithms:
1. Round Robin: Requests are distributed evenly in circular order (implemented here)
2. Weighted Round Robin: Servers get different weights based on capacity
3. Least Connections: Route to server with fewest active connections
4. Random: Randomly select a backend server
5. Hash-based: Use request characteristics to consistently route to same server

How This Implementation Works:
1. Maintain a list of backend servers
2. For each request, select next server using round-robin
3. Forward the request to selected backend
4. Return backend response to client
5. Track statistics for monitoring

Benefits:
- High availability (if one server fails, others continue)
- Better performance (load distributed across servers)
- Scalability (easy to add more backend servers)
"""

import asyncio               # Asynchronous I/O for handling concurrent requests
import http.server          # HTTP server framework for handling requests
import socketserver         # Socket server framework for network services
import urllib.request       # HTTP client for making requests to backends
import urllib.parse         # URL parsing utilities
import json                 # JSON serialization for API responses and stats
import threading            # Threading support (used by socketserver)
import time                 # Time functions for logging and statistics
from collections import deque    # Double-ended queue for efficient rotation (round-robin)

class SimpleLoadBalancer:
    """
    Simple round-robin load balancer.
    
    This class manages a pool of backend servers and distributes requests
    among them using a round-robin algorithm. It also tracks statistics
    for monitoring performance and health.
    """
    
    def __init__(self, backends, port=8082):
        # Use deque for efficient rotation - deque.rotate() is O(1)
        # This makes round-robin selection very fast
        self.backends = deque(backends)  
        
        # Port for the load balancer to listen on
        self.port = port
        
        # Statistics tracking for each backend server
        # Tracks requests sent and errors encountered per backend
        self.stats = {backend: {"requests": 0, "errors": 0} for backend in backends}
        
        # Will hold reference to the HTTP server instance
        self.server = None
        
    def get_next_backend(self):
        """
        Get next backend using round-robin algorithm.
        
        Round-robin works by cycling through backends in order:
        - First request goes to backend[0]
        - Second request goes to backend[1] 
        - After last backend, wraps around to backend[0]
        
        Using deque.rotate(-1) efficiently moves first element to end,
        so self.backends[0] always gives us the "next" backend.
        """
        backend = self.backends[0]        # Get current first backend
        self.backends.rotate(-1)          # Move first to last (rotate left by 1)
        return backend
    
    def health_check(self, backend):
        """Check if backend is healthy."""
        try:
            url = f"{backend}/status" if not backend.endswith('/') else f"{backend}status"
            response = urllib.request.urlopen(url, timeout=5)
            return response.status == 200
        except:
            return False

class LoadBalancerHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for load balancer."""
    
    def do_GET(self):
        self.handle_request()
    
    def do_POST(self):
        self.handle_request()
    
    def do_PUT(self):
        self.handle_request()
    
    def do_DELETE(self):
        self.handle_request()
    
    def handle_request(self):
        """Handle incoming request and forward to backend."""
        balancer = self.server.balancer
        
        # Special endpoints
        if self.path == '/_lb/stats':
            self.send_stats(balancer)
            return
        elif self.path == '/_lb/health':
            self.send_health(balancer)
            return
        
        # Get next backend
        backend = balancer.get_next_backend()
        
        try:
            # Build target URL
            target_url = backend.rstrip('/') + self.path
            
            # Read request body if present
            body = None
            if 'content-length' in self.headers:
                content_length = int(self.headers['content-length'])
                body = self.rfile.read(content_length)
            
            # Create request
            req = urllib.request.Request(target_url, data=body, method=self.command)
            
            # Copy headers (except some)
            for header, value in self.headers.items():
                if header.lower() not in ['host', 'connection']:
                    req.add_header(header, value)
            
            # Add load balancer headers
            req.add_header('X-Forwarded-For', self.client_address[0])
            req.add_header('X-Load-Balancer', 'SimpleLoadBalancer/1.0')
            req.add_header('X-Backend', backend)
            
            print(f"Forwarding {self.command} {self.path} to {backend}")
            
            # Make request to backend
            with urllib.request.urlopen(req, timeout=30) as response:
                # Send response status
                self.send_response(response.status)
                
                # Send headers
                for header, value in response.headers.items():
                    if header.lower() not in ['connection', 'transfer-encoding']:
                        self.send_header(header, value)
                
                self.send_header('X-Load-Balancer', 'SimpleLoadBalancer/1.0')
                self.send_header('X-Backend', backend)
                self.end_headers()
                
                # Send body
                self.wfile.write(response.read())
                
                # Update stats
                balancer.stats[backend]["requests"] += 1
                
        except Exception as e:
            print(f"Error forwarding to {backend}: {e}")
            balancer.stats[backend]["errors"] += 1
            
            self.send_response(502)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Bad Gateway: {str(e)}".encode())
    
    def send_stats(self, balancer):
        """Send load balancer statistics."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        stats = {
            "backends": list(balancer.backends),
            "stats": balancer.stats,
            "total_requests": sum(s["requests"] for s in balancer.stats.values()),
            "total_errors": sum(s["errors"] for s in balancer.stats.values())
        }
        
        self.wfile.write(json.dumps(stats, indent=2).encode())
    
    def send_health(self, balancer):
        """Send health check response."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        health = {
            "status": "healthy",
            "backends": {backend: balancer.health_check(backend) for backend in balancer.backends},
            "load_balancer": "SimpleLoadBalancer/1.0"
        }
        
        self.wfile.write(json.dumps(health, indent=2).encode())
    
    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")

def start_load_balancer(backends, port=8082):
    """Start the load balancer server."""
    balancer = SimpleLoadBalancer(backends, port)
    
    # Create custom server class to hold balancer reference
    class LoadBalancerServer(socketserver.TCPServer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.balancer = balancer
    
    server = LoadBalancerServer(("localhost", port), LoadBalancerHandler)
    server.allow_reuse_address = True
    
    print(f"Load Balancer started on localhost:{port}")
    print(f"Backends: {backends}")
    print(f"Stats endpoint: http://localhost:{port}/_lb/stats")
    print(f"Health endpoint: http://localhost:{port}/_lb/health")
    print("Press Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nLoad balancer stopped by user")
    finally:
        server.shutdown()
        server.server_close()

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple Load Balancer")
    parser.add_argument("--port", type=int, default=8082, help="Port to bind to")
    parser.add_argument("--backends", nargs="+", 
                       default=["http://httpbin.org", "http://jsonplaceholder.typicode.com"],
                       help="Backend server URLs")
    
    args = parser.parse_args()
    
    start_load_balancer(args.backends, args.port)

if __name__ == "__main__":
    main()
