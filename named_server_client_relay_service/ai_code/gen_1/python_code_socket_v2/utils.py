import time
import socket

def pipe_thread(source:socket.socket, destination:socket.socket, name:str):
    timed_print("Running pipe thread:", name)
    try:
        while True:
            timed_print("Receiving data at pipe thread", name)
            data = source.recv(4096)
            timed_print("Received %s bytes at pipe thread" % len(data), name)
            # print hex repr
            timed_print("Received bytes at pipe thread %s" % name, data.hex()[:20] + ("..." if len(data.hex()) > 20 else ""))
            # init bytes from vnc server: 0a
            # although the service send 1 byte to relay, the relay does not forward the data, result into no response in client side.
            if not data:
                break
            timed_print("Sending data at pipe thread", name)
            destination.sendall(data) # send immediately
    except Exception as e:
        timed_print(f"Pipe thread %s error: {e}" % name)
    finally:
        try:
            source.shutdown(socket.SHUT_RDWR)
            source.close()
        except: pass
        try:
            destination.shutdown(socket.SHUT_RDWR)
            destination.close()
        except: pass
def timed_print(*args, **kwargs):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}]", *args, **kwargs)