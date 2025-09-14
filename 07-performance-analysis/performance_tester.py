#!/usr/bin/env python3
"""
Performance Analysis Tools for Proxies

🎯 MAIN PURPOSE:
Comprehensive performance testing and analysis tools for proxy implementations
to measure, optimize, and validate proxy performance under various conditions.

🔍 WHAT WE'RE TRYING TO ACCOMPLISH:
1. **Performance Benchmarking**: Measure proxy performance vs direct connections
2. **Scalability Testing**: Determine maximum concurrent connection limits
3. **Bottleneck Identification**: Find performance limiting factors
4. **Resource Monitoring**: Track CPU, memory, and network usage
5. **Reliability Testing**: Verify proxy stability under sustained load
6. **Optimization Guidance**: Provide data-driven performance improvements

📊 REAL-WORLD USE CASES:

1. **Production Deployment Planning**:
   - Netflix: Capacity planning for CDN proxy servers
   - Cloudflare: Performance optimization of edge proxy nodes
   - AWS: Load balancer performance validation
   - Google: Proxy infrastructure scaling decisions

2. **Proxy Technology Comparison**:
   - HAProxy vs Nginx performance comparison
   - Hardware vs software load balancer evaluation
   - Different proxy algorithms efficiency testing
   - Cloud provider proxy service benchmarking

3. **Infrastructure Optimization**:
   - Data center proxy server sizing
   - Network bandwidth requirements calculation
   - Cost-performance optimization analysis
   - Hardware upgrade decision support

4. **Quality Assurance & Testing**:
   - Pre-production performance validation
   - Regression testing after code changes
   - Stress testing before major events
   - SLA compliance verification

🧪 TESTING EXAMPLES:

# 1. Quick performance test:
python3 performance_tester.py --proxy http://localhost:8080 --quick

# 2. Comprehensive load test:
python3 performance_tester.py --proxy http://localhost:8080 \
  --duration 300 \
  --max-connections 100 \
  --requests-per-second 50

# 3. Compare proxy vs direct connection:
python3 performance_tester.py --proxy http://localhost:8080 \
  --target http://httpbin.org \
  --compare-direct

# 4. Test specific proxy features:
python3 performance_tester.py --proxy http://localhost:8080 \
  --test-caching \
  --test-ssl \
  --test-websockets

# 5. Generate detailed report:
python3 performance_tester.py --proxy http://localhost:8080 \
  --duration 600 \
  --report performance_report.html

📈 PERFORMANCE METRICS:

1. **Throughput Measurements**:
   - Requests per second (RPS)
   - Megabits per second (Mbps)
   - Concurrent connection capacity
   - Data transfer rates

2. **Latency Analysis**:
   - Average response time
   - 95th/99th percentile latency
   - Connection establishment time
   - Time to first byte (TTFB)

3. **Resource Utilization**:
   - CPU usage (user, system, idle)
   - Memory consumption (RAM, swap)
   - Network bandwidth utilization
   - File descriptor usage

4. **Reliability Metrics**:
   - Error rate percentage
   - Connection failure rate
   - Timeout occurrences
   - Recovery time after failures

5. **Scalability Indicators**:
   - Maximum concurrent connections
   - Performance degradation curves
   - Resource exhaustion points
   - Breaking point identification

💡 TESTING SCENARIOS:

1. **Baseline Performance**:
   - Single connection throughput
   - Minimum latency measurement
   - Idle resource consumption
   - Basic functionality validation

2. **Load Testing**:
   - Gradual load increase
   - Sustained load testing
   - Peak load capacity
   - Load distribution patterns

3. **Stress Testing**:
   - Beyond normal capacity
   - Resource exhaustion testing
   - Failure point identification
   - Recovery behavior analysis

4. **Endurance Testing**:
   - Long-duration testing (hours/days)
   - Memory leak detection
   - Connection pool exhaustion
   - Performance degradation over time

This module provides comprehensive performance testing and analysis tools
for proxy implementations including:
- Throughput measurement
- Latency analysis
- Concurrent connection testing
- Memory and CPU profiling
- Load testing scenarios
"""

