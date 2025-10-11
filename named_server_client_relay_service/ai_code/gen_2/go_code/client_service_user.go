package main

import (
	"bufio"
	"fmt"
	"net"
	"strings"
	"time"
)

func StartClient(relayHost string, relayPort int, serviceName string, localPort int) {
	for {
		listener, err := net.Listen("tcp", fmt.Sprintf("localhost:%d", localPort))
		if err != nil {
			TimedPrintf("Listen error: %v", err)
			time.Sleep(5 * time.Second)
			continue
		}

		TimedPrintf("Local forwarder listening on localhost:%d", localPort)
		
		clientConn, err := listener.Accept()
		if err != nil {
			TimedPrintf("Accept error: %v", err)
			listener.Close()
			time.Sleep(5 * time.Second)
			continue
		}
		TimedPrintf("Local client connected from %s", clientConn.RemoteAddr())
		listener.Close()

		relayConn, err := net.Dial("tcp", fmt.Sprintf("%s:%d", relayHost, relayPort))
		if err != nil {
			TimedPrintf("Failed to connect to relay: %v", err)
			clientConn.Close()
			time.Sleep(5 * time.Second)
			continue
		}

		relayConn.Write([]byte(fmt.Sprintf("REQUEST:%s\n", serviceName)))
		reader := bufio.NewReader(relayConn)
		response, err := reader.ReadString('\n')
		if err != nil {
			TimedPrintf("Read error: %v", err)
			clientConn.Close()
			relayConn.Close()
			time.Sleep(5 * time.Second)
			continue
		}

		if strings.TrimSpace(response) != "OK" {
			TimedPrintf("Unexpected response: %s", response)
			clientConn.Close()
			relayConn.Close()
			time.Sleep(5 * time.Second)
			continue
		}

		relayConn.Write([]byte("CONNECT\n"))
		done := make(chan struct{})
		go func() {
			Pipe(clientConn, relayConn, "client->relay")
			close(done)
		}()
		go func() {
			Pipe(relayConn, clientConn, "relay->client")
			close(done)
		}()

		<-done
		clientConn.Close()
		relayConn.Close()
		TimedPrintf("Connection aborted. Retrying...")
	}
}

func main() {
	StartClient("localhost", 8888, "vnc_service_a", 15900)
}
