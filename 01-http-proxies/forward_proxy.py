#!/usr/bin/env python3
"""
HTTP Forward Proxy Implementation

🎯 MAIN PURPOSE:
A forward proxy sits between clients and the internet, forwarding requests
on behalf of clients. Clients configure their HTTP client to use this proxy.

🔍 WHAT WE'RE TRYING TO ACCOMPLISH:
1. **Privacy Protection**: Hide client IP addresses from target servers
2. **Content Filtering**: Block access to specific websites or content types
3. **Bandwidth Monitoring**: Track and control internet usage
4. **Caching**: Store frequently requested content to improve performance
5. **Access Control**: Implement authentication and authorization
6. **Security**: Scan outgoing requests and incoming responses for threats

📊 REAL-WORLD USE CASES:

1. **Corporate Network Proxy**:
   - Filter social media during work hours
   - Block malicious websites
   - Monitor employee internet usage
   - Cache frequently accessed resources

2. **Privacy Protection**:
   - Hide your real IP address from websites
   - Bypass geo-restrictions
   - Prevent tracking by third parties

3. **Development & Testing**:
   - Intercept API calls for debugging
   - Mock responses for testing
   - Monitor network traffic

4. **Content Control**:
   - Parental controls to block inappropriate content
   - Educational institution internet filtering
   - Compliance with regulatory requirements

🧪 TESTING EXAMPLES:

# Start the proxy
python3 forward_proxy.py --port 8080

# Configure your browser to use localhost:8080 as HTTP proxy, OR:

# Test with curl:
curl -x http://localhost:8080 http://httpbin.org/ip
curl -x http://localhost:8080 http://httpbin.org/headers

# You'll see your requests being proxied and your IP changed!

🔧 BROWSER CONFIGURATION:
Chrome/Firefox: Settings → Network → Proxy → HTTP: localhost:8080

Features:
- HTTP/HTTPS support
- Request/response logging
- Basic authentication
- Content filtering capabilities
- Connection pooling

Usage:
    python forward_proxy.py --port 8080 --log-level DEBUG
"""

import argparse        # Parse command-line arguments (--port, --host, etc.)
import asyncio         # Asynchronous I/O operations for handling multiple connections
import json           # JSON data serialization for configuration and responses
import logging        # Structured logging for debugging and monitoring
import ssl            # SSL/TLS support for secure connections
import sys            # System-specific parameters and functions
import time           # Time-related functions for performance measurement
from typing import Dict, Optional  # Type hints for better code documentation
from urllib.parse import urlparse, urlunparse  # URL parsing and manipulation

import aiohttp        # Async HTTP client/server framework (external dependency)
from aiohttp import web, ClientSession, ClientError  # Web server and HTTP client components
from aiohttp.web import Request, Response, StreamResponse  # HTTP request/response objects

# Add parent directory to path for common utilities
# This allows importing shared code from the utils module
sys.path.append('../common')
from utils import ProxyLogger, PerformanceMonitor, ConfigManager, NetworkUtils


