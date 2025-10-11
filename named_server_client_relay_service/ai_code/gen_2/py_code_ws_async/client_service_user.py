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
