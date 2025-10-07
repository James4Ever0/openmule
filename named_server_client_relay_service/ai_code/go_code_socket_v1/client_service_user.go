package main

import (
	"bufio"
	"fmt"
	"io"
	"log"
	"net"
	"strings"
)

type RelayClient struct {
	relayHost string
	relayPort int
}

func NewRelayClient(relayHost string, relayPort int) *RelayClient {
	return &RelayClient{
		relayHost: relayHost,
		relayPort: relayPort,
	}
}

func (rc *RelayClient) ConnectToService(serviceName string, localPort int) error {
	// Connect to relay server
	relayAddr := fmt.Sprintf("%s:%d", rc.relayHost, rc.relayPort)
	relayConn, err := net.Dial("tcp", relayAddr)
	if err != nil {
		return fmt.Errorf("failed to connect to relay: %v", err)
	}

	// Request service
	requestMsg := fmt.Sprintf("REQUEST:%s\n", serviceName)
	_, err = relayConn.Write([]byte(requestMsg))
	if err != nil {
		return fmt.Errorf("failed to request service: %v", err)
	}

	// Read response
	reader := bufio.NewReader(relayConn)
	response, err := reader.ReadString('\n')
	if err != nil {
		return fmt.Errorf("failed to read response: %v", err)
	}

	if !strings.HasPrefix(response, "OK:") {
		return fmt.Errorf("service connection failed: %s", response)
	}

	log.Printf("Successfully connected to service '%s'", serviceName)

	// Start local server that forwards to relay connection
	return rc.startLocalForwarder(localPort, relayConn)
}

func (rc *RelayClient) startLocalForwarder(localPort int, relayConn net.Conn) error {
	localAddr := fmt.Sprintf("localhost:%d", localPort)
	listener, err := net.Listen("tcp", localAddr)
	if err != nil {
		return fmt.Errorf("failed to start local forwarder: %v", err)
	}
	defer listener.Close()

	log.Printf("Local forwarder listening on %s", localAddr)

	for {
		localConn, err := listener.Accept()
		if err != nil {
			log.Printf("Error accepting local connection: %v", err)
			continue
		}

		log.Printf("New local connection, forwarding to service via relay")
		
		// Bidirectional relay between local connection and relay
		go rc.pipeConnections(localConn, relayConn)
		
		// Note: In production, you'd want to handle multiple local clients
		// by creating a new relay connection for each local client
	}
}

func (rc *RelayClient) pipeConnections(src, dst net.Conn) {
	defer src.Close()
	
	// Use channels to wait for copy operations to finish
	done := make(chan struct{}, 2)
	
	go func() {
		io.Copy(dst, src)
		done <- struct{}{}
	}()
	
	go func() {
		io.Copy(src, dst)
		done <- struct{}{}
	}()
	
	// Wait for one direction to finish
	<-done
}

func main() {
	client := NewRelayClient("localhost", 8888)
	
	// Connect to VNC service and create local port 15900
	err := client.ConnectToService("vnc_service_a", 15900)
	if err != nil {
		log.Fatal(err)
	}
	
	// Keep the program running
	select {}
}