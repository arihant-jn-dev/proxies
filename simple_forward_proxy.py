#!/usr/bin/env python3
"""
Simple HTTP Forward Proxy Demo

A basic HTTP forward proxy that works without external dependencies
for demonstration purposes.
"""

import asyncio
import logging
import socket
import sys
import argparse
from urllib.parse import urlparse

class SimpleHTTPForwardProxy:
    """Simple HTTP forward proxy for demonstration."""
    
    def __init__(self, host='localhost', port=8080):
        self.host = host
        self.port = port
        self.logger = logging.getLogger('forward-proxy')
        
    async def handle_client(self, client_reader, client_writer):
        """Handle client connection."""
        try:
            # Read the HTTP request
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
