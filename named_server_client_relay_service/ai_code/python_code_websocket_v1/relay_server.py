import asyncio
import websockets

class WebSocketTCPRelay:
    def __init__(self, ws_host, ws_port):
        self.ws_host = ws_host
        self.ws_port = ws_port
    
    async def handle_websocket_client(self, websocket, path):
        """Handle WebSocket connection and relay to TCP"""
        try:
            # Extract target service from path
            service_name = path.lstrip('/')
            
            # Connect to actual TCP service
            reader, writer = await asyncio.open_connection(
                'localhost', 8080)  # Your actual service
            
            # Bidirectional relay
            await asyncio.gather(
                self.ws_to_tcp(websocket, writer),
                self.tcp_to_ws(reader, websocket)
            )
            
        except Exception as e:
            print(f"WebSocket relay error: {e}")
    
    async def ws_to_tcp(self, websocket, writer):
        async for message in websocket:
            writer.write(message)
            await writer.drain()
    
    async def tcp_to_ws(self, reader, websocket):
        while True:
            data = await reader.read(4096)
            if not data:
                break
            await websocket.send(data)

# Start WebSocket relay
start_server = websockets.serve(
    WebSocketTCPRelay().handle_websocket_client, 
    "localhost", 8765
)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()