# Load Balancer Proxies - Traffic Distribution

Load balancer proxies distribute incoming requests across multiple backend servers to improve performance, reliability, and scalability. They act as intelligent traffic distributors that ensure optimal resource utilization.

## 📋 Table of Contents

- [What are Load Balancer Proxies?](#what-are-load-balancer-proxies)
- [Load Balancing Algorithms](#load-balancing-algorithms)
- [Health Checking](#health-checking)
- [Quick Start](#quick-start)
- [Examples](#examples)
- [Configuration](#configuration)
- [Advanced Features](#advanced-features)
- [Monitoring and Metrics](#monitoring-and-metrics)

## What are Load Balancer Proxies?

Load balancer proxies sit between clients and multiple backend servers, distributing requests to ensure:

- **High Availability**: If one server fails, traffic continues to healthy servers
- **Scalability**: Add more servers to handle increased load
- **Performance**: Distribute load to prevent server overload
- **Reliability**: Health checks ensure traffic only goes to healthy servers

### Architecture Diagram

```
                    Load Balancer Proxy
                           │
    Client ────────────────┼────────────────► Backend Pool
                           │
                    ┌──────┼──────┐
                    │      │      │
                Server 1  Server 2  Server 3
                (Active) (Active) (Standby)
```

### Traffic Distribution Flow

```
1. Client Request → Load Balancer
2. Algorithm Selection → Choose Backend Server
3. Health Check → Verify Server Status
4. Forward Request → Selected Server
5. Response Relay → Back to Client
6. Metrics Update → Record Performance
```

## Load Balancing Algorithms

### 1. Round Robin
**Description**: Distributes requests sequentially to each server
**Use Case**: Equal capacity servers with similar request types
**Pros**: Simple, fair distribution
**Cons**: Doesn't consider server load or capacity

```python
class RoundRobin:
    def __init__(self, servers):
        self.servers = servers
        self.current = 0
    
    def select_server(self):
        server = self.servers[self.current]
        self.current = (self.current + 1) % len(self.servers)
        return server
```

### 2. Weighted Round Robin
**Description**: Assigns weights to servers based on capacity
**Use Case**: Servers with different capacities
**Pros**: Accounts for server differences
**Cons**: Static weights don't adapt to current load

```python
class WeightedRoundRobin:
    def __init__(self, servers_weights):
        self.servers_weights = servers_weights
        self.current_weights = {s: 0 for s, w in servers_weights}
    
    def select_server(self):
        total_weight = sum(w for s, w in self.servers_weights)
        
        for server, weight in self.servers_weights:
            self.current_weights[server] += weight
            
            if self.current_weights[server] >= total_weight:
                self.current_weights[server] -= total_weight
                return server
```

### 3. Least Connections
**Description**: Routes to server with fewest active connections
**Use Case**: Long-lived connections or varying request duration
**Pros**: Adapts to actual load
**Cons**: Requires connection tracking

```python
class LeastConnections:
    def __init__(self, servers):
        self.servers = servers
        self.connections = {s: 0 for s in servers}
    
    def select_server(self):
        return min(self.servers, key=lambda s: self.connections[s])
    
    def on_connection_start(self, server):
        self.connections[server] += 1
    
    def on_connection_end(self, server):
        self.connections[server] -= 1
```

### 4. Least Response Time
**Description**: Routes to server with fastest average response time
**Use Case**: Performance-critical applications
**Pros**: Optimizes for speed
**Cons**: Requires response time tracking

```python
class LeastResponseTime:
    def __init__(self, servers):
        self.servers = servers
        self.response_times = {s: [] for s in servers}
    
    def select_server(self):
        def avg_response_time(server):
            times = self.response_times[server]
            return sum(times) / len(times) if times else 0
        
        return min(self.servers, key=avg_response_time)
    
    def record_response_time(self, server, response_time):
        times = self.response_times[server]
        times.append(response_time)
        if len(times) > 100:  # Keep last 100 measurements
            times.pop(0)
```

### 5. IP Hash
**Description**: Uses client IP hash to ensure session persistence
**Use Case**: Stateful applications requiring session affinity
**Pros**: Session persistence
**Cons**: May cause uneven distribution

```python
import hashlib

class IPHash:
    def __init__(self, servers):
        self.servers = servers
    
    def select_server(self, client_ip):
        hash_value = int(hashlib.md5(client_ip.encode()).hexdigest(), 16)
        return self.servers[hash_value % len(self.servers)]
```

### 6. Consistent Hashing
**Description**: Uses consistent hashing for better distribution when servers change
**Use Case**: Distributed systems with dynamic server pools
**Pros**: Minimal redistribution when servers change
**Cons**: More complex implementation

```python
import hashlib
import bisect

class ConsistentHash:
    def __init__(self, servers, replicas=150):
        self.servers = servers
        self.replicas = replicas
        self.ring = {}
        self.sorted_keys = []
        self._build_ring()
    
    def _build_ring(self):
        for server in self.servers:
            for i in range(self.replicas):
                key = self._hash(f"{server}:{i}")
                self.ring[key] = server
                self.sorted_keys.append(key)
        self.sorted_keys.sort()
    
    def _hash(self, key):
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
    
    def select_server(self, client_key):
        if not self.ring:
            return None
        
        key = self._hash(client_key)
        idx = bisect.bisect_right(self.sorted_keys, key)
        if idx == len(self.sorted_keys):
            idx = 0
        
        return self.ring[self.sorted_keys[idx]]
```

## Health Checking

### Active Health Checks
**Description**: Proactively check server health at regular intervals
**Methods**: HTTP GET, TCP connect, custom protocols

```python
class HealthChecker:
    def __init__(self, servers, check_interval=30, timeout=5):
        self.servers = servers
        self.check_interval = check_interval
        self.timeout = timeout
        self.health_status = {s: True for s in servers}
    
    async def start_health_checks(self):
        while True:
            await asyncio.sleep(self.check_interval)
            await self.check_all_servers()
    
    async def check_all_servers(self):
        tasks = [self.check_server(server) for server in self.servers]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def check_server(self, server):
        try:
            # HTTP health check
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{server}/health",
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    is_healthy = response.status == 200
                    
                    if is_healthy != self.health_status[server]:
                        status = "healthy" if is_healthy else "unhealthy"
                        print(f"Server {server} is now {status}")
                    
                    self.health_status[server] = is_healthy
        
        except Exception as e:
            if self.health_status[server]:
                print(f"Server {server} health check failed: {e}")
            self.health_status[server] = False
    
    def get_healthy_servers(self):
        return [s for s in self.servers if self.health_status[s]]
```

### Passive Health Checks
**Description**: Monitor server health based on request/response patterns
**Triggers**: Connection timeouts, HTTP 5xx errors, response time thresholds

```python
class PassiveHealthChecker:
    def __init__(self, servers, failure_threshold=5, recovery_threshold=2):
        self.servers = servers
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.failure_counts = {s: 0 for s in servers}
        self.success_counts = {s: 0 for s in servers}
        self.health_status = {s: True for s in servers}
    
    def record_success(self, server):
        if not self.health_status[server]:
            self.success_counts[server] += 1
            if self.success_counts[server] >= self.recovery_threshold:
                print(f"Server {server} recovered")
                self.health_status[server] = True
                self.success_counts[server] = 0
                self.failure_counts[server] = 0
        else:
            self.failure_counts[server] = 0  # Reset failure count
    
    def record_failure(self, server):
        if self.health_status[server]:
            self.failure_counts[server] += 1
            if self.failure_counts[server] >= self.failure_threshold:
                print(f"Server {server} marked as unhealthy")
                self.health_status[server] = False
                self.success_counts[server] = 0
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r ../common/requirements.txt
```

### 2. Run Basic Load Balancer

```bash
# Round-robin load balancer
python load_balancer.py --port 8080 --backends http://localhost:3001,http://localhost:3002,http://localhost:3003

# Weighted round-robin
python load_balancer.py --port 8080 --algorithm weighted --weights 3,2,1 --backends http://localhost:3001,http://localhost:3002,http://localhost:3003

# Least connections
python load_balancer.py --port 8080 --algorithm least_connections --backends http://localhost:3001,http://localhost:3002,http://localhost:3003
```

### 3. Test Load Distribution

```bash
# Send multiple requests to see distribution
for i in {1..10}; do
  curl http://localhost:8080/api/test
  echo ""
done

# Load test with Apache Bench
ab -n 1000 -c 10 http://localhost:8080/

# Monitor load balancer stats
curl http://localhost:8080/_lb/stats
```

## Examples

| File | Description | Algorithm | Features | Complexity |
|------|-------------|-----------|----------|------------|
| `basic_load_balancer.py` | Simple round-robin LB | Round Robin | Basic distribution | ⭐⭐ |
| `advanced_load_balancer.py` | Full-featured LB | Multiple | Health checks, metrics | ⭐⭐⭐⭐ |
| `weighted_load_balancer.py` | Weighted distribution | Weighted RR | Server weights | ⭐⭐⭐ |
| `session_aware_lb.py` | Session persistence | IP Hash | Session affinity | ⭐⭐⭐ |
| `health_checking_lb.py` | Health monitoring | Configurable | Active/passive checks | ⭐⭐⭐⭐ |
| `high_performance_lb.py` | Optimized performance | Least Response | Connection pooling | ⭐⭐⭐⭐⭐ |

## Configuration

### Load Balancer Configuration (`lb_config.json`)

```json
{
  "server": {
    "bind_host": "0.0.0.0",
    "bind_port": 8080,
    "max_connections": 1000,
    "connection_timeout": 30
  },
  
  "backends": [
    {
      "url": "http://backend1.example.com:3000",
      "weight": 3,
      "max_connections": 100,
      "enabled": true
    },
    {
      "url": "http://backend2.example.com:3000", 
      "weight": 2,
      "max_connections": 100,
      "enabled": true
    },
    {
      "url": "http://backend3.example.com:3000",
      "weight": 1,
      "max_connections": 50,
      "enabled": false
    }
  ],
  
  "load_balancing": {
    "algorithm": "weighted_round_robin",
    "session_persistence": {
      "enabled": true,
      "method": "ip_hash",
      "timeout": 3600
    }
  },
  
  "health_checking": {
    "active": {
      "enabled": true,
      "interval": 30,
      "timeout": 5,
      "path": "/health",
      "expected_status": 200
    },
    "passive": {
      "enabled": true,
      "failure_threshold": 5,
      "recovery_threshold": 2,
      "error_codes": [500, 502, 503, 504]
    }
  },
  
  "monitoring": {
    "metrics_enabled": true,
    "stats_endpoint": "/_lb/stats",
    "prometheus_enabled": false,
    "log_requests": true
  },
  
  "ssl": {
    "enabled": false,
    "cert_file": "cert.pem",
    "key_file": "key.pem",
    "backend_ssl_verify": true
  }
}
```

## Advanced Features

### 1. Circuit Breaker Pattern

Prevent cascading failures by temporarily stopping requests to failing servers:

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=10, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def can_execute(self):
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
```

### 2. Rate Limiting

Control request rates to prevent server overload:

```python
class RateLimiter:
    def __init__(self, max_requests_per_second):
        self.max_requests = max_requests_per_second
        self.requests = []
        self.lock = asyncio.Lock()
    
    async def is_allowed(self):
        async with self.lock:
            now = time.time()
            # Remove old requests (older than 1 second)
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < 1.0]
            
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            
            return False
```

### 3. Connection Pooling

Reuse connections to backend servers for better performance:

```python
class ConnectionPool:
    def __init__(self, server, max_connections=10):
        self.server = server
        self.max_connections = max_connections
        self.available_connections = asyncio.Queue(maxsize=max_connections)
        self.total_connections = 0
        self.lock = asyncio.Lock()
    
    async def get_connection(self):
        try:
            # Try to get existing connection
            connection = await asyncio.wait_for(
                self.available_connections.get(), timeout=1.0)
            return connection
        except asyncio.TimeoutError:
            # Create new connection if under limit
            async with self.lock:
                if self.total_connections < self.max_connections:
                    connection = await self.create_connection()
                    self.total_connections += 1
                    return connection
            
            # Wait for available connection
            return await self.available_connections.get()
    
    async def return_connection(self, connection):
        if not connection.closed:
            await self.available_connections.put(connection)
        else:
            async with self.lock:
                self.total_connections -= 1
```

### 4. SSL Termination

Handle SSL encryption/decryption at the load balancer:

```python
import ssl

class SSLTerminatingLoadBalancer:
    def __init__(self, cert_file, key_file):
        self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.ssl_context.load_cert_chain(cert_file, key_file)
    
    async def start_ssl_server(self, host, port):
        server = await asyncio.start_server(
            self.handle_client,
            host, port,
            ssl=self.ssl_context
        )
        return server
    
    async def handle_client(self, reader, writer):
        # SSL is already terminated by asyncio
        # Process plain HTTP traffic to backends
        pass
```

## Monitoring and Metrics

### Key Metrics to Track

1. **Request Metrics**
   - Requests per second
   - Response times (avg, p50, p95, p99)
   - Error rates by status code
   - Request size distribution

2. **Backend Metrics**
   - Active connections per backend
   - Backend response times
   - Backend error rates
   - Backend health status

3. **Load Balancer Metrics**
   - CPU and memory usage
   - Connection pool utilization
   - Queue lengths
   - Cache hit rates (if applicable)

### Prometheus Integration

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

class PrometheusMetrics:
    def __init__(self):
        self.requests_total = Counter(
            'lb_requests_total', 
            'Total requests processed',
            ['backend', 'status_code']
        )
        
        self.request_duration = Histogram(
            'lb_request_duration_seconds',
            'Request duration in seconds',
            ['backend']
        )
        
        self.active_connections = Gauge(
            'lb_active_connections',
            'Active connections',
            ['backend']
        )
        
        self.backend_health = Gauge(
            'lb_backend_health',
            'Backend health status (1=healthy, 0=unhealthy)',
            ['backend']
        )
    
    def record_request(self, backend, status_code, duration):
        self.requests_total.labels(backend=backend, status_code=status_code).inc()
        self.request_duration.labels(backend=backend).observe(duration)
    
    def update_connections(self, backend, count):
        self.active_connections.labels(backend=backend).set(count)
    
    def update_health(self, backend, is_healthy):
        self.backend_health.labels(backend=backend).set(1 if is_healthy else 0)
```

### Real-time Dashboard

```python
class LoadBalancerDashboard:
    def __init__(self, load_balancer):
        self.lb = load_balancer
    
    async def get_stats(self):
        stats = {
            "uptime": time.time() - self.lb.start_time,
            "total_requests": self.lb.total_requests,
            "requests_per_second": self.lb.get_rps(),
            "backends": []
        }
        
        for backend in self.lb.backends:
            backend_stats = {
                "url": backend.url,
                "healthy": backend.is_healthy(),
                "active_connections": backend.active_connections,
                "total_requests": backend.total_requests,
                "avg_response_time": backend.get_avg_response_time(),
                "error_rate": backend.get_error_rate()
            }
            stats["backends"].append(backend_stats)
        
        return stats
    
    async def serve_dashboard(self, request):
        stats = await self.get_stats()
        
        # Render HTML dashboard or return JSON
        if request.headers.get('Accept') == 'application/json':
            return web.json_response(stats)
        else:
            return web.Response(text=self.render_html_dashboard(stats), 
                              content_type='text/html')
```

## Testing and Validation

### Load Testing

```bash
# Test with different loads
wrk -t12 -c400 -d30s http://localhost:8080/

# Test failover
# Stop one backend server during load test
# Verify traffic redistributes to healthy servers

# Test recovery
# Restart failed server
# Verify traffic returns when server is healthy
```

### Chaos Engineering

```python
class ChaosTestor:
    def __init__(self, load_balancer):
        self.lb = load_balancer
    
    async def kill_random_backend(self):
        """Randomly kill a backend to test failover."""
        import random
        backend = random.choice(self.lb.backends)
        print(f"Killing backend {backend.url}")
        backend.force_unhealthy()
    
    async def add_latency(self, backend, delay_ms):
        """Add artificial latency to a backend."""
        backend.add_artificial_delay(delay_ms / 1000.0)
    
    async def simulate_high_load(self, backend, cpu_percent):
        """Simulate high CPU load on a backend."""
        backend.simulate_cpu_load(cpu_percent)
```

## Best Practices

### 1. **Algorithm Selection**
- Use **Round Robin** for homogeneous servers with short requests
- Use **Weighted Round Robin** for servers with different capacities
- Use **Least Connections** for long-lived connections
- Use **IP Hash** for session-aware applications

### 2. **Health Checking**
- Implement both active and passive health checks
- Use appropriate check intervals (30-60 seconds)
- Set proper failure thresholds (3-5 failures)
- Monitor health check endpoint performance

### 3. **Performance Optimization**
- Enable connection pooling and keep-alive
- Use async I/O for high concurrency
- Implement proper caching strategies
- Monitor and tune buffer sizes

### 4. **Security**
- Implement rate limiting per client
- Use SSL/TLS for sensitive traffic
- Log and monitor for abuse patterns
- Implement proper access controls

## Troubleshooting

### Common Issues

1. **Uneven Load Distribution**
   - Check server weights and capacities
   - Verify health check configuration
   - Monitor connection persistence settings

2. **High Response Times**
   - Check backend server performance
   - Verify connection pool settings
   - Monitor network latency
   - Check for resource bottlenecks

3. **Connection Failures**
   - Verify backend server availability
   - Check network connectivity
   - Review timeout settings
   - Monitor connection limits

### Debug Commands

```bash
# Check backend connectivity
curl -v http://backend1.example.com/health

# Monitor load balancer stats
watch -n 1 'curl -s http://localhost:8080/_lb/stats | jq'

# Test specific backend
curl -H "X-Backend-Override: backend1" http://localhost:8080/api/test

# Check connection distribution
netstat -an | grep :8080 | wc -l
```

## Next Steps

1. **Start Simple**: Implement basic round-robin load balancing
2. **Add Health Checks**: Ensure traffic only goes to healthy servers
3. **Implement Monitoring**: Track performance and health metrics
4. **Add Advanced Features**: Circuit breakers, rate limiting, SSL termination
5. **Optimize Performance**: Connection pooling, caching, async I/O

---

**Continue Learning**: Next, explore [API Gateway Proxies](../04-api-gateway-proxies/) for advanced request routing and management.
