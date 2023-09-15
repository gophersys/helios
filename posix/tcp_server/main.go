package main

import (
	"fmt"
	"net"
	"os"
)

func main() {
	listen, err := net.Listen("tcp", ":6969")
	if err != nil {
		fmt.Printf("Failed to listen on port 6969: %v\n", err)
		os.Exit(1)
	}
	defer listen.Close()

	fmt.Println("Listening on port 6969...")

	for {
		conn, err := listen.Accept()
		if err != nil {
			fmt.Printf("Failed to accept connection: %v\n", err)
			continue
		}

		go handleConnection(conn)
	}
}

func handleConnection(conn net.Conn) {
	defer conn.Close()

	fmt.Printf("Received connection from %s\n", conn.RemoteAddr())

	_, err := conn.Write([]byte("Hello, Client!\n"))
	if err != nil {
		fmt.Printf("Failed to send message to client: %v\n", err)
	}
}
