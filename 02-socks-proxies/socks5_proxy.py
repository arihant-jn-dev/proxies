#!/usr/bin/env python3
"""
SOCKS5 Proxy Server Implementation

A complete SOCKS5 proxy server supporting:
- Multiple authentication methods (none, username/password)
- IPv4 and IPv6 connections
- TCP tunneling with CONNECT command
- UDP relay with UDP ASSOCIATE command
- Domain name resolution by proxy

Usage:
    python socks5_proxy.py --port 1080
    python socks5_proxy.py --port 1080 --auth admin:password
    python socks5_proxy.py --port 1080 --enable-udp --auth-file users.txt
"""

import argparse
import asyncio
import hashlib
import json
import logging
import socket
import struct
import sys
import time
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for common utilities
sys.path.append('../common')
from utils import ProxyLogger, PerformanceMonitor, ConfigManager


class SOCKS5Protocol:
    """SOCKS5 protocol constants and utilities."""
    
    # Version
    VERSION = 0x05
    
    # Authentication methods
    AUTH_NONE = 0x00
    AUTH_GSSAPI = 0x01
    AUTH_USERNAME_PASSWORD = 0x02
    AUTH_NO_ACCEPTABLE = 0xFF
    
    # Commands
    CMD_CONNECT = 0x01
    CMD_BIND = 0x02
    CMD_UDP_ASSOCIATE = 0x03
    
    # Address types
    ATYP_IPV4 = 0x01
    ATYP_DOMAIN = 0x03
    ATYP_IPV6 = 0x04
    
    # Reply codes
    REP_SUCCESS = 0x00
    REP_GENERAL_FAILURE = 0x01
    REP_CONNECTION_NOT_ALLOWED = 0x02
    REP_NETWORK_UNREACHABLE = 0x03
    REP_HOST_UNREACHABLE = 0x04
    REP_CONNECTION_REFUSED = 0x05
    REP_TTL_EXPIRED = 0x06
    REP_COMMAND_NOT_SUPPORTED = 0x07
    REP_ADDRESS_TYPE_NOT_SUPPORTED = 0x08
    
    @staticmethod
    def pack_address(address: str, port: int) -> bytes:
        """Pack address and port into SOCKS5 format."""
        try:
            # Try IPv4
            addr_bytes = socket.inet_pton(socket.AF_INET, address)
            return struct.pack('!B4sH', SOCKS5Protocol.ATYP_IPV4, addr_bytes, port)
        except OSError:
            pass
        
        try:
            # Try IPv6
            addr_bytes = socket.inet_pton(socket.AF_INET6, address)
            return struct.pack('!B16sH', SOCKS5Protocol.ATYP_IPV6, addr_bytes, port)
        except OSError:
            pass
        
        # Domain name
        addr_bytes = address.encode('utf-8')
        return struct.pack('!BB', SOCKS5Protocol.ATYP_DOMAIN, len(addr_bytes)) + addr_bytes + struct.pack('!H', port)
    
    @staticmethod
    def unpack_address(data: bytes, offset: int = 0) -> Tuple[str, int, int]:
        """Unpack address from SOCKS5 format."""
        atyp = data[offset]
        
        if atyp == SOCKS5Protocol.ATYP_IPV4:
            addr_bytes = data[offset + 1:offset + 5]
            port = struct.unpack('!H', data[offset + 5:offset + 7])[0]
            address = socket.inet_ntop(socket.AF_INET, addr_bytes)
            return address, port, offset + 7
        
        elif atyp == SOCKS5Protocol.ATYP_IPV6:
            addr_bytes = data[offset + 1:offset + 17]
            port = struct.unpack('!H', data[offset + 17:offset + 19])[0]
            address = socket.inet_ntop(socket.AF_INET6, addr_bytes)
            return address, port, offset + 19
        
        elif atyp == SOCKS5Protocol.ATYP_DOMAIN:
            domain_len = data[offset + 1]
            domain_bytes = data[offset + 2:offset + 2 + domain_len]
            port = struct.unpack('!H', data[offset + 2 + domain_len:offset + 4 + domain_len])[0]
            address = domain_bytes.decode('utf-8')
            return address, port, offset + 4 + domain_len
        
        else:
            raise ValueError(f"Unsupported address type: {atyp}")


