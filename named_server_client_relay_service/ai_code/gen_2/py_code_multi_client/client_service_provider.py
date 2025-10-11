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
