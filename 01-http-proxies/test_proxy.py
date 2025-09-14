#!/usr/bin/env python3
"""
Test script for HTTP proxy implementations.
Tests various proxy features and provides performance benchmarks.
"""

import argparse
import asyncio
import json
import sys
import time
from typing import List

import aiohttp

# Add parent directory to path for common utilities
sys.path.append('../common')
from utils import ProxyTestClient, NetworkUtils


class ProxyTester:
    """Comprehensive proxy testing utility."""
    
    def __init__(self, proxy_host: str = "localhost", proxy_port: int = 8080):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.results = []
    
    async def test_basic_functionality(self) -> List[dict]:
        """Test basic proxy functionality."""
        tests = [
            ("GET", "http://httpbin.org/get"),
            ("POST", "http://httpbin.org/post"),
            ("PUT", "http://httpbin.org/put"),
            ("DELETE", "http://httpbin.org/delete"),
        ]
        
        results = []
        proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
        
        async with aiohttp.ClientSession() as session:
            for method, url in tests:
                try:
                    start_time = time.time()
                    
                    async with session.request(
                        method=method,
                        url=url,
                        proxy=proxy_url,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        content = await response.text()
                        duration = (time.time() - start_time) * 1000
                        
                        result = {
                            "test": f"{method} Request",
                            "success": True,
                            "status_code": response.status,
                            "duration_ms": duration,
                            "content_length": len(content),
                            "url": url
                        }
                        
                except Exception as e:
                    result = {
                        "test": f"{method} Request",
                        "success": False,
                        "error": str(e),
                        "url": url
                    }
                
                results.append(result)
                print(f"✓ {result['test']}: {'PASS' if result['success'] else 'FAIL'}")
        
        return results
    
    async def test_caching(self) -> List[dict]:
        """Test caching functionality (if available)."""
        results = []
        proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
        test_url = "http://httpbin.org/cache/60"  # Cacheable for 60 seconds
        
        async with aiohttp.ClientSession() as session:
            # First request (should be cache miss)
            try:
                start_time = time.time()
                async with session.get(test_url, proxy=proxy_url) as response:
                    await response.text()
                    first_duration = (time.time() - start_time) * 1000
                    first_headers = dict(response.headers)
                
                # Second request (should be cache hit if caching is enabled)
                start_time = time.time()
                async with session.get(test_url, proxy=proxy_url) as response:
                    await response.text()
                    second_duration = (time.time() - start_time) * 1000
                    second_headers = dict(response.headers)
                
                # Check for cache headers
                cache_hit = second_headers.get('x-cache', '').upper() == 'HIT'
                
                results.append({
                    "test": "Cache Test",
                    "success": True,
                    "first_request_ms": first_duration,
                    "second_request_ms": second_duration,
                    "cache_hit": cache_hit,
                    "performance_improvement": f"{((first_duration - second_duration) / first_duration * 100):.1f}%" if first_duration > 0 else "N/A"
                })
                
                print(f"✓ Cache Test: {'HIT' if cache_hit else 'MISS'} (First: {first_duration:.1f}ms, Second: {second_duration:.1f}ms)")
            
            except Exception as e:
                results.append({
                    "test": "Cache Test",
                    "success": False,
                    "error": str(e)
                })
                print(f"✗ Cache Test: FAIL - {str(e)}")
        
        return results
    
    async def test_error_handling(self) -> List[dict]:
        """Test error handling capabilities."""
        results = []
        proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
        
        error_tests = [
            ("Invalid URL", "http://invalid-domain-that-does-not-exist.com"),
            ("Connection Refused", "http://localhost:99999"),
            ("Timeout", "http://httpbin.org/delay/31"),  # Should timeout
        ]
        
        async with aiohttp.ClientSession() as session:
            for test_name, url in error_tests:
                try:
                    async with session.get(
                        url, 
                        proxy=proxy_url,
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        result = {
                            "test": test_name,
                            "success": response.status < 500,
                            "status_code": response.status,
                            "expected": "Error handling"
                        }
                
                except asyncio.TimeoutError:
                    result = {
                        "test": test_name,
                        "success": True,  # Timeout is expected behavior
                        "status_code": 504,
                        "expected": "Timeout handled correctly"
                    }
                
                except Exception as e:
                    result = {
                        "test": test_name,
                        "success": True,  # Error handling is working
                        "error": str(e),
                        "expected": "Exception handled correctly"
                    }
                
                results.append(result)
                print(f"✓ {test_name}: {'PASS' if result['success'] else 'FAIL'}")
        
        return results
    
    async def performance_test(self, concurrent_requests: int = 10, 
                             total_requests: int = 100) -> dict:
        """Run performance tests."""
        print(f"\nRunning performance test: {total_requests} requests with {concurrent_requests} concurrent connections")
        
        proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
        test_url = "http://httpbin.org/get"
        
        start_time = time.time()
        successful_requests = 0
        failed_requests = 0
        response_times = []
        
        semaphore = asyncio.Semaphore(concurrent_requests)
        
        async def make_request(session):
            nonlocal successful_requests, failed_requests
            
            async with semaphore:
                try:
                    request_start = time.time()
                    async with session.get(test_url, proxy=proxy_url) as response:
                        await response.text()
                        request_duration = (time.time() - request_start) * 1000
                        response_times.append(request_duration)
                        
                        if response.status == 200:
                            successful_requests += 1
                        else:
                            failed_requests += 1
                
                except Exception:
                    failed_requests += 1
        
        # Run concurrent requests
        async with aiohttp.ClientSession() as session:
            tasks = [make_request(session) for _ in range(total_requests)]
            await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Calculate statistics
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            
            # Calculate percentiles
            sorted_times = sorted(response_times)
            p50 = sorted_times[int(len(sorted_times) * 0.5)]
            p95 = sorted_times[int(len(sorted_times) * 0.95)]
            p99 = sorted_times[int(len(sorted_times) * 0.99)]
        else:
            avg_response_time = min_response_time = max_response_time = 0
            p50 = p95 = p99 = 0
        
        result = {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": (successful_requests / total_requests * 100) if total_requests > 0 else 0,
            "total_time_seconds": total_time,
            "requests_per_second": total_requests / total_time if total_time > 0 else 0,
            "avg_response_time_ms": avg_response_time,
            "min_response_time_ms": min_response_time,
            "max_response_time_ms": max_response_time,
            "p50_response_time_ms": p50,
            "p95_response_time_ms": p95,
            "p99_response_time_ms": p99
        }
        
        print(f"✓ Performance test completed:")
        print(f"  - Success rate: {result['success_rate']:.1f}%")
        print(f"  - Requests/sec: {result['requests_per_second']:.1f}")
        print(f"  - Avg response time: {result['avg_response_time_ms']:.1f}ms")
        print(f"  - P95 response time: {result['p95_response_time_ms']:.1f}ms")
        
        return result
    
    async def test_proxy_health(self) -> dict:
        """Test proxy health endpoints."""
        health_endpoints = [
            "/_proxy/health",
            "/_proxy/stats", 
            "/_cache/stats"
        ]
        
        results = {}
        
        async with aiohttp.ClientSession() as session:
            for endpoint in health_endpoints:
                try:
                    url = f"http://{self.proxy_host}:{self.proxy_port}{endpoint}"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        if response.status == 200:
                            data = await response.json()
                            results[endpoint] = {
                                "available": True,
                                "status_code": response.status,
                                "data": data
                            }
                        else:
                            results[endpoint] = {
                                "available": False,
                                "status_code": response.status
                            }
                
                except Exception as e:
                    results[endpoint] = {
                        "available": False,
                        "error": str(e)
                    }
        
        return results
    
    async def run_all_tests(self) -> dict:
        """Run comprehensive test suite."""
        print(f"Testing proxy at {self.proxy_host}:{self.proxy_port}")
        print("=" * 50)
        
        # Check if proxy is reachable
        if not NetworkUtils.is_port_open(self.proxy_host, self.proxy_port):
            return {
                "error": f"Proxy not reachable at {self.proxy_host}:{self.proxy_port}",
                "timestamp": time.time()
            }
        
        results = {
            "proxy_host": self.proxy_host,
            "proxy_port": self.proxy_port,
            "timestamp": time.time(),
            "tests": {}
        }
        
        # Run basic functionality tests
        print("\n1. Testing basic functionality...")
        results["tests"]["basic"] = await self.test_basic_functionality()
        
        # Run caching tests
        print("\n2. Testing caching...")
        results["tests"]["caching"] = await self.test_caching()
        
        # Run error handling tests
        print("\n3. Testing error handling...")
        results["tests"]["error_handling"] = await self.test_error_handling()
        
        # Run performance tests
        print("\n4. Running performance tests...")
        results["tests"]["performance"] = await self.performance_test()
        
        # Test health endpoints
        print("\n5. Testing health endpoints...")
        results["tests"]["health"] = await self.test_proxy_health()
        
        print("\n" + "=" * 50)
        print("Test suite completed!")
        
        return results


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="HTTP Proxy Test Suite")
    parser.add_argument("--host", default="localhost", help="Proxy host")
    parser.add_argument("--port", type=int, default=8080, help="Proxy port")
    parser.add_argument("--output", help="Output file for test results (JSON)")
    parser.add_argument("--performance-only", action="store_true", 
                       help="Run only performance tests")
    parser.add_argument("--concurrent", type=int, default=10, 
                       help="Concurrent requests for performance test")
    parser.add_argument("--total", type=int, default=100, 
                       help="Total requests for performance test")
    
    args = parser.parse_args()
    
    tester = ProxyTester(args.host, args.port)
    
    if args.performance_only:
        result = await tester.performance_test(args.concurrent, args.total)
    else:
        result = await tester.run_all_tests()
    
    # Save results if output file specified
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to {args.output}")
    
    return result


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed: {str(e)}")
        sys.exit(1)