class SOCKS5User:
    """SOCKS5 user authentication."""
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.created_at = time.time()
        self.last_login = None
        self.login_count = 0
    
    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate user credentials."""
        if self.username == username and self.password == password:
            self.last_login = time.time()
            self.login_count += 1
            return True
        return False


class UDPRelay:
    """UDP relay for SOCKS5 UDP ASSOCIATE command."""
    
    def __init__(self, bind_host: str, bind_port: int = 0):
        self.bind_host = bind_host
        self.bind_port = bind_port
        self.socket = None
        self.client_map = {}  # Map client addresses to target addresses
        self.running = False
    
    async def start(self) -> Tuple[str, int]:
        """Start UDP relay and return bind address."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.bind_host, self.bind_port))
        self.socket.setblocking(False)
        
        actual_host, actual_port = self.socket.getsockname()
        self.running = True
        
        # Start relay loop
        asyncio.create_task(self.relay_loop())
        
        return actual_host, actual_port
    
    async def relay_loop(self):
        """Main UDP relay loop."""
        loop = asyncio.get_event_loop()
        
        while self.running:
            try:
                data, client_addr = await loop.sock_recvfrom(self.socket, 65535)
                await self.handle_udp_packet(data, client_addr)
            except Exception as e:
                if self.running:
                    print(f"UDP relay error: {e}")
                break
    
    async def handle_udp_packet(self, data: bytes, client_addr: Tuple[str, int]):
        """Handle incoming UDP packet."""
        try:
            # Parse SOCKS5 UDP request header
            if len(data) < 10:
                return
            
            rsv = struct.unpack('!H', data[0:2])[0]  # Reserved, must be 0
            frag = data[2]  # Fragment number
            
            if rsv != 0 or frag != 0:
                return  # Invalid packet
            
            # Extract target address and port
            target_addr, target_port, header_len = SOCKS5Protocol.unpack_address(data, 3)
            udp_data = data[header_len:]
            
            # Forward packet to target
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            target_socket.sendto(udp_data, (target_addr, target_port))
            
            # Wait for response (with timeout)
            target_socket.settimeout(5.0)
            try:
                response_data, _ = target_socket.recvfrom(65535)
                
                # Build SOCKS5 UDP response
                response_header = struct.pack('!HB', 0, 0)  # RSV=0, FRAG=0
                response_header += SOCKS5Protocol.pack_address(target_addr, target_port)
                response_packet = response_header + response_data
                
                # Send back to client
                loop = asyncio.get_event_loop()
                await loop.sock_sendto(self.socket, response_packet, client_addr)
                
            except socket.timeout:
                pass  # No response from target
            
            target_socket.close()
            
        except Exception as e:
            print(f"UDP packet handling error: {e}")
    
    def stop(self):
        """Stop UDP relay."""
        self.running = False
        if self.socket:
            self.socket.close()


