#!/usr/bin/env python3
"""
Simple Proxy Testing Suite

This script tests the working simple proxy implementations.
"""

import subprocess
import time
import urllib.request
import json
import signal
import sys
import os

class SimpleProxyTester:
    """Simple proxy testing suite for working implementations."""
    
    def __init__(self):
        self.processes = []
        self.test_results = {}
    
    def start_proxy(self, script_name, port, wait_time=3):
        """Start a proxy server and return the process."""
        cmd = [sys.executable, script_name, "--port", str(port)]
        
        print(f"🚀 Starting {script_name} on port {port}...")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        self.processes.append((process, script_name))
        time.sleep(wait_time)  # Wait for proxy to start
        
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(f"❌ Failed to start {script_name}")
            print(f"Error: {stderr}")
            return None
        
        print(f"✅ {script_name} started successfully (PID: {process.pid})")
        return process
    
    def test_http_request(self, url, proxy_url=None, timeout=10):
        """Test HTTP request through proxy."""
        try:
            if proxy_url:
                proxy_handler = urllib.request.ProxyHandler({'http': proxy_url})
                opener = urllib.request.build_opener(proxy_handler)
                urllib.request.install_opener(opener)
            else:
                # Reset to no proxy
                urllib.request.install_opener(urllib.request.build_opener())
            
            with urllib.request.urlopen(url, timeout=timeout) as response:
                data = response.read().decode()
                return {
                    "success": True,
                    "status": response.status,
                    "size": len(data),
                    "data": data
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def test_forward_proxy(self):
        """Test HTTP forward proxy."""
        print("\n" + "="*50)
        print("🌐 TESTING HTTP FORWARD PROXY")
        print("="*50)
        
        # Start forward proxy
        process = self.start_proxy("simple_forward_proxy.py", 8080)
        if not process:
            return False
        
        tests = [
            ("http://httpbin.org/get", "Basic GET request"),
            ("http://httpbin.org/user-agent", "User-Agent test"),
            ("http://httpbin.org/ip", "IP address test")
        ]
        
        results = []
        for url, description in tests:
            print(f"\n🔍 Testing: {description}")
            print(f"   URL: {url}")
            
            # Test with proxy
            proxy_result = self.test_http_request(url, "http://localhost:8080")
            
            if proxy_result['success']:
                print(f"   ✅ Success - Status: {proxy_result['status']}, Size: {proxy_result['size']} bytes")
                try:
                    data = json.loads(proxy_result['data'])
                    if 'origin' in data:
                        print(f"   📍 Origin IP: {data['origin']}")
                    if 'headers' in data and 'User-Agent' in data['headers']:
                        print(f"   🔍 User-Agent: {data['headers']['User-Agent']}")
                except:
                    pass
                results.append(True)
            else:
                print(f"   ❌ Failed: {proxy_result['error']}")
                results.append(False)
        
        success_rate = (sum(results) / len(results)) * 100
        print(f"\n📊 Forward Proxy Results: {sum(results)}/{len(results)} tests passed ({success_rate:.0f}%)")
        
        self.test_results['forward_proxy'] = {
            'passed': sum(results),
            'total': len(results),
            'success_rate': success_rate
        }
        
        return True
    
    def test_socks5_proxy(self):
        """Test SOCKS5 proxy using curl."""
        print("\n" + "="*50)
        print("🧦 TESTING SOCKS5 PROXY")
        print("="*50)
        
        # Start SOCKS5 proxy
        process = self.start_proxy("simple_socks5_proxy.py", 1080)
        if not process:
            return False
        
        # Check if curl is available
        try:
            subprocess.run(["curl", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  curl not found, skipping SOCKS5 tests")
            return False
        
        tests = [
            ("http://httpbin.org/ip", "IP address test"),
            ("http://httpbin.org/get", "Basic GET test")
        ]
        
        results = []
        for url, description in tests:
            print(f"\n🔍 Testing: {description}")
            print(f"   URL: {url}")
            
            try:
                cmd = ["curl", "-s", "--socks5", "localhost:1080", url, "--max-time", "10"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                
                if result.returncode == 0:
                    print(f"   ✅ Success - Response size: {len(result.stdout)} bytes")
                    try:
                        data = json.loads(result.stdout)
                        if 'origin' in data:
                            print(f"   📍 Origin IP: {data['origin']}")
                    except:
                        print(f"   📄 Response preview: {result.stdout[:100]}...")
                    results.append(True)
                else:
                    print(f"   ❌ Failed: {result.stderr}")
                    results.append(False)
                    
            except subprocess.TimeoutExpired:
                print(f"   ⏰ Timeout")
                results.append(False)
        
        success_rate = (sum(results) / len(results)) * 100 if results else 0
        print(f"\n📊 SOCKS5 Proxy Results: {sum(results)}/{len(results)} tests passed ({success_rate:.0f}%)")
        
        self.test_results['socks5_proxy'] = {
            'passed': sum(results),
            'total': len(results),
            'success_rate': success_rate
        }
        
        return True
    
    def test_load_balancer(self):
        """Test load balancer proxy."""
        print("\n" + "="*50)
        print("⚖️  TESTING LOAD BALANCER PROXY")
        print("="*50)
        
        # Start load balancer
        process = self.start_proxy("simple_load_balancer.py", 8082)
        if not process:
            return False
        
        tests = [
            ("http://localhost:8082/get", "Backend routing test"),
            ("http://localhost:8082/_lb/health", "Health check"),
            ("http://localhost:8082/_lb/stats", "Statistics endpoint")
        ]
        
        results = []
        for url, description in tests:
            print(f"\n🔍 Testing: {description}")
            print(f"   URL: {url}")
            
            result = self.test_http_request(url)
            
            if result['success']:
                print(f"   ✅ Success - Status: {result['status']}, Size: {result['size']} bytes")
                
                if url.endswith('/health') or url.endswith('/stats'):
                    try:
                        data = json.loads(result['data'])
                        if url.endswith('/health'):
                            print(f"   💚 Status: {data.get('status', 'unknown')}")
                            backends = data.get('backends', {})
                            for backend, healthy in backends.items():
                                status = "✅" if healthy else "❌"
                                print(f"   🔗 {backend}: {status}")
                        elif url.endswith('/stats'):
                            stats = data.get('stats', {})
                            total_requests = sum(s.get('requests', 0) for s in stats.values())
                            print(f"   📈 Total requests: {total_requests}")
                    except:
                        pass
                
                results.append(True)
            else:
                print(f"   ❌ Failed: {result['error']}")
                results.append(False)
        
        success_rate = (sum(results) / len(results)) * 100
        print(f"\n📊 Load Balancer Results: {sum(results)}/{len(results)} tests passed ({success_rate:.0f}%)")
        
        self.test_results['load_balancer'] = {
            'passed': sum(results),
            'total': len(results),
            'success_rate': success_rate
        }
        
        return True
    
    def performance_comparison(self):
        """Compare performance of direct vs proxy requests."""
        print("\n" + "="*50)
        print("🏃 PERFORMANCE COMPARISON")
        print("="*50)
        
        url = "http://httpbin.org/get"
        iterations = 3
        
        print(f"Testing {iterations} requests to {url}")
        
        # Test direct connection
        print(f"\n⚡ Direct connection:")
        direct_times = []
        for i in range(iterations):
            start = time.time()
            result = self.test_http_request(url)
            if result['success']:
                duration = time.time() - start
                direct_times.append(duration)
                print(f"   Request {i+1}: {duration:.3f}s")
        
        # Test through forward proxy
        print(f"\n🔄 Through forward proxy:")
        proxy_times = []
        for i in range(iterations):
            start = time.time()
            result = self.test_http_request(url, "http://localhost:8080")
            if result['success']:
                duration = time.time() - start
                proxy_times.append(duration)
                print(f"   Request {i+1}: {duration:.3f}s")
        
        if direct_times and proxy_times:
            avg_direct = sum(direct_times) / len(direct_times)
            avg_proxy = sum(proxy_times) / len(proxy_times)
            overhead = ((avg_proxy - avg_direct) / avg_direct) * 100
            
            print(f"\n📊 Performance Summary:")
            print(f"   Direct:    {avg_direct:.3f}s average")
            print(f"   Proxy:     {avg_proxy:.3f}s average")
            print(f"   Overhead:  {overhead:+.1f}%")
            
            self.test_results['performance'] = {
                'direct_avg': avg_direct,
                'proxy_avg': avg_proxy,
                'overhead_percent': overhead
            }
    
    def cleanup(self):
        """Clean up all running processes."""
        print(f"\n🧹 Cleaning up {len(self.processes)} processes...")
        for process, name in self.processes:
            if process.poll() is None:
                print(f"   Stopping {name} (PID: {process.pid})")
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
        
        self.processes.clear()
    
    def run_all_tests(self):
        """Run all proxy tests."""
        print("🎯 SIMPLE PROXY TESTING SUITE")
        print("=" * 60)
        print("Testing working proxy implementations...")
        
        try:
            # Test each proxy type
            self.test_forward_proxy()
            self.test_socks5_proxy()
            self.test_load_balancer()
            
            # Performance testing
            self.performance_comparison()
            
            # Final summary
            print("\n" + "="*60)
            print("📋 FINAL TEST SUMMARY")
            print("="*60)
            
            total_tests = 0
            total_passed = 0
            
            for proxy_type, results in self.test_results.items():
                if proxy_type != 'performance':
                    total_tests += results['total']
                    total_passed += results['passed']
                    
                    status = "✅ PASS" if results['success_rate'] >= 80 else "❌ FAIL"
                    print(f"{proxy_type.replace('_', ' ').title():<20}: {results['passed']}/{results['total']} ({results['success_rate']:.0f}%) {status}")
            
            overall_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
            print(f"\n🎯 OVERALL SUCCESS RATE: {total_passed}/{total_tests} ({overall_rate:.0f}%)")
            
            if 'performance' in self.test_results:
                perf = self.test_results['performance']
                print(f"⚡ PROXY OVERHEAD: {perf['overhead_percent']:+.1f}%")
            
            # Save results
            with open('simple_test_results.json', 'w') as f:
                json.dump(self.test_results, f, indent=2)
            print(f"\n💾 Detailed results saved to simple_test_results.json")
            
        except KeyboardInterrupt:
            print("\n⚠️  Tests interrupted by user")
        finally:
            self.cleanup()

def main():
    """Main entry point."""
    tester = SimpleProxyTester()
    
    # Set up signal handler for cleanup
    def signal_handler(sig, frame):
        print("\n🛑 Received interrupt signal")
        tester.cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run tests
    tester.run_all_tests()

if __name__ == "__main__":
    main()
