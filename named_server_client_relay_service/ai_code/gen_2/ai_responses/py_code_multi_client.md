I'll rewrite your code to support multiple clients with connection IDs. Here's the multi-client version:

relay_server.py
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


client_service_provider.py
import socket
import threading
import uuid
from utils import timed_print, pipe_thread

def start_service_provider(
    relay_host: str,
    relay_port: int,
    service_name: str,
    target_host: str,
    target_port: int,
    max_clients: int = 10
):
    """Start a service provider that can handle multiple clients"""
    
    def handle_client_connection(connection_id, relay_sock):
        """Handle a single client connection"""
        try:
            # Connect to the target service
            service_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            service_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            service_sock.connect((target_host, target_port))
            
            timed_print(f"Connection {connection_id}: Connected to target service")
            
            # Create bidirectional pipe between relay and target service
            thread1 = threading.Thread(
                target=pipe_thread, 
                args=(relay_sock, service_sock, f"relay_{connection_id}_service"), 
                daemon=True
            )
            thread2 = threading.Thread(
                target=pipe_thread, 
                args=(service_sock, relay_sock, f"service_{connection_id}_relay"), 
                daemon=True
            )

            thread1.start()
            thread2.start()
            
            # Wait for both threads to complete
            thread1.join()
            thread2.join()
            
            timed_print(f"Connection {connection_id}: Disconnected")
            
        except Exception as e:
            timed_print(f"Connection {connection_id}: Error handling client: {e}")
        finally:
            try:
                service_sock.close()
            except:
                pass
            try:
                relay_sock.close()
            except:
                pass

    def provider_main():
        """Main provider loop"""
        while True:
            try:
                # Connect to the relay server
                relay_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                relay_sock.connect((relay_host, relay_port))

                # Register as a service provider
                registration_msg = f"REGISTER:{service_name}"
                relay_sock.sendall(registration_msg.encode("utf-8"))
                timed_print(f"Registered service '{service_name}' with relay")

                # Handle multiple client connections
                client_count = 0
                while client_count < max_clients:
                    try:
                        # Notify relay we're ready for a client
                        relay_sock.sendall(b"READY")
                        
                        # Wait for response from relay
                        response = relay_sock.recv(1024).decode('utf-8').strip()
                        
                        if response == "WAIT":
                            continue
                        elif response.startswith("CONNECT:"):
                            connection_id = response.split(":")[1]
                            timed_print(f"New client connection: {connection_id}")
                            
                            # Handle this client in a separate thread
                            client_thread = threading.Thread(
                                target=handle_client_connection,
                                args=(connection_id, relay_sock),
                                daemon=True
                            )
                            client_thread.start()
                            client_count += 1
                        else:
                            timed_print(f"Unexpected response from relay: {response}")
                            break
                            
                    except Exception as e:
                        timed_print(f"Error in provider main loop: {e}")
                        break
                        
                timed_print("Provider reached maximum client limit or encountered error. Reconnecting...")
                
            except Exception as e:
                timed_print(f"Provider connection error: {e}")
                
            # Wait before reconnecting
            import time
            time.sleep(5)

    # Start the provider
    provider_thread = threading.Thread(target=provider_main, daemon=True)
    provider_thread.start()
    provider_thread.join()

if __name__ == "__main__":
    # Example: start a service provider for VNC service
    start_service_provider(
        relay_host="localhost", 
        relay_port=8888, 
        service_name="vnc_service_a", 
        target_host="localhost", 
        target_port=5950,
        max_clients=5
    )


client_service_user.py
import socket
import threading
import uuid
from utils import timed_print, pipe_thread

def connect_to_relay(relay_host, relay_port, service_name, connection_id=None):
    """Connect to relay and request service"""
    if connection_id is None:
        connection_id = str(uuid.uuid4())
        
    # Connect to the relay server
    relay_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    relay_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    relay_sock.connect((relay_host, relay_port))

    # Request the service by name with connection ID
    request_msg = f"REQUEST:{service_name}:{connection_id}"
    relay_sock.sendall(request_msg.encode("utf-8"))

    # Check for initial response
    initial_response = relay_sock.recv(1024).decode('utf-8')
    if initial_response.startswith("ERROR"):
        timed_print(f"Failed to connect to service: {initial_response}")
        relay_sock.close()
        return None, None
    if initial_response.startswith("OK:"):
        received_conn_id = initial_response.split(":")[1]
        timed_print(f"Connected to service '{service_name}' via relay, Connection ID: {received_conn_id}")
        return relay_sock, received_conn_id
    else:
        timed_print(f"Unexpected response from relay: {initial_response}")
        relay_sock.close()
        return None, None

