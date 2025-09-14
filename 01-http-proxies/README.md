# HTTP Proxies - Forward & Reverse

HTTP proxies are the most common type of proxy, handling HTTP and HTTPS traffic between clients and servers. This section covers both forward proxies (client-side) and reverse proxies (server-side).

## 📋 Table of Contents

- [What are HTTP Proxies?](#what-are-http-proxies)
- [Forward vs Reverse Proxies](#forward-vs-reverse-proxies)
- [Quick Start](#quick-start)
- [Examples](#examples)
- [Configuration](#configuration)
- [Use Cases](#use-cases)
- [Performance Considerations](#performance-considerations)

## What are HTTP Proxies?

HTTP proxies operate at the application layer (Layer 7) and understand HTTP protocol specifics. They can:

- **Inspect and modify** HTTP headers and content
- **Cache responses** to improve performance
- **Filter requests** based on content, URLs, or headers
- **Add authentication** and authorization layers
- **Compress content** to reduce bandwidth usage
- **Handle SSL termination** for HTTPS traffic

### Traffic Flow Diagram

```
Forward Proxy:
Client → Forward Proxy → Internet → Server
   ↑                               ↓
   └─────── Response ──────────────┘

Reverse Proxy:
Client → Internet → Reverse Proxy → Server(s)
   ↑                               ↓
   └─────── Response ──────────────┘
```

## Forward vs Reverse Proxies

### Forward Proxy (Client-Side)
- **Purpose**: Acts on behalf of clients
- **Location**: Between client and internet
- **Visibility**: Server sees proxy IP, not client IP
- **Use Cases**: Privacy, content filtering, caching, bypassing restrictions

### Reverse Proxy (Server-Side)
- **Purpose**: Acts on behalf of servers
- **Location**: Between internet and servers
- **Visibility**: Client sees proxy IP, not server IP
- **Use Cases**: Load balancing, SSL termination, caching, security

## Quick Start

### 1. Install Dependencies

```bash
pip install -r ../common/requirements.txt
```

### 2. Run a Basic Forward Proxy

```bash
python forward_proxy.py --port 8080
```

### 3. Run a Basic Reverse Proxy

```bash
python reverse_proxy.py --port 8080 --backend http://localhost:3000
```

### 4. Test the Proxy

```bash
# Test forward proxy
curl -x http://localhost:8080 http://httpbin.org/ip

# Test reverse proxy
curl http://localhost:8080/api/status
```

## Examples

| File | Description | Complexity |
|------|-------------|------------|
| `forward_proxy.py` | Basic HTTP forward proxy | ⭐⭐ |
| `reverse_proxy.py` | Basic HTTP reverse proxy | ⭐⭐ |
| `caching_proxy.py` | Proxy with HTTP caching | ⭐⭐⭐ |
| `filtering_proxy.py` | Content filtering proxy | ⭐⭐⭐ |
| `ssl_terminating_proxy.py` | HTTPS termination | ⭐⭐⭐⭐ |
| `middleware_proxy.py` | Advanced middleware system | ⭐⭐⭐⭐ |

## Configuration

### Basic Configuration (`config.json`)

```json
{
  "bind_host": "0.0.0.0",
  "bind_port": 8080,
  "backend_servers": [
    "http://localhost:3000",
    "http://localhost:3001"
  ],
  "cache_enabled": true,
  "cache_ttl_seconds": 300,
  "ssl_enabled": false,
  "ssl_cert_file": "cert.pem",
  "ssl_key_file": "key.pem",
  "access_log": true,
  "max_request_size": "10MB",
  "timeout_seconds": 30
}
```

### Environment Variables

```bash
# Copy and modify the example environment file
cp .env.example .env

# Key variables:
PROXY_PORT=8080
BACKEND_URL=http://localhost:3000
LOG_LEVEL=INFO
CACHE_ENABLED=true
```

## Use Cases

### 1. Development Proxy
- **Purpose**: Local development with CORS handling
- **Features**: Request/response logging, header modification
- **Example**: `development_proxy.py`

### 2. Content Filtering
- **Purpose**: Block malicious or inappropriate content
- **Features**: URL filtering, content scanning, malware detection
- **Example**: `filtering_proxy.py`

### 3. Performance Optimization
- **Purpose**: Improve response times and reduce bandwidth
- **Features**: Response caching, compression, connection pooling
- **Example**: `caching_proxy.py`

### 4. Security Enhancement
- **Purpose**: Add security layers without modifying backend
- **Features**: SSL termination, rate limiting, DDoS protection
- **Example**: `ssl_terminating_proxy.py`

## Performance Considerations

### Connection Management
- **Keep-Alive**: Reuse connections to reduce overhead
- **Connection Pooling**: Manage multiple concurrent connections
- **Timeouts**: Set appropriate timeout values

### Caching Strategy
- **Cache Headers**: Respect `Cache-Control` and `ETag` headers
- **Cache Storage**: Choose between memory, disk, or Redis
- **Cache Invalidation**: Implement proper cache eviction policies

### Scaling
- **Async I/O**: Use asyncio for high concurrency
- **Process Pooling**: Scale across multiple CPU cores
- **Load Balancing**: Distribute traffic across proxy instances

### Monitoring
- **Metrics**: Track response times, error rates, cache hit ratios
- **Logging**: Structured logging for debugging and analysis
- **Health Checks**: Monitor backend server availability

## Testing

### Unit Tests
```bash
pytest tests/test_http_proxy.py -v
```

### Load Testing
```bash
# Install load testing tools
pip install locust

# Run load test
locust -f load_test.py --host=http://localhost:8080
```

### Integration Tests
```bash
# Test with real HTTP services
python test_integration.py
```

## Advanced Topics

### Custom Middleware
Create custom middleware for request/response processing:

```python
class AuthMiddleware:
    async def process_request(self, request):
        # Add authentication logic
        pass
    
    async def process_response(self, response):
        # Add response processing
        pass
```

### Plugin System
Extend functionality with a plugin architecture:

```python
class ProxyPlugin:
    def on_request(self, request):
        pass
    
    def on_response(self, response):
        pass
```

### Circuit Breaker
Implement circuit breaker pattern for backend resilience:

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        # Implementation...
```

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Find process using port
   lsof -i :8080
   # Kill process
   kill -9 <PID>
   ```

2. **SSL Certificate Errors**
   ```bash
   # Generate self-signed certificate
   openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
   ```

3. **Connection Timeouts**
   - Check backend server availability
   - Verify network connectivity
   - Adjust timeout settings

### Debugging
- Enable debug logging: `LOG_LEVEL=DEBUG`
- Use proxy debugging tools: `mitmproxy`, `Charles Proxy`
- Monitor network traffic: `tcpdump`, `Wireshark`

## Next Steps

1. **Try the Examples**: Start with `forward_proxy.py` and `reverse_proxy.py`
2. **Explore Advanced Features**: Look at caching and SSL termination
3. **Learn About Other Proxy Types**: Check out SOCKS proxies and load balancers
4. **Build Your Own**: Use the utilities in `common/` to create custom solutions

---

**Continue Learning**: Next, explore [SOCKS Proxies](../02-socks-proxies/) for lower-level traffic handling.
