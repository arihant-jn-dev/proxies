# 🔄 Load Balancer Execution Flow Diagram

This document shows the detailed execution flow for the Load Balancer implementation after the `main()` function is called.

## 📋 Load Balancer Flow

### File: `load_balancer.py`

```
main() function called
        │
        ▼
┌─────────────────────────┐
│  Parse command line     │
│  arguments:             │
│  • port, host           │
│  • backends list        │
│  • weights              │
│  • algorithm            │
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
│  Create                 │
│  LoadBalancerProxy      │
│  instance               │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Add backend servers    │
│  with weights to        │
│  LoadBalancer           │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Set load balancing     │
│  algorithm              │
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
│  ClientSession for      │
│  backend requests       │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Start health monitoring│
│  background task        │
│  (every 30 seconds)     │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Create web.Application │
│  and setup routes:      │
│  • ALL /{path:.*}       │
│  • GET /_lb/stats       │
│  • GET /_lb/health      │
│  • POST /_lb/algorithm  │
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
│  Print status info      │
└─────────┬───────────────┘
          │
          ▼ (Status Loop - every 10 seconds)
┌─────────────────────────┐
│  Print current status:  │
│  • Healthy backends     │
│  • Total requests       │
└─────────────────────────┘
```

---

## 🔄 Request Handling Flow

### When Client Request Arrives:

```
Client Request Received
        │
        ▼
┌─────────────────────────┐
│  handle_request()       │
│  method called          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Extract client IP      │
│  from request           │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Call                   │
│  load_balancer.         │
│  get_backend(client_ip) │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Backend Selection      │
│  Decision Tree          │
└─────────┬───────────────┘
          │
          ▼
    ┌─────────────────────────────────────────┐
    │              BACKEND SELECTION          │
    │                                         │
    │  1. Check Sticky Sessions               │
    │     ├─── If client_ip has session       │
    │     │    └─── Use same backend          │
    │     └─── If no session, continue        │
    │                                         │
    │  2. Apply Load Balancing Algorithm      │
    │     ├─── round_robin: Cycle through     │
    │     ├─── weighted: Consider weights     │
    │     ├─── least_connections: Min active  │
    │     └─── random: Random selection       │
    │                                         │
    │  3. Filter by Health Status             │
    │     └─── Only select healthy backends   │
    │                                         │
    │  4. Create Sticky Session               │
    │     └─── Store client_ip → backend_url  │
    └─────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────┐
│  Backend Selected?      │
└─────────┬───────────────┘
          │
          ├─── NO ────────────────────────────┐
          │                                   │
          ▼                                   ▼
┌─────────────────────────┐         ┌─────────────────────────┐
│  YES - Continue         │         │  Return 503 Service     │
│  processing             │         │  Unavailable            │
└─────────┬───────────────┘         └─────────────────────────┘
          │
          ▼
┌─────────────────────────┐
│  Increment counters:    │
│  • active_connections++ │
│  • total_requests++     │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Build target URL:      │
│  backend_url + path_qs  │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Prepare headers:       │
│  • Remove 'host'        │
│  • Add X-Forwarded-For  │
│  • Add X-Load-Balancer  │
│  • Add X-Backend        │
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
│  selected backend       │
│  using aiohttp          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Wait for response      │
│  from backend           │
└─────────┬───────────────┘
          │
          ├─── SUCCESS ───────────────────────┐
          │                                   │
          ▼                                   │
┌─────────────────────────┐                 │
│  Read response content  │                 │
│  and headers            │                 │
└─────────┬───────────────┘                 │
          │                                   │
          ▼                                   │
┌─────────────────────────┐                 │
│  Add response headers:  │                 │
│  • X-Load-Balancer     │                 │
│  • X-Backend           │                 │
└─────────┬───────────────┘                 │
          │                                   │
          ▼                                   │
┌─────────────────────────┐                 │
│  Return response to     │                 │
│  client                 │                 │
└─────────┬───────────────┘                 │
          │                                   │
          ▼                                   ▼
┌─────────────────────────┐         ┌─────────────────────────┐
│  Decrement:             │         │  ERROR HANDLING:        │
│  active_connections--   │         │  • failed_requests++    │
│  Log success            │         │  • Return 502 error     │
└─────────────────────────┘         │  • Log error details    │
                                    └─────────┬───────────────┘
                                              │
                                              ▼
                                    ┌─────────────────────────┐
                                    │  Decrement:             │
                                    │  active_connections--   │
                                    └─────────────────────────┘
```

