package main

import (
	"bufio"
	"fmt"
	"log"
	"net"
	"time"
)

type ServiceProvider struct {
	relayHost string
	relayPort int
}

func NewServiceProvider(relayHost string, relayPort int) *ServiceProvider {
	return &ServiceProvider{
		relayHost: relayHost,
		relayPort: relayPort,
	}
}

func (sp *ServiceProvider) RegisterService(serviceName string, localPort int) error {
	// Connect to relay server
	relayAddr := fmt.Sprintf("%s:%d", sp.relayHost, sp.relayPort)
	conn, err := net.Dial("tcp", relayAddr)
	if err != nil {
		return fmt.Errorf("failed to connect to relay: %v", err)
	}

	// Register service
	registrationMsg := fmt.Sprintf("REGISTER:%s\n", serviceName)
	_, err = conn.Write([]byte(registrationMsg))
	if err != nil {
		return fmt.Errorf("failed to register service: %v", err)
	}

	// Read response
	reader := bufio.NewReader(conn)
	response, err := reader.ReadString('\n')
	if err != nil {
		return fmt.Errorf("failed to read response: %v", err)
	}

	if !strings.HasPrefix(response, "OK:") {
		return fmt.Errorf("registration failed: %s", response)
	}

	log.Printf("Successfully registered service '%s'", serviceName)

	// In a real implementation, you would:
	// 1. Accept local connections on localPort
	// 2. Forward them through the relay connection
	// For this demo, we'll just keep the connection alive
	sp.keepAlive(conn)

	return nil
}

func (sp *ServiceProvider) keepAlive(conn net.Conn) {
	// Keep the connection alive and handle incoming relay connections
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	buffer := make([]byte, 1024)
	for {
		select {
		case <-ticker.C:
			// Send keep-alive
			conn.Write([]byte{0})
		default:
			conn.SetReadDeadline(time.Now().Add(15 * time.Second))
			_, err := conn.Read(buffer)
			if err != nil {
				log.Printf("Connection to relay lost: %v", err)
				return
			}
			// In real implementation, this is where you'd handle data relay
		}
	}
}

func main() {
	provider := NewServiceProvider("localhost", 8888)
	
	// Register VNC service
	err := provider.RegisterService("vnc_service_a", 5900)
	if err != nil {
		log.Fatal(err)
	}

	// Keep the program running
	select {}
}