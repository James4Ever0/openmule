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