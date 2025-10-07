import socket
import threading
import sys
import time

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
        self.sock.bind((self.host, self.port))
        self.sock.listen(10)
        print(f"Relay server listening on {self.host}:{self.port}")

        try:
            while True:
                client_sock, client_addr = self.sock.accept()
                print(f"New connection from {client_addr}")
                # Handle each connection in a new thread
                client_thread = threading.Thread(target=self.handle_connection, args=(client_sock,))
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            print("Server is shutting down.")
        finally:
            self.sock.close()

    def handle_connection(self, sock):
        """Handle initial communication to identify service provider or client"""
        try:
            # Initial identification message
            ident_data = sock.recv(1024).decode('utf-8').strip()
            print(f"Received identification: {ident_data}")

            if ident_data.startswith("REGISTER:"):
                # This is a service provider registering a service
                service_name = ident_data.split(":")[1]
                self.register_service(service_name, sock)
            elif ident_data.startswith("REQUEST:"):
                # This is a client requesting a service
                service_name = ident_data.split(":")[1]
                self.handle_client_request(service_name, sock)
            else:
                print(f"Unknown protocol message: {ident_data}")
                sock.close()
        except Exception as e:
            print(f"Error handling connection: {e}")
            sock.close()

    def register_service(self, service_name, provider_sock):
        """Register a service provider in the registry"""
        with self.lock:
            if service_name in self.service_registry:
                print(f"Service '{service_name}' is already registered. Closing old connection.")
                old_sock = self.service_registry[service_name]
                old_sock.close()
            self.service_registry[service_name] = provider_sock
            print(f"Service '{service_name}' registered successfully.")

        # Keep the connection open and monitor for closure
        try:
            while True:
                # If recv returns empty data, the connection is closed
                if not provider_sock.recv(1024):
                    break
        except:
            pass
        finally:
            self.unregister_service(service_name, provider_sock)

    def unregister_service(self, service_name, provider_sock):
        """Remove a service from the registry when the provider disconnects"""
        with self.lock:
            if service_name in self.service_registry and self.service_registry[service_name] is provider_sock:
                del self.service_registry[service_name]
                print(f"Service '{service_name}' unregistered.")

    def handle_client_request(self, service_name, client_sock):
        """Handle a client request by connecting it to the registered service provider"""
        with self.lock:
            provider_sock = self.service_registry.get(service_name)

        if provider_sock is None:
            print(f"Client requested unknown service: {service_name}")
            client_sock.send(b"ERROR:Service not found")
            client_sock.close()
            return

        print(f"Connecting client to service '{service_name}'")
        # Create the bidirectional pipe between client and service provider
        self.create_bidirectional_pipe(client_sock, provider_sock)

    def create_bidirectional_pipe(self, sock1, sock2):
        """Create two threads to relay data bidirectionally between two sockets:cite[2]:cite[10]"""
        def pipe_thread(source, destination):
            try:
                while True:
                    data = source.recv(4096)
                    if not data:
                        break
                    destination.sendall(data)
            except Exception as e:
                print(f"Pipe thread error: {e}")
            finally:
                source.close()
                destination.close()

        # Start threads for both directions
        thread1 = threading.Thread(target=pipe_thread, args=(sock1, sock2))
        thread2 = threading.Thread(target=pipe_thread, args=(sock2, sock1))
        thread1.daemon = True
        thread2.daemon = True
        thread1.start()
        thread2.start()

if __name__ == "__main__":
    relay = RelayServer('0.0.0.0', 8888)
    relay.start()