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
