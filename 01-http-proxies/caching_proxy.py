#!/usr/bin/env python3
"""
HTTP Caching Proxy Implementation

A caching proxy that stores responses to improve performance and reduce
backend load. Implements HTTP caching standards with TTL and cache invalidation.

Features:
- HTTP cache headers compliance (Cache-Control, ETag, Last-Modified)
- Memory and disk cache storage
- Cache invalidation and purging
- Conditional requests (If-None-Match, If-Modified-Since)
- Cache statistics and monitoring

Usage:
    python caching_proxy.py --port 8080 --cache-size 100MB --cache-ttl 300
"""

import argparse          # Command line argument parsing
import asyncio            # Asynchronous I/O operations
import hashlib            # Generate cache keys using SHA256 hashing
import json              # JSON serialization for API responses
import logging           # Structured logging for debugging and monitoring
import os                # Operating system interface for file operations
import pickle            # Python object serialization for disk cache
import sys               # System-specific parameters and functions
import time              # Time-related functions for cache expiry
from datetime import datetime, timedelta    # Date/time handling for HTTP cache headers
from typing import Dict, Optional, Tuple, Any    # Type hints for better code clarity
from urllib.parse import urlparse    # URL parsing utilities

import aiohttp           # High-performance HTTP client/server library
from aiohttp import web, ClientSession    # Web framework and HTTP client
from aiohttp.web import Request, Response    # HTTP request/response objects

# Add parent directory to path for common utilities
# This allows importing shared utilities from the common folder
sys.path.append('../common')
from utils import ProxyLogger, PerformanceMonitor, ConfigManager, NetworkUtils


class CacheEntry:
    """
    Represents a cached HTTP response with metadata.
    
    This class stores all information needed to serve a cached response:
    - Response data (body content)
    - HTTP headers 
    - Status code
    - Cache timing information
    - Access statistics
    """
    
    def __init__(self, response_data: bytes, headers: Dict[str, str], 
                 status_code: int, ttl: int = 300):
        # Store the actual response content as bytes
        self.response_data = response_data
        # Store HTTP headers as dictionary for easy access
        self.headers = headers
        # HTTP status code (200, 404, etc.)
        self.status_code = status_code
        # When this cache entry was created (Unix timestamp)
        self.created_at = time.time()
        # Time To Live - how long this entry should be cached (seconds)
        self.ttl = ttl
        # Track how many times this cached response has been used
        self.access_count = 0
        # When this entry was last accessed (for LRU eviction)
        self.last_accessed = time.time()
        
        # Extract cache-related headers for HTTP compliance
        # ETag is used for conditional requests (If-None-Match)
        self.etag = headers.get('etag', '')
        # Last-Modified is used for conditional requests (If-Modified-Since)  
        self.last_modified = headers.get('last-modified', '')
        # Cache-Control header contains caching directives
        self.cache_control = headers.get('cache-control', '')
        
        # Calculate when this entry expires based on HTTP cache headers
        self.expires_at = self._calculate_expiry()
    
    def _calculate_expiry(self) -> float:
        """Calculate when this cache entry expires."""
        # Check Cache-Control header for max-age
        if 'max-age=' in self.cache_control.lower():
            try:
                max_age = int(self.cache_control.lower().split('max-age=')[1].split(',')[0])
                return self.created_at + max_age
            except (ValueError, IndexError):
                pass
        
        # Check Expires header
        expires_header = self.headers.get('expires', '')
        if expires_header:
            try:
                expires_dt = datetime.strptime(expires_header, '%a, %d %b %Y %H:%M:%S %Z')
                return expires_dt.timestamp()
            except ValueError:
                pass
        
        # Fall back to configured TTL
        return self.created_at + self.ttl
    
    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return time.time() > self.expires_at
    
    def is_stale(self) -> bool:
        """Check if this cache entry is stale and needs validation."""
        # Check Cache-Control directives
        if 'no-cache' in self.cache_control.lower():
            return True
        if 'must-revalidate' in self.cache_control.lower() and self.is_expired():
            return True
        
        return self.is_expired()
    
    def access(self):
        """Record access to this cache entry."""
        self.access_count += 1
        self.last_accessed = time.time()
    
    def size(self) -> int:
        """Get the size of this cache entry in bytes."""
        return len(self.response_data) + sum(len(k) + len(v) for k, v in self.headers.items())


