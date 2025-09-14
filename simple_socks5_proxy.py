#!/usr/bin/env python3
"""
Simple SOCKS5 Proxy Demo

A basic SOCKS5 proxy implementation for demonstration purposes.

SOCKS5 Protocol Explanation:
SOCKS5 operates at Layer 5 (Session Layer) and creates a tunnel between
client and target server. Unlike HTTP proxies that understand HTTP,
SOCKS5 is protocol-agnostic and can tunnel any TCP/UDP traffic.

Protocol Flow:
1. Client connects to SOCKS5 proxy
2. Authentication negotiation (we use "no authentication" method)
3. Client sends connection request with target server details
4. Proxy establishes connection to target server  
5. Proxy sends success/failure response to client
6. Bidirectional data relay begins

Advantages over HTTP proxy:
- Works with any protocol (not just HTTP)
- Supports UDP relay
- More secure (doesn't modify data)
- Better for applications that need direct socket access
"""

import asyncio      # Async I/O for concurrent connection handling
import logging      # Structured logging for debugging
import socket       # Low-level socket operations for network connections
import struct       # Binary data packing/unpacking for SOCKS5 protocol
import argparse     # Command line argument parsing

class SimpleSocks5Proxy:
    """
    Simple SOCKS5 proxy for demonstration.
    
    Implements the SOCKS5 protocol as defined in RFC 1928.
    This proxy handles the SOCKS5 handshake and data relay.
    """
    
    # SOCKS5 protocol version number (always 0x05)
    VERSION = 0x05
    
    def __init__(self, host='localhost', port=1080):
        self.host = host
        self.port = port
        self.logger = logging.getLogger('socks5-proxy')
    
    async def handle_client(self, client_reader, client_writer):
        """Handle SOCKS5 client connection."""
        try:
            # Authentication negotiation
            if not await self.negotiate_auth(client_reader, client_writer):
                return
            
            # Handle connection request
            await self.handle_request(client_reader, client_writer)
            
        except Exception as e:
            self.logger.error(f"Error handling client: {e}")
        finally:
            client_writer.close()
            await client_writer.wait_closed()
    
    async def negotiate_auth(self, client_reader, client_writer):
        """Handle SOCKS5 authentication negotiation."""
        try:
            # Read initial request
            data = await client_reader.read(2)
            if len(data) != 2:
                return False
            
            version, nmethods = struct.unpack('!BB', data)
            if version != self.VERSION:
                return False
            
            # Read authentication methods
            methods = await client_reader.read(nmethods)
            if len(methods) != nmethods:
                return False
            
            # Select "no authentication" method
            response = struct.pack('!BB', self.VERSION, 0x00)
            client_writer.write(response)
            await client_writer.drain()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Auth negotiation failed: {e}")
            return False
    
    async def handle_request(self, client_reader, client_writer):
        """Handle SOCKS5 connection request."""
        try:
            # Read request header
            data = await client_reader.read(4)
            if len(data) != 4:
                return
            
            version, cmd, rsv, atyp = struct.unpack('!BBBB', data)
            
            if version != self.VERSION or cmd != 0x01:  # Only support CONNECT
                await self.send_error(client_writer, 0x07)  # Command not supported
                return
            
            # Read target address
            if atyp == 0x01:  # IPv4
                addr_data = await client_reader.read(6)
                target_addr = socket.inet_ntop(socket.AF_INET, addr_data[:4])
                target_port = struct.unpack('!H', addr_data[4:6])[0]
                
            elif atyp == 0x03:  # Domain name
                domain_len_data = await client_reader.read(1)
                domain_len = domain_len_data[0]
                domain_data = await client_reader.read(domain_len + 2)
                target_addr = domain_data[:domain_len].decode('utf-8')
                target_port = struct.unpack('!H', domain_data[domain_len:domain_len+2])[0]
                
            else:
                await self.send_error(client_writer, 0x08)  # Address type not supported
                return
            
            self.logger.info(f"CONNECT to {target_addr}:{target_port}")
            
            # Connect to target
            try:
                target_reader, target_writer = await asyncio.open_connection(target_addr, target_port)
                
                # Send success response
                response = struct.pack('!BBBB', self.VERSION, 0x00, 0x00, 0x01)
                response += socket.inet_aton('0.0.0.0')  # Bind address
                response += struct.pack('!H', 0)  # Bind port
                client_writer.write(response)
                await client_writer.drain()
                
                # Start data relay
                await asyncio.gather(
                    self.relay_data(client_reader, target_writer),
                    self.relay_data(target_reader, client_writer)
                )
                
            except Exception as e:
                self.logger.error(f"Connection to {target_addr}:{target_port} failed: {e}")
                await self.send_error(client_writer, 0x05)  # Connection refused
                
        except Exception as e:
            self.logger.error(f"Request handling failed: {e}")
    
    async def send_error(self, client_writer, error_code):
        """Send SOCKS5 error response."""
        response = struct.pack('!BBBB', self.VERSION, error_code, 0x00, 0x01)
        response += struct.pack('!LH', 0, 0)  # 0.0.0.0:0
        client_writer.write(response)
        await client_writer.drain()
    
    async def relay_data(self, reader, writer):
        """Relay data between connections."""
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def start(self):
        """Start the SOCKS5 proxy server."""
        server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )
        
        self.logger.info(f"SOCKS5 Proxy started on {self.host}:{self.port}")
        
        async with server:
            await server.serve_forever()

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Simple SOCKS5 Proxy")
    parser.add_argument("--port", type=int, default=1080, help="Port to bind to")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    proxy = SimpleSocks5Proxy(args.host, args.port)
    
    try:
        await proxy.start()
    except KeyboardInterrupt:
        print("\nProxy stopped by user")

if __name__ == "__main__":
    asyncio.run(main())