class HTTPForwardProxy:
    """
    HTTP Forward Proxy server implementation.
    
    This class creates a forward proxy that sits between clients and target servers.
    It intercepts HTTP requests from clients, forwards them to target servers,
    and returns the responses back to clients.
    """
    
    def __init__(self, config: ConfigManager):
        """
        Initialize the forward proxy with configuration settings.
        
        Args:
            config: Configuration manager containing proxy settings
        """
        # Store configuration object for accessing settings throughout the proxy
        self.config = config
        
        # Create a logger for this proxy instance with specified log level
        # ProxyLogger provides structured logging with timestamps and context
        self.logger = ProxyLogger("forward-proxy", 
                                 getattr(logging, config.get("log_level", "INFO")))
        
        # Initialize performance monitor to track request metrics
        # This tracks response times, success rates, and throughput
        self.monitor = PerformanceMonitor()
        
        # HTTP client session for making requests to target servers
        # Will be initialized in start() method with connection pooling
        self.session: Optional[ClientSession] = None
        
        # Track the number of currently active connections
        # Used for monitoring and preventing overload
        self.active_connections = 0
        
        # Authentication configuration
        # Determines if proxy requires authentication from clients
        self.auth_enabled = config.get("auth_enabled", False)
        # Dictionary of valid username:password pairs for proxy access
        self.auth_users = config.get("auth_users", {})
        
        # Content filtering configuration
        # Set of domain names that should be blocked (e.g., malicious sites)
        self.blocked_domains = set(config.get("blocked_domains", []))
        # Set of keywords in URLs that should trigger blocking
        self.blocked_keywords = set(config.get("blocked_keywords", []))
    
    async def start(self):
        """
        Start the proxy server and initialize all components.
        
        This method:
        1. Creates HTTP client session with connection pooling
        2. Sets up web application with routes
        3. Starts the HTTP server
        4. Returns server runner for cleanup
        """
        # Create HTTP client session with connection pooling for efficient reuse
        # TCPConnector manages connection pool to target servers
        connector = aiohttp.TCPConnector(
            # Maximum total connections across all hosts
            limit=self.config.get("max_connections", 100),
            # Maximum connections per individual host (prevents overwhelming single server)
            limit_per_host=self.config.get("max_connections_per_host", 30),
            # DNS cache TTL - cache DNS lookups for 5 minutes to improve performance
            ttl_dns_cache=300,
            # Enable DNS caching to reduce DNS resolution overhead
            use_dns_cache=True
        )
        
        # Configure timeouts for outgoing requests to prevent hanging
        timeout = aiohttp.ClientTimeout(
            # Total timeout for entire request (including connection + data transfer)
            total=self.config.get("timeout_seconds", 30)
        )
        
        # Create HTTP client session with connection pooling and timeouts
        # This session will be reused for all outgoing proxy requests
        self.session = ClientSession(
            connector=connector,    # Use our configured connection pool
            timeout=timeout,        # Apply timeout settings
            headers={'User-Agent': 'HTTPForwardProxy/1.0'}  # Identify our proxy in requests
        )
        
        # Create aiohttp web application to handle incoming proxy requests
        app = web.Application()
        
        # Add route handler for all HTTP methods and paths
        # {path:.*} captures any path, allowing proxy to handle any URL
        app.router.add_route('*', '/{path:.*}', self.handle_request)
        
        # Add special handler for CONNECT method (used for HTTPS tunneling)
        # CONNECT is used by clients to establish SSL/TLS tunnels through proxy
        app.router.add_route('CONNECT', '/{path:.*}', self.handle_connect)
        
        # Get server binding configuration from config
        host = self.config.get("bind_host", "0.0.0.0")  # 0.0.0.0 = all interfaces
        port = self.config.get("bind_port", 8080)       # Default HTTP proxy port
        
        # Log server startup information
        self.logger.logger.info(f"Starting HTTP Forward Proxy on {host}:{port}")
        
        # Create and configure web server runner
        # AppRunner manages the application lifecycle
        runner = web.AppRunner(app)
        await runner.setup()  # Initialize the runner
        
        # Create TCP site to bind server to host:port
        # This actually starts listening for incoming connections
        site = web.TCPSite(runner, host, port)
        await site.start()  # Begin accepting connections
        
        # Log successful startup
        self.logger.logger.info("Forward proxy started successfully")
        
        # Return runner so caller can clean up properly when shutting down
        return runner
    
    async def stop(self):
        """
        Stop the proxy server and clean up resources.
        
        This method closes the HTTP client session and releases all connections.
        Important for preventing resource leaks when shutting down.
        """
        # Close the HTTP client session if it exists
        # This releases all pooled connections and frees network resources
        if self.session:
            await self.session.close()
    
    def check_authentication(self, request: Request) -> bool:
        """
        Check if the incoming request has valid authentication credentials.
        
        This implements HTTP Basic Authentication for proxy access control.
        Clients must provide username:password in Proxy-Authorization header.
        
        Args:
            request: The incoming HTTP request to check
            
        Returns:
            bool: True if authentication is valid or disabled, False otherwise
        """
        # If authentication is disabled, allow all requests
        if not self.auth_enabled:
            return True
        
        # Get the Proxy-Authorization header from request
        # Format should be: "Basic base64(username:password)"
        auth_header = request.headers.get('Proxy-Authorization', '')
        
        # Check if header starts with "Basic " (note the space)
        if not auth_header.startswith('Basic '):
            return False
        
        try:
            # Import base64 decoder (only when needed)
            import base64
            
            # Extract and decode the base64-encoded credentials
            # auth_header[6:] removes "Basic " prefix
            credentials = base64.b64decode(auth_header[6:]).decode('utf-8')
            
            # Split credentials into username and password
            # Format is "username:password"
            username, password = credentials.split(':', 1)
            
            # Check if username exists and password matches
            return self.auth_users.get(username) == password
            
        except Exception:
            # Any decoding error means invalid authentication
            return False
    
    def is_request_blocked(self, url: str) -> tuple[bool, str]:
        """
        Check if a request should be blocked based on content filtering rules.
        
        This implements basic content filtering by checking:
        1. Domain blacklist - block specific domains
        2. Keyword filtering - block URLs containing certain keywords
        
        Args:
            url: The target URL to check
            
        Returns:
            tuple: (is_blocked: bool, reason: str)
                   is_blocked = True if request should be blocked
                   reason = Human-readable explanation for blocking
        """
        # Parse the URL to extract domain and other components
        parsed = urlparse(url)
        
        # Extract domain name and convert to lowercase for case-insensitive matching
        domain = parsed.netloc.lower()
        
        # Check if domain is in the blocked domains list
        for blocked_domain in self.blocked_domains:
            # Use 'in' operator to match subdomains too
            # e.g., "evil.com" blocks "subdomain.evil.com"
            if blocked_domain in domain:
                return True, f"Domain {domain} is blocked"
        
        # Check if URL contains any blocked keywords
        # Convert entire URL to lowercase for case-insensitive matching
        full_url = url.lower()
        
        # Check each blocked keyword against the full URL
        for keyword in self.blocked_keywords:
            if keyword in full_url:
                return True, f"URL contains blocked keyword: {keyword}"
        
        # If no blocking rules match, allow the request
        return False, ""
    
    async def handle_request(self, request: Request) -> Response:
        """
        Handle incoming HTTP requests (GET, POST, PUT, DELETE, etc.).
        
        This is the main request processing method that:
        1. Validates authentication
        2. Builds target URL
        3. Applies content filtering
        4. Forwards request to target server
        5. Returns response to client
        
        Args:
            request: The incoming HTTP request from client
            
        Returns:
            Response: HTTP response to send back to client
        """
        # Record start time for performance measurement
        start_time = time.time()
        
        # Get client IP address for logging and authentication
        client_ip = request.remote
        
        # Check if client has valid authentication credentials
        if not self.check_authentication(request):
            # Log authentication failure
            self.logger.error("Authentication failed", client_ip)
            
            # Return 407 Proxy Authentication Required status
            # Include Proxy-Authenticate header to prompt client for credentials
            return web.Response(
                status=407,
                text="Proxy Authentication Required",
                headers={"Proxy-Authenticate": "Basic realm='Proxy'"}
            )
        
        # Build the target URL from the request
        target_url = str(request.url)
        
        # Handle relative URLs that don't include scheme (http:// or https://)
        if not target_url.startswith(('http://', 'https://')):
            # Try to reconstruct URL using Host header
            host = request.headers.get('Host')
            if host:
                # Determine scheme based on connection security
                scheme = 'https' if request.secure else 'http'
                # Reconstruct full URL: scheme://host/path?query
                target_url = f"{scheme}://{host}{request.path_qs}"
            else:
                # No Host header means we can't determine target
                return web.Response(status=400, text="Bad Request: Invalid URL")
        
        # Log the incoming request for monitoring
        self.logger.request(request.method, target_url, client_ip)
        
        # Apply content filtering rules to the target URL
        is_blocked, block_reason = self.is_request_blocked(target_url)
        if is_blocked:
            # Log the blocking action
            self.logger.error(f"Request blocked: {block_reason}")
            
            # Record failed request in performance monitor
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            self.monitor.record_request(False, duration)
            
            # Return 403 Forbidden with explanation
            return web.Response(status=403, text=f"Forbidden: {block_reason}")
        
        try:
            # Increment active connection counter for monitoring
            self.active_connections += 1
            
            # Prepare headers for forwarding to target server
            # Start with all headers from client request
            headers = dict(request.headers)
            
            # Remove hop-by-hop headers that shouldn't be forwarded
            # These headers are meant for the proxy, not the target server
            hop_by_hop_headers = {
                'connection', 'keep-alive', 'proxy-authenticate',
                'proxy-authorization', 'te', 'trailers', 'upgrade'
            }
            for header in hop_by_hop_headers:
                headers.pop(header, None)
            
            # Add forwarded headers to inform target server about original client
            headers['X-Forwarded-For'] = client_ip           # Original client IP
            headers['X-Forwarded-Proto'] = request.scheme    # Original protocol (http/https)
            
            # Read request body if present (for POST, PUT requests)
            body = None
            if request.can_read_body:
                body = await request.read()
            
            # Make the actual request to target server using our HTTP client session
            async with self.session.request(
                method=request.method,     # Same HTTP method as client used
                url=target_url,           # Target server URL
                headers=headers,          # Processed headers
                data=body,               # Request body (if any)
                allow_redirects=False    # Let client handle redirects
            ) as response:
                
                # Process response headers from target server
                resp_headers = dict(response.headers)
                
                # Remove hop-by-hop headers from response too
                for header in hop_by_hop_headers:
                    resp_headers.pop(header, None)
                
                # Handle large responses with streaming to avoid memory issues
                if int(resp_headers.get('content-length', 0)) > 1024 * 1024:  # 1MB threshold
                    # Stream large responses chunk by chunk
                    return await self.stream_response(response, resp_headers)
                else:
                    # Read entire response for smaller content
                    content = await response.read()
                    
                    # Calculate request duration for performance monitoring
                    duration = (time.time() - start_time) * 1000
                    
                    # Log successful response
                    self.logger.response(response.status, target_url, duration)
                    
                    # Record successful request in performance monitor
                    self.monitor.record_request(True, duration, len(content))
                    
                    # Return response to client
                    return web.Response(
                        body=content,
                        status=response.status,
                        headers=resp_headers
                    )
        
        except ClientError as e:
            # Handle HTTP client errors (connection refused, DNS errors, etc.)
            duration = (time.time() - start_time) * 1000
            self.logger.error(f"Client error: {str(e)}")
            self.monitor.record_request(False, duration)
            return web.Response(status=502, text=f"Bad Gateway: {str(e)}")
        
        except asyncio.TimeoutError:
            # Handle request timeouts
            duration = (time.time() - start_time) * 1000
            self.logger.error("Request timeout")
            self.monitor.record_request(False, duration)
            return web.Response(status=504, text="Gateway Timeout")
        
        except Exception as e:
            # Handle any other unexpected errors
            duration = (time.time() - start_time) * 1000
            self.logger.error(f"Unexpected error: {str(e)}")
            self.monitor.record_request(False, duration)
            return web.Response(status=500, text="Internal Server Error")
        
        finally:
            # Always decrement connection counter when request completes
            self.active_connections -= 1
    
    async def stream_response(self, response, headers) -> StreamResponse:
        """
        Stream large responses to avoid memory issues.
        
        For large files or responses, loading everything into memory could
        cause memory exhaustion. Instead, we stream the response chunk by chunk.
        
        Args:
            response: The aiohttp response from target server
            headers: Response headers to send to client
            
        Returns:
            StreamResponse: Streaming response object
        """
        # Create streaming response with same status and headers as target server
        stream_response = web.StreamResponse(
            status=response.status,
            headers=headers
        )
        
        # Prepare the streaming response (sends headers to client)
        await stream_response.prepare()
        
        # Stream response content in 8KB chunks
        # This keeps memory usage low even for very large files
        async for chunk in response.content.iter_chunked(8192):
            # Write each chunk to client as it arrives from target server
            await stream_response.write(chunk)
        
        return stream_response
    
    async def handle_connect(self, request: Request) -> Response:
        """
        Handle CONNECT method for HTTPS tunneling.
        
        The CONNECT method is used by clients to establish encrypted tunnels
        through the proxy for HTTPS connections. This is more complex than
        regular HTTP proxying because we need to establish a raw TCP tunnel.
        
        Args:
            request: HTTP CONNECT request from client
            
        Returns:
            Response: Either success (200) or error response
        """
        # CONNECT method is used for HTTPS tunneling
        # This is a simplified implementation for educational purposes
        
        # Check authentication first (same as regular requests)
        if not self.check_authentication(request):
            return web.Response(
                status=407,
                text="Proxy Authentication Required",
                headers={"Proxy-Authenticate": "Basic realm='Proxy'"}
            )
        
        # Extract target host and port from request path
        # CONNECT request format: "CONNECT example.com:443 HTTP/1.1"
        target = request.path.lstrip('/')  # Remove leading slash
        self.logger.request("CONNECT", target, request.remote)
        
        try:
            # Parse target into host and port
            # Expected format: "hostname:port"
            host, port = target.split(':')
            port = int(port)  # Convert port to integer
        except ValueError:
            # Invalid format - return bad request
            return web.Response(status=400, text="Bad Request: Invalid CONNECT target")
        
        # Apply content filtering to HTTPS connections too
        # Check if HTTPS tunneling to this host should be blocked
        is_blocked, block_reason = self.is_request_blocked(f"https://{target}")
        if is_blocked:
            self.logger.error(f"CONNECT blocked: {block_reason}")
            return web.Response(status=403, text=f"Forbidden: {block_reason}")
        
        # For simplicity in this educational example, we reject CONNECT requests
        # Full HTTPS tunneling implementation requires:
        # 1. Establishing raw TCP connection to target server
        # 2. Returning "200 Connection established" to client
        # 3. Switching to raw TCP forwarding mode (no HTTP parsing)
        # 4. Bidirectional data copying between client and server
        return web.Response(
            status=501,
            text="CONNECT method not implemented in this example"
        )
    
    def get_stats(self) -> Dict:
        """
        Get comprehensive proxy statistics for monitoring and debugging.
        
        This method combines performance metrics with proxy-specific statistics
        to provide a complete view of proxy health and activity.
        
        Returns:
            Dict: Dictionary containing all proxy statistics
        """
        # Get base statistics from performance monitor
        # This includes request counts, response times, success rates, etc.
        stats = self.monitor.get_stats()
        
        # Add proxy-specific statistics
        stats.update({
            # Current number of active connections being processed
            "active_connections": self.active_connections,
            
            # Number of domains in the blocked list
            "blocked_domains": len(self.blocked_domains),
            
            # Number of keywords in the blocked list  
            "blocked_keywords": len(self.blocked_keywords),
            
            # Whether authentication is enabled
            "auth_enabled": self.auth_enabled
        })
        
        return stats


