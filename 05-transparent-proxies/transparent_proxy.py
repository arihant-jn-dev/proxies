#!/usr/bin/env python3
"""
Transparent Proxy Implementation

A transparent proxy that intercepts network traffic without requiring
client configuration. This type of proxy is often used for:
- Network monitoring and analytics
- Content filtering at the network level
- Traffic shaping and bandwidth control
- Security monitoring

Note: This is a demonstration implementation. Real transparent proxies
typically require iptables rules and root privileges.
"""

import asyncio
import socket
import logging
import time
import json
from typing import Dict, Set, Optional
from collections import defaultdict
import threading


class ConnectionTracker:
    """Track active connections and statistics."""
    
    def __init__(self):
        self.connections: Dict[str, Dict] = {}
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "bytes_transferred": 0,
            "blocked_connections": 0
        }
        self.blocked_hosts: Set[str] = set()
        self.allowed_hosts: Set[str] = set()
        
    def start_connection(self, conn_id: str, client_addr: str, target_addr: str) -> str:
        """Start tracking a new connection."""
        self.connections[conn_id] = {
            "client": client_addr,
            "target": target_addr,
            "start_time": time.time(),
            "bytes_sent": 0,
            "bytes_received": 0,
            "status": "active"
        }
        self.stats["total_connections"] += 1
        self.stats["active_connections"] += 1
        return conn_id
    
    def end_connection(self, conn_id: str):
        """End tracking a connection."""
        if conn_id in self.connections:
            conn = self.connections[conn_id]
            conn["end_time"] = time.time()
            conn["duration"] = conn["end_time"] - conn["start_time"]
            conn["status"] = "closed"
            self.stats["active_connections"] -= 1
    
    def log_data(self, conn_id: str, bytes_sent: int, bytes_received: int):
        """Log data transfer for a connection."""
        if conn_id in self.connections:
            self.connections[conn_id]["bytes_sent"] += bytes_sent
            self.connections[conn_id]["bytes_received"] += bytes_received
            self.stats["bytes_transferred"] += bytes_sent + bytes_received
    
    def is_allowed(self, host: str) -> bool:
        """Check if connection to host is allowed."""
        if host in self.blocked_hosts:
            return False
        if self.allowed_hosts and host not in self.allowed_hosts:
            return False
        return True
    
    def block_host(self, host: str):
        """Block connections to a host."""
        self.blocked_hosts.add(host)
    
    def allow_host(self, host: str):
        """Explicitly allow connections to a host."""
        self.allowed_hosts.add(host)
    
    def get_stats(self) -> Dict:
        """Get connection statistics."""
        return {
            "stats": self.stats.copy(),
            "blocked_hosts": list(self.blocked_hosts),
            "allowed_hosts": list(self.allowed_hosts),
            "active_connections": len([
                c for c in self.connections.values() 
                if c["status"] == "active"
            ])
        }


