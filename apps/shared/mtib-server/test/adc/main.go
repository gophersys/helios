package main

import (
	"bufio"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	MQTT "github.com/eclipse/paho.mqtt.golang"
)

const (
	mqttBroker = "tcp://kubecop.ad.corekinect.com:1883"
	devicePath = "/sys/bus/iio/devices/iio:device1"
	interval   = 10 * time.Millisecond
)

type ADCReader struct {
	channel int
	client  MQTT.Client
	wg      *sync.WaitGroup
}

func NewADCReader(channel int, client MQTT.Client, wg *sync.WaitGroup) *ADCReader {
	return &ADCReader{
		channel: channel,
		client:  client,
		wg:      wg,
	}
}

func (r *ADCReader) readADCValue() (float64, error) {
	// Read raw ADC value
	rawPath := fmt.Sprintf("%s/in_voltage%d_raw", devicePath, r.channel)
	rawFile, err := os.Open(rawPath)
	if err != nil {
		return 0, fmt.Errorf("failed to open raw file for channel %d: %v", r.channel, err)
	}
	defer rawFile.Close()

	scanner := bufio.NewScanner(rawFile)
	if !scanner.Scan() {
		return 0, fmt.Errorf("failed to read raw value for channel %d", r.channel)
	}

	rawValue, err := strconv.Atoi(strings.TrimSpace(scanner.Text()))
	if err != nil {
		return 0, fmt.Errorf("failed to parse raw value for channel %d: %v", r.channel, err)
	}

	// For 16-bit ADC with 4.096V reference
	// Voltage = (RawValue / 65535) * 4.096V
	// Convert to millivolts for precision
	voltage := (float64(rawValue) / 65535.0) * 4.096 * 1000
	return voltage, nil
}

func (r *ADCReader) publishReading() {
	value, err := r.readADCValue()
	if err != nil {
		log.Printf("Error reading ADC channel %d: %v", r.channel, err)
		return
	}

	topic := fmt.Sprintf("adc/%d", r.channel)
	payload := fmt.Sprintf("%f", value)
	
	token := r.client.Publish(topic, 0, false, payload)
	if token.Wait() && token.Error() != nil {
		log.Printf("Error publishing to topic %s: %v", topic, token.Error())
		return
	}

	// if r.channel == 0 {
	// 	log.Printf("Published channel %d: %f mV to topic %s", r.channel, value, topic)
	// }
}

func (r *ADCReader) Start() {
	defer r.wg.Done()
	
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	log.Printf("Starting ADC reader for channel %d", r.channel)

	for {
		select {
		case <-ticker.C:
			r.publishReading()
		}
	}
}

func main() {
	// MQTT client options
	opts := MQTT.NewClientOptions()
	opts.AddBroker(mqttBroker)
	opts.SetClientID("adc-reader")
	opts.SetAutoReconnect(true)
	opts.SetConnectRetry(true)
	opts.SetConnectRetryInterval(5 * time.Second)

	// Create MQTT client
	client := MQTT.NewClient(opts)
	
	// Connect to MQTT broker
	if token := client.Connect(); token.Wait() && token.Error() != nil {
		log.Fatalf("Failed to connect to MQTT broker: %v", token.Error())
	}
	log.Printf("Connected to MQTT broker: %s", mqttBroker)

	// Verify ADC device exists
	if _, err := os.Stat(devicePath); os.IsNotExist(err) {
		log.Fatalf("ADC device not found at %s", devicePath)
	}
	log.Printf("Found ADC device at %s", devicePath)

	// Create wait group for goroutines
	var wg sync.WaitGroup

	// Start 8 goroutines for ADC channels 0-7
	// for i := 0; i < 8; i++ {
	// 	reader := NewADCReader(i, client, &wg)
	// 	wg.Add(1)
	// 	go reader.Start()
	// }

	reader := NewADCReader(2, client, &wg)
	wg.Add(1)
	go reader.Start()

	log.Println("All ADC readers started. Press Ctrl+C to stop.")

	// Wait for all goroutines (they run indefinitely)
	wg.Wait()
}
