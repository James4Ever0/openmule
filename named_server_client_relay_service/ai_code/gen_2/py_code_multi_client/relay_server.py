import socket
import threading
import uuid
from utils import timed_print, pipe_thread

class RelayServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        # Dictionary to map service names to provider sockets
        self.service_registry = {}
        # Dictionary to track active connections by connection_id
        self.active_connections = {}
        self.lock = threading.Lock()

    def start(self):
        """Start the relay server to listen for connections"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(10)
        timed_print(f"Relay server listening on {self.host}:{self.port}")

        try:
            while True:
                client_sock, client_addr = self.sock.accept()
                timed_print(f"New connection from {client_addr}")
                # Handle each connection in a new thread
                client_thread = threading.Thread(target=self.handle_connection, args=(client_sock, client_addr))
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            timed_print("Server is shutting down.")
        finally:
            self.sock.close()

    def handle_connection(self, sock, addr):
        """Handle initial communication to identify service provider or client"""
        try:
            # Initial identification message
            ident_data = sock.recv(1024).decode('utf-8').strip()
            timed_print(f"Received identification from {addr}: {ident_data}")

            if ident_data.startswith("REGISTER:"):
                # This is a service provider registering a service
                service_name = ident_data.split(":")[1]
                self.register_service(service_name, sock, addr)
            elif ident_data.startswith("REQUEST:"):
                # This is a client requesting a service
                parts = ident_data.split(":")
                service_name = parts[1]
                connection_id = parts[2] if len(parts) > 2 else str(uuid.uuid4())
                self.handle_client_request(service_name, connection_id, sock, addr)
            else:
                timed_print(f"Unknown protocol message from {addr}: {ident_data}")
                sock.close()
        except Exception as e:
            timed_print(f"Error handling connection from {addr}: {e}")
            sock.close()

    def register_service(self, service_name: str, provider_sock: socket.socket, addr):
        """Register a service provider in the registry"""
        with self.lock:
            if service_name in self.service_registry:
                timed_print(f"Service '{service_name}' is already registered. Closing old connection.")
                old_sock = self.service_registry[service_name]
                try:
                    old_sock.shutdown(socket.SHUT_RDWR)
                    old_sock.close()
                except: 
                    pass
            self.service_registry[service_name] = provider_sock
            timed_print(f"Service '{service_name}' registered successfully from {addr}.")

        # Keep the provider connection alive and handle multiple clients
        threading.Thread(target=self.handle_provider_connection, 
                         args=(service_name, provider_sock, addr), 
                         daemon=True).start()

    def handle_provider_connection(self, service_name, provider_sock, addr):
        """Handle the provider connection and wait for client connections"""
        try:
            while True:
                # Wait for provider to be ready for new connection
                ready_msg = provider_sock.recv(1024).decode('utf-8').strip()
                if not ready_msg:
                    break
                    
                if ready_msg == "READY":
                    timed_print(f"Provider for '{service_name}' is ready for new client")
                    
                    # Check if there are pending client connections for this service
                    with self.lock:
                        pending_clients = [conn_id for conn_id, conn_info in self.active_connections.items() 
                                         if conn_info.get('service_name') == service_name and conn_info.get('status') == 'pending']
                    
                    if pending_clients:
                        connection_id = pending_clients[0]
                        with self.lock:
                            client_sock = self.active_connections[connection_id]['client_sock']
                            self.active_connections[connection_id]['status'] = 'connecting'
                        
                        # Notify provider about the connection
                        provider_sock.sendall(f"CONNECT:{connection_id}".encode())
                        
                        # Create bidirectional pipe
                        self.create_bidirectional_pipe(connection_id, client_sock, provider_sock)
                    else:
                        provider_sock.sendall(b"WAIT")
                else:
                    timed_print(f"Unexpected message from provider: {ready_msg}")
        except Exception as e:
            timed_print(f"Error handling provider connection for '{service_name}': {e}")
        finally:
            self.unregister_service(service_name, provider_sock)

    def unregister_service(self, service_name, provider_sock):
        """Remove a service from the registry when the provider disconnects"""
        with self.lock:
            if service_name in self.service_registry and self.service_registry[service_name] is provider_sock:
                try:
                    provider_sock.shutdown(socket.SHUT_RDWR)
                    provider_sock.close()
                except: 
                    pass
                del self.service_registry[service_name]
                timed_print(f"Service '{service_name}' unregistered.")
                
                # Clean up pending connections for this service
                for conn_id, conn_info in list(self.active_connections.items()):
                    if conn_info.get('service_name') == service_name and conn_info.get('status') == 'pending':
                        try:
                            conn_info['client_sock'].sendall(b"ERROR:Service unavailable")
                            conn_info['client_sock'].close()
                        except:
                            pass
                        del self.active_connections[conn_id]

    def handle_client_request(self, service_name, connection_id, client_sock, addr):
        """Handle a client request by connecting it to the registered service provider"""
        with self.lock:
            provider_sock = self.service_registry.get(service_name)

        if provider_sock is None:
            timed_print(f"Client requested unknown service: {service_name}")
            client_sock.sendall(b"ERROR:Service not found")
            client_sock.close()
            return

        # Store the client connection
        with self.lock:
            self.active_connections[connection_id] = {
                'client_sock': client_sock,
                'service_name': service_name,
                'status': 'pending',
                'client_addr': addr
            }

        timed_print(f"Client connection {connection_id} queued for service '{service_name}'")
        client_sock.sendall(f"OK:{connection_id}".encode())

    def create_bidirectional_pipe(self, connection_id, client_sock, provider_sock):
        """Create two threads to relay data bidirectionally between two sockets"""
        timed_print(f"Starting bidirectional pipe for connection {connection_id}")

        # Update connection status
        with self.lock:
            if connection_id in self.active_connections:
                self.active_connections[connection_id]['status'] = 'active'

        # Start threads for both directions
        thread1 = threading.Thread(target=pipe_thread, 
                                 args=(client_sock, provider_sock, f"client_{connection_id}_provider"))
        thread2 = threading.Thread(target=pipe_thread, 
                                 args=(provider_sock, client_sock, f"provider_{connection_id}_client"))
        thread1.daemon = True
        thread2.daemon = True
        thread1.start()
        thread2.start()

        # Monitor threads and clean up when done
        def monitor_connection():
            thread1.join()
            thread2.join()
            with self.lock:
                if connection_id in self.active_connections:
                    del self.active_connections[connection_id]
            timed_print(f"Connection {connection_id} closed")

        monitor_thread = threading.Thread(target=monitor_connection, daemon=True)
        monitor_thread.start()

if __name__ == "__main__":
    relay = RelayServer('0.0.0.0', 8888)
    relay.start()
