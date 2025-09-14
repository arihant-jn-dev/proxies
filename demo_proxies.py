#!/usr/bin/env python3
"""
Proxy Demonstration Script

This script demonstrates working proxy implementations by:
1. Starting simple proxy servers
2. Testing them with real HTTP requests
3. Showing the differences between proxy types
"""

import asyncio
import subprocess
import time
import sys
import signal
import requests
from urllib.parse import urlparse

class ProxyDemo:
    """Demonstrates different proxy types with working examples."""
    
    def __init__(self):
        self.processes = []
    
    def start_proxy(self, script, port, name):
        """Start a proxy server in the background."""
        try:
            cmd = [sys.executable, script, "--port", str(port), "--host", "localhost"]
            
            print(f"🚀 Starting {name} on port {port}...")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Give proxy time to start
            time.sleep(2)
            
            # Check if it's still running
            if process.poll() is None:
                self.processes.append((process, name))
                print(f"✅ {name} started successfully (PID: {process.pid})")
                return True
            else:
                stdout, stderr = process.communicate()
                print(f"❌ Failed to start {name}")
                if stderr:
                    print(f"Error: {stderr.decode()[:200]}")
                return False
                
        except Exception as e:
            print(f"❌ Error starting {name}: {str(e)}")
            return False
    
    def test_http_forward_proxy(self, port=8080):
        """Test HTTP forward proxy."""
        print(f"\n🧪 Testing HTTP Forward Proxy (port {port})")
        print("-" * 50)
        
        proxy_url = f"http://localhost:{port}"
        test_urls = [
            "http://httpbin.org/ip",
            "http://httpbin.org/headers",
            "http://httpbin.org/user-agent"
        ]
        
        for i, url in enumerate(test_urls, 1):
            try:
                print(f"\nTest {i}: {url}")
                
                # Test with proxy
                response = requests.get(
                    url, 
                    proxies={"http": proxy_url}, 
                    timeout=10
                )
                
                if response.status_code == 200:
                    print(f"✅ SUCCESS - Status: {response.status_code}")
                    
                    # Show interesting parts of response
                    if "ip" in url:
                        data = response.json()
                        print(f"   Your IP via proxy: {data.get('origin', 'Unknown')}")
                    elif "headers" in url:
                        data = response.json()
                        headers = data.get('headers', {})
                        forwarded = headers.get('X-Forwarded-For', 'Not set')
                        print(f"   X-Forwarded-For: {forwarded}")
                    elif "user-agent" in url:
                        data = response.json()
                        ua = data.get('user-agent', 'Unknown')
                        print(f"   User-Agent: {ua}")
                else:
                    print(f"❌ FAILED - Status: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ ERROR: {str(e)}")
    
    def test_socks5_proxy(self, port=1080):
        """Test SOCKS5 proxy."""
        print(f"\n🧪 Testing SOCKS5 Proxy (port {port})")
        print("-" * 50)
        
        # Test using curl with SOCKS5 support
        test_commands = [
            f"curl --socks5 localhost:{port} http://httpbin.org/ip",
            f"curl --socks5 localhost:{port} http://httpbin.org/headers"
        ]
        
        for i, cmd in enumerate(test_commands, 1):
            try:
                print(f"\nTest {i}: {cmd}")
                
                result = subprocess.run(
                    cmd.split(), 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                
                if result.returncode == 0:
                    print(f"✅ SUCCESS")
                    # Show first part of response
                    output = result.stdout.strip()
                    if output:
                        lines = output.split('\n')
                        print(f"   Response preview: {lines[0][:100]}...")
                else:
                    print(f"❌ FAILED - Exit code: {result.returncode}")
                    if result.stderr:
                        print(f"   Error: {result.stderr.strip()[:100]}")
                        
            except subprocess.TimeoutExpired:
                print(f"⏰ TIMEOUT")
            except Exception as e:
                print(f"❌ ERROR: {str(e)}")
    
    def demonstrate_proxy_differences(self):
        """Demonstrate the differences between proxy types."""
        print(f"\n🎨 Demonstrating Proxy Differences")
        print("=" * 60)
        
        print("\n1. HTTP Forward Proxy Features:")
        print("   - Works with HTTP protocol only")
        print("   - Client configures proxy settings")
        print("   - Can inspect and modify HTTP requests/responses")
        print("   - Adds forwarding headers (X-Forwarded-For)")
        
        print("\n2. SOCKS5 Proxy Features:")
        print("   - Protocol-agnostic (works with any TCP/UDP traffic)")
        print("   - Lower-level than HTTP proxies")
        print("   - Supports authentication")
        print("   - Can tunnel any application protocol")
        
        print("\n3. Comparison Test:")
        try:
            # Test the same URL through both proxies
            test_url = "http://httpbin.org/ip"
            
            # HTTP Forward Proxy
            print(f"\n   Via HTTP Forward Proxy:")
            response1 = requests.get(
                test_url, 
                proxies={"http": "http://localhost:8080"}, 
                timeout=5
            )
            if response1.status_code == 200:
                ip1 = response1.json().get('origin', 'Unknown')
                print(f"   IP seen by server: {ip1}")
            
            # SOCKS5 Proxy (using curl)
            print(f"\n   Via SOCKS5 Proxy:")
            result = subprocess.run(
                ["curl", "--socks5", "localhost:1080", test_url],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                try:
                    import json
                    data = json.loads(result.stdout)
                    ip2 = data.get('origin', 'Unknown')
                    print(f"   IP seen by server: {ip2}")
                except:
                    print(f"   Response received (couldn't parse JSON)")
            
        except Exception as e:
            print(f"   Comparison failed: {str(e)}")
    
    def run_performance_comparison(self):
        """Compare performance of different proxy types."""
        print(f"\n⚡ Performance Comparison")
        print("=" * 40)
        
        test_url = "http://httpbin.org/get"
        num_requests = 5
        
        # Direct connection (baseline)
        print(f"\n1. Direct Connection (baseline):")
        direct_times = []
        for i in range(num_requests):
            start_time = time.time()
            try:
                response = requests.get(test_url, timeout=5)
                if response.status_code == 200:
                    direct_times.append((time.time() - start_time) * 1000)
            except:
                pass
        
        if direct_times:
            avg_direct = sum(direct_times) / len(direct_times)
            print(f"   Average response time: {avg_direct:.1f}ms")
        
        # HTTP Forward Proxy
        print(f"\n2. HTTP Forward Proxy:")
        proxy_times = []
        for i in range(num_requests):
            start_time = time.time()
            try:
                response = requests.get(
                    test_url, 
                    proxies={"http": "http://localhost:8080"}, 
                    timeout=5
                )
                if response.status_code == 200:
                    proxy_times.append((time.time() - start_time) * 1000)
            except:
                pass
        
        if proxy_times:
            avg_proxy = sum(proxy_times) / len(proxy_times)
            print(f"   Average response time: {avg_proxy:.1f}ms")
            
            if direct_times:
                overhead = ((avg_proxy - avg_direct) / avg_direct) * 100
                print(f"   Overhead compared to direct: {overhead:.1f}%")
        
        # SOCKS5 would require more complex setup for fair comparison
        print(f"\n3. SOCKS5 Proxy:")
        print(f"   (Requires specialized client library for fair comparison)")
    
    def cleanup(self):
        """Stop all running processes."""
        print(f"\n🧹 Stopping {len(self.processes)} proxy processes...")
        
        for process, name in self.processes:
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"✅ Stopped {name} (PID: {process.pid})")
            except subprocess.TimeoutExpired:
                process.kill()
                print(f"🔪 Killed {name} (PID: {process.pid})")
            except Exception as e:
                print(f"⚠️  Error stopping {name}: {str(e)}")
        
        self.processes.clear()

def main():
    """Main demonstration function."""
    print("🎯 PROXY DEMONSTRATION SUITE")
    print("=" * 50)
    print("This demo will start and test different proxy types.")
    print("You'll see how each proxy works and their differences.")
    print()
    
    demo = ProxyDemo()
    
    try:
        # Start the simple proxies
        http_started = demo.start_proxy("simple_forward_proxy.py", 8080, "HTTP Forward Proxy")
        socks_started = demo.start_proxy("simple_socks5_proxy.py", 1080, "SOCKS5 Proxy")
        
        if not http_started and not socks_started:
            print("❌ No proxies started successfully. Exiting.")
            return
        
        # Wait for proxies to be ready
        print(f"\n⏳ Waiting for proxies to be ready...")
        time.sleep(3)
        
        # Test each proxy type
        if http_started:
            demo.test_http_forward_proxy(8080)
            
        if socks_started:
            demo.test_socks5_proxy(1080)
        
        # Demonstrate differences
        if http_started and socks_started:
            demo.demonstrate_proxy_differences()
        
        # Performance comparison
        if http_started:
            demo.run_performance_comparison()
        
        print(f"\n🎉 DEMONSTRATION COMPLETE!")
        print("=" * 40)
        print("Key Takeaways:")
        print("• HTTP proxies work at application layer (Layer 7)")
        print("• SOCKS proxies work at session layer (Layer 5)")
        print("• Each proxy type has different use cases")
        print("• Performance overhead varies by proxy type")
        print("• Both provide anonymity and traffic routing")
        
    except KeyboardInterrupt:
        print("\n⚠️  Demo interrupted by user")
        
    finally:
        demo.cleanup()

if __name__ == "__main__":
    main()
