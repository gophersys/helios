package main

import (
	"bytes"
	"encoding/binary"
	"log"
	"net"
	"os"
	"time"
)

const ServerProtocolVersion = 1

type CipherPacketHeader struct {
	SourceID      uint16
	DestinationID uint16
	ServiceID     uint32
	OperationID   uint32
	PayloadLen    uint32
	SequenceNum   uint16
	Type          uint16
	Flags         uint8
}

type CipherPayloadSd struct {
	ServiceID uint8
	NumHops   uint16
}

func main() {
	listen, err := net.Listen("tcp", ":5000")
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

		handleConnection(conn)
	}
}

func handleConnection(conn net.Conn) {
	defer conn.Close()

	if err := handShakeDownlink(conn); err != nil {
		log.Printf("Could not handshake: %v", err)
		return
	}

	log.Printf("Received connection from %s", conn.RemoteAddr())

	header := &CipherPacketHeader{
		SourceID:      1234,
		DestinationID: 0,
		Type:          2,
		PayloadLen:    3,
		Flags:         0x01,
	}

	ticker := time.NewTicker(1 * time.Millisecond)
	defer ticker.Stop()

	var counter int
	for range ticker.C {
		raw := &CipherPayloadSd{
			ServiceID: 69,
			NumHops:   uint16(counter),
		}
		counter++

		payload := PackPayloadSd(raw)
		sendPacket(conn, header, payload)
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

func PackHeader(header *CipherPacketHeader) []byte {
	buf := make([]byte, 11)
	binary.BigEndian.PutUint16(buf[0:], header.SourceID)
	binary.BigEndian.PutUint16(buf[2:], header.DestinationID)
	combinedUint32 := (header.ServiceID & 0x3FFF) |
		(header.OperationID & 0xFF << 14) |
		(header.PayloadLen & 0x3FF << 22)
	binary.BigEndian.PutUint32(buf[4:], combinedUint32)
	combinedUint16 := (header.SequenceNum & 0x1FFF) |
		(header.Type & 0x7 << 13)
	binary.BigEndian.PutUint16(buf[8:], combinedUint16)
	buf[10] = header.Flags

	return buf
}

func PackPayloadSd(payload *CipherPayloadSd) []byte {
	buf := new(bytes.Buffer)

	// Write ServiceID in network byte order
	err := binary.Write(buf, binary.BigEndian, payload.ServiceID)
	if err != nil {
		log.Fatalf("Failed to pack ServiceID: %v\n", err)
	}

	// Write NumHops in network byte order
	err = binary.Write(buf, binary.BigEndian, payload.NumHops)
	if err != nil {
		log.Fatalf("Failed to pack NumHops: %v\n", err)
	}

	return buf.Bytes()
}

func sendPacket(conn net.Conn, header *CipherPacketHeader, payload []byte) {
	packet := append(PackHeader(header), payload...)
	log.Printf(("Sending %v bytes"), len(packet))
	_, err := conn.Write(packet)
	if err != nil {
		log.Printf("Failed to send packet: %v\n", err)
	}
}

// package main

// import (
// 	"io"
// 	"log"
// 	"net"
// )

// const serverPort = ":6969"

// func main() {
// 	listener, err := net.Listen("tcp", serverPort)
// 	if err != nil {
// 		log.Fatalf("Failed to start server: %v", err)
// 	}
// 	defer listener.Close()

// 	log.Printf("Server started on port %s", serverPort)

// 	for {
// 		conn, err := listener.Accept()
// 		if err != nil {
// 			log.Printf("Failed to accept connection: %v", err)
// 			continue
// 		}
// 		go handleClient(conn)
// 	}
// }

// func handleClient(conn net.Conn) {
// 	defer conn.Close()

// 	buffer := make([]byte, 1024)
// 	for {
// 		n, err := conn.Read(buffer)
// 		if err != nil {
// 			if err != io.EOF {
// 				log.Printf("Failed to read data: %v", err)
// 			}
// 			break
// 		}

// 		log.Printf("Received: %s", string(buffer[:n]))

// 		_, err = conn.Write(buffer[:n])
// 		if err != nil {
// 			log.Printf("Failed to write data: %v", err)
// 			break
// 		}
// 	}
// }
