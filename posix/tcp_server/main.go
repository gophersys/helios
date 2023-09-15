package main

import (
	"encoding/binary"
	"log"
	"net"
	"os"
)

const ServerProtocolVersion = 1

func main() {
	listen, err := net.Listen("tcp", ":6969")
	if err != nil {
		log.Printf("Failed to listen on port 6969: %v\n", err)
		os.Exit(1)
	}
	defer listen.Close()

	log.Println("Listening on port 6969...")

	for {
		conn, err := listen.Accept()
		if err != nil {
			log.Printf("Failed to accept connection: %v\n", err)
			continue
		}

		go handleConnection(conn)
	}
}

func handleConnection(conn net.Conn) {
	defer conn.Close()

	if err := handShakeDownlink(conn); err != nil {
		log.Printf("Could not handshake: %v", err)
		return
	}

	log.Printf("Received connection from %s", conn.RemoteAddr())

	_, err := conn.Write([]byte("Hello, Client!\n"))
	if err != nil {
		log.Printf("Failed to send message to client: %v\n", err)
		return
	}
}

func handShakeDownlink(conn net.Conn) error {
	var clientVersion uint16

	// Receive the version from client
	if err := binary.Read(conn, binary.BigEndian, &clientVersion); err != nil {
		return err
	}

	// Compare the version and send back the result
	if clientVersion == ServerProtocolVersion {
		_, err := conn.Write([]byte{1}) // Send true (as byte)
		return err
	}

	log.Printf("Invalid client version %v", clientVersion)
	_, err := conn.Write([]byte{0}) // Send false (as byte)
	return err
}
