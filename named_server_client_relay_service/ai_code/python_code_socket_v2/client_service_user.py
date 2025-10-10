import socket
import threading

from utils import timed_print, pipe_thread

def connect_to_relay(relay_host, relay_port, service_name):
    # Connect to the relay server
    relay_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    relay_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    relay_sock.connect((relay_host, relay_port))

    # Request the service by name
    request_msg = f"REQUEST:{service_name}"
    relay_sock.sendall(request_msg.encode("utf-8"))

    # Check for initial response
    initial_response = relay_sock.recv(1024)
    if initial_response.startswith(b"ERROR"):
        timed_print(f"Failed to connect to service: {initial_response.decode()}")
        relay_sock.close()
        return None
    if initial_response.startswith(b"OK"):
        timed_print(f"Connected to service '{service_name}' via relay")
    else:
        timed_print(f"Unexpected response from relay: {initial_response.decode()}")
        relay_sock.close()
        return None
    return relay_sock



def start_client(relay_host, relay_port, service_name, local_port:int):
    local_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # local_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        local_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        local_sock.bind(("localhost", local_port))
        local_sock.listen(1)
        timed_print(f"Local forwarder listening on localhost:{local_port}")

        relay_sock = connect_to_relay(relay_host, relay_port, service_name)
        try:
            client_sock, addr = local_sock.accept()
            timed_print(f"Local client connected from {addr}")
            if relay_sock is None:
                # close the client sock
                client_sock.close()
                return
            relay_sock.sendall("CONNECT".encode())
            thread1 = threading.Thread(target=pipe_thread, args=(client_sock, relay_sock, "client_relay"), daemon=True,)
            thread2 = threading.Thread(
                target=pipe_thread,
                args=(relay_sock, client_sock, "relay_client"),
                daemon=True,
            )
            # ready_msg = relay_sock.recv(1024)
            # timed_print("Received message:")
            # if ready_msg != b"PROVIDER_READY":
            #     timed_print("Provider is not ready")
            #     return
            thread1.start()
            thread2.start()
            thread1.join()
            thread2.join()
        finally:
            try:
                if relay_sock is not None:
                    relay_sock.shutdown(socket.SHUT_RDWR)
                    relay_sock.close()
            except: pass
            try:
                client_sock.shutdown(socket.SHUT_RDWR)
                client_sock.close()
            except: pass
    finally:
        local_sock.close()


if __name__ == "__main__":
    # Connect to "http_service_a" and create local port 18800
    # start_client("localhost", 8888, "http_service_a", 18800)
    while True:
        start_client("localhost", 8888, "vnc_service_a", 15900)
        timed_print("Connection aborted. Retrying...")
    # Keep the main thread alive