class HTTPCache:
    """HTTP cache implementation with memory and disk storage."""
    
    def __init__(self, max_size_mb: int = 100, disk_cache: bool = False, 
                 cache_dir: str = "/tmp/proxy_cache"):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.disk_cache = disk_cache
        self.cache_dir = cache_dir
        
        # In-memory cache
        self.cache: Dict[str, CacheEntry] = {}
        self.current_size = 0
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.invalidations = 0
        
        # Create cache directory if using disk cache
        if self.disk_cache:
            os.makedirs(self.cache_dir, exist_ok=True)
    
    def _generate_key(self, method: str, url: str, headers: Dict[str, str] = None) -> str:
        """Generate a cache key for the request."""
        # Basic key is method + URL
        key_data = f"{method}:{url}"
        
        # Add relevant headers that affect caching
        if headers:
            vary_headers = headers.get('vary', '').lower().split(',')
            for header_name in vary_headers:
                header_name = header_name.strip()
                if header_name and header_name in headers:
                    key_data += f":{header_name}:{headers[header_name]}"
        
        # Generate hash
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def get(self, method: str, url: str, headers: Dict[str, str] = None) -> Tuple[Optional[CacheEntry], bool]:
        """
        Get cached response.
        Returns (cache_entry, is_stale) tuple.
        """
        key = self._generate_key(method, url, headers)
        
        # Only cache GET and HEAD requests
        if method.upper() not in ['GET', 'HEAD']:
            self.misses += 1
            return None, False
        
        # Check memory cache first
        if key in self.cache:
            entry = self.cache[key]
            entry.access()
            
            if entry.is_expired():
                # Remove expired entry
                self._remove_from_cache(key)
                self.misses += 1
                return None, False
            
            if entry.is_stale():
                self.hits += 1
                return entry, True  # Return but mark as stale for validation
            
            self.hits += 1
            return entry, False
        
        # Check disk cache if enabled
        if self.disk_cache:
            entry = self._load_from_disk(key)
            if entry and not entry.is_expired():
                self.cache[key] = entry
                self.current_size += entry.size()
                entry.access()
                self.hits += 1
                return entry, entry.is_stale()
        
        self.misses += 1
        return None, False
    
    def put(self, method: str, url: str, response_data: bytes, 
            headers: Dict[str, str], status_code: int, ttl: int = 300):
        """Store response in cache."""
        # Only cache successful GET/HEAD responses
        if method.upper() not in ['GET', 'HEAD'] or status_code not in [200, 301, 302, 304]:
            return
        
        # Check if response is cacheable
        cache_control = headers.get('cache-control', '').lower()
        if 'no-store' in cache_control or 'private' in cache_control:
            return
        
        key = self._generate_key(method, url, headers)
        entry = CacheEntry(response_data, headers, status_code, ttl)
        
        # Ensure we don't exceed memory limit
        while self.current_size + entry.size() > self.max_size_bytes and self.cache:
            self._evict_lru()
        
        # Store in memory
        if key in self.cache:
            self.current_size -= self.cache[key].size()
        
        self.cache[key] = entry
        self.current_size += entry.size()
        
        # Store on disk if enabled
        if self.disk_cache:
            self._save_to_disk(key, entry)
    
    def invalidate(self, method: str, url: str, headers: Dict[str, str] = None):
        """Invalidate cached entry."""
        key = self._generate_key(method, url, headers)
        self._remove_from_cache(key)
        self.invalidations += 1
    
    def _remove_from_cache(self, key: str):
        """Remove entry from cache."""
        if key in self.cache:
            self.current_size -= self.cache[key].size()
            del self.cache[key]
        
        if self.disk_cache:
            disk_path = os.path.join(self.cache_dir, f"{key}.cache")
            if os.path.exists(disk_path):
                os.remove(disk_path)
    
    def _evict_lru(self):
        """Evict least recently used entry."""
        if not self.cache:
            return
        
        lru_key = min(self.cache.keys(), key=lambda k: self.cache[k].last_accessed)
        self._remove_from_cache(lru_key)
    
    def _save_to_disk(self, key: str, entry: CacheEntry):
        """Save cache entry to disk."""
        try:
            disk_path = os.path.join(self.cache_dir, f"{key}.cache")
            with open(disk_path, 'wb') as f:
                pickle.dump(entry, f)
        except Exception:
            pass  # Ignore disk cache errors
    
    def _load_from_disk(self, key: str) -> Optional[CacheEntry]:
        """Load cache entry from disk."""
        try:
            disk_path = os.path.join(self.cache_dir, f"{key}.cache")
            if os.path.exists(disk_path):
                with open(disk_path, 'rb') as f:
                    return pickle.load(f)
        except Exception:
            pass  # Ignore disk cache errors
        return None
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": round(hit_rate, 2),
            "invalidations": self.invalidations,
            "entries": len(self.cache),
            "size_bytes": self.current_size,
            "size_mb": round(self.current_size / (1024 * 1024), 2),
            "max_size_mb": round(self.max_size_bytes / (1024 * 1024), 2)
        }
    
    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        self.current_size = 0
        
        if self.disk_cache:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cache'):
                    os.remove(os.path.join(self.cache_dir, filename))


