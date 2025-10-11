I'll rewrite the Python socket relay system in Rust using Tokio. Here's the implementation:

utils.rs:
use std::time::SystemTime;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;

pub fn timed_print(message: &str) {
    let now = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap()
        .as_secs();
    println!("[{}] {}", now, message);
}

pub async fn pipe(
    mut source: TcpStream,
    mut destination: TcpStream,
    label: &str,
) -> tokio::io::Result<()> {
    timed_print(&format!("Running pipe thread: {}", label));
    let (mut source_reader, mut source_writer) = source.split();
    let (mut dest_reader, mut dest_writer) = destination.split();

    let read_task = async move {
        let mut buf = [0; 4096];
        loop {
            timed_print(&format!("Receiving data at pipe thread {}", label));
            let n = match source_reader.read(&mut buf).await {
                Ok(n) if n == 0 => break,
                Ok(n) => n,
                Err(e) => {
                    timed_print(&format!("Pipe thread {} read error: {}", label, e));
                    break;
                }
            };
            timed_print(&format!(
                "Received {} bytes at pipe thread {}: {:x?}",
                n,
                label,
                &buf[..n.min(10)]
            ));
            timed_print(&format!("Sending data at pipe thread {}", label));
            if let Err(e) = dest_writer.write_all(&buf[..n]).await {
                timed_print(&format!("Pipe thread {} write error: {}", label, e));
                break;
            }
        }
        let _ = dest_writer.shutdown().await;
        Ok::<(), tokio::io::Error>(())
    };

    let write_task = async move {
        let mut buf = [0; 4096];
        loop {
            let n = match dest_reader.read(&mut buf).await {
                Ok(n) if n == 0 => break,
                Ok(n) => n,
                Err(e) => {
                    timed_print(&format!("Pipe thread {} read error: {}", label, e));
                    break;
                }
            };
            if let Err(e) = source_writer.write_all(&buf[..n]).await {
                timed_print(&format!("Pipe thread {} write error: {}", label, e));
                break;
            }
        }
        let _ = source_writer.shutdown().await;
        Ok::<(), tokio::io::Error>(())
    };

    tokio::select! {
        _ = read_task => {},
        _ = write_task => {},
    }

    timed_print(&format!("Pipe thread {} finished", label));
    Ok(())
}


relay_server.rs:
use std::collections::HashMap;
use std::sync::Arc;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::Mutex;
use crate::utils::{pipe, timed_print};

pub struct RelayServer {
    service_registry: Arc<Mutex<HashMap<String, TcpStream>>>,
}

