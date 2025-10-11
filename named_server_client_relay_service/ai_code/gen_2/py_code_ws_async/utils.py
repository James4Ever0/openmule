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
