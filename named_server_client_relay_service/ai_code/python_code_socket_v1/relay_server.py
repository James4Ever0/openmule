import socket
import threading

class TCPRelay:
    def __init__(self, relay_host, relay_port, auth_required=False):
        self.relay_host = relay_host
        self.relay_port = relay_port
        self.auth_required = auth_required
        # Stores active connections: {client_socket: server_socket}
        self.connections = {}
        self.services = {}
        # Simple user credentials storage
        self.users = {"testuser": "testpass"}
        self.running = False
        
    def get_connection_stats(self):
        stats = {}
        for client_sock, server_sock in self.connections.items():
            stats[client_sock.getpeername()] = {
                'service': getattr(client_sock, 'service_name', 'Unknown'),
                'paired': server_sock is not None,
                'connected_since': getattr(client_sock, 'connect_time', 'Unknown')
            }
        return stats

    def start_relay(self):
        """Start the main relay server"""
        self.relay_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.relay_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.relay_socket.bind((self.relay_host, self.relay_port))
        self.relay_socket.listen(5)
        self.running = True
        
        print(f"TCP Relay started on {self.relay_host}:{self.relay_port}")
        
        while self.running:
            try:
                client_socket, client_addr = self.relay_socket.accept()
                print(f"New connection from {client_addr}")
                
                # Handle each client in a separate thread
                client_thread = threading.Thread(
                    target=self.handle_client, 
                    args=(client_socket,)
                )
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}")

    def handle_client(self, client_socket):
        """Handle authentication and connection setup for a client"""
        try:
            # Simple authentication protocol
            if self.auth_required:
                auth_data = client_socket.recv(1024).decode().strip()
                username, password = auth_data.split(":", 1)
                
                if not self.authenticate(username, password):
                    client_socket.send(b"AUTH_FAILED")
                    client_socket.close()
                    return
                else:
                    client_socket.send(b"AUTH_SUCCESS")
            
            # Client specifies target service
            service_info = client_socket.recv(1024).decode().strip()
            
            if service_info.startswith("PROVIDE:"):
                # This client is providing a service
                service_name = service_info.split(":", 1)[1]
                self.register_service_provider(service_name, client_socket)
                
            elif service_info.startswith("CONNECT:"):
                # This client wants to use a service
                service_name = service_info.split(":", 1)[1]
                self.connect_to_service(service_name, client_socket)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error handling client: {e}")
            client_socket.close()

    def authenticate(self, username, password):
        """Simple username/password authentication"""
        return self.users.get(username) == password

    def register_service_provider(self, service_name, provider_socket):
        """Register a service provider"""
        if service_name in self.services:
            provider_socket.send(b"SERVICE_ALREADY_REGISTERED")
            provider_socket.close()
            return
        print(f"Service '{service_name}' registered")
        self.connections[provider_socket] = None
        # Store service mapping (in real implementation, use proper data structure)
        # cannot do setattr here
        self.services[service_name] = provider_socket
        # so closing provider socket is possible

    def connect_to_service(self, service_name, client_socket):
        """Connect client to a service provider"""
        # Find service provider (simplified - in real implementation needs proper lookup)
        for key_service_name, value_provider_socket in self.services.items():
            if service_name == key_service_name:
                provider_socket = value_provider_socket
                # Pair the client with the service provider
                self.connections[provider_socket] = client_socket
                self.connections[client_socket] = provider_socket
                
                print(f"Connected client to service '{service_name}'")
                
                # Start bidirectional relay
                self.start_bidirectional_relay(provider_socket, client_socket)
                return
        
        # Service not found
        client_socket.send(b"SERVICE_NOT_FOUND")
        client_socket.close()

    def start_bidirectional_relay(self, socket_a, socket_b):
        """Start relaying data between two sockets using threads"""
        def relay_data(from_socket, to_socket, banner:str):
            print("starting relay_data", banner)
            try:
                while self.running: # guess it is simply "not data"
                    print("Waiting for data...", banner) # still waiting for provider to send data, which is blocking
                    # but we have terminated the relay server, so it should break out of this loop
                    # and close the sockets
                    # or we can tell the difference between client disconnection and server provider disconnection
                    # as well as relay server termination
                    # can we force the client to close the socket?
                    data = from_socket.recv(4096)
                    if not data:
                        break
                    print(f"Relaying {len(data)} bytes", banner)
                    to_socket.sendall(data)
            except:
                # what is the exception when client breaks?
                # do we need to log it?
                import traceback
                traceback.print_exc()
                pass
            finally:
                print("Ending relay_data", banner)
                # Clean up when connection breaks
                self.close_connection_pair(socket_a, socket_b)

        # Start threads for both directions
        thread_a = threading.Thread(target=relay_data, args=(socket_a, socket_b, "socket_a to socket_b"))
        thread_b = threading.Thread(target=relay_data, args=(socket_b, socket_a, "socket_b to socket_a"))
        
        thread_a.daemon = True
        thread_b.daemon = True
        
        thread_a.start()
        thread_b.start()

    def close_connection_pair(self, socket_a:socket.socket, socket_b:socket.socket): # only one thread will call this, another thread seems to be blocked at recv()
        """Clean up both ends of a connection pair"""
        print("Tried to close connection pair", socket_a, socket_b)
        for sock in [socket_a, socket_b]:
            for key_service_name, value_provider_socket in self.services.items():
                if value_provider_socket == sock:
                    del self.services[key_service_name]
                    break
            if sock in self.connections:
                del self.connections[sock]
            try:
                print("Closing socket:", sock)
                # sock.close()
                sock.shutdown(socket.SHUT_RDWR) # now we are talking...
            except:
                # import traceback
                # traceback.print_exc()
                pass
            try:
                sock.close()
            except:
                pass

    def stop(self):
        """Stop the relay server"""
        self.running = False
        self.relay_socket.close()

if __name__ == "__main__":
    # Start relay on localhost port 8888
    relay = TCPRelay("0.0.0.0", 8888, auth_required=True)
    try:
        relay.start_relay()
    except KeyboardInterrupt:
        relay.stop()
        print("Relay stopped")