#!/usr/bin/env python3
"""
Comprehensive Proxy Testing and Demonstration Script

This script demonstrates all proxy types by:
1. Starting each proxy type in the background
2. Running tests against them
3. Showing practical usage examples
4. Measuring performance
"""

import asyncio
import json
import subprocess
import sys
import time
import signal
import os
from typing import List, Dict, Optional
import requests

# Test configurations for different proxy types
PROXY_CONFIGS = {
    "http_forward": {
        "name": "HTTP Forward Proxy",
        "script": "01-http-proxies/forward_proxy.py",
        "port": 8080,
        "test_commands": [
            "curl -x http://localhost:8080 http://httpbin.org/ip",
            "curl -x http://localhost:8080 http://httpbin.org/headers",
            "curl -x http://localhost:8080 http://httpbin.org/get?test=forward_proxy"
        ]
    },
    "http_reverse": {
        "name": "HTTP Reverse Proxy",
        "script": "01-http-proxies/reverse_proxy.py",
        "port": 8081,
        "args": ["--backend", "http://httpbin.org"],
        "test_commands": [
            "curl http://localhost:8081/ip",
            "curl http://localhost:8081/headers", 
            "curl http://localhost:8081/get?test=reverse_proxy"
        ]
    },
    "http_caching": {
        "name": "HTTP Caching Proxy",
        "script": "01-http-proxies/caching_proxy.py",
        "port": 8082,
        "args": ["--backend", "http://httpbin.org"],
        "test_commands": [
            "curl http://localhost:8082/cache/60",  # Cacheable for 60s
            "curl http://localhost:8082/cache/60",  # Should be cache hit
            "curl http://localhost:8082/_cache/stats"  # Cache statistics
        ]
    },
    "socks5": {
        "name": "SOCKS5 Proxy",
        "script": "02-socks-proxies/socks5_proxy.py", 
        "port": 1080,
        "test_commands": [
            "curl --socks5 localhost:1080 http://httpbin.org/ip",
            "curl --socks5 localhost:1080 http://httpbin.org/headers"
        ]
    }
}

