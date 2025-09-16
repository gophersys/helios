package main

import (
	"bufio"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	MQTT "github.com/eclipse/paho.mqtt.golang"
)

const (
	mqttBroker = "tcp://kubecop.ad.corekinect.com:1883"
	interval   = 200 * time.Millisecond
	// Voltage divider ratio - actual voltage is 3.48x the ADC reading
	// This compensates for the voltage divider circuit
	// Circuit: R29=82kΩ, R32=33kΩ
	// Divider ratio = R32/(R29+R32) = 33/(82+33) = 33/115 = 0.287
	// Compensation ratio = 1/0.287 = 3.48
	voltageDividerRatio = 3.48
)

/*
ADS1015/ADS1115 Gain Settings and Voltage Ranges:
- 0.007812500 = ±0.256V range
- 0.015625000 = ±0.512V range
- 0.031250000 = ±1.024V range
- 0.062500000 = ±4.096V range
- 0.125000000 = ±2.048V range
- 0.187500000 = ±6.144V range (recommended for VCC up to 4.75V)

For VCC = 4.75V, use scale 0.187500000 to get full range coverage.
The scale factor can be changed at runtime by writing to in_voltageX_scale files.
*/

// Real channel to MQTT channel mapping
// [real_channel, mqtt_channel]
// Based on schematic: ADC1-4 -> U8(0x48), ADC5-8 -> U31(0x49)
// Actual mapping from user description:
// Physical 0->MQTT 1, Physical 1->MQTT 2, Physical 2->MQTT 0, Physical 3->MQTT 3
var channelMapping = [][2]int{
	{7, 7}, {6, 6}, {5, 5}, {4, 4}, // Device 0x49 channels (ADC5-8)
	{3, 3}, {2, 2}, {1, 1}, {0, 0}, // Device 0x48 channels (ADC1-4)
}

// GPIO pin mapping for reading only
// Note: We can read pins 0-6 even though they're controlled by the Python program
// Maps GPIO number to chip and line
var gpioPinMap = map[int]struct {
	chip string
	line int
}{
	0: {"/dev/gpiochip2", 4},  // SODIMM_206 - GPIO_0
	1: {"/dev/gpiochip4", 5},  // SODIMM_208 - GPIO_1
	2: {"/dev/gpiochip4", 26}, // SODIMM_210 - GPIO_2
	3: {"/dev/gpiochip4", 27}, // SODIMM_212 - GPIO_3
	4: {"/dev/gpiochip3", 26}, // SODIMM_34 - I2S1_D_OUT
	5: {"/dev/gpiochip3", 25}, // SODIMM_30 - I2S1_BCLK
	6: {"/dev/gpiochip3", 24}, // SODIMM_32 - I2S1_SYNC
}

type ADCReader struct {
	realChannel   int    // Real channel (1-8)
	mqttChannel   int    // MQTT channel (0-7)
	deviceChannel string // Device channel 0-3 (within the specific device)
	devicePath    string // Path to the specific device
	client        MQTT.Client
	wg            *sync.WaitGroup
	scaleFactor   float64 // Scale factor from device (mV per raw unit)
}

type GPIOReader struct {
	gpioNumber int    // GPIO number (0-6)
	chipPath   string // Path to the GPIO chip device
	lineNumber int    // Line number within the chip
	client     MQTT.Client
	wg         *sync.WaitGroup
}

// Auto-detect ADC devices by I2C address
func detectADCDevices() (map[string]string, error) {
	devices := make(map[string]string)

	// Scan all IIO devices
	deviceDirs, err := filepath.Glob("/sys/bus/iio/devices/iio:device*")
	if err != nil {
		return nil, fmt.Errorf("failed to scan IIO devices: %v", err)
	}

	for _, deviceDir := range deviceDirs {
		// Read the device name
		nameFile := filepath.Join(deviceDir, "name")
		nameData, err := os.ReadFile(nameFile)
		if err != nil {
			continue // Skip devices we can't read
		}

		deviceName := strings.TrimSpace(string(nameData))
		if deviceName == "ads1015" {
			// Read the I2C address from the device path
			// The path format is: /sys/bus/iio/devices/iio:deviceX -> ../../../devices/platform/soc@0/30800000.bus/30a50000.i2c/i2c-3/3-0048/iio:deviceX
			// We need to extract the address (0048 or 0049) from the symlink target
			linkTarget, err := os.Readlink(deviceDir)
			if err != nil {
				log.Printf("Warning: cannot read symlink for %s: %v", deviceDir, err)
				continue
			}

			// Extract I2C address from the path
			parts := strings.Split(linkTarget, "/")
			for _, part := range parts {
				if strings.HasPrefix(part, "3-") && len(part) == 6 {
					// Extract the address part (last 2 characters, removing leading zeros)
					address := part[2:]
					// Remove leading zeros to get 2-character address
					if len(address) == 4 {
						address = address[2:] // Take last 2 characters
					}
					devices[address] = deviceDir
					log.Printf("Found ADS1015 device at address 0x%s: %s", address, deviceDir)
					break
				}
			}
		}
	}

	return devices, nil
}

