import socket
import threading

def start_service_provider(relay_host, relay_port, service_name, target_host='localhost', target_port=5900):
    # Connect to the relay server
    relay_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    relay_sock.connect((relay_host, relay_port))
    
    # Register as a service provider
    registration_msg = f"REGISTER:{service_name}"
    relay_sock.send(registration_msg.encode('utf-8'))
    print(f"Registered service '{service_name}' with relay")

    # This socket now acts as a bridge to the relay
    # In a more advanced version, you could automatically connect to the local service (e.g., localhost:5900)
    # and pipe data between `relay_sock` and the local service socket.
    return relay_sock

if __name__ == "__main__":
    # Example: Register "vnc_service_a" for the VNC server on this machine
    start_service_provider('localhost', 8888, 'vnc_service_a')
    # Keep the thread alive
    threading.Event().wait()