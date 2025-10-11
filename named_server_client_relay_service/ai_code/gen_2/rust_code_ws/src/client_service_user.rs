
use tokio::net::{TcpListener, TcpStream};
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
    let local_port = 15900;

    loop {
        info!("Starting client service user...");
        if let Err(e) = start_client(relay_host, relay_port, service_name, local_port).await {
            error!("Error: {}", e);
        }
        info!("Disconnected, retrying...");
        tokio::time::sleep(std::time::Duration::from_secs(1)).await;
    }
}

async fn start_client(
    relay_host: &str,
    relay_port: u16,
    service_name: &str,
    local_port: u16,
) -> Result<(), Box<dyn std::error::Error>> {
    let listener = TcpListener::bind(format!("127.0.0.1:{}", local_port)).await?;
    info!("Listening on port {}", local_port);
    
    let (mut client_stream, _) = listener.accept().await?;
    info!("Local client connected");
    
    let relay_addr = format!("ws://{}:{}", relay_host, relay_port);
    let (ws_stream, _) = connect_async(relay_addr).await?;
    let (mut ws_sender, mut ws_receiver) = ws_stream.split();
    
    // Request service
    ws_sender.send(Message::Text(format!("REQUEST:{}", service_name))).await?;
    
    // Check response
    if let Some(Ok(Message::Text(text))) = ws_receiver.next().await {
        if text == "OK" {
            ws_sender.send(Message::Text("CONNECT".to_string())).await?;
            
            let (mut client_reader, mut client_writer) = client_stream.split();
            let (mut ws_sender, mut ws_receiver) = ws_sender.reunite(ws_receiver)?.split();
            
            let client_to_ws = async {
                let mut buf = [0u8; 4096];
                loop {
                    match client_reader.read(&mut buf).await {
                        Ok(0) => break,
                        Ok(n) => {
                            if ws_sender.send(Message::Binary(buf[..n].to_vec())).await.is_err() {
                                break;
                            }
                        }
                        Err(_) => break,
                    }
                }
            };
            
            let ws_to_client = async {
                while let Some(Ok(msg)) = ws_receiver.next().await {
                    if let Message::Binary(data) = msg {
                        if client_writer.write_all(&data).await.is_err() {
                            break;
                        }
                    }
                }
            };
            
            tokio::select! {
                _ = client_to_ws => {},
                _ = ws_to_client => {},
            }
        } else {
            error!("Service error: {}", text);
        }
    }
    
    Ok(())
}