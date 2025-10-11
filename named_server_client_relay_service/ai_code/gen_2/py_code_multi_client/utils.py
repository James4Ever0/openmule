import time
import socket

def pipe_thread(source: socket.socket, destination: socket.socket, name: str):
    """Thread function to pipe data between two sockets with connection tracking"""
    timed_print(f"Starting pipe thread: {name}")
    try:
        while True:
            data = source.recv(4096)
            if not data:
                break
            destination.sendall(data)
    except Exception as e:
        timed_print(f"Pipe thread {name} error: {e}")
    finally:
        try:
            source.shutdown(socket.SHUT_RDWR)
        except:
            pass
        try:
            source.close()
        except:
            pass
        timed_print(f"Pipe thread {name} finished")

def timed_print(*args, **kwargs):
    """Print with timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}]", *args, **kwargs)