class HTTPCachingProxy:
    """HTTP caching proxy implementation."""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.logger = ProxyLogger("caching-proxy", 
                                 getattr(logging, config.get("log_level", "INFO")))
        self.monitor = PerformanceMonitor()
        self.session: Optional[ClientSession] = None
        
        # Initialize cache
        cache_size_mb = config.get("cache_max_size_mb", 100)
        cache_disk = config.get("cache_disk_enabled", False)
        cache_dir = config.get("cache_directory", "/tmp/proxy_cache")
        
        self.cache = HTTPCache(cache_size_mb, cache_disk, cache_dir)
        
        # Backend configuration
        self.backend_url = config.get("backend_url", "http://localhost:3000")
        self.default_ttl = config.get("cache_default_ttl", 300)
    
    async def start(self):
        """Start the caching proxy server."""
        # Create HTTP client session
        connector = aiohttp.TCPConnector(
            limit=self.config.get("max_connections", 100),
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
        
        # Create web application
        app = web.Application()
        
        # Add routes
        app.router.add_route('*', '/{path:.*}', self.handle_request)
        
        # Add management endpoints
        app.router.add_get('/_cache/stats', self.cache_stats)
        app.router.add_post('/_cache/clear', self.cache_clear)
        app.router.add_delete('/_cache/{path:.*}', self.cache_invalidate)
        
        # Start server
        host = self.config.get("bind_host", "0.0.0.0")
        port = self.config.get("bind_port", 8080)
        
        self.logger.logger.info(f"Starting HTTP Caching Proxy on {host}:{port}")
        self.logger.logger.info(f"Backend URL: {self.backend_url}")
        self.logger.logger.info(f"Cache size: {self.cache.max_size_bytes // (1024*1024)}MB")
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        self.logger.logger.info("Caching proxy started successfully")
        return runner
    
    async def stop(self):
        """Stop the caching proxy server."""
        if self.session:
            await self.session.close()
    
    async def handle_request(self, request: Request) -> Response:
        """Handle incoming requests with caching."""
        start_time = time.time()
        method = request.method
        url = str(request.url)
        headers = dict(request.headers)
        
        self.logger.request(method, url, request.remote)
        
        # Check cache first
        cache_entry, is_stale = self.cache.get(method, url, headers)
        
        if cache_entry and not is_stale:
            # Cache hit - return cached response
            duration = (time.time() - start_time) * 1000
            self.logger.response(cache_entry.status_code, url, duration)
            self.monitor.record_request(True, duration, len(cache_entry.response_data))
            
            # Add cache headers
            response_headers = cache_entry.headers.copy()
            response_headers['X-Cache'] = 'HIT'
            response_headers['X-Cache-Age'] = str(int(time.time() - cache_entry.created_at))
            
            return web.Response(
                body=cache_entry.response_data,
                status=cache_entry.status_code,
                headers=response_headers
            )
        
        # Prepare backend request
        backend_url = self.backend_url.rstrip('/') + request.path_qs
        
        # Handle conditional requests for stale cache entries
        if cache_entry and is_stale:
            if cache_entry.etag:
                headers['If-None-Match'] = cache_entry.etag
            if cache_entry.last_modified:
                headers['If-Modified-Since'] = cache_entry.last_modified
        
        try:
            # Remove hop-by-hop headers
            hop_by_hop = {'connection', 'keep-alive', 'proxy-authenticate',
                         'proxy-authorization', 'te', 'trailers', 'upgrade'}
            for header in hop_by_hop:
                headers.pop(header, None)
            
            # Read request body
            body = None
            if request.can_read_body:
                body = await request.read()
            
            # Make backend request
            async with self.session.request(
                method=method,
                url=backend_url,
                headers=headers,
                data=body,
                allow_redirects=False
            ) as response:
                
                resp_headers = dict(response.headers)
                
                # Handle 304 Not Modified
                if response.status == 304 and cache_entry:
                    duration = (time.time() - start_time) * 1000
                    self.logger.response(200, url, duration)  # Log as 200 for client
                    self.monitor.record_request(True, duration, len(cache_entry.response_data))
                    
                    # Update cache entry timestamp
                    cache_entry.created_at = time.time()
                    cache_entry.expires_at = cache_entry._calculate_expiry()
                    
                    response_headers = cache_entry.headers.copy()
                    response_headers['X-Cache'] = 'REFRESH'
                    
                    return web.Response(
                        body=cache_entry.response_data,
                        status=cache_entry.status_code,
                        headers=response_headers
                    )
                
                # Read response content
                content = await response.read()
                
                # Cache the response
                self.cache.put(method, url, content, resp_headers, 
                             response.status, self.default_ttl)
                
                duration = (time.time() - start_time) * 1000
                self.logger.response(response.status, url, duration)
                self.monitor.record_request(True, duration, len(content))
                
                # Add cache headers
                resp_headers['X-Cache'] = 'MISS'
                
                return web.Response(
                    body=content,
                    status=response.status,
                    headers=resp_headers
                )
        
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            self.logger.error(f"Backend error: {str(e)}")
            self.monitor.record_request(False, duration)
            return web.Response(status=502, text=f"Bad Gateway: {str(e)}")
    
    async def cache_stats(self, request: Request) -> Response:
        """Return cache statistics."""
        stats = {
            "cache": self.cache.get_stats(),
            "proxy": self.monitor.get_stats()
        }
        return web.json_response(stats)
    
    async def cache_clear(self, request: Request) -> Response:
        """Clear all cache entries."""
        self.cache.clear()
        self.logger.logger.info("Cache cleared manually")
        return web.json_response({"message": "Cache cleared successfully"})
    
    async def cache_invalidate(self, request: Request) -> Response:
        """Invalidate specific cache entry."""
        path = '/' + request.match_info['path']
        self.cache.invalidate('GET', path)
        self.logger.logger.info(f"Cache invalidated for: {path}")
        return web.json_response({"message": f"Cache invalidated for {path}"})


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="HTTP Caching Proxy Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--backend", default="http://localhost:3000", help="Backend server URL")
    parser.add_argument("--cache-size", type=int, default=100, help="Cache size in MB")
    parser.add_argument("--cache-ttl", type=int, default=300, help="Default cache TTL in seconds")
    parser.add_argument("--disk-cache", action="store_true", help="Enable disk cache")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--log-level", default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Load configuration
    config = ConfigManager(args.config) if args.config else ConfigManager()
    config.set("bind_host", args.host)
    config.set("bind_port", args.port)
    config.set("backend_url", args.backend)
    config.set("cache_max_size_mb", args.cache_size)
    config.set("cache_default_ttl", args.cache_ttl)
    config.set("cache_disk_enabled", args.disk_cache)
    config.set("log_level", args.log_level)
    
    proxy = HTTPCachingProxy(config)
    
    try:
        runner = await proxy.start()
        
        print(f"HTTP Caching Proxy running on {args.host}:{args.port}")
        print(f"Backend: {args.backend}")
        print(f"Cache size: {args.cache_size}MB, TTL: {args.cache_ttl}s")
        print("\nManagement endpoints:")
        print(f"  Stats: http://{args.host}:{args.port}/_cache/stats")
        print(f"  Clear: curl -X POST http://{args.host}:{args.port}/_cache/clear")
        print("\nPress Ctrl+C to stop")
        
        # Keep server running
        while True:
            await asyncio.sleep(10)
            
            # Print cache stats
            cache_stats = proxy.cache.get_stats()
            if cache_stats['hits'] + cache_stats['misses'] > 0:
                print(f"Cache: {cache_stats['hit_rate_percent']:.1f}% hit rate, "
                      f"{cache_stats['entries']} entries, "
                      f"{cache_stats['size_mb']:.1f}MB used")
    
    except KeyboardInterrupt:
        print("\nShutting down proxy...")
    finally:
        await proxy.stop()
        if 'runner' in locals():
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
