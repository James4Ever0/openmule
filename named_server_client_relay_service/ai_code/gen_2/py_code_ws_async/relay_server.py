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