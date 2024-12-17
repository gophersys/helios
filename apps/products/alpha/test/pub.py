import paho.mqtt.client as mqtt
import time
import math
import threading

# MQTT Broker configuration
BROKER_ADDRESS = "localhost"  # Replace with your broker's address
BROKER_PORT = 1883
TOPIC_BASE = "sensor"

# Initialize the MQTT client with protocol version 5
client = mqtt.Client(protocol=mqtt.MQTTv311, callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
client.connect(BROKER_ADDRESS, BROKER_PORT)

# Frequency in Hz for sine and cosine waves
BASE_FREQ = 1  # 1 Hz frequency for demonstration
AMPLITUDE = 1  # Amplitude of the waves


# Function to publish data to a topic
def publish(topic, data):
    client.publish(topic, str(data))


# Function to generate sinusoidal data for accelerometer (sine) and PPG (cosine)
def generate_sin_data(t, rate):
    accelerometer_data = AMPLITUDE * math.sin(2 * math.pi * BASE_FREQ * t)
    ppg_data = [AMPLITUDE * math.cos(2 * math.pi * BASE_FREQ * t)]
    return accelerometer_data, ppg_data


def generate_cos_data(t, rate):
    accelerometer_data = AMPLITUDE * math.cos(2 * math.pi * BASE_FREQ * t)
    ppg_data = [AMPLITUDE * math.sin(2 * math.pi * BASE_FREQ * t)]
    return accelerometer_data, ppg_data


# Function to convert 32-bit to 16-bit values
def convert_to_16bit(data):
    return [int(value * 32767) for value in data]


# Thread function for publishing at 25 Hz
def publish_25hz():
    t = 0  # Time counter
    while True:
        # Generate sinusoidal data
        accelerometer_data, ppg_data = generate_sin_data(t, 25)

        # Publish raw data at 25 Hz
        publish(f"{TOPIC_BASE}/accelerometer/25hz/32bit/x", accelerometer_data)
        publish(f"{TOPIC_BASE}/ppg/25hz/32bit/x", ppg_data)

        # Update time for the next sample
        t += 1 / 25.0
        time.sleep(0.04)  # Sleep to simulate 25 Hz


# Thread function for publishing at 32 Hz (upsampled and 16-bit)
def publish_32hz():
    time.sleep(5)
    t = 0  # Time counter
    while True:
        # Generate sinusoidal data
        accelerometer_data, ppg_data = generate_cos_data(t, 32)

        # Publish upsampled data at 32 Hz
        publish(f"{TOPIC_BASE}/accelerometer/32hz/32bit/y", accelerometer_data)
        publish(f"{TOPIC_BASE}/ppg/32hz/32bit/y", ppg_data)

        # # Convert to 16-bit and publish
        # accelerometer_data_16bit = convert_to_16bit(accelerometer_data)
        # ppg_data_16bit = convert_to_16bit(ppg_data)
        # publish(f"{TOPIC_BASE}/accelerometer/32hz/16bit", accelerometer_data_16bit)
        # publish(f"{TOPIC_BASE}/ppg/32hz/16bit", ppg_data_16bit)

        # Update time for the next sample
        t += 1 / 32.0
        time.sleep(0.03125)  # Sleep to simulate 32 Hz


# Create and start threads for 25 Hz and 32 Hz publishing
thread_25hz = threading.Thread(target=publish_25hz, daemon=True)
thread_32hz = threading.Thread(target=publish_32hz, daemon=True)
thread_25hz.start()
thread_32hz.start()

try:
    # Keep the main thread alive to let the publishing threads run
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping MQTT data publishing.")
    client.disconnect()
    # No need for explicit thread cleanup as they are daemon threads
