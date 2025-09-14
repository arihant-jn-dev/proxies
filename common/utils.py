#!/usr/bin/env python3
"""
Common utilities for proxy implementations and testing.
This module provides shared functionality across all proxy examples.
"""

import asyncio
import json
import logging
import socket
import ssl
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union
import urllib.parse


class ProxyLogger:
    """Enhanced logging for proxy operations with structured output."""
    
    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Create formatter for structured logging
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
    def request(self, method: str, url: str, client_ip: str = "unknown"):
        """Log incoming request."""
        self.logger.info(f"REQUEST | {method} | {url} | Client: {client_ip}")
    
    def response(self, status_code: int, url: str, duration_ms: float):
        """Log outgoing response."""
        self.logger.info(f"RESPONSE | {status_code} | {url} | Duration: {duration_ms:.2f}ms")
    
    def error(self, message: str, error: Exception = None):
        """Log error with optional exception details."""
        if error:
            self.logger.error(f"ERROR | {message} | Exception: {str(error)}")
        else:
            self.logger.error(f"ERROR | {message}")
    
    def debug(self, message: str):
        """Log debug information."""
        self.logger.debug(f"DEBUG | {message}")


class NetworkUtils:
    """Network utility functions for proxy implementations."""
    
    @staticmethod
    def is_port_open(host: str, port: int, timeout: float = 5.0) -> bool:
        """Check if a port is open on a given host."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.timeout, socket.error):
            return False
    
    @staticmethod
    def get_local_ip() -> str:
        """Get the local IP address of this machine."""
        try:
            # Create a socket and connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
    
    @staticmethod
    def parse_proxy_url(proxy_url: str) -> Dict[str, Union[str, int]]:
        """Parse a proxy URL into components."""
        parsed = urllib.parse.urlparse(proxy_url)
        return {
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "port": parsed.port,
            "username": parsed.username,
            "password": parsed.password
        }
    
    @staticmethod
    def format_bytes(size_bytes: int) -> str:
        """Format bytes into human-readable format."""
        if size_bytes == 0:
            return "0B"
        
        units = ['B', 'KB', 'MB', GB', 'TB']
        i = 0
        while size_bytes >= 1024.0 and i < len(units) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f}{units[i]}"


class PerformanceMonitor:
    """Monitor and track proxy performance metrics."""
    
    def __init__(self):
        self.requests_total = 0
        self.requests_success = 0
        self.requests_error = 0
        self.response_times = []
        self.bytes_transferred = 0
        self.start_time = time.time()
    
    def record_request(self, success: bool, response_time_ms: float, bytes_count: int = 0):
        """Record a completed request."""
        self.requests_total += 1
        if success:
            self.requests_success += 1
        else:
            self.requests_error += 1
        
        self.response_times.append(response_time_ms)
        self.bytes_transferred += bytes_count
    
    def get_stats(self) -> Dict:
        """Get current performance statistics."""
        uptime = time.time() - self.start_time
        
        if self.response_times:
            avg_response_time = sum(self.response_times) / len(self.response_times)
            min_response_time = min(self.response_times)
            max_response_time = max(self.response_times)
        else:
            avg_response_time = min_response_time = max_response_time = 0
        
        return {
            "uptime_seconds": uptime,
            "requests_total": self.requests_total,
            "requests_success": self.requests_success,
            "requests_error": self.requests_error,
            "success_rate": (self.requests_success / max(self.requests_total, 1)) * 100,
            "avg_response_time_ms": avg_response_time,
            "min_response_time_ms": min_response_time,
            "max_response_time_ms": max_response_time,
            "bytes_transferred": self.bytes_transferred,
            "bytes_transferred_formatted": NetworkUtils.format_bytes(self.bytes_transferred),
            "requests_per_second": self.requests_total / max(uptime, 1)
        }
    
    def reset(self):
        """Reset all metrics."""
        self.__init__()


class ConfigManager:
    """Configuration management for proxy settings."""
    
    DEFAULT_CONFIG = {
        "bind_host": "0.0.0.0",
        "bind_port": 8080,
        "log_level": "INFO",
        "max_connections": 1000,
        "timeout_seconds": 30,
        "buffer_size": 8192,
        "enable_ssl": False,
        "ssl_cert_file": None,
        "ssl_key_file": None
    }
    
    def __init__(self, config_file: Optional[str] = None):
        self.config = self.DEFAULT_CONFIG.copy()
        if config_file:
            self.load_from_file(config_file)
    
    def load_from_file(self, config_file: str):
        """Load configuration from JSON file."""
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                self.config.update(file_config)
        except Exception as e:
            raise ValueError(f"Failed to load config from {config_file}: {e}")
    
    def get(self, key: str, default=None):
        """Get configuration value."""
        return self.config.get(key, default)
    
    def set(self, key: str, value):
        """Set configuration value."""
        self.config[key] = value
    
    def save_to_file(self, config_file: str):
        """Save current configuration to JSON file."""
        with open(config_file, 'w') as f:
            json.dump(self.config, f, indent=2)


class SSLHelper:
    """SSL/TLS helper functions for secure proxy implementations."""
    
    @staticmethod
    def create_ssl_context(cert_file: str = None, key_file: str = None, 
                          is_server: bool = True) -> ssl.SSLContext:
        """Create SSL context for server or client use."""
        if is_server:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            if cert_file and key_file:
                context.load_cert_chain(cert_file, key_file)
            else:
                # Create self-signed certificate for testing
                context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        else:
            context = ssl.create_default_context()
            # For testing, don't verify certificates
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        
        return context
    
    @staticmethod
    def generate_self_signed_cert(cert_file: str, key_file: str, 
                                common_name: str = "localhost"):
        """Generate a self-signed certificate for testing."""
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import ipaddress
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name)
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(common_name),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Write certificate and key to files
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        with open(key_file, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))


class ProxyTestClient:
    """Test client for proxy functionality."""
    
    def __init__(self, proxy_host: str = "localhost", proxy_port: int = 8080):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.session_stats = PerformanceMonitor()
    
    async def test_http_proxy(self, target_url: str) -> Dict:
        """Test HTTP proxy functionality."""
        import aiohttp
        
        start_time = time.time()
        try:
            proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
            async with aiohttp.ClientSession() as session:
                async with session.get(target_url, proxy=proxy_url) as response:
                    content = await response.read()
                    duration = (time.time() - start_time) * 1000
                    
                    result = {
                        "success": True,
                        "status_code": response.status,
                        "duration_ms": duration,
                        "content_length": len(content),
                        "headers": dict(response.headers)
                    }
                    
                    self.session_stats.record_request(True, duration, len(content))
                    return result
        
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            result = {
                "success": False,
                "error": str(e),
                "duration_ms": duration
            }
            self.session_stats.record_request(False, duration)
            return result
    
    def get_test_stats(self) -> Dict:
        """Get statistics from test session."""
        return self.session_stats.get_stats()


# Example usage and testing
if __name__ == "__main__":
    # Test the utilities
    logger = ProxyLogger("test")
    logger.request("GET", "http://example.com", "192.168.1.100")
    logger.response(200, "http://example.com", 150.5)
    
    # Test network utils
    print(f"Local IP: {NetworkUtils.get_local_ip()}")
    print(f"Google DNS reachable: {NetworkUtils.is_port_open('8.8.8.8', 53)}")
    
    # Test performance monitor
    monitor = PerformanceMonitor()
    monitor.record_request(True, 100.0, 1024)
    monitor.record_request(False, 5000.0, 0)
    print(f"Stats: {json.dumps(monitor.get_stats(), indent=2)}")
