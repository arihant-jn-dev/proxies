#!/bin/bash
# Quick Proxy Testing Commands
# Use these commands to manually test each proxy type

echo "🎯 PROXY TESTING GUIDE"
echo "======================"
echo ""

echo "📋 PREREQUISITES:"
echo "   cd /Users/arihant.ja/Desktop/copilot/proxies"
echo "   source venv/bin/activate"
echo ""

echo "🌐 HTTP FORWARD PROXY TEST:"
echo "   Terminal 1: python simple_forward_proxy.py --port 8080"
echo "   Terminal 2: curl -x http://localhost:8080 http://httpbin.org/ip"
echo "   Terminal 2: curl -x http://localhost:8080 http://httpbin.org/get"
echo ""

echo "🧦 SOCKS5 PROXY TEST:"
echo "   Terminal 1: python simple_socks5_proxy.py --port 1080"
echo "   Terminal 2: curl --socks5 localhost:1080 http://httpbin.org/ip"
echo "   Terminal 2: curl --socks5 localhost:1080 http://httpbin.org/get"
echo ""

echo "⚖️  LOAD BALANCER PROXY TEST:"
echo "   Terminal 1: python simple_load_balancer.py --port 8082"
echo "   Terminal 2: curl http://localhost:8082/get"
echo "   Terminal 2: curl http://localhost:8082/_lb/health"
echo "   Terminal 2: curl http://localhost:8082/_lb/stats"
echo ""

echo "🔄 REVERSE PROXY TEST (requires aiohttp):"
echo "   Terminal 1: python simple_reverse_proxy.py --port 8081 --backend http://httpbin.org"
echo "   Terminal 2: curl http://localhost:8081/get"
echo "   Terminal 2: curl http://localhost:8081/_proxy/health"
echo ""

echo "🏃 AUTOMATED TESTING:"
echo "   python simple_test_suite.py    # Test all working proxies"
echo "   python demo_proxies.py         # Quick demo"
echo ""

echo "📊 MONITORING COMMANDS:"
echo "   # Monitor proxy logs"
echo "   tail -f proxy.log"
echo ""
echo "   # Check proxy processes"
echo "   ps aux | grep python | grep proxy"
echo ""
echo "   # Network connections"
echo "   netstat -an | grep LISTEN | grep -E '8080|8081|8082|1080'"
echo ""

echo "💡 TIPS:"
echo "   - Use Ctrl+C to stop any proxy"
echo "   - Each proxy runs on a different port to avoid conflicts"
echo "   - Check the JSON responses to see proxy headers added"
echo "   - Monitor system resources with 'top' or 'htop'"
echo ""

echo "🚀 QUICK START:"
echo "   ./setup.sh                      # Initial setup"
echo "   python simple_test_suite.py     # Run all tests"