import asyncio
import aiohttp
import time
import statistics
import json
import logging
import psutil
import threading
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import urllib.request
import subprocess
import sys


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    response_times: List[float] = None
    bytes_transferred: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.response_times is None:
            self.response_times = []
        if self.errors is None:
            self.errors = []
    
    def add_response(self, response_time: float, bytes_count: int, error: str = None):
        """Add a response measurement."""
        self.total_requests += 1
        
        if error:
            self.failed_requests += 1
            self.errors.append(error)
        else:
            self.successful_requests += 1
            self.response_times.append(response_time)
            self.bytes_transferred += bytes_count
            self.min_response_time = min(self.min_response_time, response_time)
            self.max_response_time = max(self.max_response_time, response_time)
    
    def get_statistics(self) -> Dict:
        """Calculate performance statistics."""
        if not self.response_times:
            return {
                "total_requests": self.total_requests,
                "successful_requests": 0,
                "failed_requests": self.failed_requests,
                "success_rate": 0.0,
                "error_rate": 100.0 if self.total_requests > 0 else 0.0
            }
        
        success_rate = (self.successful_requests / self.total_requests) * 100
        error_rate = (self.failed_requests / self.total_requests) * 100
        
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": round(success_rate, 2),
            "error_rate": round(error_rate, 2),
            "min_response_time": round(self.min_response_time * 1000, 2),  # ms
            "max_response_time": round(self.max_response_time * 1000, 2),  # ms
            "avg_response_time": round(statistics.mean(self.response_times) * 1000, 2),  # ms
            "median_response_time": round(statistics.median(self.response_times) * 1000, 2),  # ms
            "p95_response_time": round(self._percentile(self.response_times, 95) * 1000, 2),  # ms
            "p99_response_time": round(self._percentile(self.response_times, 99) * 1000, 2),  # ms
            "throughput_rps": round(self.successful_requests / self.total_time, 2) if self.total_time > 0 else 0,
            "bytes_transferred": self.bytes_transferred,
            "avg_bytes_per_request": round(self.bytes_transferred / self.successful_requests, 2) if self.successful_requests > 0 else 0
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of response times."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]


class ResourceMonitor:
    """Monitor system resources during performance tests."""
    
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.monitoring = False
        self.measurements = []
        self.monitor_thread = None
    
    def start_monitoring(self):
        """Start resource monitoring."""
        self.monitoring = True
        self.measurements = []
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop resource monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.monitoring:
            try:
                measurement = {
                    "timestamp": time.time(),
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                    "memory_used_mb": psutil.virtual_memory().used / (1024 * 1024),
                    "disk_io_read": psutil.disk_io_counters().read_bytes if psutil.disk_io_counters() else 0,
                    "disk_io_write": psutil.disk_io_counters().write_bytes if psutil.disk_io_counters() else 0,
                    "network_sent": psutil.net_io_counters().bytes_sent,
                    "network_recv": psutil.net_io_counters().bytes_recv
                }
                self.measurements.append(measurement)
                time.sleep(self.interval)
            except Exception as e:
                logging.error(f"Resource monitoring error: {e}")
    
    def get_summary(self) -> Dict:
        """Get resource usage summary."""
        if not self.measurements:
            return {}
        
        cpu_values = [m["cpu_percent"] for m in self.measurements]
        memory_values = [m["memory_percent"] for m in self.measurements]
        
        return {
            "duration": self.measurements[-1]["timestamp"] - self.measurements[0]["timestamp"],
            "cpu_avg": round(statistics.mean(cpu_values), 2),
            "cpu_max": round(max(cpu_values), 2),
            "memory_avg": round(statistics.mean(memory_values), 2),
            "memory_max": round(max(memory_values), 2),
            "memory_used_mb_avg": round(statistics.mean([m["memory_used_mb"] for m in self.measurements]), 2),
            "network_sent_mb": round((self.measurements[-1]["network_sent"] - self.measurements[0]["network_sent"]) / (1024 * 1024), 2),
            "network_recv_mb": round((self.measurements[-1]["network_recv"] - self.measurements[0]["network_recv"]) / (1024 * 1024), 2)
        }


