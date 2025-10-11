package main

import (
	"bufio"
	"fmt"
	"log"
	"net"
	"strings"
	"sync"
)

type RelayServer struct {
	host           string
	port           int
	serviceRegistry map[string]net.Conn
	lock           sync.Mutex
}

func NewRelayServer(host string, port int) *RelayServer {
	return &RelayServer{
		host:           host,
		port:           port,
		serviceRegistry: make(map[string]net.Conn),
	}
}

func (rs *RelayServer) Start() error {
	listener, err := net.Listen("tcp", fmt.Sprintf("%s:%d", rs.host, rs.port))
	if err != nil {
		return err
	}
	defer listener.Close()
	
	TimedPrintf("Relay server listening on %s:%d", rs.host, rs.port)

	for {
		conn, err := listener.Accept()
		if err != nil {
			TimedPrintf("Accept error: %v", err)
			continue
		}
		TimedPrintf("New connection from %s", conn.RemoteAddr())
		go rs.handleConnection(conn)
	}
}

func (rs *RelayServer) handleConnection(conn net.Conn) {
	defer conn.Close()

	reader := bufio.NewReader(conn)
	identData, err := reader.ReadString('\n')
	if err != nil {
		TimedPrintf("Read error: %v", err)
		return
	}
	identData = strings.TrimSpace(identData)
	TimedPrintf("Received identification: %s", identData)

	switch {
	case strings.HasPrefix(identData, "REGISTER:"):
		serviceName := identData[len("REGISTER:"):]
		rs.registerService(serviceName, conn)
	case strings.HasPrefix(identData, "REQUEST:"):
		serviceName := identData[len("REQUEST:"):]
		rs.handleClientRequest(serviceName, conn)
	default:
		TimedPrintf("Unknown protocol message: %s", identData)
	}
}

func (rs *RelayServer) registerService(serviceName string, conn net.Conn) {
	rs.lock.Lock()
	defer rs.lock.Unlock()

	if oldConn, exists := rs.serviceRegistry[serviceName]; exists {
		TimedPrintf("Service '%s' already registered. Closing old connection", serviceName)
		oldConn.Close()
	}
	rs.serviceRegistry[serviceName] = conn
	TimedPrintf("Service '%s' registered successfully", serviceName)
}

func (rs *RelayServer) unregisterService(serviceName string, conn net.Conn) {
	rs.lock.Lock()
	defer rs.lock.Unlock()

	if currentConn, exists := rs.serviceRegistry[serviceName]; exists && currentConn == conn {
		conn.Close()
		delete(rs.serviceRegistry, serviceName)
		TimedPrintf("Service '%s' unregistered", serviceName)
	}
}

func (rs *RelayServer) handleClientRequest(serviceName string, clientConn net.Conn) {
	rs.lock.Lock()
	providerConn, exists := rs.serviceRegistry[serviceName]
	rs.lock.Unlock()

	if !exists {
		TimedPrintf("Client requested unknown service: %s", serviceName)
		clientConn.Write([]byte("ERROR:Service not found\n"))
		clientConn.Close()
		return
	}

	clientConn.Write([]byte("OK\n"))
	TimedPrintf("Connecting client to service '%s'", serviceName)

	done := make(chan struct{})
	go func() {
		Pipe(clientConn, providerConn, "client->provider")
		close(done)
	}()
	go func() {
		Pipe(providerConn, clientConn, "provider->client")
		close(done)
	}()

	<-done
	clientConn.Close()
	rs.unregisterService(serviceName, providerConn)
	TimedPrintf("Client disconnected from service '%s'", serviceName)
}

func main() {
	relay := NewRelayServer("0.0.0.0", 8888)
	relay.Start()
}