class ProxyTester:
    """Test runner for all proxy types."""
    
    def __init__(self):
        self.running_processes: List[subprocess.Popen] = []
        self.test_results: Dict = {}
        
    def start_proxy(self, config: Dict) -> Optional[subprocess.Popen]:
        """Start a proxy server in the background."""
        try:
            cmd = [sys.executable, config["script"], "--port", str(config["port"])]
            if "args" in config:
                cmd.extend(config["args"])
            
            print(f"🚀 Starting {config['name']} on port {config['port']}...")
            
            # Activate virtual environment first
            env = os.environ.copy()
            venv_python = "./venv/bin/python"
            if os.path.exists(venv_python):
                cmd[0] = venv_python
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            
            # Give the proxy time to start
            time.sleep(2)
            
            # Check if process is still running
            if process.poll() is None:
                self.running_processes.append(process)
                print(f"✅ {config['name']} started successfully (PID: {process.pid})")
                return process
            else:
                stdout, stderr = process.communicate()
                print(f"❌ Failed to start {config['name']}")
                print(f"Error: {stderr.decode()}")
                return None
                
        except Exception as e:
            print(f"❌ Error starting {config['name']}: {str(e)}")
            return None
    
    def test_proxy(self, config: Dict) -> Dict:
        """Test a proxy with the configured test commands."""
        results = {
            "name": config["name"],
            "port": config["port"],
            "tests": [],
            "success_count": 0,
            "total_count": 0
        }
        
        print(f"\n🧪 Testing {config['name']}...")
        print("=" * 50)
        
        for i, cmd in enumerate(config["test_commands"], 1):
            print(f"\nTest {i}: {cmd}")
            
            try:
                # Run the test command
                result = subprocess.run(
                    cmd.split(),
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                success = result.returncode == 0
                results["tests"].append({
                    "command": cmd,
                    "success": success,
                    "returncode": result.returncode,
                    "stdout": result.stdout[:500],  # Limit output
                    "stderr": result.stderr[:500]
                })
                
                if success:
                    results["success_count"] += 1
                    print(f"✅ PASSED")
                    if result.stdout.strip():
                        print(f"Response preview: {result.stdout[:200]}...")
                else:
                    print(f"❌ FAILED (exit code: {result.returncode})")
                    if result.stderr:
                        print(f"Error: {result.stderr[:200]}")
                
                results["total_count"] += 1
                
            except subprocess.TimeoutExpired:
                print(f"⏰ TIMEOUT")
                results["tests"].append({
                    "command": cmd,
                    "success": False,
                    "error": "timeout"
                })
                results["total_count"] += 1
                
            except Exception as e:
                print(f"❌ ERROR: {str(e)}")
                results["tests"].append({
                    "command": cmd,
                    "success": False,
                    "error": str(e)
                })
                results["total_count"] += 1
        
        success_rate = (results["success_count"] / results["total_count"] * 100) if results["total_count"] > 0 else 0
        print(f"\n📊 {config['name']} Results: {results['success_count']}/{results['total_count']} tests passed ({success_rate:.1f}%)")
        
        return results
    
    def run_performance_test(self, config: Dict) -> Dict:
        """Run a simple performance test against the proxy."""
        print(f"\n⚡ Performance testing {config['name']}...")
        
        if "socks" in config["script"]:
            # SOCKS proxy requires special handling
            return {"skipped": "SOCKS performance test requires special client"}
        
        results = {
            "name": config["name"],
            "metrics": {}
        }
        
        try:
            import time
            import requests
            
            # Test URL based on proxy type
            if "reverse" in config["script"] or "caching" in config["script"]:
                test_url = f"http://localhost:{config['port']}/get"
                proxies = None
            else:
                test_url = "http://httpbin.org/get"
                proxies = {"http": f"http://localhost:{config['port']}"}
            
            # Warm up
            try:
                requests.get(test_url, proxies=proxies, timeout=5)
            except:
                pass
            
            # Performance test
            num_requests = 10
            start_time = time.time()
            successful_requests = 0
            response_times = []
            
            for i in range(num_requests):
                try:
                    req_start = time.time()
                    response = requests.get(test_url, proxies=proxies, timeout=5)
                    req_end = time.time()
                    
                    if response.status_code == 200:
                        successful_requests += 1
                        response_times.append((req_end - req_start) * 1000)  # ms
                        
                except Exception as e:
                    print(f"Request {i+1} failed: {str(e)}")
            
            total_time = time.time() - start_time
            
            if response_times:
                results["metrics"] = {
                    "total_requests": num_requests,
                    "successful_requests": successful_requests,
                    "success_rate": (successful_requests / num_requests) * 100,
                    "total_time_seconds": total_time,
                    "avg_response_time_ms": sum(response_times) / len(response_times),
                    "min_response_time_ms": min(response_times),
                    "max_response_time_ms": max(response_times),
                    "requests_per_second": successful_requests / total_time
                }
                
                print(f"📈 Performance Results:")
                print(f"   Success Rate: {results['metrics']['success_rate']:.1f}%")
                print(f"   Avg Response Time: {results['metrics']['avg_response_time_ms']:.1f}ms")
                print(f"   Requests/Second: {results['metrics']['requests_per_second']:.1f}")
            else:
                results["metrics"] = {"error": "No successful requests"}
                
        except Exception as e:
            results["metrics"] = {"error": str(e)}
            print(f"❌ Performance test failed: {str(e)}")
        
        return results
    
    def demonstrate_specific_features(self):
        """Demonstrate specific features of different proxy types."""
        print("\n🎨 Demonstrating Specific Features")
        print("=" * 50)
        
        # HTTP Caching Proxy - Cache demonstration
        print("\n1. HTTP Caching Proxy - Cache Behavior:")
        try:
            # First request (should be cache miss)
            start_time = time.time()
            response1 = requests.get("http://localhost:8082/cache/60", timeout=5)
            time1 = (time.time() - start_time) * 1000
            
            # Second request (should be cache hit)
            start_time = time.time()
            response2 = requests.get("http://localhost:8082/cache/60", timeout=5)
            time2 = (time.time() - start_time) * 1000
            
            print(f"   First request (cache miss): {time1:.1f}ms")
            print(f"   Second request (cache hit): {time2:.1f}ms")
            print(f"   Cache performance improvement: {((time1 - time2) / time1 * 100):.1f}%")
            
            # Check cache headers
            cache_header = response2.headers.get('X-Cache', 'UNKNOWN')
            print(f"   Cache status: {cache_header}")
            
        except Exception as e:
            print(f"   Cache demo failed: {str(e)}")
        
        # HTTP Reverse Proxy - Load balancing stats
        print("\n2. HTTP Reverse Proxy - Backend Stats:")
        try:
            response = requests.get("http://localhost:8081/_proxy/stats", timeout=5)
            if response.status_code == 200:
                stats = response.json()
                print(f"   Total requests: {stats.get('requests_total', 0)}")
                print(f"   Success rate: {stats.get('success_rate', 0):.1f}%")
                print(f"   Avg response time: {stats.get('avg_response_time_ms', 0):.1f}ms")
            else:
                print(f"   Stats endpoint returned {response.status_code}")
        except Exception as e:
            print(f"   Stats demo failed: {str(e)}")
        
        # HTTP Forward Proxy - Header modification
        print("\n3. HTTP Forward Proxy - Header Inspection:")
        try:
            response = requests.get(
                "http://httpbin.org/headers",
                proxies={"http": "http://localhost:8080"},
                timeout=5
            )
            if response.status_code == 200:
                headers = response.json().get('headers', {})
                forwarded_for = headers.get('X-Forwarded-For', 'Not set')
                forwarded_proto = headers.get('X-Forwarded-Proto', 'Not set')
                print(f"   X-Forwarded-For: {forwarded_for}")
                print(f"   X-Forwarded-Proto: {forwarded_proto}")
            else:
                print(f"   Header check returned {response.status_code}")
        except Exception as e:
            print(f"   Header demo failed: {str(e)}")
    
    def cleanup(self):
        """Stop all running proxy processes."""
        print(f"\n🧹 Stopping {len(self.running_processes)} proxy processes...")
        
        for process in self.running_processes:
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"✅ Stopped process {process.pid}")
            except subprocess.TimeoutExpired:
                process.kill()
                print(f"🔪 Killed process {process.pid}")
            except Exception as e:
                print(f"⚠️  Error stopping process {process.pid}: {str(e)}")
        
        self.running_processes.clear()
    
    def generate_report(self):
        """Generate a comprehensive test report."""
        print("\n📋 COMPREHENSIVE TEST REPORT")
        print("=" * 60)
        
        total_tests = 0
        total_passed = 0
        
        for proxy_type, results in self.test_results.items():
            print(f"\n🔍 {results['name']}")
            print("-" * 40)
            print(f"Port: {results['port']}")
            print(f"Tests: {results['success_count']}/{results['total_count']} passed")
            
            if 'performance' in results:
                perf = results['performance'].get('metrics', {})
                if 'success_rate' in perf:
                    print(f"Performance: {perf['success_rate']:.1f}% success rate, {perf['avg_response_time_ms']:.1f}ms avg")
                elif 'error' in perf:
                    print(f"Performance: {perf['error']}")
                else:
                    print("Performance: Skipped")
            
            total_tests += results['total_count']
            total_passed += results['success_count']
        
        overall_success = (total_passed / total_tests * 100) if total_tests > 0 else 0
        print(f"\n🎯 OVERALL RESULTS")
        print(f"Total tests: {total_passed}/{total_tests} passed ({overall_success:.1f}%)")
        
        # Save detailed results to file
        with open("proxy_test_results.json", "w") as f:
            json.dump(self.test_results, f, indent=2)
        print(f"\n💾 Detailed results saved to proxy_test_results.json")


