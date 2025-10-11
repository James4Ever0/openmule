use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use tokio::net::TcpListener;
use tokio_tungstenite::tungstenite::protocol::Message;
use futures_util::{SinkExt, StreamExt};
use log::{info, error};
use crate::utils;

type WsStream = tokio_tungstenite::WebSocketStream<tokio::net::TcpStream>;
type Registry = Arc<Mutex<HashMap<String, WsStream>>>;

pub struct RelayServer {
    registry: Registry,
}

impl RelayServer {
    pub fn new() -> Self {
        RelayServer {
            registry: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub async fn start(&self, addr: &str) {
        let listener = TcpListener::bind(addr).await.unwrap();
        info!("Relay server listening on {}", addr);
        
        while let Ok((stream, _)) = listener.accept().await {
            let ws_stream = match tokio_tungstenite::accept_async(stream).await {
                Ok(ws) => ws,
                Err(e) => {
                    error!("WebSocket handshake failed: {}", e);
                    continue;
                }
            };
            
            let registry = self.registry.clone();
            tokio::spawn(Self::handle_connection(ws_stream, registry));
        }
    }

    async fn handle_connection(mut ws_stream: WsStream, registry: Registry) {
        let (mut ws_sender, mut ws_receiver) = ws_stream.split();
        
        if let Some(Ok(first_msg)) = ws_receiver.next().await {
            if let Message::Text(text) = first_msg {
                if text.starts_with("REGISTER:") {
                    let service_name = text.trim_start_matches("REGISTER:").to_string();
                    let mut reg = registry.lock().unwrap();
                    
                    // Close existing connection if present
                    if let Some(old_ws) = reg.insert(service_name.clone(), ws_sender.reunite(ws_receiver).unwrap()) {
                        let _ = old_ws.close().await;
                        info!("Replaced existing service: {}", service_name);
                    } else {
                        info!("Registered new service: {}", service_name);
                    }
                    return;
                } else if text.starts_with("REQUEST:") {
                    let service_name = text.trim_start_matches("REQUEST:").to_string();
                    let provider = {
                        let mut reg = registry.lock().unwrap();
                        reg.remove(&service_name)
                    };
                    
                    match provider {
                        Some(provider) => {
                            if ws_sender.send(Message::Text("OK".to_string())).await.is_err() {
                                error!("Failed to send OK to client");
                                return;
                            }
                            
                            let (mut client_sender, mut client_receiver) = ws_sender.split();
                            let (mut provider_sender, mut provider_receiver) = provider.split();
                            
                            let client_to_provider = async {
                                while let Some(Ok(msg)) = client_receiver.next().await {
                                    if provider_sender.send(msg).await.is_err() {
                                        break;
                                    }
                                }
                            };
                            
                            let provider_to_client = async {
                                while let Some(Ok(msg)) = provider_receiver.next().await {
                                    if client_sender.send(msg).await.is_err() {
                                        break;
                                    }
                                }
                            };
                            
                            tokio::select! {
                                _ = client_to_provider => {},
                                _ = provider_to_client => {},
                            }
                            
                            info!("Connection closed for service: {}", service_name);
                        }
                        None => {
                            let _ = ws_sender.send(Message::Text("ERROR:Service not found".to_string())).await;
                        }
                    }
                }
            }
        }
    }
}

#[tokio::main]
async fn main() {
    utils::init_logger();
    let relay = RelayServer::new();
    relay.start("0.0.0.0:8888").await;
}
