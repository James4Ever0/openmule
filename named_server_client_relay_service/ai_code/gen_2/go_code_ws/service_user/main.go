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
	localPort := 15900

	for {
		listener, err := net.Listen("tcp", ":"+string(localPort))
		if err != nil {
			log.Fatal(err)
		}
		log.Printf("Listening on port %d", localPort)

		clientConn, err := listener.Accept()
		if err != nil {
			log.Printf("Accept error: %v", err)
			listener.Close()
			continue
		}
		log.Println("Client connected")

		ws, _, err := websocket.DefaultDialer.Dial(relayURL, nil)
		if err != nil {
			log.Printf("Dial error: %v", err)
			clientConn.Close()
			listener.Close()
			time.Sleep(5 * time.Second)
			continue
		}

		err = ws.WriteMessage(websocket.TextMessage, []byte("REQUEST:"+serviceName))
		if err != nil {
			log.Printf("Request error: %v", err)
			ws.Close()
			clientConn.Close()
			listener.Close()
			time.Sleep(5 * time.Second)
			continue
		}

		_, resp, err := ws.ReadMessage()
		if err != nil || string(resp) != "OK" {
			log.Printf("Unexpected response: %s", string(resp))
			ws.Close()
			clientConn.Close()
			listener.Close()
			time.Sleep(5 * time.Second)
			continue
		}

		log.Println("Starting bridge...")
		go pipeWebSocketToTCP(ws, clientConn)
		pipeTCPToWebSocket(clientConn, ws)
		
		log.Println("Bridge closed. Restarting listener")
		listener.Close()
	}
}