class SOCKS5Connection:
    """Handles a single SOCKS5 client connection."""
    
    def __init__(self, client_socket, client_addr, proxy_server):
        self.client_socket = client_socket
        self.client_addr = client_addr
        self.proxy_server = proxy_server
        self.logger = proxy_server.logger
        self.authenticated = False
        self.target_socket = None
    
    async def handle(self):
        """Handle the complete SOCKS5 connection."""
        try:
            # Step 1: Authentication negotiation
            auth_method = await self.negotiate_authentication()
            if auth_method is None:
                return
            
            # Step 2: Authentication (if required)
            if auth_method == SOCKS5Protocol.AUTH_USERNAME_PASSWORD:
                if not await self.authenticate_user():
                    return
            
            self.authenticated = True
            
            # Step 3: Handle client request
            await self.handle_request()
            
        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
        finally:
            await self.cleanup()
    
    async def negotiate_authentication(self) -> Optional[int]:
        """Negotiate authentication method."""
        try:
            # Receive initial request
            data = await self.recv_exact(2)
            if not data:
                return None
            
            version, nmethods = struct.unpack('!BB', data)
            if version != SOCKS5Protocol.VERSION:
                self.logger.error(f"Unsupported SOCKS version: {version}")
                return None
            
            # Receive authentication methods
            methods_data = await self.recv_exact(nmethods)
            if not methods_data:
                return None
            
            methods = list(methods_data)
            self.logger.debug(f"Client methods: {[hex(m) for m in methods]}")
            
            # Select authentication method
            selected_method = self.select_auth_method(methods)
            
            # Send method selection response
            response = struct.pack('!BB', SOCKS5Protocol.VERSION, selected_method)
            await self.send_all(response)
            
            return selected_method if selected_method != SOCKS5Protocol.AUTH_NO_ACCEPTABLE else None
            
        except Exception as e:
            self.logger.error(f"Authentication negotiation failed: {str(e)}")
            return None
    
    def select_auth_method(self, client_methods: List[int]) -> int:
        """Select the best authentication method."""
        # Check if authentication is required
        if not self.proxy_server.auth_required:
            if SOCKS5Protocol.AUTH_NONE in client_methods:
                return SOCKS5Protocol.AUTH_NONE
        
        # Check for username/password auth
        if (self.proxy_server.users and 
            SOCKS5Protocol.AUTH_USERNAME_PASSWORD in client_methods):
            return SOCKS5Protocol.AUTH_USERNAME_PASSWORD
        
        # No acceptable method
        return SOCKS5Protocol.AUTH_NO_ACCEPTABLE
    
    async def authenticate_user(self) -> bool:
        """Authenticate user with username/password."""
        try:
            # Receive authentication request
            data = await self.recv_exact(2)
            if not data:
                return False
            
            version, ulen = struct.unpack('!BB', data)
            if version != 0x01:  # Username/password auth version
                return False
            
            # Receive username
            username_data = await self.recv_exact(ulen)
            if not username_data:
                return False
            username = username_data.decode('utf-8')
            
            # Receive password length and password
            plen_data = await self.recv_exact(1)
            if not plen_data:
                return False
            plen = plen_data[0]
            
            password_data = await self.recv_exact(plen)
            if not password_data:
                return False
            password = password_data.decode('utf-8')
            
            # Authenticate
            success = self.proxy_server.authenticate_user(username, password)
            
            # Send authentication response
            status = 0x00 if success else 0x01
            response = struct.pack('!BB', 0x01, status)
            await self.send_all(response)
            
            if success:
                self.logger.logger.info(f"User {username} authenticated successfully")
            else:
                self.logger.logger.warning(f"Authentication failed for user {username}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"User authentication failed: {str(e)}")
            return False
    
    async def handle_request(self):
        """Handle client connection request."""
        try:
            # Receive request header
            data = await self.recv_exact(4)
            if not data:
                return
            
            version, cmd, rsv, atyp = struct.unpack('!BBBB', data)
            
            if version != SOCKS5Protocol.VERSION:
                await self.send_error_response(SOCKS5Protocol.REP_GENERAL_FAILURE)
                return
            
            # Receive address and port
            if atyp == SOCKS5Protocol.ATYP_IPV4:
                addr_data = await self.recv_exact(6)  # 4 bytes IP + 2 bytes port
                if not addr_data:
                    return
                target_addr = socket.inet_ntop(socket.AF_INET, addr_data[:4])
                target_port = struct.unpack('!H', addr_data[4:6])[0]
                
            elif atyp == SOCKS5Protocol.ATYP_IPV6:
                addr_data = await self.recv_exact(18)  # 16 bytes IP + 2 bytes port
                if not addr_data:
                    return
                target_addr = socket.inet_ntop(socket.AF_INET6, addr_data[:16])
                target_port = struct.unpack('!H', addr_data[16:18])[0]
                
            elif atyp == SOCKS5Protocol.ATYP_DOMAIN:
                domain_len_data = await self.recv_exact(1)
                if not domain_len_data:
                    return
                domain_len = domain_len_data[0]
                
                domain_data = await self.recv_exact(domain_len + 2)  # domain + port
                if not domain_data:
                    return
                
                target_addr = domain_data[:domain_len].decode('utf-8')
                target_port = struct.unpack('!H', domain_data[domain_len:domain_len+2])[0]
                
            else:
                await self.send_error_response(SOCKS5Protocol.REP_ADDRESS_TYPE_NOT_SUPPORTED)
                return
            
            self.logger.request(f"SOCKS5 {cmd}", f"{target_addr}:{target_port}", self.client_addr[0])
            
            # Handle command
            if cmd == SOCKS5Protocol.CMD_CONNECT:
                await self.handle_connect(target_addr, target_port)
            elif cmd == SOCKS5Protocol.CMD_UDP_ASSOCIATE:
                await self.handle_udp_associate(target_addr, target_port)
            else:
                await self.send_error_response(SOCKS5Protocol.REP_COMMAND_NOT_SUPPORTED)
                
        except Exception as e:
            self.logger.error(f"Request handling failed: {str(e)}")
            await self.send_error_response(SOCKS5Protocol.REP_GENERAL_FAILURE)
    
    async def handle_connect(self, target_addr: str, target_port: int):
        """Handle CONNECT command."""
        try:
            # Resolve domain if needed
            if not target_addr.replace('.', '').isdigit():  # It's a domain
                try:
                    target_addr = socket.gethostbyname(target_addr)
                except socket.gaierror:
                    await self.send_error_response(SOCKS5Protocol.REP_HOST_UNREACHABLE)
                    return
            
            # Connect to target
            self.target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.target_socket.setblocking(False)
            
            try:
                await asyncio.wait_for(
                    asyncio.get_event_loop().sock_connect(self.target_socket, (target_addr, target_port)),
                    timeout=10.0
                )
            except (asyncio.TimeoutError, OSError):
                await self.send_error_response(SOCKS5Protocol.REP_CONNECTION_REFUSED)
                return
            
            # Send success response
            local_addr, local_port = self.target_socket.getsockname()
            response = struct.pack('!BBBB', SOCKS5Protocol.VERSION, SOCKS5Protocol.REP_SUCCESS, 0x00, SOCKS5Protocol.ATYP_IPV4)
            response += socket.inet_aton(local_addr)
            response += struct.pack('!H', local_port)
            await self.send_all(response)
            
            # Start data relay
            await self.relay_data()
            
        except Exception as e:
            self.logger.error(f"CONNECT failed: {str(e)}")
            await self.send_error_response(SOCKS5Protocol.REP_GENERAL_FAILURE)
    
    async def handle_udp_associate(self, target_addr: str, target_port: int):
        """Handle UDP ASSOCIATE command."""
        if not self.proxy_server.udp_enabled:
            await self.send_error_response(SOCKS5Protocol.REP_COMMAND_NOT_SUPPORTED)
            return
        
        try:
            # Start UDP relay
            udp_relay = UDPRelay(self.proxy_server.bind_host)
            relay_addr, relay_port = await udp_relay.start()
            
            # Send success response with UDP relay address
            response = struct.pack('!BBBB', SOCKS5Protocol.VERSION, SOCKS5Protocol.REP_SUCCESS, 0x00, SOCKS5Protocol.ATYP_IPV4)
            response += socket.inet_aton(relay_addr)
            response += struct.pack('!H', relay_port)
            await self.send_all(response)
            
            self.logger.logger.info(f"UDP relay started on {relay_addr}:{relay_port}")
            
            # Keep connection alive while UDP relay is active
            while True:
                data = await self.recv_data(1024)
                if not data:
                    break
            
            udp_relay.stop()
            
        except Exception as e:
            self.logger.error(f"UDP ASSOCIATE failed: {str(e)}")
            await self.send_error_response(SOCKS5Protocol.REP_GENERAL_FAILURE)
    
    async def send_error_response(self, error_code: int):
        """Send error response to client."""
        response = struct.pack('!BBBB', SOCKS5Protocol.VERSION, error_code, 0x00, SOCKS5Protocol.ATYP_IPV4)
        response += struct.pack('!LH', 0, 0)  # 0.0.0.0:0
        await self.send_all(response)
    
    async def relay_data(self):
        """Relay data between client and target."""
        if not self.target_socket:
            return
        
        try:
            await asyncio.gather(
                self.relay_client_to_target(),
                self.relay_target_to_client()
            )
        except Exception as e:
            self.logger.debug(f"Data relay ended: {str(e)}")
    
    async def relay_client_to_target(self):
        """Relay data from client to target."""
        loop = asyncio.get_event_loop()
        while True:
            data = await loop.sock_recv(self.client_socket, 8192)
            if not data:
                break
            await loop.sock_sendall(self.target_socket, data)
    
    async def relay_target_to_client(self):
        """Relay data from target to client."""
        loop = asyncio.get_event_loop()
        while True:
            data = await loop.sock_recv(self.target_socket, 8192)
            if not data:
                break
            await loop.sock_sendall(self.client_socket, data)
    
    async def recv_exact(self, n: int) -> Optional[bytes]:
        """Receive exactly n bytes."""
        data = b''
        while len(data) < n:
            chunk = await self.recv_data(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data
    
    async def recv_data(self, max_bytes: int) -> Optional[bytes]:
        """Receive data from client socket."""
        try:
            loop = asyncio.get_event_loop()
            return await loop.sock_recv(self.client_socket, max_bytes)
        except Exception:
            return None
    
    async def send_all(self, data: bytes):
        """Send all data to client socket."""
        try:
            loop = asyncio.get_event_loop()
            await loop.sock_sendall(self.client_socket, data)
        except Exception as e:
            raise e
    
    async def cleanup(self):
        """Clean up resources."""
        if self.target_socket:
            self.target_socket.close()
        self.client_socket.close()


class SOCKS5Server:
    """SOCKS5 proxy server."""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.logger = ProxyLogger("socks5-proxy", 
                                 getattr(logging, config.get("log_level", "INFO")))
        self.monitor = PerformanceMonitor()
        
        # Server configuration
        self.bind_host = config.get("bind_host", "0.0.0.0")
        self.bind_port = config.get("bind_port", 1080)
        
        # Authentication
        self.auth_required = config.get("auth_required", False)
        self.users: Dict[str, SOCKS5User] = {}
        
        # Load users
        users_config = config.get("users", {})
        for username, password in users_config.items():
            self.users[username] = SOCKS5User(username, password)
        
        # Features
        self.udp_enabled = config.get("udp_enabled", True)
        
        # Server socket
        self.server_socket = None
        self.running = False
    
    def authenticate_user(self, username: str, password: str) -> bool:
        """Authenticate user credentials."""
        user = self.users.get(username)
        return user.authenticate(username, password) if user else False
    
    async def start(self):
        """Start the SOCKS5 server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.bind_host, self.bind_port))
        self.server_socket.listen(100)
        self.server_socket.setblocking(False)
        
        self.running = True
        
        self.logger.logger.info(f"SOCKS5 server started on {self.bind_host}:{self.bind_port}")
        self.logger.logger.info(f"Authentication: {'Required' if self.auth_required else 'Not required'}")
        self.logger.logger.info(f"UDP support: {'Enabled' if self.udp_enabled else 'Disabled'}")
        
        # Accept connections
        loop = asyncio.get_event_loop()
        while self.running:
            try:
                client_socket, client_addr = await loop.sock_accept(self.server_socket)
                client_socket.setblocking(False)
                
                self.logger.logger.info(f"New connection from {client_addr[0]}:{client_addr[1]}")
                
                # Handle connection in background
                connection = SOCKS5Connection(client_socket, client_addr, self)
                asyncio.create_task(connection.handle())
                
            except Exception as e:
                if self.running:
                    self.logger.error(f"Accept error: {str(e)}")
                break
    
    def stop(self):
        """Stop the SOCKS5 server."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="SOCKS5 Proxy Server")
    parser.add_argument("--port", type=int, default=1080, help="Port to bind to")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--auth", help="Authentication in format username:password")
    parser.add_argument("--auth-file", help="File containing username:password pairs")
    parser.add_argument("--no-udp", action="store_true", help="Disable UDP support")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--log-level", default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Load configuration
    config = ConfigManager(args.config) if args.config else ConfigManager()
    config.set("bind_host", args.host)
    config.set("bind_port", args.port)
    config.set("log_level", args.log_level)
    config.set("udp_enabled", not args.no_udp)
    
    # Setup authentication
    users = {}
    
    if args.auth:
        username, password = args.auth.split(':', 1)
        users[username] = password
        config.set("auth_required", True)
    
    if args.auth_file:
        try:
            with open(args.auth_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and ':' in line:
                        username, password = line.split(':', 1)
                        users[username] = password
            config.set("auth_required", True)
        except FileNotFoundError:
            print(f"Authentication file not found: {args.auth_file}")
            return
    
    config.set("users", users)
    
    server = SOCKS5Server(config)
    
    try:
        print(f"Starting SOCKS5 proxy on {args.host}:{args.port}")
        if users:
            print(f"Authentication enabled with {len(users)} user(s)")
        print("Press Ctrl+C to stop")
        
        await server.start()
    
    except KeyboardInterrupt:
        print("\nShutting down SOCKS5 proxy...")
    finally:
        server.stop()


if __name__ == "__main__":
    asyncio.run(main())
