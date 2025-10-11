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
