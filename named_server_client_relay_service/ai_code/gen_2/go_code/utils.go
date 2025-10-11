package main

import (
	"encoding/hex"
	"fmt"
	"io"
	"log"
	"time"
)

func Pipe(src io.Reader, dst io.Writer, name string) {
	buf := make([]byte, 4096)
	for {
		n, err := src.Read(buf)
		if n > 0 {
			hexStr := hex.EncodeToString(buf[:n])
			if len(hexStr) > 20 {
				hexStr = hexStr[:20] + "..."
			}
			TimedPrintf("Pipe %s: read %d bytes: %s", name, n, hexStr)
			if _, err := dst.Write(buf[:n]); err != nil {
				TimedPrintf("Pipe %s write error: %v", name, err)
				break
			}
		}
		if err != nil {
			if err != io.EOF {
				TimedPrintf("Pipe %s read error: %v", name, err)
			}
			break
		}
	}
}

func TimedPrintf(format string, args ...interface{}) {
	timestamp := time.Now().Format("2006-01-02 15:04:05")
	log.Printf("[%s] %s", timestamp, fmt.Sprintf(format, args...))
}
