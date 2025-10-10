import socket
import threading
# import sys
from utils import timed_print, pipe_thread

# it is hard to say if the ai has improved, but the code is different, and we may want to try before changing the code manually

# the relay server need to either buffer the data from the service provider or only invoke connection when the client connects.
# record connection ids to enable multi connections.
# otherwise we cannot ensure vnc connection established after the client connects to the relay server.

class RelayServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        # Dictionary to map service names to provider sockets
        self.service_registry = {}
        self.lock = threading.Lock()

    def start(self):
        """Start the relay server to listen for connections"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(10)
        timed_print(f"Relay server listening on {self.host}:{self.port}")

        try:
            while True:
                client_sock, client_addr = self.sock.accept()
                timed_print(f"New connection from {client_addr}")
                # Handle each connection in a new thread
                client_thread = threading.Thread(target=self.handle_connection, args=(client_sock,))
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            timed_print("Server is shutting down.")
        finally:
            self.sock.close()

    def handle_connection(self, sock):
        """Handle initial communication to identify service provider or client"""
        try:
            # Initial identification message
            ident_data = sock.recv(1024).decode('utf-8').strip()
            timed_print(f"Received identification: {ident_data}")

            if ident_data.startswith("REGISTER:"):
                # This is a service provider registering a service
                service_name = ident_data.split(":")[1]
                self.register_service(service_name, sock)
            elif ident_data.startswith("REQUEST:"):
                # This is a client requesting a service
                service_name = ident_data.split(":")[1]
                self.handle_client_request(service_name, sock)
            else:
                timed_print(f"Unknown protocol message: {ident_data}")
                sock.close()
        except Exception as e:
            timed_print(f"Error handling connection: {e}")
            sock.close()

    def register_service(self, service_name:str, provider_sock:socket.socket):
        """Register a service provider in the registry"""
        with self.lock:
            if service_name in self.service_registry:
                timed_print(f"Service '{service_name}' is already registered. Closing old connection.")
                old_sock = self.service_registry[service_name]
                try:
                    old_sock.shutdown(socket.SHUT_RDWR)
                    old_sock.close()
                except: pass
            self.service_registry[service_name] = provider_sock
            timed_print(f"Service '{service_name}' registered successfully.")

    def unregister_service(self, service_name, provider_sock):
        """Remove a service from the registry when the provider disconnects"""
        with self.lock:
            if service_name in self.service_registry and self.service_registry[service_name] is provider_sock:
                try:
                    provider_sock.shutdown(socket.SHUT_RDWR)
                    provider_sock.close()
                except: pass
                del self.service_registry[service_name]
                timed_print(f"Service '{service_name}' unregistered.")

    def handle_client_request(self, service_name, client_sock):
        """Handle a client request by connecting it to the registered service provider"""
        with self.lock:
            provider_sock = self.service_registry.get(service_name)

        if provider_sock is None:
            timed_print(f"Client requested unknown service: {service_name}")
            client_sock.sendall(b"ERROR:Service not found")
            client_sock.close()
            return

        timed_print(f"Connecting client to service '{service_name}'")
        client_sock.sendall(b"OK")
        # Create the bidirectional pipe between client and service provider
        threads = self.create_bidirectional_pipe(client_sock, provider_sock)
        for t in threads:
            t.join()
        timed_print(f"Client disconnected from service '{service_name}'")
        self.unregister_service(service_name, provider_sock)

    def create_bidirectional_pipe(self, sock1, sock2):
        """Create two threads to relay data bidirectionally between two sockets"""

        # Start threads for both directions
        thread1 = threading.Thread(target=pipe_thread, args=(sock1, sock2, "sock1_sock2"))
        thread2 = threading.Thread(target=pipe_thread, args=(sock2, sock1, "sock2_sock1"))
        thread1.daemon = True
        thread2.daemon = True
        thread1.start()
        thread2.start()
        threads = [thread1, thread2]
        return threads

if __name__ == "__main__":
    relay = RelayServer('0.0.0.0', 8888)
    relay.start()