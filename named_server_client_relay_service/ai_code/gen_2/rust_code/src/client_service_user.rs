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
