# SOCKS Proxies - SOCKS4 & SOCKS5

SOCKS (Socket Secure) is a protocol that routes network packets between a client and server through a proxy server. Unlike HTTP proxies, SOCKS proxies work at a lower level and can handle any type of traffic (TCP/UDP).

## 📋 Table of Contents

- [What are SOCKS Proxies?](#what-are-socks-proxies)
- [SOCKS4 vs SOCKS5](#socks4-vs-socks5)
- [Protocol Deep Dive](#protocol-deep-dive)
- [Quick Start](#quick-start)
- [Examples](#examples)
- [Configuration](#configuration)
- [Use Cases](#use-cases)
- [Security Considerations](#security-considerations)

## What are SOCKS Proxies?

SOCKS proxies operate at the **session layer** (Layer 5) of the OSI model, making them protocol-agnostic. They can tunnel:

- **HTTP/HTTPS traffic** (web browsing)
- **FTP transfers** (file uploads/downloads)
- **SMTP/POP3/IMAP** (email protocols)
- **SSH connections** (secure shell)
- **Any TCP/UDP traffic** (games, streaming, etc.)

### Key Characteristics

- **Protocol Agnostic**: Works with any TCP/UDP application
- **Lower Level**: Operates below application protocols
- **Bidirectional**: Supports both incoming and outgoing connections
- **Authentication**: SOCKS5 supports multiple authentication methods
- **UDP Support**: SOCKS5 can proxy UDP traffic

### Traffic Flow Diagram

```
SOCKS Proxy Flow:
Client → SOCKS Proxy → Target Server
   ↑                        ↓
   └──── Data Tunnel ───────┘

Detailed Handshake:
1. Client → Proxy: Connection Request
2. Proxy → Client: Method Selection
3. Client → Proxy: Authentication (if required)
4. Client → Proxy: Connection Request (target)
5. Proxy → Target: Direct Connection
6. Proxy → Client: Connection Status
7. Data flows transparently through tunnel
```

## SOCKS4 vs SOCKS5

| Feature | SOCKS4 | SOCKS5 |
|---------|--------|--------|
| **Authentication** | None | Multiple methods (None, Username/Password, GSSAPI) |
| **IPv6 Support** | No | Yes |
| **UDP Support** | No | Yes |
| **Domain Resolution** | Client-side only | Both client and proxy-side |
| **Complexity** | Simple | More complex |
| **Security** | Basic | Enhanced |
| **Use Cases** | Legacy applications | Modern applications |

### SOCKS4 Protocol

- **Simple** and lightweight
- **No authentication** mechanism
- **IPv4 only** support
- **TCP only** (no UDP)
- **Fixed packet format**

### SOCKS5 Protocol (RFC 1928)

- **Multiple authentication** methods
- **IPv4 and IPv6** support
- **TCP and UDP** support
- **Domain name resolution** by proxy
- **More flexible** packet format

## Protocol Deep Dive

### SOCKS5 Handshake Process

#### 1. Initial Connection
```
Client → Proxy: Version + Number of Methods + Methods
┌──────┬─────────┬──────────┬─────────┐
│ VER  │ NMETHODS│ METHODS  │   ...   │
│ 0x05 │   0x01  │   0x00   │         │
└──────┴─────────┴──────────┴─────────┘
```

#### 2. Method Selection
```
Proxy → Client: Version + Selected Method
┌──────┬────────┐
│ VER  │ METHOD │
│ 0x05 │  0x00  │
└──────┴────────┘
```

#### 3. Connection Request
```
Client → Proxy: Request Details
┌──────┬─────┬──────┬──────┬──────────┬────────┐
│ VER  │ CMD │ RSV  │ ATYP │   ADDR   │  PORT  │
│ 0x05 │0x01 │ 0x00 │ 0x01 │ 4 bytes  │2 bytes │
└──────┴─────┴──────┴──────┴──────────┴────────┘
```

#### 4. Connection Response
```
Proxy → Client: Connection Status
┌──────┬─────┬──────┬──────┬──────────┬────────┐
│ VER  │ REP │ RSV  │ ATYP │   ADDR   │  PORT  │
│ 0x05 │0x00 │ 0x00 │ 0x01 │ 4 bytes  │2 bytes │
└──────┴─────┴──────┴──────┴──────────┴────────┘
```

### Authentication Methods

| Method | Value | Description |
|--------|-------|-------------|
| No Authentication | 0x00 | No authentication required |
| GSSAPI | 0x01 | Generic Security Services API |
| Username/Password | 0x02 | RFC 1929 authentication |
| IANA Assigned | 0x03-0x7F | Reserved for IANA |
| Private Methods | 0x80-0xFE | Reserved for private use |
| No Acceptable | 0xFF | No acceptable methods |

## Quick Start

### 1. Install Dependencies

```bash
pip install -r ../common/requirements.txt
```

### 2. Run SOCKS5 Proxy

```bash
# Basic SOCKS5 proxy
python socks5_proxy.py --port 1080

# With authentication
python socks5_proxy.py --port 1080 --auth username:password

# With UDP support
python socks5_proxy.py --port 1080 --enable-udp
```

### 3. Run SOCKS4 Proxy

```bash
python socks4_proxy.py --port 1080
```

### 4. Test the Proxy

```bash
# Test with curl (SOCKS5)
curl --socks5 localhost:1080 http://httpbin.org/ip

# Test with curl (SOCKS4)
curl --socks4 localhost:1080 http://httpbin.org/ip

# Test with Python requests
python test_socks.py --proxy socks5://localhost:1080
```

## Examples

| File | Description | Features | Complexity |
|------|-------------|----------|------------|
| `socks4_proxy.py` | Basic SOCKS4 implementation | TCP tunneling, simple protocol | ⭐⭐ |
| `socks5_proxy.py` | Full SOCKS5 implementation | Authentication, IPv6, UDP | ⭐⭐⭐⭐ |
| `authenticated_socks5.py` | SOCKS5 with authentication | User/pass auth, multiple methods | ⭐⭐⭐ |
| `udp_socks5.py` | SOCKS5 with UDP support | UDP relay, associate command | ⭐⭐⭐⭐ |
| `high_performance_socks.py` | Optimized SOCKS proxy | Connection pooling, async I/O | ⭐⭐⭐⭐⭐ |
| `socks_chain.py` | Proxy chaining | Multiple proxy hops | ⭐⭐⭐⭐ |

## Configuration

### Basic Configuration (`socks_config.json`)

```json
{
  "bind_host": "0.0.0.0",
  "bind_port": 1080,
  "protocol_version": 5,
  
  "authentication": {
    "enabled": true,
    "methods": ["none", "username_password"],
    "users": {
      "admin": "secure_password",
      "user": "user_password"
    }
  },
  
  "features": {
    "ipv6_enabled": true,
    "udp_enabled": true,
    "domain_resolution": "proxy"
  },
  
  "logging": {
    "level": "INFO",
    "log_connections": true,
    "log_data_transfer": false
  },
  
  "performance": {
    "max_connections": 1000,
    "connection_timeout": 30,
    "buffer_size": 8192,
    "keepalive_enabled": true
  },
  
  "security": {
    "allowed_commands": ["connect", "bind", "udp_associate"],
    "blocked_addresses": [],
    "rate_limiting": {
      "enabled": false,
      "max_connections_per_ip": 10
    }
  }
}
```

### Environment Variables

```bash
# Copy and modify environment file
cp .env.example .env

# Key variables:
SOCKS_PORT=1080
SOCKS_AUTH_ENABLED=true
SOCKS_AUTH_USERS=admin:password,user:pass
SOCKS_UDP_ENABLED=true
LOG_LEVEL=INFO
```

## Use Cases

### 1. **Web Browsing Privacy**
- Hide client IP from web servers
- Bypass geographical restrictions
- Circumvent network censorship

### 2. **Application Tunneling**
- Tunnel any TCP/UDP application
- Secure connections over untrusted networks
- Protocol-agnostic proxy solution

### 3. **Network Testing**
- Simulate different network conditions
- Test application behavior through proxies
- Network debugging and analysis

### 4. **Enterprise Network Access**
- Provide secure remote access
- Control and monitor network traffic
- Implement network policies

### 5. **Gaming and Streaming**
- Reduce latency to game servers
- Access geo-restricted content
- Load balance across multiple connections

## Security Considerations

### Authentication Security

```python
# Strong password requirements
def validate_password(password):
    return (len(password) >= 8 and
            any(c.isupper() for c in password) and
            any(c.islower() for c in password) and
            any(c.isdigit() for c in password))

# Rate limiting for authentication attempts
class AuthRateLimit:
    def __init__(self, max_attempts=5, window=300):
        self.max_attempts = max_attempts
        self.window = window
        self.attempts = {}
    
    def is_allowed(self, client_ip):
        now = time.time()
        if client_ip not in self.attempts:
            self.attempts[client_ip] = []
        
        # Clean old attempts
        self.attempts[client_ip] = [
            attempt for attempt in self.attempts[client_ip]
            if now - attempt < self.window
        ]
        
        return len(self.attempts[client_ip]) < self.max_attempts
```

### Access Control

```python
# IP-based access control
class AccessControl:
    def __init__(self, allowed_ips=None, blocked_ips=None):
        self.allowed_ips = set(allowed_ips or [])
        self.blocked_ips = set(blocked_ips or [])
    
    def is_allowed(self, client_ip):
        if self.blocked_ips and client_ip in self.blocked_ips:
            return False
        
        if self.allowed_ips and client_ip not in self.allowed_ips:
            return False
        
        return True
```

### Destination Filtering

```python
# Block access to specific destinations
class DestinationFilter:
    def __init__(self, blocked_domains=None, blocked_ips=None):
        self.blocked_domains = set(blocked_domains or [])
        self.blocked_ips = set(blocked_ips or [])
    
    def is_allowed(self, address, port):
        # Check IP blocks
        if address in self.blocked_ips:
            return False
        
        # Check domain blocks
        try:
            import socket
            hostname = socket.gethostbyaddr(address)[0]
            for blocked_domain in self.blocked_domains:
                if blocked_domain in hostname:
                    return False
        except:
            pass
        
        return True
```

## Performance Optimization

### Connection Pooling

- **Reuse connections** to reduce overhead
- **Connection limits** to prevent resource exhaustion
- **Idle timeout** to clean up unused connections

### Async I/O

- **Non-blocking sockets** for high concurrency
- **Event-driven architecture** for scalability
- **Efficient buffer management** for data transfer

### Monitoring and Metrics

```python
class SOCKSMetrics:
    def __init__(self):
        self.connections_total = 0
        self.connections_active = 0
        self.bytes_transferred = 0
        self.auth_failures = 0
        self.connection_errors = 0
    
    def record_connection(self):
        self.connections_total += 1
        self.connections_active += 1
    
    def record_disconnection(self):
        self.connections_active -= 1
    
    def record_data_transfer(self, bytes_count):
        self.bytes_transferred += bytes_count
```

## Testing and Debugging

### Protocol Testing

```bash
# Test SOCKS5 handshake manually
echo -e "\\x05\\x01\\x00" | nc localhost 1080 | hexdump -C

# Test authentication
echo -e "\\x05\\x01\\x02" | nc localhost 1080 | hexdump -C
```

### Application Testing

```python
# Test with different applications
import requests
import socket

# HTTP requests through SOCKS
session = requests.Session()
session.proxies = {'http': 'socks5://localhost:1080',
                  'https': 'socks5://localhost:1080'}

# Raw socket through SOCKS
import socks
socks.set_default_proxy(socks.SOCKS5, "localhost", 1080)
socket.socket = socks.socksocket
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Check if proxy is running on correct port
   - Verify firewall settings
   - Check bind address (0.0.0.0 vs localhost)

2. **Authentication Failures**
   - Verify username/password combinations
   - Check authentication method compatibility
   - Review rate limiting settings

3. **Slow Performance**
   - Increase buffer sizes
   - Enable connection pooling
   - Check network latency
   - Monitor CPU and memory usage

### Debug Logging

```python
# Enable detailed protocol logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Log packet contents
def log_packet(data, direction):
    logger.debug(f"{direction}: {data.hex()}")
```

## Advanced Features

### Proxy Chaining

Chain multiple SOCKS proxies for enhanced anonymity:

```python
# Client → SOCKS1 → SOCKS2 → Target
proxies = [
    "socks5://proxy1.example.com:1080",
    "socks5://proxy2.example.com:1080"
]
```

### UDP Relay

SOCKS5 UDP associate command for UDP traffic:

```python
class UDPRelay:
    def __init__(self, bind_addr):
        self.bind_addr = bind_addr
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
    async def handle_udp_packet(self, data, addr):
        # Parse SOCKS5 UDP request
        # Forward to target
        # Relay response back to client
        pass
```

## Next Steps

1. **Start with SOCKS4**: Implement basic TCP tunneling
2. **Upgrade to SOCKS5**: Add authentication and UDP support  
3. **Add Security**: Implement access controls and monitoring
4. **Optimize Performance**: Add connection pooling and async I/O
5. **Explore Advanced Features**: Proxy chaining, UDP relay, custom protocols

---

**Continue Learning**: Next, explore [Load Balancer Proxies](../03-load-balancer-proxies/) for traffic distribution.