func NewADCReader(realChannel int, mqttChannel int, devicePath string, client MQTT.Client, wg *sync.WaitGroup) *ADCReader {
	// Determine device channel based on real channel
	var deviceChannel int

	if realChannel >= 4 && realChannel <= 7 {
		// Channels 4-7 (device 0x49): map to device channels 0-3
		// Channel mapping: 7->0, 6->1, 5->2, 4->3
		deviceChannel = 7 - realChannel
	} else {
		// Channels 0-3 (device 0x48): map to device channels 0-3
		// Channel mapping: 0->0, 1->1, 2->2, 3->3
		deviceChannel = realChannel
	}

	reader := &ADCReader{
		realChannel:   realChannel,
		mqttChannel:   mqttChannel,
		deviceChannel: strconv.Itoa(deviceChannel),
		devicePath:    devicePath,
		client:        client,
		wg:            wg,
	}

	// Set all the channels to the same scale factor by writing to the scale file
	for i := 0; i < 4; i++ {
		scalePath := fmt.Sprintf("%s/in_voltage%s_scale", devicePath, strconv.Itoa(i))
		scaleFile, err := os.OpenFile(scalePath, os.O_WRONLY, 0644)
		if err != nil {
			log.Printf("Warning: cannot write to scale file for device %s channel %d: %v", devicePath, i, err)
		} else {
			_, err = scaleFile.WriteString(fmt.Sprintf("%.9f", 0.187500000))
			scaleFile.Close()
		}
	}

	// Set optimal gain for VCC up to 4.75V (use ±6.144V range)
	optimalScale := 0.187500000
	scalePath := fmt.Sprintf("%s/in_voltage%s_scale", devicePath, reader.deviceChannel)

	// Try to set the optimal scale
	scaleFile, err := os.OpenFile(scalePath, os.O_WRONLY, 0644)
	if err != nil {
		log.Printf("Warning: cannot write to scale file for real channel %d: %v", realChannel, err)
	} else {
		_, err = scaleFile.WriteString(fmt.Sprintf("%.9f", optimalScale))
		scaleFile.Close()
		if err != nil {
			log.Printf("Warning: failed to set optimal scale for real channel %d: %v", realChannel, err)
		} else {
			log.Printf("Set optimal scale %.9f for real channel %d (MQTT: %d, device: %s)", optimalScale, realChannel, mqttChannel, devicePath)
		}
	}

	// Read the current scale factor from the device
	scaleFile, err = os.Open(scalePath)
	if err != nil {
		log.Printf("Warning: failed to open scale file for real channel %d: %v", realChannel, err)
		// Use default scale factor if file not found
		reader.scaleFactor = optimalScale
	} else {
		defer scaleFile.Close()
		scanner := bufio.NewScanner(scaleFile)
		if scanner.Scan() {
			scale, err := strconv.ParseFloat(strings.TrimSpace(scanner.Text()), 64)
			if err != nil {
				log.Printf("Warning: failed to parse scale factor for real channel %d: %v", realChannel, err)
				reader.scaleFactor = optimalScale
			} else {
				reader.scaleFactor = scale
			}
		} else {
			log.Printf("Warning: failed to read scale factor for real channel %d", realChannel)
			reader.scaleFactor = optimalScale
		}
	}

	log.Printf("ADC Reader for real channel %d (MQTT: %d) initialized with scale factor: %f mV/unit (device: %s, device_channel: %s)",
		realChannel, mqttChannel, reader.scaleFactor, devicePath, reader.deviceChannel)
	return reader
}

