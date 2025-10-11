I'll rewrite the relay system using asyncio and websockets. Here's the complete solution:

utils.py
import time
import asyncio
import logging

def timed_print(*args, **kwargs):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}]", *args, **kwargs)

async def pipe_ws_to_tcp(websocket, writer):
    try:
        async for message in websocket:
            writer.write(message)
            await writer.drain()
    except Exception as e:
        timed_print(f"pipe_ws_to_tcp error: {e}")
    finally:
        writer.close()

async def pipe_tcp_to_ws(reader, websocket):
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            await websocket.send(data)
    except Exception as e:
        timed_print(f"pipe_tcp_to_ws error: {e}")


relay_server.py
import asyncio
import websockets
from utils import timed_print

class RelayServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.service_registry = {}
        self.lock = asyncio.Lock()

    async def run(self):
        async with websockets.serve(self.handler, self.host, self.port):
            timed_print(f"Relay server listening on {self.host}:{self.port}")
            await asyncio.Future()  # Run forever

    async def handler(self, websocket, path):
        try:
            message = await websocket.recv()
            timed_print(f"Received identification: {message}")

            if message.startswith("REGISTER:"):
                service_name = message.split(":", 1)[1]
                await self.register_service(service_name, websocket)
            elif message.startswith("REQUEST:"):
                service_name = message.split(":", 1)[1]
                await self.handle_client_request(service_name, websocket)
            else:
                timed_print(f"Unknown protocol message: {message}")
                await websocket.close()
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            timed_print(f"Error handling connection: {e}")

    async def register_service(self, service_name, provider_ws):
        async with self.lock:
            if service_name in self.service_registry:
                timed_print(f"Service '{service_name}' is already registered. Closing old connection.")
                old_ws = self.service_registry[service_name]
                await old_ws.close()
            
            self.service_registry[service_name] = provider_ws
            timed_print(f"Service '{service_name}' registered successfully.")

    async def unregister_service(self, service_name):
        async with self.lock:
            if service_name in self.service_registry:
                ws = self.service_registry.pop(service_name)
                await ws.close()
                timed_print(f"Service '{service_name}' unregistered.")

    async def handle_client_request(self, service_name, client_ws):
        async with self.lock:
            provider_ws = self.service_registry.get(service_name)
            
        if provider_ws is None:
            timed_print(f"Client requested unknown service: {service_name}")
            await client_ws.send("ERROR:Service not found")
            await client_ws.close()
            return

        timed_print(f"Connecting client to service '{service_name}'")
        await client_ws.send("OK")
        await self.create_bidirectional_pipe(client_ws, provider_ws)
        timed_print(f"Client disconnected from service '{service_name}'")
        await self.unregister_service(service_name)

    async def create_bidirectional_pipe(self, ws1, ws2):
        pipe1 = self.pipe(ws1, ws2)
        pipe2 = self.pipe(ws2, ws1)
        await asyncio.gather(pipe1, pipe2, return_exceptions=True)

    async def pipe(self, source, sink):
        try:
            async for message in source:
                await sink.send(message)
        except websockets.exceptions.ConnectionClosed:
            pass

if __name__ == "__main__":
    relay = RelayServer('0.0.0.0', 8888)
    asyncio.run(relay.run())


client_service_provider.py
import asyncio
import websockets
from utils import timed_print, pipe_ws_to_tcp, pipe_tcp_to_ws

async def run_provider(relay_host, relay_port, service_name, target_host, target_port):
    while True:
        try:
            async with websockets.connect(f"ws://{relay_host}:{relay_port}") as websocket:
                await websocket.send(f"REGISTER:{service_name}")
                timed_print(f"Registered service '{service_name}'")

                # Connect to target service
                reader, writer = await asyncio.open_connection(target_host, target_port)
                timed_print(f"Connected to target {target_host}:{target_port}")

                # Start bidirectional piping
                await asyncio.gather(
                    pipe_ws_to_tcp(websocket, writer),
                    pipe_tcp_to_ws(reader, websocket)
                )
        except Exception as e:
            timed_print(f"Provider error: {e}")
        timed_print("Provider disconnected. Reconnecting...")
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run_provider("localhost", 8888, "vnc_service_a", "localhost", 5950))


client_service_user.py
import asyncio
import websockets
from utils import timed_print, pipe_ws_to_tcp, pipe_tcp_to_ws

async def handle_local_client(local_reader, local_writer, relay_host, relay_port, service_name):
    try:
        async with websockets.connect(f"ws://{relay_host}:{relay_port}") as websocket:
            await websocket.send(f"REQUEST:{service_name}")
            response = await websocket.recv()
            
            if response != "OK":
                timed_print(f"Failed to get service: {response}")
                return
                
            timed_print(f"Connected to service '{service_name}'")
            await asyncio.gather(
                pipe_ws_to_tcp(websocket, local_writer),
                pipe_tcp_to_ws(local_reader, websocket)
            )
    except Exception as e:
        timed_print(f"Client error: {e}")
    finally:
        await local_writer.drain()
        local_writer.close()

async def run_user(relay_host, relay_port, service_name, local_port):
    server = await asyncio.start_server(
        lambda r, w: handle_local_client(r, w, relay_host, relay_port, service_name),
        'localhost', local_port
    )
    async with server:
        timed_print(f"Local forwarder listening on localhost:{local_port}")
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(run_user("localhost", 8888, "vnc_service_a", 15900))


Key changes made:
1. Replaced threading with asyncio for asynchronous I/O
2. Replaced socket with websockets for WebSocket communication
3. Implemented bidirectional data piping using async generators
4. Simplified connection management with async context managers
5. Removed manual thread management in favor of asyncio tasks
6. Improved error handling and resource cleanup
7. Maintained the same core functionality with cleaner async code

The system now uses WebSockets for all relay communications while maintaining TCP connections to local services. The relay server manages service registrations and connects clients to providers through WebSocket bridges.