---

## 🔄 Load Balancing Algorithms Flow

### 1. Round Robin Algorithm
```
get_backend_round_robin()
        │
        ▼
┌─────────────────────────┐
│  Filter healthy         │
│  backends only          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Use current_index      │
│  % len(healthy_backends)│
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Increment current_index│
│  Return selected backend│
└─────────────────────────┘
```

### 2. Weighted Round Robin Algorithm
```
get_backend_weighted()
        │
        ▼
┌─────────────────────────┐
│  Create weighted list:  │
│  [backend] * weight     │
│  for each healthy       │
│  backend                │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Use current_index      │
│  % len(weighted_list)   │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Increment current_index│
│  Return selected backend│
└─────────────────────────┘
```

### 3. Least Connections Algorithm
```
get_backend_least_connections()
        │
        ▼
┌─────────────────────────┐
│  Filter healthy         │
│  backends only          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Find backend with      │
│  minimum                │
│  active_connections     │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Return backend with    │
│  least connections      │
└─────────────────────────┘
```

### 4. Random Algorithm
```
get_backend_random()
        │
        ▼
┌─────────────────────────┐
│  Filter healthy         │
│  backends only          │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Use random.choice()    │
│  to select backend      │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Return randomly        │
│  selected backend       │
└─────────────────────────┘
```

---

## 🔄 Health Monitoring Flow

### Background Health Check Task:

```
start_health_monitoring()
        │
        ▼ (Infinite Loop)
┌─────────────────────────┐
│  Wait 30 seconds        │
│  (health_check_interval)│
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Call health_check()    │
│  for all backends       │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  For each backend:      │
│  Send GET request to    │
│  backend_url/health     │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Measure response time  │
│  Check status code      │
└─────────┬───────────────┘
          │
          ├─── STATUS 200 ────────────────────┐
          │                                   │
          ▼                                   │
┌─────────────────────────┐                 │
│  Mark backend healthy   │                 │
│  Update response_time   │                 │
│  Log success (DEBUG)    │                 │
└─────────┬───────────────┘                 │
          │                                   │
          ▼                                   ▼
┌─────────────────────────┐         ┌─────────────────────────┐
│  Update                 │         │  Mark backend unhealthy │
│  last_health_check      │         │  Set response_time=5.0  │
│  timestamp              │         │  Log error/warning      │
└─────────┬───────────────┘         └─────────┬───────────────┘
          │                                   │
          └─────────────────┬─────────────────┘
                            │
                            ▼
                  ┌─────────────────────────┐
                  │  Continue to next       │
                  │  backend in list        │
                  └─────────────────────────┘
```

---

## 🔄 Management Endpoints Flow

### Statistics Endpoint (`/_lb/stats`):
```
GET /_lb/stats
        │
        ▼
┌─────────────────────────┐
│  get_stats() called     │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Calculate totals:      │
│  • total_requests       │
│  • total_failed         │
│  • success_rate         │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  For each backend:      │
│  • health status        │
│  • request counts       │
│  • response times       │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Return JSON response   │
│  with all statistics    │
└─────────────────────────┘
```

### Health Endpoint (`/_lb/health`):
```
GET /_lb/health
        │
        ▼
┌─────────────────────────┐
│  get_health() called    │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Count healthy backends │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Return JSON with:      │
│  • overall status       │
│  • healthy count        │
│  • total count          │
│  • current algorithm    │
└─────────────────────────┘
```