func (r *ADCReader) readADCValue() (float64, error) {
	// Read raw ADC value from the specified device channel
	rawPath := fmt.Sprintf("%s/in_voltage%s_raw", r.devicePath, r.deviceChannel)
	rawFile, err := os.Open(rawPath)
	if err != nil {
		return 0, fmt.Errorf("failed to open raw file for MQTT channel %d (device_channel %s): %v", r.realChannel, r.deviceChannel, err)
	}
	defer rawFile.Close()

	scanner := bufio.NewScanner(rawFile)
	if !scanner.Scan() {
		return 0, fmt.Errorf("failed to read raw value for MQTT channel %d", r.realChannel)
	}

	rawValue, err := strconv.Atoi(strings.TrimSpace(scanner.Text()))
	if err != nil {
		return 0, fmt.Errorf("failed to parse raw value for MQTT channel %d: %v", r.realChannel, err)
	}

	// Convert raw ADC value to voltage
	// 1. Multiply raw value by scale factor to get voltage in mV
	voltage_mV := float64(rawValue) * r.scaleFactor

	// 2. Apply voltage divider compensation
	realVoltage_mV := voltage_mV * voltageDividerRatio

	// 3. Convert to volts
	voltage_V := realVoltage_mV / 1000.0

	return voltage_V, nil
}

func (r *ADCReader) publishReading() {
	value, err := r.readADCValue()
	if err != nil {
		log.Printf("Error reading ADC real channel %d: %v", r.realChannel, err)
		return
	}

	topic := fmt.Sprintf("adc/%d", r.mqttChannel)
	payload := fmt.Sprintf("%.6f", value) // Use 6 decimal places for precision

	token := r.client.Publish(topic, 0, false, payload)
	if token.Wait() && token.Error() != nil {
		log.Printf("Error publishing to topic %s: %v", topic, token.Error())
		return
	}
}

func (r *ADCReader) Start() {
	defer r.wg.Done()

	log.Printf("Starting ADC reader for real channel %d (MQTT: %d) (device: %s, device_channel: %s)",
		r.realChannel, r.mqttChannel, r.devicePath, r.deviceChannel)

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			r.publishReading()
		}
	}
}

func NewGPIOReader(gpioNumber int, client MQTT.Client, wg *sync.WaitGroup) *GPIOReader {
	// Get the chip and line information from the mapping
	pinInfo, exists := gpioPinMap[gpioNumber]
	if !exists {
		log.Printf("Warning: GPIO number %d not found in pin map", gpioNumber)
		return nil
	}

	reader := &GPIOReader{
		gpioNumber: gpioNumber,
		chipPath:   pinInfo.chip,
		lineNumber: pinInfo.line,
		client:     client,
		wg:         wg,
	}

	log.Printf("GPIO Reader for GPIO %d initialized (chip: %s, line: %d)",
		gpioNumber, pinInfo.chip, pinInfo.line)
	return reader
}

func (r *GPIOReader) readGPIOValue() (int, error) {
	// Read GPIO value directly from the chip device file without exporting
	// This approach reads the current state without interfering with the Python program

	// Try to read from the chip device file directly
	// Extract chip number from path like "/dev/gpiochip2"
	chipNum := 0
	if strings.Contains(r.chipPath, "gpiochip2") {
		chipNum = 2
	} else if strings.Contains(r.chipPath, "gpiochip3") {
		chipNum = 3
	} else if strings.Contains(r.chipPath, "gpiochip4") {
		chipNum = 4
	}

	// Try to read from the chip device file directly
	// Format: /sys/class/gpio/gpiochip<chip>/line<line>/value
	valuePath := fmt.Sprintf("/sys/class/gpio/gpiochip%d/line%d/value", chipNum, r.lineNumber)

	// First try the direct chip approach
	valueFile, err := os.Open(valuePath)
	if err != nil {
		// Fallback: try reading from the global GPIO number
		globalGpioNum := chipNum*32 + r.lineNumber
		valuePath = fmt.Sprintf("/sys/class/gpio/gpio%d/value", globalGpioNum)

		// Check if the GPIO is already exported by the Python program
		if _, err := os.Stat(valuePath); os.IsNotExist(err) {
			// GPIO not exported, try to read from the chip directly using a different approach
			// This is a read-only operation that shouldn't interfere with the Python program
			return 0, fmt.Errorf("GPIO %d not accessible for reading (may not be exported): %v", r.gpioNumber, err)
		}

		valueFile, err = os.Open(valuePath)
		if err != nil {
			return 0, fmt.Errorf("failed to open GPIO value file for GPIO %d: %v", r.gpioNumber, err)
		}
	}
	defer valueFile.Close()

	scanner := bufio.NewScanner(valueFile)
	if !scanner.Scan() {
		return 0, fmt.Errorf("failed to read GPIO value for GPIO %d", r.gpioNumber)
	}

	value, err := strconv.Atoi(strings.TrimSpace(scanner.Text()))
	if err != nil {
		return 0, fmt.Errorf("failed to parse GPIO value for GPIO %d: %v", r.gpioNumber, err)
	}

	return value, nil
}