class TransparentProxy:
    """Transparent proxy that intercepts and forwards traffic."""
    
    def __init__(self, listen_port: int = 8888, target_host: str = None, target_port: int = None):
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self.logger = logging.getLogger("transparent_proxy")
        self.tracker = ConnectionTracker()
        self.running = False
        
        # Traffic analysis
        self.traffic_log = []
        self.max_log_entries = 1000
    
    async def start(self):
        """Start the transparent proxy server."""
        self.running = True
        
        # Create server socket
        server = await asyncio.start_server(
            self.handle_client,
            'localhost',
            self.listen_port
        )
        
        addr = server.sockets[0].getsockname()
        self.logger.info(f"Transparent proxy listening on {addr[0]}:{addr[1]}")
        
        if self.target_host and self.target_port:
            self.logger.info(f"Default target: {self.target_host}:{self.target_port}")
        else:
            self.logger.info("No default target - will extract from requests")
        
        return server
    
    async def handle_client(self, client_reader, client_writer):
        """Handle client connection."""
        client_addr = client_writer.get_extra_info('peername')
        conn_id = f"{client_addr[0]}:{client_addr[1]}_{int(time.time())}"
        
        try:
            # Read first chunk to determine target
            first_data = await client_reader.read(4096)
            if not first_data:
                return
            
            # Try to extract target from HTTP request
            target_host, target_port = self.extract_target(first_data)
            
            # Use default target if extraction failed
            if not target_host and self.target_host:
                target_host = self.target_host
                target_port = self.target_port
            
            if not target_host:
                self.logger.error("Could not determine target host")
                client_writer.close()
                return
            
            # Check if connection is allowed
            if not self.tracker.is_allowed(target_host):
                self.logger.warning(f"Blocked connection to {target_host}")
                self.tracker.stats["blocked_connections"] += 1
                client_writer.close()
                return
            
            # Start tracking
            self.tracker.start_connection(conn_id, f"{client_addr[0]}:{client_addr[1]}", 
                                        f"{target_host}:{target_port}")
            
            self.logger.info(f"Connecting {client_addr} to {target_host}:{target_port}")
            
            # Connect to target server
            try:
                target_reader, target_writer = await asyncio.open_connection(
                    target_host, target_port
                )
            except Exception as e:
                self.logger.error(f"Failed to connect to {target_host}:{target_port}: {e}")
                self.tracker.end_connection(conn_id)
                client_writer.close()
                return
            
            # Send the first data we already read
            target_writer.write(first_data)
            await target_writer.drain()
            
            # Log traffic
            self.log_traffic(conn_id, client_addr, target_host, target_port, first_data, "request")
            
            # Start bidirectional relay
            await asyncio.gather(
                self.relay_data(client_reader, target_writer, conn_id, "client_to_target"),
                self.relay_data(target_reader, client_writer, conn_id, "target_to_client"),
                return_exceptions=True
            )
            
        except Exception as e:
            self.logger.error(f"Error handling client {client_addr}: {e}")
        finally:
            # Clean up
            self.tracker.end_connection(conn_id)
            client_writer.close()
            if 'target_writer' in locals():
                target_writer.close()
    
    def extract_target(self, data: bytes) -> tuple:
        """Extract target host and port from request data."""
        try:
            # Try to parse as HTTP request
            request_str = data.decode('utf-8', errors='ignore')
            lines = request_str.split('\n')
            
            # Look for Host header
            for line in lines:
                if line.lower().startswith('host:'):
                    host_line = line.split(':', 1)[1].strip()
                    if ':' in host_line:
                        host, port = host_line.split(':', 1)
                        return host.strip(), int(port)
                    else:
                        return host_line.strip(), 80
            
            # Look for CONNECT method (HTTPS proxy)
            if lines[0].startswith('CONNECT '):
                target = lines[0].split(' ')[1]
                if ':' in target:
                    host, port = target.split(':', 1)
                    return host.strip(), int(port)
        
        except Exception as e:
            self.logger.debug(f"Could not extract target: {e}")
        
        return None, None
    
    async def relay_data(self, reader, writer, conn_id: str, direction: str):
        """Relay data between client and target."""
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                
                # Log data transfer
                if direction == "client_to_target":
                    self.tracker.log_data(conn_id, len(data), 0)
                else:
                    self.tracker.log_data(conn_id, 0, len(data))
                
                # Log traffic sample
                if len(self.traffic_log) < self.max_log_entries:
                    self.log_traffic_data(conn_id, direction, data[:200])  # First 200 bytes
                
                writer.write(data)
                await writer.drain()
                
        except Exception as e:
            self.logger.debug(f"Relay error ({direction}): {e}")
        finally:
            writer.close()
    
    def log_traffic(self, conn_id: str, client_addr: tuple, target_host: str, 
                   target_port: int, data: bytes, direction: str):
        """Log traffic information."""
        entry = {
            "timestamp": time.time(),
            "connection_id": conn_id,
            "client": f"{client_addr[0]}:{client_addr[1]}",
            "target": f"{target_host}:{target_port}",
            "direction": direction,
            "size": len(data),
            "sample": data[:100].hex() if len(data) > 0 else ""
        }
        
        if len(self.traffic_log) >= self.max_log_entries:
            self.traffic_log.pop(0)
        
        self.traffic_log.append(entry)
    
    def log_traffic_data(self, conn_id: str, direction: str, data: bytes):
        """Log ongoing traffic data."""
        entry = {
            "timestamp": time.time(),
            "connection_id": conn_id,
            "direction": direction,
            "size": len(data),
            "sample": data[:50].hex() if len(data) > 0 else ""
        }
        
        if len(self.traffic_log) >= self.max_log_entries:
            self.traffic_log.pop(0)
        
        self.traffic_log.append(entry)


