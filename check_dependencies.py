#!/usr/bin/env python3
"""
Proxy Dependencies Check & Install Script

This script checks for required dependencies and helps install them.
"""

import subprocess
import sys
import importlib
import os

class DependencyManager:
    """Manage proxy implementation dependencies."""
    
    def __init__(self):
        self.required_packages = {
            'aiohttp': {
                'pip_name': 'aiohttp',
                'used_by': ['load_balancer.py', 'api_gateway.py', 'transparent_proxy.py', 'security_proxy.py'],
                'purpose': 'Async HTTP client/server framework for advanced proxies'
            },
            'psutil': {
                'pip_name': 'psutil',
                'used_by': ['performance_tester.py'],
                'purpose': 'System and process monitoring for performance analysis'
            }
        }
        
        self.simple_implementations = [
            'simple_forward_proxy.py',
            'simple_socks5_proxy.py', 
            'simple_load_balancer.py'
        ]
    
    def check_package(self, package_name: str) -> bool:
        """Check if a package is installed."""
        try:
            importlib.import_module(package_name)
            return True
        except ImportError:
            return False
    
    def check_all_dependencies(self) -> dict:
        """Check all required dependencies."""
        results = {}
        
        print("🔍 Checking proxy dependencies...")
        print("=" * 50)
        
        for package, info in self.required_packages.items():
            installed = self.check_package(package)
            results[package] = {
                'installed': installed,
                'info': info
            }
            
            status = "✅ Installed" if installed else "❌ Missing"
            print(f"{package:<15}: {status}")
            
            if not installed:
                print(f"   Used by: {', '.join(info['used_by'])}")
                print(f"   Purpose: {info['purpose']}")
        
        return results
    
    def install_missing_packages(self, missing_packages: list) -> bool:
        """Install missing packages."""
        if not missing_packages:
            print("✅ All required packages are already installed!")
            return True
        
        print(f"\n📦 Installing {len(missing_packages)} missing package(s)...")
        
        for package in missing_packages:
            pip_name = self.required_packages[package]['pip_name']
            print(f"   Installing {package}...")
            
            try:
                subprocess.check_call([
                    sys.executable, '-m', 'pip', 'install', pip_name
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print(f"   ✅ {package} installed successfully")
            except subprocess.CalledProcessError as e:
                print(f"   ❌ Failed to install {package}: {e}")
                return False
        
        return True
    
    def analyze_proxy_files(self) -> dict:
        """Analyze which proxy files can run without additional dependencies."""
        analysis = {
            'working_without_deps': [],
            'need_dependencies': [],
            'missing_files': []
        }
        
        print("\n📊 Analyzing proxy implementations...")
        print("=" * 50)
        
        # Check simple implementations
        for file in self.simple_implementations:
            if os.path.exists(file):
                analysis['working_without_deps'].append(file)
                print(f"✅ {file:<30}: Ready to use (no deps)")
            else:
                analysis['missing_files'].append(file)
                print(f"❌ {file:<30}: File not found")
        
        # Check advanced implementations
        advanced_files = [
            '03-load-balancer-proxies/load_balancer.py',
            '04-api-gateway-proxies/api_gateway.py', 
            '05-transparent-proxies/transparent_proxy.py',
            '06-security-proxies/security_proxy.py',
            '07-performance-analysis/performance_tester.py'
        ]
        
        for file in advanced_files:
            if os.path.exists(file):
                analysis['need_dependencies'].append(file)
                print(f"📦 {file:<30}: Needs dependencies")
            else:
                analysis['missing_files'].append(file)
                print(f"❌ {file:<30}: File not found")
        
        return analysis
    
    def provide_recommendations(self, dep_results: dict, file_analysis: dict):
        """Provide recommendations based on analysis."""
        print("\n💡 RECOMMENDATIONS")
        print("=" * 50)
        
        # Quick start option
        if file_analysis['working_without_deps']:
            print("🚀 QUICK START (No Dependencies Required):")
            for file in file_analysis['working_without_deps']:
                print(f"   python3 {file}")
            print("   These work immediately without any setup!")
        
        # Missing dependencies
        missing_deps = [pkg for pkg, info in dep_results.items() if not info['installed']]
        if missing_deps:
            print(f"\n📦 TO USE ALL FEATURES:")
            print(f"   pip install {' '.join([self.required_packages[pkg]['pip_name'] for pkg in missing_deps])}")
            print("   This enables all advanced proxy features")
        
        # Learning path
        print(f"\n🎓 SUGGESTED LEARNING ORDER:")
        print("1. simple_forward_proxy.py    - Learn HTTP proxy basics")
        print("2. simple_socks5_proxy.py     - Understand SOCKS protocol") 
        print("3. simple_load_balancer.py    - Grasp load balancing concepts")
        print("4. load_balancer.py           - Advanced load balancing algorithms")
        print("5. api_gateway.py             - API management patterns")
        print("6. security_proxy.py          - Security filtering techniques")
        print("7. performance_tester.py      - Performance analysis tools")
        
        # Testing
        print(f"\n🧪 TESTING:")
        print("   python3 test_all_implementations.py")
        print("   This script tests ALL proxy types automatically")


def main():
    """Main entry point."""
    print("🔧 PROXY DEPENDENCIES MANAGER")
    print("Checking and managing proxy implementation dependencies")
    print("=" * 60)
    
    manager = DependencyManager()
    
    # Check dependencies
    dep_results = manager.check_all_dependencies()
    
    # Analyze proxy files
    file_analysis = manager.analyze_proxy_files()
    
    # Ask user about installation
    missing_deps = [pkg for pkg, info in dep_results.items() if not info['installed']]
    
    if missing_deps:
        print(f"\n❓ Missing dependencies: {', '.join(missing_deps)}")
        response = input("Install missing dependencies? (y/n): ").lower().strip()
        
        if response in ['y', 'yes']:
            success = manager.install_missing_packages(missing_deps)
            if success:
                print("\n✅ All dependencies installed successfully!")
                print("   You can now run ALL proxy implementations")
            else:
                print("\n⚠️  Some installations failed")
                print("   Simple proxies will still work without dependencies")
        else:
            print("\n⏭️  Skipping installation")
            print("   You can still use simple proxy implementations")
    
    # Provide recommendations
    manager.provide_recommendations(dep_results, file_analysis)
    
    print(f"\n🎯 Ready to explore proxies! Start with:")
    if file_analysis['working_without_deps']:
        print(f"   python3 {file_analysis['working_without_deps'][0]}")
    else:
        print("   First create simple proxy implementations")


if __name__ == "__main__":
    main()
