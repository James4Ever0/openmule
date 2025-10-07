package main

import (
	"bufio"
	"fmt"
	"log"
	"net"
	"strings"
	"sync"
	"time"
)

type ServiceRegistry struct {
	sync.RWMutex
	services map[string]net.Conn
}

type ConnectionPair struct {
	client net.Conn
	server net.Conn
}

type RelayServer struct {
	host        string
	port        int
	registry    *ServiceRegistry
	connections map[net.Conn]bool
	connMutex   sync.RWMutex
}

func NewRelayServer(host string, port int) *RelayServer {
	return &RelayServer{
		host: host,
		port: port,
		registry: &ServiceRegistry{
			services: make(map[string]net.Conn),
		},
		connections: make(map[net.Conn]bool),
	}
}

func (rs *RelayServer) Start() error {
	addr := fmt.Sprintf("%s:%d", rs.host, rs.port)
	listener, err := net.Listen("tcp", addr)
	if err != nil {
		return fmt.Errorf("failed to start relay server: %v", err)
	}
	defer listener.Close()

	log.Printf("Relay server listening on %s", addr)

	for {
		conn, err := listener.Accept()
		if err != nil {
			log.Printf("Error accepting connection: %v", err)
			continue
		}

		rs.connMutex.Lock()
		rs.connections[conn] = true
		rs.connMutex.Unlock()

		go rs.handleConnection(conn)
	}
}

func (rs *RelayServer) handleConnection(conn net.Conn) {
	defer func() {
		conn.Close()
		rs.connMutex.Lock()
		delete(rs.connections, conn)
		rs.connMutex.Unlock()
	}()

	reader := bufio.NewReader(conn)
	message, err := reader.ReadString('\n')
	if err != nil {
		log.Printf("Error reading from connection: %v", err)
		return
	}

	message = strings.TrimSpace(message)
	log.Printf("Received: %s", message)

	switch {
	case strings.HasPrefix(message, "REGISTER:"):
		rs.handleServiceRegistration(conn, message)
	case strings.HasPrefix(message, "REQUEST:"):
		rs.handleClientRequest(conn, message)
	default:
		conn.Write([]byte("ERROR:Invalid protocol\n"))
	}
}

func (rs *RelayServer) handleServiceRegistration(conn net.Conn, message string) {
	parts := strings.SplitN(message, ":", 2)
	if len(parts) != 2 {
		conn.Write([]byte("ERROR:Invalid registration format\n"))
		return
	}

	serviceName := parts[1]
	
	rs.registry.Lock()
	// Close existing connection if service already registered
	if existingConn, exists := rs.registry.services[serviceName]; exists {
		existingConn.Close()
	}
	rs.registry.services[serviceName] = conn
	rs.registry.Unlock()

	conn.Write([]byte("OK:Service registered\n"))
	log.Printf("Service '%s' registered successfully", serviceName)

	// Keep connection alive and monitor for disconnection
	buffer := make([]byte, 1)
	for {
		conn.SetReadDeadline(time.Now().Add(30 * time.Second))
		_, err := conn.Read(buffer)
		if err != nil {
			log.Printf("Service '%s' disconnected: %v", serviceName, err)
			rs.registry.Lock()
			if rs.registry.services[serviceName] == conn {
				delete(rs.registry.services, serviceName)
			}
			rs.registry.Unlock()
			return
		}
	}
}

func (rs *RelayServer) handleClientRequest(conn net.Conn, message string) {
	parts := strings.SplitN(message, ":", 2)
	if len(parts) != 2 {
		conn.Write([]byte("ERROR:Invalid request format\n"))
		return
	}

	serviceName := parts[1]

	rs.registry.RLock()
	serviceConn, exists := rs.registry.services[serviceName]
	rs.registry.RUnlock()

	if !exists {
		conn.Write([]byte("ERROR:Service not found\n"))
		return
	}

	conn.Write([]byte("OK:Connected to service\n"))
	log.Printf("Connecting client to service '%s'", serviceName)

	// Create bidirectional relay between client and service
	rs.createBidirectionalRelay(conn, serviceConn)
}

func (rs *RelayServer) createBidirectionalRelay(client, server net.Conn) {
	// Use channels to coordinate the relay
	done := make(chan bool, 2)

	// Client -> Server direction
	go func() {
		buffer := make([]byte, 4096)
		for {
			n, err := client.Read(buffer)
			if err != nil {
				break
			}
			_, err = server.Write(buffer[:n])
			if err != nil {
				break
			}
		}
		done <- true
	}()

	// Server -> Client direction
	go func() {
		buffer := make([]byte, 4096)
		for {
			n, err := server.Read(buffer)
			if err != nil {
				break
			}
			_, err = client.Write(buffer[:n])
			if err != nil {
				break
			}
		}
		done <- true
	}()

	// Wait for either direction to finish
	<-done
	client.Close()
	server.Close()
	<-done // Wait for the other direction to clean up
}

func main() {
	server := NewRelayServer("0.0.0.0", 8888)
	if err := server.Start(); err != nil {
		log.Fatal(err)
	}
}