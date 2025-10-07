// This client connects to the relay, requests a service, and exposes a local port.
package main

import (
    "log"
    "net"

    "github.com/gobwas/ws"
)

func (cc *RelayClient) startLocalForwarder(localPort int, relayConn net.Conn) error {
    // Listen on a local port
    listener, err := net.Listen("tcp", fmt.Sprintf("localhost:%d", localPort))
    if err != nil {
        return err
    }
    defer listener.Close()
    log.Printf("Local forwarder listening on localhost:%d", localPort)

    for {
        localConn, err := listener.Accept()
        if err != nil {
            log.Printf("Accept failed: %v", err)
            continue
        }
        // For each local connection, relay data to the WebSocket connection to the relay
        go cc.pipeConnections(localConn, relayConn)
    }
}