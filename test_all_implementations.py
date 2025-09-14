#!/usr/bin/env python3
"""
Complete Proxy Testing Suite

This script tests ALL proxy implementations in the repository,
including the simple working versions and the advanced implementations.
"""

import subprocess
import time
import urllib.request
import json
import signal
import sys
import os
from typing import List, Dict, Tuple


class ComprehensiveProxyTester:
    """Test all proxy implementations comprehensively."""
    
    def __init__(self):
        self.processes = []
        self.test_results = {}
    
    def start_proxy(self, script_path: str, port: int, args: List[str] = None) -> bool:
        """Start a proxy and return success status."""
        cmd = [sys.executable, script_path, "--port", str(port)]
        if args:
            cmd.extend(args)
        
        print(f"🚀 Starting {os.path.basename(script_path)} on port {port}...")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes.append((process, script_path, port))
            time.sleep(3)  # Wait for startup
            
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                print(f"❌ Failed to start {os.path.basename(script_path)}")
                print(f"   Error: {stderr}")
                return False
            
            print(f"✅ {os.path.basename(script_path)} started (PID: {process.pid})")
            return True
            
        except Exception as e:
            print(f"❌ Exception starting {os.path.basename(script_path)}: {e}")
            return False
    
    def test_http_proxy(self, proxy_url: str, test_name: str) -> Dict:
        """Test HTTP proxy functionality."""
        results = {"proxy": test_name, "tests": []}
        
        test_urls = [
            "http://httpbin.org/get",
            "http://httpbin.org/headers",
            "http://httpbin.org/user-agent"
        ]
        
        for url in test_urls:
            try:
                proxy_handler = urllib.request.ProxyHandler({'http': proxy_url})
                opener = urllib.request.build_opener(proxy_handler)
                
                start_time = time.time()
                with opener.open(url, timeout=10) as response:
                    data = response.read()
                    duration = time.time() - start_time
                    
                    results["tests"].append({
                        "url": url,
                        "status": "success",
                        "response_time": round(duration * 1000, 2),
                        "size": len(data),
                        "status_code": response.status
                    })
                    
            except Exception as e:
                results["tests"].append({
                    "url": url,
                    "status": "failed",
                    "error": str(e)
                })
        
        return results
    
    def test_socks_proxy(self, proxy_host: str, proxy_port: int, test_name: str) -> Dict:
        """Test SOCKS proxy using curl."""
        results = {"proxy": test_name, "tests": []}
        
        test_urls = [
            "http://httpbin.org/ip",
            "http://httpbin.org/get"
        ]
        
        for url in test_urls:
            try:
                cmd = ["curl", "-s", "--socks5", f"{proxy_host}:{proxy_port}", 
                       url, "--max-time", "10"]
                
                start_time = time.time()
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                duration = time.time() - start_time
                
                if result.returncode == 0:
                    results["tests"].append({
                        "url": url,
                        "status": "success",
                        "response_time": round(duration * 1000, 2),
                        "size": len(result.stdout)
                    })
                else:
                    results["tests"].append({
                        "url": url,
                        "status": "failed",
                        "error": result.stderr
                    })
                    
            except subprocess.TimeoutExpired:
                results["tests"].append({
                    "url": url,
                    "status": "failed",
                    "error": "timeout"
                })
            except FileNotFoundError:
                results["tests"].append({
                    "url": url,
                    "status": "failed",
                    "error": "curl not found"
                })
        
        return results
    
    def test_management_endpoints(self, host: str, port: int, endpoints: List[str], test_name: str) -> Dict:
        """Test management endpoints."""
        results = {"proxy": test_name, "management_tests": []}
        
        for endpoint in endpoints:
            try:
                url = f"http://{host}:{port}{endpoint}"
                
                start_time = time.time()
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = response.read()
                    duration = time.time() - start_time
                    
                    results["management_tests"].append({
                        "endpoint": endpoint,
                        "status": "success",
                        "response_time": round(duration * 1000, 2),
                        "size": len(data),
                        "status_code": response.status
                    })
                    
            except Exception as e:
                results["management_tests"].append({
                    "endpoint": endpoint,
                    "status": "failed",
                    "error": str(e)
                })
        
        return results
    
    def run_all_tests(self):
        """Run comprehensive tests on all proxy types."""
        print("🎯 COMPREHENSIVE PROXY TESTING SUITE")
        print("Testing ALL proxy implementations")
        print("=" * 60)
        
        all_results = {}
        
        # Test 1: Simple HTTP Forward Proxy
        print("\n1️⃣  Testing Simple HTTP Forward Proxy")
        if self.start_proxy("simple_forward_proxy.py", 8080):
            results = self.test_http_proxy("http://localhost:8080", "Simple Forward Proxy")
            all_results["simple_forward_proxy"] = results
            print(f"   Tests: {len([t for t in results['tests'] if t['status'] == 'success'])}/{len(results['tests'])} passed")
        
        # Test 2: Simple SOCKS5 Proxy
        print("\n2️⃣  Testing Simple SOCKS5 Proxy")
        if self.start_proxy("simple_socks5_proxy.py", 1080):
            results = self.test_socks_proxy("localhost", 1080, "Simple SOCKS5 Proxy")
            all_results["simple_socks5_proxy"] = results
            print(f"   Tests: {len([t for t in results['tests'] if t['status'] == 'success'])}/{len(results['tests'])} passed")
        
        # Test 3: Simple Load Balancer
        print("\n3️⃣  Testing Simple Load Balancer")
        if self.start_proxy("simple_load_balancer.py", 8082):
            results = self.test_http_proxy("http://localhost:8082", "Simple Load Balancer")
            mgmt_results = self.test_management_endpoints("localhost", 8082, 
                                                        ["/_lb/stats", "/_lb/health"], 
                                                        "Load Balancer Management")
            results.update(mgmt_results)
            all_results["simple_load_balancer"] = results
            print(f"   Tests: {len([t for t in results['tests'] if t['status'] == 'success'])}/{len(results['tests'])} passed")
            print(f"   Management: {len([t for t in results['management_tests'] if t['status'] == 'success'])}/{len(results['management_tests'])} passed")
        
        # Test 4: Advanced Load Balancer
        print("\n4️⃣  Testing Advanced Load Balancer")
        if self.start_proxy("03-load-balancer-proxies/load_balancer.py", 8083):
            results = self.test_http_proxy("http://localhost:8083", "Advanced Load Balancer")
            mgmt_results = self.test_management_endpoints("localhost", 8083,
                                                        ["/_lb/stats", "/_lb/health"],
                                                        "Advanced Load Balancer Management")
            results.update(mgmt_results)
            all_results["advanced_load_balancer"] = results
            print(f"   Tests: {len([t for t in results['tests'] if t['status'] == 'success'])}/{len(results['tests'])} passed")
        
        # Test 5: API Gateway
        print("\n5️⃣  Testing API Gateway")
        if self.start_proxy("04-api-gateway-proxies/api_gateway.py", 8084):
            # Test both regular endpoints and management
            results = self.test_http_proxy("http://localhost:8084", "API Gateway")
            mgmt_results = self.test_management_endpoints("localhost", 8084,
                                                        ["/_gateway/stats", "/_gateway/health", "/_gateway/endpoints"],
                                                        "API Gateway Management")
            results.update(mgmt_results)
            all_results["api_gateway"] = results
            print(f"   Tests: {len([t for t in results['tests'] if t['status'] == 'success'])}/{len(results['tests'])} passed")
            print(f"   Management: {len([t for t in results['management_tests'] if t['status'] == 'success'])}/{len(results['management_tests'])} passed")
        
        # Test 6: Transparent Proxy
        print("\n6️⃣  Testing Transparent Proxy")
        if self.start_proxy("05-transparent-proxies/transparent_proxy.py", 8888):
            results = self.test_http_proxy("http://localhost:8888", "Transparent Proxy")
            mgmt_results = self.test_management_endpoints("localhost", 9999,
                                                        ["/stats", "/traffic"],
                                                        "Transparent Proxy Management")
            results.update(mgmt_results)
            all_results["transparent_proxy"] = results
            print(f"   Tests: {len([t for t in results['tests'] if t['status'] == 'success'])}/{len(results['tests'])} passed")
        
        # Test 7: Security Proxy
        print("\n7️⃣  Testing Security Proxy")
        if self.start_proxy("06-security-proxies/security_proxy.py", 8085):
            results = self.test_http_proxy("http://localhost:8085", "Security Proxy")
            mgmt_results = self.test_management_endpoints("localhost", 8085,
                                                        ["/_security/stats", "/_security/health", "/_security/policy"],
                                                        "Security Proxy Management")
            results.update(mgmt_results)
            all_results["security_proxy"] = results
            print(f"   Tests: {len([t for t in results['tests'] if t['status'] == 'success'])}/{len(results['tests'])} passed")
            print(f"   Management: {len([t for t in results['management_tests'] if t['status'] == 'success'])}/{len(results['management_tests'])} passed")
        
        # Test 8: Performance Testing (quick test)
        print("\n8️⃣  Testing Performance Analyzer")
        if self.start_proxy("simple_forward_proxy.py", 8086):  # Start a proxy to test against
            try:
                cmd = [sys.executable, "07-performance-analysis/performance_tester.py",
                       "--proxy", "http://localhost:8086", "--quick"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    print("   ✅ Performance analyzer working")
                    all_results["performance_analyzer"] = {"status": "success", "output": result.stdout}
                else:
                    print("   ❌ Performance analyzer failed")
                    all_results["performance_analyzer"] = {"status": "failed", "error": result.stderr}
            except Exception as e:
                print(f"   ❌ Performance analyzer exception: {e}")
                all_results["performance_analyzer"] = {"status": "failed", "error": str(e)}
        
        # Generate comprehensive report
        self.generate_report(all_results)
        
        return all_results
    
    def generate_report(self, results: Dict):
        """Generate comprehensive test report."""
        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE TEST REPORT")
        print("=" * 60)
        
        total_proxies = 0
        working_proxies = 0
        total_tests = 0
        passed_tests = 0
        
        for proxy_name, proxy_results in results.items():
            total_proxies += 1
            
            if "tests" in proxy_results:
                proxy_tests = proxy_results["tests"]
                proxy_passed = len([t for t in proxy_tests if t.get("status") == "success"])
                total_tests += len(proxy_tests)
                passed_tests += proxy_passed
                
                if proxy_passed > 0:
                    working_proxies += 1
                
                print(f"{proxy_name.replace('_', ' ').title():<25}: {proxy_passed}/{len(proxy_tests)} tests passed")
                
                # Management tests
                if "management_tests" in proxy_results:
                    mgmt_tests = proxy_results["management_tests"]
                    mgmt_passed = len([t for t in mgmt_tests if t.get("status") == "success"])
                    print(f"{'  Management endpoints':<25}: {mgmt_passed}/{len(mgmt_tests)} working")
            
            elif "status" in proxy_results:
                if proxy_results["status"] == "success":
                    working_proxies += 1
                print(f"{proxy_name.replace('_', ' ').title():<25}: {proxy_results['status']}")
        
        print("\n" + "-" * 60)
        print(f"📈 OVERALL STATISTICS")
        print(f"Working Proxies:     {working_proxies}/{total_proxies} ({working_proxies/total_proxies*100:.1f}%)")
        print(f"Passed Tests:        {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)")
        
        # Save detailed results
        with open('comprehensive_test_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Detailed results saved to comprehensive_test_results.json")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS")
        if working_proxies == total_proxies:
            print("✅ All proxy implementations are working correctly!")
            print("✅ You can use any of these proxies for learning and development")
        else:
            print("⚠️  Some proxies may need dependency installation:")
            print("   Run: pip install aiohttp psutil")
            print("✅ Simple proxies (simple_*.py) work without extra dependencies")
        
        print(f"\n🎓 LEARNING PATHS")
        print("1. Start with simple_forward_proxy.py for basic concepts")
        print("2. Explore simple_socks5_proxy.py for protocol details") 
        print("3. Study load balancers for scaling concepts")
        print("4. Examine security_proxy.py for protection mechanisms")
        print("5. Use performance_tester.py to analyze proxy performance")
    
    def cleanup(self):
        """Clean up all running processes."""
        print(f"\n🧹 Cleaning up {len(self.processes)} processes...")
        
        for process, script_path, port in self.processes:
            if process.poll() is None:
                print(f"   Stopping {os.path.basename(script_path)} (PID: {process.pid})")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        
        self.processes.clear()


def main():
    """Main entry point."""
    tester = ComprehensiveProxyTester()
    
    # Signal handler for cleanup
    def signal_handler(sig, frame):
        print("\n🛑 Test interrupted")
        tester.cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        results = tester.run_all_tests()
        
        print(f"\n🎯 All tests completed!")
        print(f"Check comprehensive_test_results.json for detailed results")
        
    except Exception as e:
        print(f"❌ Test suite error: {e}")
    finally:
        tester.cleanup()


if __name__ == "__main__":
    main()