### Algorithm Change (`/_lb/algorithm/{algorithm}`):
```
POST /_lb/algorithm/least_connections
        │
        ▼
┌─────────────────────────┐
│  set_algorithm() called │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Validate algorithm     │
│  against allowed list   │
└─────────┬───────────────┘
          │
          ├─── VALID ─────────────────────────┐
          │                                   │
          ▼                                   │
┌─────────────────────────┐                 │
│  Update                 │                 │
│  load_balancer.algorithm│                 │
└─────────┬───────────────┘                 │
          │                                   │
          ▼                                   │
┌─────────────────────────┐                 │
│  Log algorithm change   │                 │
└─────────┬───────────────┘                 │
          │                                   │
          ▼                                   ▼
┌─────────────────────────┐         ┌─────────────────────────┐
│  Return success JSON    │         │  Return 400 error      │
│  with new algorithm     │         │  with valid options     │
└─────────────────────────┘         └─────────────────────────┘
```

---

## 🧠 Key Features Flow

### Session Affinity (Sticky Sessions):
```
Client Request with IP: 192.168.1.100
        │
        ▼
┌─────────────────────────┐
│  Check                  │
│  sticky_sessions dict   │
└─────────┬───────────────┘
          │
          ├─── FOUND ────────────────────────┐
          │                                  │
          ▼                                  │
┌─────────────────────────┐                │
│  NO SESSION - Select    │                │
│  backend using algorithm│                │
└─────────┬───────────────┘                │
          │                                  │
          ▼                                  │
┌─────────────────────────┐                │
│  Store in sticky_       │                │
│  sessions:              │                │
│  IP → backend_url       │                │
└─────────┬───────────────┘                │
          │                                  │
          └─────────────────┬────────────────┘
                            │
                            ▼
                  ┌─────────────────────────┐
                  │  Use existing backend   │
                  │  if still healthy       │
                  └─────────────────────────┘
```

---

## 🎯 Complete Load Balancer Architecture

```
                    ┌─────────────────┐
                    │     CLIENT      │
                    └─────────┬───────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ LOAD BALANCER   │
                    │   (Port 8080)   │
                    └─────────┬───────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────┐
    │              BACKEND SELECTION                  │
    │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
    │  │ ALGORITHM   │ │ HEALTH      │ │ SESSION     ││
    │  │ • Round     │ │ • Monitoring│ │ • Affinity  ││
    │  │ • Weighted  │ │ • /health   │ │ • Sticky    ││
    │  │ • Least     │ │ • 30s check │ │ • Client IP ││
    │  │ • Random    │ │             │ │             ││
    │  └─────────────┘ └─────────────┘ └─────────────┘│
    └─────────────────────────────────────────────────┘
                              │
                              ▼
            ┌─────────────────────────────────────┐
            │         BACKEND SERVERS             │
            ├─────────────┬───────────────────────┤
            │ Backend 1   │ Backend 2             │
            │ Weight: 2   │ Weight: 1             │
            │ Healthy: ✅  │ Healthy: ✅            │
            │ Connections:│ Connections: 2        │
            │ 5           │                       │
            └─────────────┴───────────────────────┘
```

---

## 🚀 Testing the Load Balancer

### Quick Start:
```bash
# Start with default backends
python3 03-load-balancer-proxies/load_balancer.py --port 8080

# Start with custom backends and weights
python3 load_balancer.py --port 8080 \
  --backends http://httpbin.org http://jsonplaceholder.typicode.com \
  --weights 2 1 \
  --algorithm least_connections
```

### Test Commands:
```bash
# Make requests
curl http://localhost:8080/get
curl http://localhost:8080/posts/1

# Check statistics
curl http://localhost:8080/_lb/stats

# Check health
curl http://localhost:8080/_lb/health

# Change algorithm
curl -X POST http://localhost:8080/_lb/algorithm/random
```

**💡 The load balancer continuously monitors backend health and routes requests intelligently based on the selected algorithm!**
