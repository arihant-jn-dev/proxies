#!/bin/bash

# Proxy Learning Environment Setup Script
# This script sets up the complete proxy learning environment

set -e

echo "🚀 Setting up Proxy Learning Environment"
echo "========================================"

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "✓ Python version: $python_version"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install common requirements
echo "📚 Installing dependencies..."
pip install -r common/requirements.txt

# Make scripts executable
echo "🔧 Making scripts executable..."
find . -name "*.py" -exec chmod +x {} \;

# Create log directory
mkdir -p logs

# Create cache directory
mkdir -p cache

echo ""
echo "✅ Setup complete!"
echo ""
echo "🎯 Quick Start Commands:"
echo "========================"
echo ""
echo "1. HTTP Forward Proxy:"
echo "   cd 01-http-proxies"
echo "   python forward_proxy.py --port 8080"
echo "   # Test: curl -x http://localhost:8080 http://httpbin.org/ip"
echo ""
echo "2. HTTP Reverse Proxy:"
echo "   cd 01-http-proxies"
echo "   python reverse_proxy.py --port 8080 --backend http://httpbin.org"
echo "   # Test: curl http://localhost:8080/get"
echo ""
echo "3. SOCKS5 Proxy:"
echo "   cd 02-socks-proxies"
echo "   python socks5_proxy.py --port 1080"
echo "   # Test: curl --socks5 localhost:1080 http://httpbin.org/ip"
echo ""
echo "4. Load Balancer:"
echo "   cd 03-load-balancer-proxies"
echo "   # Start multiple backends first:"
echo "   # python -m http.server 3001 &"
echo "   # python -m http.server 3002 &"
echo "   # python load_balancer.py --port 8080 --backends http://localhost:3001,http://localhost:3002"
echo ""
echo "📖 For detailed documentation, see README.md in each directory"
echo ""
echo "🧪 To run tests:"
echo "   cd 01-http-proxies"
echo "   python test_proxy.py --host localhost --port 8080"
echo ""
echo "🌟 Happy learning!"