func (r *GPIOReader) publishReading() {
	value, err := r.readGPIOValue()
	if err != nil {
		log.Printf("Error reading GPIO %d: %v", r.gpioNumber, err)
		return
	}

	topic := fmt.Sprintf("gpio/%d", r.gpioNumber)
	payload := fmt.Sprintf("%d", value)

	token := r.client.Publish(topic, 0, false, payload)
	if token.Wait() && token.Error() != nil {
		log.Printf("Error publishing to topic %s: %v", topic, token.Error())
		return
	}
}

func (r *GPIOReader) Start() {
	defer r.wg.Done()

	log.Printf("Starting GPIO reader for GPIO %d (chip: %s, line: %d)",
		r.gpioNumber, r.chipPath, r.lineNumber)

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			r.publishReading()
		}
	}
}

func main() {
	log.Println("Starting ADC and GPIO reader")

	// Auto-detect ADC devices
	devices, err := detectADCDevices()
	if err != nil {
		log.Fatalf("Failed to detect ADC devices: %v", err)
	}

	// Verify we have both required devices
	if _, ok := devices["48"]; !ok {
		log.Fatalf("ADC device at address 0x48 not found")
	}
	if _, ok := devices["49"]; !ok {
		log.Fatalf("ADC device at address 0x49 not found")
	}

	log.Printf("Found ADC devices: 0x48 -> %s, 0x49 -> %s", devices["48"], devices["49"])

	// MQTT client options
	opts := MQTT.NewClientOptions()
	opts.AddBroker(mqttBroker)
	opts.SetClientID("adc-reader")
	opts.SetConnectRetry(false)
	opts.SetConnectRetryInterval(5 * time.Second)

	// Create MQTT client
	client := MQTT.NewClient(opts)

	// Connect to MQTT broker
	if token := client.Connect(); token.Wait() && token.Error() != nil {
		log.Fatalf("Failed to connect to MQTT broker: %v", token.Error())
	}
	log.Printf("Connected to MQTT broker: %s", mqttBroker)

	// Create wait group for goroutines
	var wg sync.WaitGroup

	// Start ADC readers for all channels using the mapping
	for _, mapping := range channelMapping {
		realChannel := mapping[0]
		mqttChannel := mapping[1]

		// Determine which device to use
		var devicePath string
		if realChannel >= 4 && realChannel <= 7 {
			devicePath = devices["49"] // 0x49
		} else {
			devicePath = devices["48"] // 0x48
		}

		reader := NewADCReader(realChannel, mqttChannel, devicePath, client, &wg)
		wg.Add(1)
		go reader.Start()
	}

	// Start GPIO readers for all configured pins (if any)
	gpioCount := 0
	for gpioNum := range gpioPinMap {
		reader := NewGPIOReader(gpioNum, client, &wg)
		if reader != nil {
			wg.Add(1)
			go reader.Start()
			gpioCount++
		}
	}

	if gpioCount > 0 {
		log.Printf("All ADC and %d GPIO readers started. Press Ctrl+C to stop.", gpioCount)
	} else {
		log.Println("All ADC readers started (no GPIO readers configured). Press Ctrl+C to stop.")
	}

	// Wait for all goroutines (they run indefinitely)
	wg.Wait()
}