def start_client(relay_host, relay_port, service_name, local_port, max_connections=10):
    """Start a client that accepts multiple local connections and forwards to relay"""
    
    def handle_local_client(client_sock, addr, connection_id):
        """Handle a single local client connection"""
        try:
            # Connect to relay service
            relay_sock, conn_id = connect_to_relay(relay_host, relay_port, service_name, connection_id)
            if relay_sock is None:
                client_sock.close()
                return
                
            timed_print(f"Connection {conn_id}: Local client {addr} connected")
            
            # Create bidirectional pipe between local client and relay
            thread1 = threading.Thread(
                target=pipe_thread, 
                args=(client_sock, relay_sock, f"client_{conn_id}_relay"), 
                daemon=True
            )
            thread2 = threading.Thread(
                target=pipe_thread, 
                args=(relay_sock, client_sock, f"relay_{conn_id}_client"), 
                daemon=True
            )
            
            thread1.start()
            thread2.start()
            
            # Wait for threads to complete
            thread1.join()
            thread2.join()
            
            timed_print(f"Connection {conn_id}: Local client {addr} disconnected")
            
        except Exception as e:
            timed_print(f"Connection {connection_id}: Error handling local client: {e}")
        finally:
            try:
                client_sock.close()
            except:
                pass
            try:
                if 'relay_sock' in locals():
                    relay_sock.close()
            except:
                pass

    # Start local server to accept multiple connections
    local_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        local_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        local_sock.bind(("localhost", local_port))
        local_sock.listen(max_connections)
        timed_print(f"Local forwarder listening on localhost:{local_port}, max connections: {max_connections}")

        connection_counter = 0
        
        while True:
            client_sock, addr = local_sock.accept()
            connection_id = f"local_conn_{connection_counter}"
            connection_counter += 1
            
            timed_print(f"New local connection from {addr}, assigning ID: {connection_id}")
            
            # Handle each local connection in a separate thread
            client_thread = threading.Thread(
                target=handle_local_client,
                args=(client_sock, addr, connection_id),
                daemon=True
            )
            client_thread.start()
            
    except Exception as e:
        timed_print(f"Local server error: {e}")
    finally:
        local_sock.close()

if __name__ == "__main__":
    # Start client that accepts multiple connections on local port 15900
    start_client("localhost", 8888, "vnc_service_a", 15900, max_connections=5)


utils.py
import time
import socket

def pipe_thread(source: socket.socket, destination: socket.socket, name: str):
    """Thread function to pipe data between two sockets with connection tracking"""
    timed_print(f"Starting pipe thread: {name}")
    try:
        while True:
            data = source.recv(4096)
            if not data:
                break
            destination.sendall(data)
    except Exception as e:
        timed_print(f"Pipe thread {name} error: {e}")
    finally:
        try:
            source.shutdown(socket.SHUT_RDWR)
        except:
            pass
        try:
            source.close()
        except:
            pass
        timed_print(f"Pipe thread {name} finished")

def timed_print(*args, **kwargs):
    """Print with timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}]", *args, **kwargs)


Key Changes Made:

1. Connection ID Support: Each connection now has a unique ID for tracking
2. Multi-client Architecture: 
   • Relay server maintains multiple concurrent connections

   • Service provider can handle multiple clients simultaneously

   • Client service user accepts multiple local connections

3. Improved Protocol:
   • Enhanced message format with connection IDs

   • Better error handling and status tracking

4. Thread Management: Each client connection runs in its own thread
5. Connection Tracking: Active connections are tracked by ID for better management
6. Resource Management: Proper cleanup of sockets and threads

Usage:

1. Start the relay server: python relay_server.py
2. Start the service provider: python client_service_provider.py
3. Start the client service user: python client_service_user.py
4. Connect multiple clients to the local port (15900 in the example)

The system now supports multiple concurrent connections with proper connection tracking and management.