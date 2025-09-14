# API Gateway Proxies

API gateways act as a single entry point for microservices, providing:

- **Request Routing**: Route requests based on URL patterns, headers, or other criteria
- **Authentication & Authorization**: Centralized security controls
- **Rate Limiting**: Protect backend services from abuse
- **Request/Response Transformation**: Modify data format between clients and services
- **Monitoring & Analytics**: Track API usage and performance

## Key Features

### 1. Request Routing
```
/api/users/*     → User Service
/api/orders/*    → Order Service  
/api/payments/*  → Payment Service
```

### 2. Authentication
- API key validation
- JWT token verification
- OAuth2 integration
- RBAC (Role-Based Access Control)

### 3. Rate Limiting
- Per-client rate limits
- Per-API endpoint limits
- Burst handling
- Quota management

### 4. Data Transformation
- Request/response format conversion
- Protocol translation (REST ↔ GraphQL)
- Header manipulation
- Payload validation

## Examples

| File | Description | Features |
|------|-------------|----------|
| `basic_api_gateway.py` | Simple routing gateway | Path-based routing |
| `auth_api_gateway.py` | Gateway with authentication | JWT validation, API keys |
| `rate_limiting_gateway.py` | Rate limiting features | Token bucket, sliding window |
| `transformation_gateway.py` | Request/response transformation | JSON transformation, validation |

## Quick Start

```bash
# Start API gateway
python api_gateway.py --port 8080 --config gateway_config.json

# Test routing
curl http://localhost:8080/api/users/123
curl http://localhost:8080/api/orders/456

# Test with authentication
curl -H "Authorization: Bearer token" http://localhost:8080/api/protected/resource
```

---

**Learn More**: Explore the examples in this directory for complete implementations.
