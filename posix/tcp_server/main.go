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
	HopCount      uint8
}

type CipherPayloadSd struct {
	ServiceID uint16
	NumHops   uint8
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

		if err := handShakeDownlink(conn); err != nil {
			log.Fatalf("Could not handshake link")
		}

		handleConnection(conn)
	}
}

func handleConnection(conn net.Conn) {
	defer conn.Close()

	log.Printf("Received connection from %s", conn.RemoteAddr())

	header := &CipherPacketHeader{
		SourceID:      1234,
		DestinationID: 0,
		Type:          2,
		Flags:         0x01,
	}

	ticker := time.NewTicker(300 * time.Millisecond)
	defer ticker.Stop()
	var counter int8
	raw := &CipherPayloadSd{
		ServiceID: 69,
		NumHops:   uint8(counter),
	}
	counter++

	payload := PackPayloadSd(raw)
	sendPacket(conn, header, payload)
	// sendPacket(conn, header, payload)
	time.Sleep(time.Second * 2)
	os.Exit(1)

	for range ticker.C {
		raw := &CipherPayloadSd{
			ServiceID: 69,
			NumHops:   uint8(counter),
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

	log.Printf("Protocol version received %v", clientVersion)

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
	buf := make([]byte, 12)
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
	buf[11] = header.HopCount
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
	header.PayloadLen = uint32(len(payload))
	packet := append(PackHeader(header), payload...)
	log.Printf(("Sending %v bytes, %v"), len(packet), packet)
	_, err := conn.Write(packet)
	if err != nil {
		log.Fatalf("Unable to send packet: %v", err)
	}
}
