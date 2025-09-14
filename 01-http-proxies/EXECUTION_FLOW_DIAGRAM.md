# 🔄 HTTP Proxy Execution Flow Diagrams

This document shows the detailed execution flow for each HTTP proxy implementation after the `main()` function is called.

## 📋 Table of Contents
1. [Forward Proxy Flow](#forward-proxy-flow)
2. [Reverse Proxy Flow](#reverse-proxy-flow)
3. [Caching Proxy Flow](#caching-proxy-flow)
4. [Simple Forward Proxy Flow](#simple-forward-proxy-flow)

---

## 🔄 Forward Proxy Flow

### File: `forward_proxy.py`

```
main() function called
        │
        ▼
┌─────────────────────────┐
│  Parse command line     │
│  arguments (port, etc)  │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Setup logging          │
│  (INFO level)           │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Create ForwardProxy    │
│  instance               │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Call proxy.start()     │
│  (async method)         │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Create aiohttp         │
│  ClientSession          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Create web.Application │
│  and setup routes       │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Setup route handlers:  │
│  • GET /_proxy/stats    │
│  • ALL /{path:.*}       │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Start web server       │
│  (AppRunner + TCPSite)  │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Server listening       │
│  on host:port           │
└─────────┬───────────────┘
          │
          ▼ (when request received)
┌─────────────────────────┐
│  handle_request()       │
│  method called          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Extract target URL     │
│  from request           │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Validate URL and       │
│  prepare headers        │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Read request body      │
│  if present             │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Forward request to     │
│  target server using    │
│  aiohttp session        │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Receive response       │
│  from target server     │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Add proxy headers      │
│  and return response    │
│  to client              │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Log request details    │
│  and update stats       │
└─────────────────────────┘
```

---

## 🔄 Reverse Proxy Flow

### File: `reverse_proxy.py`

```
main() function called
        │
        ▼
┌─────────────────────────┐
│  Parse command line     │
│  arguments              │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Setup logging          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Create ReverseProxy    │
│  with backend URLs      │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Call proxy.start()     │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Create aiohttp         │
│  ClientSession          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Setup route handlers:  │
│  • GET /_proxy/stats    │
│  • GET /_proxy/health   │
│  • ALL /{path:.*}       │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Start health checker   │
│  background task        │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Server listening       │
└─────────┬───────────────┘
          │
          ▼ (when request received)
┌─────────────────────────┐
│  handle_request()       │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Select healthy backend │
│  (round-robin)          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Build backend URL      │
│  with request path      │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Add forwarding headers │
│  (X-Forwarded-For, etc) │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Forward to backend     │
│  and stream response    │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Handle errors and      │
│  fallback to next       │
│  backend if needed      │
└─────────────────────────┘

Health Check Loop (parallel):
┌─────────────────────────┐
│  Every 30 seconds:      │
│  check_backend_health() │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  For each backend:      │
│  GET /health endpoint   │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Update backend status  │
│  (healthy/unhealthy)    │
└─────────────────────────┘
```

---

## 🔄 Caching Proxy Flow

### File: `caching_proxy.py`

```
main() function called
        │
        ▼
┌─────────────────────────┐
│  Parse arguments        │
│  (cache size, TTL)      │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Create CachingProxy    │
│  with cache config      │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Initialize LRU cache   │
│  with max size          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Start cache cleanup    │
│  background task        │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Setup route handlers:  │
│  • GET /_cache/stats    │
│  • DELETE /_cache/clear │
│  • ALL /{path:.*}       │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Server listening       │
└─────────┬───────────────┘
          │
          ▼ (when request received)
┌─────────────────────────┐
│  handle_request()       │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Check if request       │
│  is cacheable           │
│  (GET method only)      │
└─────────┬───────────────┘
          │
          ▼
      ┌─────────┐      ┌─────────────────────────┐
      │ YES     │      │ NO - Forward request    │
      │         │      │ directly to target      │
      └────┬────┘      └─────────────────────────┘
           │
           ▼
┌─────────────────────────┐
│  Generate cache key     │
│  from URL + headers     │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Check cache for        │
│  existing entry         │
└─────────┬───────────────┘
          │
          ▼
    ┌─────────┐        ┌─────────────────────────┐
    │ FOUND   │        │ NOT FOUND              │
    │         │        │                        │
    └────┬────┘        └─────────┬───────────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│  Check if entry         │  │  Forward request to     │
│  is still valid         │  │  target server          │
│  (not expired)          │  │                         │
└─────────┬───────────────┘  └─────────┬───────────────┘
          │                            │
          ▼                            ▼
    ┌─────────┐                ┌─────────────────────────┐
    │ VALID   │                │  Cache response if      │
    │         │                │  cacheable (200 status │
    └────┬────┘                │  + cache headers)      │
         │                     └─────────┬───────────────┘
         ▼                               │
┌─────────────────────────┐              │
│  Return cached          │              │
│  response to client     │              │
└─────────────────────────┘              │
                                         ▼
                                ┌─────────────────────────┐
                                │  Return response        │
                                │  to client              │
                                └─────────────────────────┘

Cache Cleanup Loop (parallel):
┌─────────────────────────┐
│  Every 60 seconds:      │
│  cleanup_cache()        │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Remove expired         │
│  cache entries          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Log cache statistics   │
└─────────────────────────┘
```

---

## 🔄 Simple Forward Proxy Flow

### File: `simple_forward_proxy.py`

```
main() function called
        │
        ▼
┌─────────────────────────┐
│  Parse command line     │
│  arguments (port)       │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Setup logging          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Create socket server   │
│  bind to host:port      │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Listen for connections │
│  (socket.listen)        │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Server ready           │
│  Print startup message  │
└─────────┬───────────────┘
          │
          ▼ (infinite loop)
┌─────────────────────────┐
│  Accept client          │
│  connection             │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Create thread for      │
│  handle_client()        │
└─────────┬───────────────┘
          │
          ▼ (in thread)
┌─────────────────────────┐
│  Read HTTP request      │
│  from client socket     │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Parse request line     │
│  (method, URL, version) │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Extract target host    │
│  and port from URL      │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Create socket to       │
│  target server          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Forward HTTP request   │
│  to target server       │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Read response from     │
│  target server          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Forward response       │
│  back to client         │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Close connections      │
│  Log request details    │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Thread ends,           │
│  return to accept       │
│  new connections        │
└─────────────────────────┘
```

---

## 🧠 Key Execution Patterns

### 1. **Async vs Threading Models**

| File | Model | Concurrency |
|------|-------|-------------|
| `forward_proxy.py` | **async/await** | aiohttp event loop |
| `reverse_proxy.py` | **async/await** | aiohttp event loop |
| `caching_proxy.py` | **async/await** | aiohttp event loop |
| `simple_forward_proxy.py` | **threading** | One thread per connection |

### 2. **Request Processing Flow**

```
Client Request → Proxy Server → Target Server → Response → Client
     ↑                                              ↓
     └──────────── Response flows back ──────────────┘
```

### 3. **Background Tasks**

| Proxy Type | Background Tasks |
|------------|------------------|
| Forward Proxy | None |
| Reverse Proxy | Health checking (30s interval) |
| Caching Proxy | Cache cleanup (60s interval) |
| Simple Forward | None |

### 4. **Error Handling Flow**

```
Request Received
      │
      ▼
Try to Process
      │
      ├─── Success → Return Response
      │
      └─── Error ┐
                 ├─── Connection Error → 502 Bad Gateway
                 ├─── Timeout → 504 Gateway Timeout  
                 ├─── Invalid URL → 400 Bad Request
                 └─── Other → 500 Internal Server Error
```

### 5. **Management Endpoints**

All advanced proxies provide management endpoints:

```
GET /_proxy/stats    → Statistics and metrics
GET /_proxy/health   → Health status (reverse proxy)
GET /_cache/stats    → Cache statistics (caching proxy)
DELETE /_cache/clear → Clear cache (caching proxy)
```

---

## 🚀 Starting Each Proxy

### Quick Start Commands:

```bash
# Simple Forward Proxy (no dependencies)
python3 simple_forward_proxy.py --port 8080

# Advanced Forward Proxy (requires aiohttp)
python3 forward_proxy.py --port 8081

# Reverse Proxy with backends
python3 reverse_proxy.py --port 8082 --backends http://httpbin.org http://jsonplaceholder.typicode.com

# Caching Proxy with custom cache size
python3 caching_proxy.py --port 8083 --cache-size 1000 --cache-ttl 300
```

### Testing Commands:

```bash
# Test forward proxy
curl -x http://localhost:8080 http://httpbin.org/ip

# Test reverse proxy
curl http://localhost:8082/get

# Check proxy stats
curl http://localhost:8081/_proxy/stats
```

---

## 📈 Performance Characteristics

| Proxy Type | Memory Usage | CPU Usage | Connections |
|------------|-------------|-----------|-------------|
| Simple Forward | Low | Low | Limited by threading |
| Advanced Forward | Medium | Medium | High (async) |
| Reverse Proxy | Medium | Medium | High (async) |
| Caching Proxy | High | Medium | High (async) |

---

**💡 Tip:** Start with `simple_forward_proxy.py` to understand the basic flow, then move to the advanced implementations to see how async programming and additional features are implemented!
