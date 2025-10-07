import socket
import threading


def start_client(relay_host, relay_port, service_name, local_port=15900):
    # Connect to the relay server
    relay_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    relay_sock.connect((relay_host, relay_port))

    # Request the service by name
    request_msg = f"REQUEST:{service_name}"
    relay_sock.send(request_msg.encode("utf-8"))

    # Check for initial response
    initial_response = relay_sock.recv(1024)
    if initial_response.startswith(b"ERROR"):
        print(f"Failed to connect to service: {initial_response.decode()}")
        relay_sock.close()
        return None

    print(f"Connected to service '{service_name}' via relay")

    # Optional: Create a local server that forwards to the relay connection
    def create_local_forwarder():
        local_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        local_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        local_sock.bind(("localhost", local_port))
        local_sock.listen(1)
        print(f"Local forwarder listening on localhost:{local_port}")

        while True:
            client_sock, addr = local_sock.accept()
            print(f"Local client connected from {addr}")
            # Pipe data bidirectionally between the local client and the relay connection
            # This is a simplified version - in production, you'd need proper connection handling
            threading.Thread(target=pipe_data, args=(client_sock, relay_sock)).start()
            threading.Thread(
                target=pipe_data,
                args=(relay_sock, client_sock),
                kwargs={"close_source": False},
            ).start()

    # Start the local forwarder in a separate thread
    forwarder_thread = threading.Thread(target=create_local_forwarder)
    forwarder_thread.daemon = True
    forwarder_thread.start()

    return relay_sock


def pipe_data(source, destination, close_source=True):
    """Simple data piping between two sockets"""
    try:
        while True:
            data = source.recv(4096)
            if not data:
                break
            destination.sendall(data)
    except:
        pass
    finally:
        if close_source:
            source.close()
        else:
            destination.close()


if __name__ == "__main__":
    # Connect to "vnc_service_a" and create local port 15900
    start_client("localhost", 8888, "vnc_service_a", 15900)
    # Keep the main thread alive
    threading.Event().wait()
