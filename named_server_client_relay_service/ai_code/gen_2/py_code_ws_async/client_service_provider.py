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