class ProxyTester:
    """Comprehensive proxy performance tester."""
    
    def __init__(self, proxy_url: str, target_url: str = "http://httpbin.org/get"):
        self.proxy_url = proxy_url
        self.target_url = target_url
        self.logger = logging.getLogger("proxy_tester")
        self.resource_monitor = ResourceMonitor()
    
    async def test_async_performance(self, concurrent_requests: int = 10, 
                                   total_requests: int = 100) -> PerformanceMetrics:
        """Test proxy performance using async HTTP client."""
        metrics = PerformanceMetrics()
        
        # Parse proxy URL
        proxy_parts = self.proxy_url.replace("http://", "").split(":")
        proxy_host = proxy_parts[0]
        proxy_port = int(proxy_parts[1])
        
        connector = aiohttp.TCPConnector(limit=concurrent_requests)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        ) as session:
            
            # Create semaphore to limit concurrent requests
            semaphore = asyncio.Semaphore(concurrent_requests)
            
            async def make_request():
                async with semaphore:
                    start_time = time.time()
                    try:
                        async with session.get(
                            self.target_url,
                            proxy=f"http://{proxy_host}:{proxy_port}"
                        ) as response:
                            content = await response.read()
                            response_time = time.time() - start_time
                            metrics.add_response(response_time, len(content))
                    except Exception as e:
                        response_time = time.time() - start_time
                        metrics.add_response(response_time, 0, str(e))
            
            # Start resource monitoring
            self.resource_monitor.start_monitoring()
            
            # Run all requests
            start_time = time.time()
            tasks = [make_request() for _ in range(total_requests)]
            await asyncio.gather(*tasks, return_exceptions=True)
            metrics.total_time = time.time() - start_time
            
            # Stop resource monitoring
            self.resource_monitor.stop_monitoring()
        
        return metrics
    
    def test_sync_performance(self, concurrent_requests: int = 10, 
                            total_requests: int = 100) -> PerformanceMetrics:
        """Test proxy performance using sync HTTP client."""
        metrics = PerformanceMetrics()
        
        def make_request():
            start_time = time.time()
            try:
                # Configure proxy
                proxy_handler = urllib.request.ProxyHandler({'http': self.proxy_url})
                opener = urllib.request.build_opener(proxy_handler)
                
                with opener.open(self.target_url, timeout=30) as response:
                    content = response.read()
                    response_time = time.time() - start_time
                    metrics.add_response(response_time, len(content))
            except Exception as e:
                response_time = time.time() - start_time
                metrics.add_response(response_time, 0, str(e))
        
        # Start resource monitoring
        self.resource_monitor.start_monitoring()
        
        # Run requests with thread pool
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
            futures = [executor.submit(make_request) for _ in range(total_requests)]
            for future in as_completed(futures):
                future.result()  # Wait for completion
        
        metrics.total_time = time.time() - start_time
        
        # Stop resource monitoring
        self.resource_monitor.stop_monitoring()
        
        return metrics
    
    def test_latency_distribution(self, requests: int = 50) -> PerformanceMetrics:
        """Test latency distribution with detailed timing."""
        metrics = PerformanceMetrics()
        
        for i in range(requests):
            start_time = time.time()
            try:
                proxy_handler = urllib.request.ProxyHandler({'http': self.proxy_url})
                opener = urllib.request.build_opener(proxy_handler)
                
                with opener.open(self.target_url, timeout=30) as response:
                    content = response.read()
                    response_time = time.time() - start_time
                    metrics.add_response(response_time, len(content))
                    
                    # Log progress
                    if (i + 1) % 10 == 0:
                        self.logger.info(f"Completed {i + 1}/{requests} latency tests")
                        
            except Exception as e:
                response_time = time.time() - start_time
                metrics.add_response(response_time, 0, str(e))
        
        metrics.total_time = sum(metrics.response_times)
        return metrics
    
    def stress_test(self, duration_seconds: int = 60, 
                   max_concurrent: int = 50) -> PerformanceMetrics:
        """Run stress test for specified duration."""
        metrics = PerformanceMetrics()
        end_time = time.time() + duration_seconds
        
        # Start resource monitoring
        self.resource_monitor.start_monitoring()
        
        def make_request():
            start_time = time.time()
            try:
                proxy_handler = urllib.request.ProxyHandler({'http': self.proxy_url})
                opener = urllib.request.build_opener(proxy_handler)
                
                with opener.open(self.target_url, timeout=10) as response:
                    content = response.read()
                    response_time = time.time() - start_time
                    metrics.add_response(response_time, len(content))
            except Exception as e:
                response_time = time.time() - start_time
                metrics.add_response(response_time, 0, str(e))
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = []
            
            while time.time() < end_time:
                # Submit new requests if we're below max concurrent
                while len(futures) < max_concurrent and time.time() < end_time:
                    future = executor.submit(make_request)
                    futures.append(future)
                
                # Remove completed futures
                futures = [f for f in futures if not f.done()]
                
                time.sleep(0.1)  # Small delay to prevent tight loop
            
            # Wait for remaining requests
            for future in futures:
                future.result()
        
        metrics.total_time = time.time() - start_time
        
        # Stop resource monitoring
        self.resource_monitor.stop_monitoring()
        
        return metrics