def main():
    """Main testing function."""
    print("🎯 COMPREHENSIVE PROXY TESTING SUITE")
    print("=" * 60)
    print("This script will test all proxy implementations with real examples.")
    print("Each proxy will be started, tested, and demonstrated.")
    print()
    
    tester = ProxyTester()
    
    try:
        # Start all proxies
        for proxy_type, config in PROXY_CONFIGS.items():
            process = tester.start_proxy(config)
            if not process:
                print(f"⚠️  Skipping tests for {config['name']} due to startup failure")
                continue
        
        # Wait a bit for all proxies to be ready
        print(f"\n⏳ Waiting for all proxies to be ready...")
        time.sleep(3)
        
        # Test each proxy
        for proxy_type, config in PROXY_CONFIGS.items():
            if any(p.poll() is None for p in tester.running_processes):  # At least one proxy is running
                results = tester.test_proxy(config)
                
                # Add performance test
                perf_results = tester.run_performance_test(config)
                results['performance'] = perf_results
                
                tester.test_results[proxy_type] = results
        
        # Demonstrate specific features
        tester.demonstrate_specific_features()
        
        # Generate final report
        tester.generate_report()
        
    except KeyboardInterrupt:
        print("\n⚠️  Testing interrupted by user")
        
    finally:
        tester.cleanup()


if __name__ == "__main__":
    main()