class TransparentProxyManager:
    """Management interface for transparent proxy."""
    
    def __init__(self, proxy: TransparentProxy, management_port: int = 9999):
        self.proxy = proxy
        self.management_port = management_port
        self.logger = logging.getLogger("proxy_manager")
    
    async def start_management_server(self):
        """Start management API server."""
        server = await asyncio.start_server(
            self.handle_management,
            'localhost',
            self.management_port
        )
        
        self.logger.info(f"Management server listening on localhost:{self.management_port}")
        return server
    
    async def handle_management(self, reader, writer):
        """Handle management API requests."""
        try:
            request = await reader.read(4096)
            request_str = request.decode('utf-8')
            
            # Parse simple HTTP request
            lines = request_str.split('\n')
            if not lines:
                writer.close()
                return
            
            method, path, _ = lines[0].split()
            
            response_data = ""
            status = "200 OK"
            
            if path == "/stats":
                response_data = json.dumps(self.proxy.tracker.get_stats(), indent=2)
            elif path == "/traffic":
                response_data = json.dumps(self.proxy.traffic_log[-50:], indent=2)  # Last 50 entries
            elif path == "/connections":
                active_connections = {
                    k: v for k, v in self.proxy.tracker.connections.items()
                    if v["status"] == "active"
                }
                response_data = json.dumps(active_connections, indent=2)
            elif path.startswith("/block/"):
                host = path.split("/")[-1]
                self.proxy.tracker.block_host(host)
                response_data = f"Blocked host: {host}"
            elif path.startswith("/allow/"):
                host = path.split("/")[-1]
                self.proxy.tracker.allow_host(host)
                response_data = f"Allowed host: {host}"
            else:
                status = "404 Not Found"
                response_data = "Endpoint not found"
            
            # Send HTTP response
            response = f"HTTP/1.1 {status}\r\n"
            response += "Content-Type: application/json\r\n"
            response += f"Content-Length: {len(response_data)}\r\n"
            response += "\r\n"
            response += response_data
            
            writer.write(response.encode())
            await writer.drain()
            
        except Exception as e:
            self.logger.error(f"Management error: {e}")
        finally:
            writer.close()


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Transparent Proxy")
    parser.add_argument("--port", type=int, default=8888, help="Proxy port")
    parser.add_argument("--target-host", help="Default target host")
    parser.add_argument("--target-port", type=int, help="Default target port")
    parser.add_argument("--management-port", type=int, default=9999, help="Management API port")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create proxy
    proxy = TransparentProxy(
        listen_port=args.port,
        target_host=args.target_host,
        target_port=args.target_port
    )
    
    # Create management interface
    manager = TransparentProxyManager(proxy, args.management_port)
    
    try:
        # Start servers
        proxy_server = await proxy.start()
        management_server = await manager.start_management_server()
        
        print(f"Transparent Proxy running on localhost:{args.port}")
        if args.target_host and args.target_port:
            print(f"Default target: {args.target_host}:{args.target_port}")
        print(f"Management API: http://localhost:{args.management_port}")
        print("\nManagement endpoints:")
        print(f"  Stats: http://localhost:{args.management_port}/stats")
        print(f"  Traffic: http://localhost:{args.management_port}/traffic")
        print(f"  Active connections: http://localhost:{args.management_port}/connections")
        print(f"  Block host: http://localhost:{args.management_port}/block/example.com")
        print(f"  Allow host: http://localhost:{args.management_port}/allow/example.com")
        print("\nUsage examples:")
        print(f"  # Proxy HTTP traffic")
        print(f"  curl --proxy localhost:{args.port} http://httpbin.org/get")
        print(f"  # View statistics")
        print(f"  curl http://localhost:{args.management_port}/stats")
        print("\nPress Ctrl+C to stop")
        
        # Keep running
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        if 'proxy_server' in locals():
            proxy_server.close()
            await proxy_server.wait_closed()
        if 'management_server' in locals():
            management_server.close()
            await management_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