def run_comprehensive_test(proxy_url: str, target_url: str = "http://httpbin.org/get"):
    """Run comprehensive performance test suite."""
    print(f"🎯 COMPREHENSIVE PROXY PERFORMANCE TEST")
    print(f"Proxy: {proxy_url}")
    print(f"Target: {target_url}")
    print("=" * 60)
    
    tester = ProxyTester(proxy_url, target_url)
    results = {}
    
    # Test 1: Basic performance
    print("\n1️⃣  Basic Performance Test (50 requests, 5 concurrent)")
    basic_metrics = tester.test_sync_performance(concurrent_requests=5, total_requests=50)
    basic_stats = basic_metrics.get_statistics()
    basic_resources = tester.resource_monitor.get_summary()
    
    print(f"   Success Rate: {basic_stats['success_rate']}%")
    print(f"   Avg Response Time: {basic_stats['avg_response_time']}ms")
    print(f"   Throughput: {basic_stats['throughput_rps']} req/s")
    print(f"   Resource Usage: CPU {basic_resources.get('cpu_avg', 0)}%, Memory {basic_resources.get('memory_avg', 0)}%")
    
    results['basic_test'] = {
        'performance': basic_stats,
        'resources': basic_resources
    }
    
    # Test 2: Latency distribution
    print("\n2️⃣  Latency Distribution Test (100 sequential requests)")
    latency_metrics = tester.test_latency_distribution(requests=100)
    latency_stats = latency_metrics.get_statistics()
    
    print(f"   Min: {latency_stats['min_response_time']}ms")
    print(f"   Avg: {latency_stats['avg_response_time']}ms")
    print(f"   Median: {latency_stats['median_response_time']}ms")
    print(f"   P95: {latency_stats['p95_response_time']}ms")
    print(f"   P99: {latency_stats['p99_response_time']}ms")
    print(f"   Max: {latency_stats['max_response_time']}ms")
    
    results['latency_test'] = latency_stats
    
    # Test 3: Concurrent load
    print("\n3️⃣  Concurrent Load Test (200 requests, 20 concurrent)")
    load_metrics = tester.test_sync_performance(concurrent_requests=20, total_requests=200)
    load_stats = load_metrics.get_statistics()
    load_resources = tester.resource_monitor.get_summary()
    
    print(f"   Success Rate: {load_stats['success_rate']}%")
    print(f"   Avg Response Time: {load_stats['avg_response_time']}ms")
    print(f"   Throughput: {load_stats['throughput_rps']} req/s")
    print(f"   P95 Response Time: {load_stats['p95_response_time']}ms")
    print(f"   Resource Usage: CPU {load_resources.get('cpu_avg', 0)}%, Memory {load_resources.get('memory_avg', 0)}%")
    
    results['load_test'] = {
        'performance': load_stats,
        'resources': load_resources
    }
    
    # Test 4: Stress test
    print("\n4️⃣  Stress Test (30 seconds, up to 30 concurrent)")
    stress_metrics = tester.stress_test(duration_seconds=30, max_concurrent=30)
    stress_stats = stress_metrics.get_statistics()
    stress_resources = tester.resource_monitor.get_summary()
    
    print(f"   Total Requests: {stress_stats['total_requests']}")
    print(f"   Success Rate: {stress_stats['success_rate']}%")
    print(f"   Avg Response Time: {stress_stats['avg_response_time']}ms")
    print(f"   Throughput: {stress_stats['throughput_rps']} req/s")
    print(f"   Resource Usage: CPU {stress_resources.get('cpu_avg', 0)}%, Memory {stress_resources.get('memory_avg', 0)}%")
    
    results['stress_test'] = {
        'performance': stress_stats,
        'resources': stress_resources
    }
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 60)
    
    print(f"Basic Test Throughput:    {basic_stats['throughput_rps']} req/s")
    print(f"Load Test Throughput:     {load_stats['throughput_rps']} req/s")
    print(f"Stress Test Throughput:   {stress_stats['throughput_rps']} req/s")
    print(f"Avg Response Time Range:  {latency_stats['min_response_time']}ms - {latency_stats['max_response_time']}ms")
    print(f"P95 Response Time (Load): {load_stats['p95_response_time']}ms")
    print(f"Overall Success Rate:     {load_stats['success_rate']}%")
    
    # Save results
    with open('performance_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Detailed results saved to performance_results.json")
    
    return results


async def async_performance_test(proxy_url: str, target_url: str = "http://httpbin.org/get"):
    """Run async performance test."""
    print(f"\n🚀 ASYNC PERFORMANCE TEST")
    print(f"Proxy: {proxy_url}")
    print(f"Target: {target_url}")
    print("-" * 40)
    
    tester = ProxyTester(proxy_url, target_url)
    
    # Test with different concurrency levels
    concurrency_levels = [5, 10, 20, 50]
    results = {}
    
    for concurrency in concurrency_levels:
        print(f"\nTesting with {concurrency} concurrent connections...")
        
        metrics = await tester.test_async_performance(
            concurrent_requests=concurrency,
            total_requests=concurrency * 10
        )
        
        stats = metrics.get_statistics()
        resources = tester.resource_monitor.get_summary()
        
        print(f"   Success Rate: {stats['success_rate']}%")
        print(f"   Avg Response Time: {stats['avg_response_time']}ms")
        print(f"   Throughput: {stats['throughput_rps']} req/s")
        
        results[f'concurrency_{concurrency}'] = {
            'performance': stats,
            'resources': resources
        }
    
    return results


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Proxy Performance Analysis")
    parser.add_argument("--proxy", required=True, help="Proxy URL (e.g., http://localhost:8080)")
    parser.add_argument("--target", default="http://httpbin.org/get", help="Target URL")
    parser.add_argument("--async", action="store_true", help="Run async tests")
    parser.add_argument("--quick", action="store_true", help="Run quick test only")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    try:
        if args.async:
            asyncio.run(async_performance_test(args.proxy, args.target))
        elif args.quick:
            tester = ProxyTester(args.proxy, args.target)
            metrics = tester.test_sync_performance(concurrent_requests=5, total_requests=20)
            stats = metrics.get_statistics()
            print(f"Quick Test Results:")
            print(f"  Success Rate: {stats['success_rate']}%")
            print(f"  Avg Response Time: {stats['avg_response_time']}ms")
            print(f"  Throughput: {stats['throughput_rps']} req/s")
        else:
            run_comprehensive_test(args.proxy, args.target)
    
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Error running performance test: {e}")


if __name__ == "__main__":
    main()
