#!/usr/bin/env python3
"""
Simple HTTP Forward Proxy Demo

A basic HTTP forward proxy that works without external dependencies
for demonstration purposes.

How Forward Proxies Work:
1. Client configures browser to use proxy (e.g., localhost:8080)
2. Instead of connecting directly to target server, client connects to proxy
3. Client sends HTTP request to proxy, including target server in request line
4. Proxy parses request, extracts target server information
5. Proxy establishes new connection to target server
6. Proxy forwards original request to target server
7. Target server responds to proxy
8. Proxy forwards response back to original client

This creates a "forward" flow: Client -> Proxy -> Target Server
"""

import asyncio        # Asynchronous I/O for handling multiple connections efficiently
import logging       # Structured logging for debugging and monitoring
import socket         # Low-level network socket operations
import sys           # System functions and parameters
import argparse      # Command line argument parsing
from urllib.parse import urlparse    # Parse URLs to extract host, port, path components

class SimpleHTTPForwardProxy:
    """
    Simple HTTP forward proxy for demonstration.
    
    This class implements a basic forward proxy that:
    - Listens for client connections on a specified port
    - Parses HTTP requests to extract target server information
    - Establishes connections to target servers
    - Relays data bidirectionally between client and target server
    """
    
    def __init__(self, host='localhost', port=8080):
        # Host interface to bind to ('0.0.0.0' for all interfaces, 'localhost' for local only)
        self.host = host
        # Port number to listen on (commonly 8080 for HTTP proxies)
        self.port = port
        # Logger for debugging and monitoring proxy activity
        self.logger = logging.getLogger('forward-proxy')
        
    async def handle_client(self, client_reader, client_writer):
        """
        Handle incoming client connection.
        
        This method:
        1. Reads the HTTP request from the client
        2. Parses the request to extract target server information
        3. Establishes connection to target server
        4. Forwards the request and relays responses
        """
        try:
            # Read the first line of HTTP request (e.g., "GET http://example.com/path HTTP/1.1")
            request_line = await client_reader.readline()
            if not request_line:
                return
                
            request_line = request_line.decode('utf-8').strip()
            self.logger.info(f"Request: {request_line}")
            
            # Parse the request
            parts = request_line.split(' ')
            if len(parts) < 3:
                return
                
            method, url, version = parts[0], parts[1], parts[2]
            
            # Parse the URL
            parsed_url = urlparse(url)
            target_host = parsed_url.hostname
            target_port = parsed_url.port or 80
            
            if not target_host:
                # Handle relative URLs by reading Host header
                headers = {}
                while True:
                    line = await client_reader.readline()
                    if not line or line == b'\r\n':
                        break
                    header = line.decode('utf-8').strip()
                    if ':' in header:
                        key, value = header.split(':', 1)
                        headers[key.strip().lower()] = value.strip()
                
                if 'host' in headers:
                    host_parts = headers['host'].split(':')
                    target_host = host_parts[0]
                    target_port = int(host_parts[1]) if len(host_parts) > 1 else 80
                else:
                    client_writer.write(b'HTTP/1.1 400 Bad Request\r\n\r\n')
                    await client_writer.drain()
                    return
            
            # Connect to target server
            try:
                target_reader, target_writer = await asyncio.open_connection(target_host, target_port)
                
                # Forward the request
                target_writer.write(request_line.encode() + b'\r\n')
                
                # Forward headers (if not already read)
                if 'host' not in locals():
                    while True:
                        line = await client_reader.readline()
                        target_writer.write(line)
                        if not line or line == b'\r\n':
                            break
                
                await target_writer.drain()
                
                # Start bidirectional relay
                await asyncio.gather(
                    self.relay_data(client_reader, target_writer),
                    self.relay_data(target_reader, client_writer)
                )
                
            except Exception as e:
                self.logger.error(f"Connection to {target_host}:{target_port} failed: {e}")
                error_response = f"HTTP/1.1 502 Bad Gateway\r\n\r\nConnection to {target_host} failed"
                client_writer.write(error_response.encode())
                await client_writer.drain()
                
        except Exception as e:
            self.logger.error(f"Error handling client: {e}")
        finally:
            client_writer.close()
            await client_writer.wait_closed()
    
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
        """Start the proxy server."""
        server = await asyncio.start_server(
            self.handle_client, 
            self.host, 
            self.port
        )
        
        self.logger.info(f"HTTP Forward Proxy started on {self.host}:{self.port}")
        
        async with server:
            await server.serve_forever()

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Simple HTTP Forward Proxy")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    proxy = SimpleHTTPForwardProxy(args.host, args.port)
    
    try:
        await proxy.start()
    except KeyboardInterrupt:
        print("\nProxy stopped by user")

if __name__ == "__main__":
    asyncio.run(main())
