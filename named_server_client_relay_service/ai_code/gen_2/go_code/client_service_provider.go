package main

import (
	"bufio"
	"fmt"
	"net"
	"strings"
	"time"
)

func StartServiceProvider(relayHost string, relayPort int, serviceName, targetHost string, targetPort int) {
	for {
		relayConn, err := net.Dial("tcp", fmt.Sprintf("%s:%d", relayHost, relayPort))
		if err != nil {
			TimedPrintf("Failed to connect to relay: %v", err)
			time.Sleep(5 * time.Second)
			continue
		}

		relayConn.Write([]byte(fmt.Sprintf("REGISTER:%s\n", serviceName)))
		TimedPrintf("Registered service '%s' with relay", serviceName)

		reader := bufio.NewReader(relayConn)
		connectMsg, err := reader.ReadString('\n')
		if err != nil {
			TimedPrintf("Read error: %v", err)
			relayConn.Close()
			time.Sleep(5 * time.Second)
			continue
		}

		if strings.TrimSpace(connectMsg) != "CONNECT" {
			TimedPrintf("Unexpected message: %s", connectMsg)
			relayConn.Close()
			time.Sleep(5 * time.Second)
			continue
		}

		targetConn, err := net.Dial("tcp", fmt.Sprintf("%s:%d", targetHost, targetPort))
		if err != nil {
			TimedPrintf("Failed to connect to target: %v", err)
			relayConn.Close()
			time.Sleep(5 * time.Second)
			continue
		}

		done := make(chan struct{})
		go func() {
			Pipe(relayConn, targetConn, "relay->target")
			close(done)
		}()
		go func() {
			Pipe(targetConn, relayConn, "target->relay")
			close(done)
		}()

		<-done
		targetConn.Close()
		relayConn.Close()
		TimedPrintf("Client or relay disconnected. Reconnecting")
	}
}

func main() {
	StartServiceProvider("localhost", 8888, "vnc_service_a", "localhost", 5950)
}