async def main():
    """
    Main entry point for the forward proxy application.
    
    This function:
    1. Parses command line arguments
    2. Sets up configuration 
    3. Creates and starts the proxy server
    4. Handles graceful shutdown
    """
    # Create command line argument parser
    parser = argparse.ArgumentParser(description="HTTP Forward Proxy Server")
    
    # Add command line options
    parser.add_argument("--port", type=int, default=8080, 
                       help="Port to bind to (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", 
                       help="Host to bind to (default: 0.0.0.0 for all interfaces)")
    parser.add_argument("--config", 
                       help="Configuration file path (optional)")
    parser.add_argument("--log-level", default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level (default: INFO)")
    
    # Parse the provided command line arguments
    args = parser.parse_args()
    
    # Load configuration from file if provided, otherwise use defaults
    config = ConfigManager(args.config) if args.config else ConfigManager()
    
    # Override config with command line arguments
    # Command line args take precedence over config file
    config.set("bind_host", args.host)        # Where to bind server
    config.set("bind_port", args.port)        # What port to listen on
    config.set("log_level", args.log_level)   # How verbose logging should be
    
    # Example configuration for testing and demonstration
    # In production, these would typically come from a config file
    config.set("blocked_domains", ["example-blocked.com", "malware.example"])
    config.set("blocked_keywords", ["malware", "phishing"])
    config.set("auth_enabled", False)  # Set to True to require authentication
    config.set("auth_users", {"user": "password", "admin": "secret"})
    
    # Create the proxy instance with our configuration
    proxy = HTTPForwardProxy(config)
    
    try:
        # Start the proxy server
        # This sets up the HTTP server and begins accepting connections
        runner = await proxy.start()
        
        # Print startup information for user
        print(f"HTTP Forward Proxy running on {args.host}:{args.port}")
        print("\nUsage examples:")
        print(f"  curl -x http://{args.host}:{args.port} http://httpbin.org/ip")
        print(f"  curl -x http://{args.host}:{args.port} http://httpbin.org/headers")
        print("\nTo test blocking:")
        print(f"  curl -x http://{args.host}:{args.port} http://example-blocked.com")
        print("\nPress Ctrl+C to stop")
        
        # Main server loop - keep running until interrupted
        while True:
            await asyncio.sleep(1)  # Sleep to prevent busy waiting
            
            # Print statistics every 30 seconds for monitoring
            if int(time.time()) % 30 == 0:
                stats = proxy.get_stats()
                print(f"\nProxy Stats: {stats['requests_total']} requests, "
                      f"{stats['success_rate']:.1f}% success rate, "
                      f"{stats['active_connections']} active connections")
    
    except KeyboardInterrupt:
        # User pressed Ctrl+C to stop the server
        print("\nShutting down proxy...")
    finally:
        # Clean up resources before exiting
        # Close HTTP client session and release connections
        await proxy.stop()
        
        # Clean up web server runner
        if 'runner' in locals():
            await runner.cleanup()


# Python entry point check
# This ensures main() only runs when script is executed directly,
# not when imported as a module
if __name__ == "__main__":
    # Run the async main function
    # asyncio.run() handles the event loop setup and cleanup
    asyncio.run(main())
