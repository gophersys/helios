package main

import (
	"context"
	"fmt"
	"log"

	"bitbucket.org/corekinect/concord/libs/protocols/mtib"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

func main() {
	// Set up a connection to the server.
	conn, err := grpc.Dial("localhost:50053", grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatalf("did not connect: %v", err)
	}
	defer conn.Close()

	// Create a new client
	client := mtib.NewMtibV1Client(conn)

	// Call the HealthCheck method
	healthCheckResponse, err := client.HealthCheck(context.Background(), &mtib.Empty{})
	if err != nil {
		log.Fatalf("HealthCheck failed: %v", err)
	}
	fmt.Printf("HealthCheck response: %v\n", healthCheckResponse)

	// Call the GpioConfig method
	gpioConfigResponse, err := client.GpioConfig(context.Background(), &mtib.GpioConfigRequest{
		Gpio:      1,
		Direction: mtib.GpioDirection_GPIO_DIRECTION_OUTPUT,
		Resistor:  mtib.GpioResistorConfig_GPIO_RESISTOR_NONE,
	})
	if err != nil {
		log.Fatalf("GpioConfig failed: %v", err)
	}
	fmt.Printf("GpioConfig response: %v\n", gpioConfigResponse)
}
