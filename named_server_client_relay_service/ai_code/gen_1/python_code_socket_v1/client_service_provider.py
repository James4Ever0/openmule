import socket

def start_service_provider(service_name):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(("localhost", 8888))
    
    # Authenticate
    client_socket.send(b"testuser:testpass")
    response = client_socket.recv(1024)
    if response != b"AUTH_SUCCESS":
        print("Authentication failed")
        return
    
    # Register as service provider
    client_socket.send(f"PROVIDE:{service_name}".encode())
    print(f"Service '{service_name}' registered with relay")
    
    # Now this socket will relay to/from the actual service
    return client_socket

def test_echo_service_provider():
    s = start_service_provider("echo_service")
    while True:
        print("Receiving data...") # stuck at here.
        data = s.recv(1024)
        if not data:
            break
        print(f"Echoing back: {data}")
        print("Sending data...")
        s.send(data)

if __name__ == "__main__":
    test_echo_service_provider()