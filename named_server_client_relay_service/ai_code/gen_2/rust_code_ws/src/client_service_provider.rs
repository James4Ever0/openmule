use tokio::net::TcpStream;
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message};
use futures_util::{SinkExt, StreamExt};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use log::{info, error};
use crate::utils;

#[tokio::main]
async fn main() {
    utils::init_logger();
    let relay_host = "localhost";
    let relay_port = 8888;
    let service_name = "vnc_service_a";
    let target_host = "localhost";
    let target_port = 5950;

    loop {
        info!("Connecting to relay server...");
        if let Err(e) = start_service_provider(
            relay_host, 
            relay_port, 
            service_name, 
            target_host, 
            target_port
        ).await {
            error!("Error: {}", e);
        }
        info!("Disconnected, reconnecting...");
        tokio::time::sleep(std::time::Duration::from_secs(1)).await;
    }
}

async fn start_service_provider(
    relay_host: &str,
    relay_port: u16,
    service_name: &str,
    target_host: &str,
    target_port: u16,
) -> Result<(), Box<dyn std::error::Error>> {
    let relay_addr = format!("ws://{}:{}", relay_host, relay_port);
    let (ws_stream, _) = connect_async(relay_addr).await?;
    let (mut ws_sender, mut ws_receiver) = ws_stream.split();
    
    // Register service
    ws_sender.send(Message::Text(format!("REGISTER:{}", service_name))).await?;
    info!("Registered service '{}'", service_name);
    
    // Wait for client connection
    if let Some(Ok(Message::Text(text))) = ws_receiver.next().await {
        if text == "CONNECT" {
            info!("Connecting to target server...");
            let mut target_stream = TcpStream::connect(format!("{}:{}", target_host, target_port)).await?;
            
            let (mut target_reader, mut target_writer) = target_stream.split();
            let (mut ws_sender, mut ws_receiver) = ws_sender.reunite(ws_receiver)?.split();
            
            let target_to_ws = async {
                let mut buf = [0u8; 4096];
                loop {
                    match target_reader.read(&mut buf).await {
                        Ok(0) => break, // EOF
                        Ok(n) => {
                            if ws_sender.send(Message::Binary(buf[..n].to_vec())).await.is_err() {
                                break;
                            }
                        }
                        Err(_) => break,
                    }
                }
            };
            
            let ws_to_target = async {
                while let Some(Ok(msg)) = ws_receiver.next().await {
                    if let Message::Binary(data) = msg {
                        if target_writer.write_all(&data).await.is_err() {
                            break;
                        }
                    }
                }
            };
            
            tokio::select! {
                _ = target_to_ws => {},
                _ = ws_to_target => {},
            }
        }
    }
    
    Ok(())
}

