import socket

def start_client(service_name):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(("localhost", 8888))
    
    # Authenticate
    client_socket.send(b"testuser:testpass")
    response = client_socket.recv(1024)
    if response != b"AUTH_SUCCESS":
        print("Authentication failed")
        return
    
    # Request service
    client_socket.send(f"CONNECT:{service_name}".encode())
    print(f"Connected to service '{service_name}' through relay")
    
    # Now use client_socket to communicate with the service
    return client_socket

def test_echo_service_user():
    s = start_client("echo_service")
    if s:
        test_message = b"Hello, Echo Service!"
        print(f"Sending: {test_message}")
        s.send(test_message)
        response = s.recv(1024)
        print(f"Received: {response}")
        s.close()

if __name__ == "__main__":
    test_echo_service_user()