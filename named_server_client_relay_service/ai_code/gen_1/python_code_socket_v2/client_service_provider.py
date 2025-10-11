import socket
import threading
from utils import timed_print, pipe_thread

def start_service_provider(
    relay_host: str,
    relay_port: int,
    service_name: str,
    target_host: str,
    target_port: int,
):
    # Connect to the relay server
    relay_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # relay_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    relay_sock.connect((relay_host, relay_port))

    # Register as a service provider
    registration_msg = f"REGISTER:{service_name}"
    relay_sock.sendall(registration_msg.encode("utf-8"))
    timed_print(f"Registered service '{service_name}' with relay")
    connect_msg = relay_sock.recv(1024)
    timed_print(f"Received %s init bytes from relay" % len(connect_msg))
    if connect_msg == b"CONNECT":
        timed_print("Relay is ready to connect")
        # This socket now acts as a bridge to the relay
        # In a more advanced version, you could automatically connect to the local service (e.g., localhost:5900)
        # and pipe data between `relay_sock` and the local service socket.
        service_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        service_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        service_sock.connect((target_host, target_port))
        thread1 = threading.Thread(
            target=pipe_thread, args=(relay_sock, service_sock, "relay_service"), daemon=True
        )
        thread2 = threading.Thread(
            target=pipe_thread, args=(service_sock, relay_sock, "service_relay"), daemon=True
        )

        thread1.start()
        thread2.start()
        # wait
        thread1.join()
        thread2.join()
    else:
        timed_print(f"Client failed to connect to relay: {connect_msg.hex()[:20]}")


if __name__ == "__main__":
    # Example: start a service provider for 'http_service_a' on port 8888
    while True:
        # start_service_provider("localhost", 8888, "http_service_a", "localhost", 8288)
        start_service_provider("localhost", 8888, "vnc_service_a", "localhost", 5950)
        timed_print("Client or relay disconnected. Reconnecting")