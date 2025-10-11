package main

import (
	"log"
	"net"
	"time"

	"github.com/gorilla/websocket"
)

func pipeWebSocketToTCP(ws *websocket.Conn, tcp net.Conn) {
	defer ws.Close()
	defer tcp.Close()
	
	for {
		_, data, err := ws.ReadMessage()
		if err != nil {
			break
		}
		tcp.Write(data)
	}
}

func pipeTCPToWebSocket(tcp net.Conn, ws *websocket.Conn) {
	defer ws.Close()
	defer tcp.Close()
	
	buffer := make([]byte, 4096)
	for {
		n, err := tcp.Read(buffer)
		if err != nil {
			break
		}
		ws.WriteMessage(websocket.BinaryMessage, buffer[:n])
	}
}

func main() {
	relayURL := "ws://localhost:8888"
	serviceName := "vnc_service_a"
	targetAddr := "localhost:5950"

	for {
		log.Println("Connecting to relay server...")
		ws, _, err := websocket.DefaultDialer.Dial(relayURL, nil)
		if err != nil {
			log.Printf("Dial error: %v. Retrying in 5s", err)
			time.Sleep(5 * time.Second)
			continue
		}

		err = ws.WriteMessage(websocket.TextMessage, []byte("REGISTER:"+serviceName))
		if err != nil {
			log.Printf("Register error: %v", err)
			ws.Close()
			time.Sleep(5 * time.Second)
			continue
		}

		log.Println("Connecting to target service...")
		tcp, err := net.Dial("tcp", targetAddr)
		if err != nil {
			log.Printf("Target connection error: %v", err)
			ws.Close()
			time.Sleep(5 * time.Second)
			continue
		}

		log.Println("Starting bridge...")
		go pipeWebSocketToTCP(ws, tcp)
		pipeTCPToWebSocket(tcp, ws)
		
		log.Println("Bridge closed. Reconnecting in 5s")
		time.Sleep(5 * time.Second)
	}
}
