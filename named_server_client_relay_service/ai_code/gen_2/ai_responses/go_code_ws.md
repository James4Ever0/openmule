I'll rewrite the system in Go using WebSockets. Here's the implementation:

1. First, install the required dependency:
go get github.com/gorilla/websocket


2. relay_server/main.go:
package main

import (
	"log"
	"net/http"
	"strings"
	"sync"

	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

type RelayServer struct {
	serviceRegistry map[string]*websocket.Conn
	lock            sync.Mutex
}

func NewRelayServer() *RelayServer {
	return &RelayServer{
		serviceRegistry: make(map[string]*websocket.Conn),
	}
}

func (rs *RelayServer) handleConnection(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("Upgrade error: %v", err)
		return
	}
	defer conn.Close()

	_, message, err := conn.ReadMessage()
	if err != nil {
		log.Printf("Read error: %v", err)
		return
	}

	msg := string(message)
	log.Printf("Received identification: %s", msg)

	switch {
	case strings.HasPrefix(msg, "REGISTER:"):
		serviceName := strings.TrimPrefix(msg, "REGISTER:")
		rs.registerService(serviceName, conn)
	case strings.HasPrefix(msg, "REQUEST:"):
		serviceName := strings.TrimPrefix(msg, "REQUEST:")
		rs.handleClientRequest(serviceName, conn)
	default:
		log.Printf("Unknown protocol message: %s", msg)
		conn.WriteMessage(websocket.TextMessage, []byte("ERROR:Unknown command"))
	}
}

func (rs *RelayServer) registerService(serviceName string, conn *websocket.Conn) {
	rs.lock.Lock()
	defer rs.lock.Unlock()

	if oldConn, exists := rs.serviceRegistry[serviceName]; exists {
		log.Printf("Service '%s' already registered. Closing old connection", serviceName)
		oldConn.Close()
	}

	rs.serviceRegistry[serviceName] = conn
	log.Printf("Service '%s' registered successfully", serviceName)

	// Wait for connection to close
	for {
		if _, _, err := conn.ReadMessage(); err != nil {
			break
		}
	}

	rs.unregisterService(serviceName, conn)
}

func (rs *RelayServer) unregisterService(serviceName string, conn *websocket.Conn) {
	rs.lock.Lock()
	defer rs.lock.Unlock()

	if currentConn, exists := rs.serviceRegistry[serviceName]; exists && currentConn == conn {
		delete(rs.serviceRegistry, serviceName)
		log.Printf("Service '%s' unregistered", serviceName)
	}
}

func (rs *RelayServer) handleClientRequest(serviceName string, clientConn *websocket.Conn) {
	rs.lock.Lock()
	providerConn, exists := rs.serviceRegistry[serviceName]
	if exists {
		delete(rs.serviceRegistry, serviceName)
	}
	rs.lock.Unlock()

	if !exists {
		log.Printf("Client requested unknown service: %s", serviceName)
		clientConn.WriteMessage(websocket.TextMessage, []byte("ERROR:Service not found"))
		clientConn.Close()
		return
	}

	log.Printf("Connecting client to service '%s'", serviceName)
	clientConn.WriteMessage(websocket.TextMessage, []byte("OK"))
	rs.bridgeConnections(clientConn, providerConn)
	log.Printf("Client disconnected from service '%s'", serviceName)
}

func (rs *RelayServer) bridgeConnections(conn1, conn2 *websocket.Conn) {
	var wg sync.WaitGroup
	wg.Add(2)

	pipe := func(src, dst *websocket.Conn) {
		defer wg.Done()
		for {
			mt, data, err := src.ReadMessage()
			if err != nil {
				break
			}
			dst.WriteMessage(mt, data)
		}
	}

	go pipe(conn1, conn2)
	go pipe(conn2, conn1)

	wg.Wait()
	conn1.Close()
	conn2.Close()
}

func main() {
	rs := NewRelayServer()
	http.HandleFunc("/", rs.handleConnection)
	log.Println("Relay server starting on :8888")
	log.Fatal(http.ListenAndServe(":8888", nil))
}


3. service_provider/main.go:
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


4. service_user/main.go:
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


Key changes from the original Python implementation:

1. WebSocket-based communication instead of raw TCP sockets
2. Simplified connection handling using HTTP/WebSocket upgrade
3. Automatic reconnection logic built into all components
4. Binary message handling for efficient data transfer
5. Concurrent data piping using goroutines instead of threads
6. Built-in logging with timestamps

To run the system:
1. Start relay_server
2. Start service_provider (connects to target service)
3. Start service_user (creates local listener)
4. Connect your client to service_user's local port

The system maintains the same functionality but uses WebSockets for more efficient communication and better compatibility with modern networks.