impl RelayServer {
    pub fn new() -> Self {
        RelayServer {
            service_registry: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub async fn start(&self, host: &str, port: u16) -> tokio::io::Result<()> {
        let listener = TcpListener::bind(format!("{}:{}", host, port)).await?;
        timed_print(&format!("Relay server listening on {}:{}", host, port));

        loop {
            let (socket, addr) = listener.accept().await?;
            timed_print(&format!("New connection from {}", addr));
            let registry = self.service_registry.clone();
            tokio::spawn(async move {
                if let Err(e) = Self::handle_connection(socket, registry).await {
                    timed_print(&format!("Error handling connection: {}", e));
                }
            });
        }
    }

    async fn handle_connection(
        mut socket: TcpStream,
        registry: Arc<Mutex<HashMap<String, TcpStream>>>,
    ) -> tokio::io::Result<()> {
        let mut buf = [0; 1024];
        let n = socket.read(&mut buf).await?;
        if n == 0 {
            return Ok(());
        }

        let ident_data = String::from_utf8_lossy(&buf[..n]).trim().to_string();
        timed_print(&format!("Received identification: {}", ident_data));

        if ident_data.starts_with("REGISTER:") {
            let service_name = ident_data.split(':').nth(1).unwrap().to_string();
            Self::register_service(service_name, socket, registry).await?;
        } else if ident_data.starts_with("REQUEST:") {
            let service_name = ident_data.split(':').nth(1).unwrap().to_string();
            Self::handle_client_request(service_name, socket, registry).await?;
        } else {
            timed_print("Unknown protocol message");
        }

        Ok(())
    }

    async fn register_service(
        service_name: String,
        provider_sock: TcpStream,
        registry: Arc<Mutex<HashMap<String, TcpStream>>>,
    ) -> tokio::io::Result<()> {
        let mut registry = registry.lock().await;
        if let Some(old_sock) = registry.insert(service_name.clone(), provider_sock) {
            timed_print(&format!(
                "Service '{}' is already registered. Closing old connection.",
                service_name
            ));
            let _ = old_sock.shutdown().await;
        } else {
            timed_print(&format!("Service '{}' registered successfully.", service_name));
        }
        Ok(())
    }

    async fn handle_client_request(
        service_name: String,
        mut client_sock: TcpStream,
        registry: Arc<Mutex<HashMap<String, TcpStream>>>,
    ) -> tokio::io::Result<()> {
        let provider_sock = {
            let mut registry = registry.lock().await;
            registry.remove(&service_name)
        };

        if provider_sock.is_none() {
            timed_print(&format!("Client requested unknown service: {}", service_name));
            client_sock.write_all(b"ERROR:Service not found").await?;
            return Ok(());
        }

        let provider_sock = provider_sock.unwrap();
        timed_print(&format!("Connecting client to service '{}'", service_name));
        client_sock.write_all(b"OK").await?;

        let client_clone = client_sock.try_clone()?;
        let provider_clone = provider_sock.try_clone()?;

        tokio::spawn(pipe(client_sock, provider_sock, "client_to_provider"));
        tokio::spawn(pipe(provider_clone, client_clone, "provider_to_client"));

        Ok(())
    }
}

#[tokio::main]
async fn main() -> tokio::io::Result<()> {
    let relay = RelayServer::new();
    relay.start("0.0.0.0", 8888).await
}


client_service_provider.rs:
use tokio::io::AsyncWriteExt;
use tokio::net::TcpStream;
use crate::utils::{pipe, timed_print};

async fn start_service_provider(
    relay_host: &str,
    relay_port: u16,
    service_name: &str,
    target_host: &str,
    target_port: u16,
) -> tokio::io::Result<()> {
    loop {
        timed_print("Connecting to relay server");
        let mut relay_sock = TcpStream::connect(format!("{}:{}", relay_host, relay_port)).await?;

        let registration_msg = format!("REGISTER:{}", service_name);
        relay_sock.write_all(registration_msg.as_bytes()).await?;
        timed_print(&format!("Registered service '{}' with relay", service_name));

        let mut connect_msg = [0; 1024];
        let n = relay_sock.read(&mut connect_msg).await?;
        timed_print(&format!("Received {} init bytes from relay", n));

        if connect_msg[..n] == b"CONNECT"[..] {
            timed_print("Relay is ready to connect");
            let mut service_sock = TcpStream::connect(format!("{}:{}", target_host, target_port)).await?;

            let relay_clone = relay_sock.try_clone()?;
            let service_clone = service_sock.try_clone()?;

            tokio::spawn(pipe(relay_sock, service_sock, "relay_service"));
            tokio::spawn(pipe(service_clone, relay_clone, "service_relay")).await?;
        } else {
            timed_print(&format!(
                "Client failed to connect to relay: {:x?}",
                &connect_msg[..n.min(20)]
            ));
        }

        timed_print("Client or relay disconnected. Reconnecting");
    }
}

#[tokio::main]
async fn main() -> tokio::io::Result<()> {
    start_service_provider("localhost", 8888, "vnc_service_a", "localhost", 5950).await
}


client_service_user.rs:
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};
use crate::utils::{pipe, timed_print};

async fn connect_to_relay(
    relay_host: &str,
    relay_port: u16,
    service_name: &str,
) -> tokio::io::Result<TcpStream> {
    let mut relay_sock = TcpStream::connect(format!("{}:{}", relay_host, relay_port)).await?;

    let request_msg = format!("REQUEST:{}", service_name);
    relay_sock.write_all(request_msg.as_bytes()).await?;

    let mut initial_response = [0; 1024];
    let n = relay_sock.read(&mut initial_response).await?;
    if n == 0 {
        return Err(tokio::io::Error::new(
            tokio::io::ErrorKind::ConnectionReset,
            "Connection closed by relay",
        ));
    }

    if initial_response.starts_with(b"ERROR") {
        return Err(tokio::io::Error::new(
            tokio::io::ErrorKind::Other,
            String::from_utf8_lossy(&initial_response[..n]),
        ));
    }

    if initial_response.starts_with(b"OK") {
        timed_print(&format!("Connected to service '{}' via relay", service_name));
    } else {
        return Err(tokio::io::Error::new(
            tokio::io::ErrorKind::InvalidData,
            format!(
                "Unexpected response from relay: {:x?}",
                &initial_response[..n.min(20)]
            ),
        ));
    }

    Ok(relay_sock)
}

async fn start_client(
    relay_host: &str,
    relay_port: u16,
    service_name: &str,
    local_port: u16,
) -> tokio::io::Result<()> {
    loop {
        let listener = TcpListener::bind(format!("127.0.0.1:{}", local_port)).await?;
        timed_print(&format!(
            "Local forwarder listening on 127.0.0.1:{}",
            local_port
        ));

        let (mut client_sock, addr) = listener.accept().await?;
        timed_print(&format!("Local client connected from {}", addr));

        let mut relay_sock = match connect_to_relay(relay_host, relay_port, service_name).await {
            Ok(sock) => sock,
            Err(e) => {
                timed_print(&format!("Failed to connect to relay: {}", e));
                let _ = client_sock.shutdown().await;
                continue;
            }
        };

        relay_sock.write_all(b"CONNECT").await?;

        let client_clone = client_sock.try_clone()?;
        let relay_clone = relay_sock.try_clone()?;

        tokio::spawn(pipe(client_sock, relay_sock, "client_relay"));
        tokio::spawn(pipe(relay_clone, client_clone, "relay_client")).await?;

        timed_print("Connection aborted. Retrying...");
    }
}

#[tokio::main]
async fn main() -> tokio::io::Result<()> {
    start_client("localhost", 8888, "vnc_service_a", 15900).await
}


This implementation:

1. Uses Tokio for asynchronous I/O operations
2. Maintains the same functionality as the Python version
3. Uses proper error handling and resource cleanup
4. Implements connection retrying logic
5. Includes detailed logging with timestamps
6. Uses proper concurrency control with Mutex for shared state
7. Handles socket splitting for bidirectional communication
8. Uses async/await syntax for readability

To use this system:

1. Run relay_server to start the relay
2. Run client_service_provider to register a service
3. Run client_service_user to create a local forwarder
4. Connect to the local forwarder port (15900 in the example)

The implementation handles:
• Service registration and discovery

• Connection forwarding

• Error handling and reconnection

• Concurrent connections using Tokio tasks

• Proper resource cleanup