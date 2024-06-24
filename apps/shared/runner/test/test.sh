#!/bin/bash

# Arrays for GPIO pins, types, and resistor configurations
gpio_pins=("GPIO_0" "GPIO_1")
gpio_types=("GPIO_INPUT" "GPIO_OUTPUT")
adc_channels=("ADC_CHANNEL_1" "ADC_CHANNEL_2" "ADC_CHANNEL_3" "ADC_CHANNEL_4" "ADC_CHANNEL_5" "ADC_CHANNEL_6" "ADC_CHANNEL_7")
delay_ms=50

# Gpio
for pin in "${gpio_pins[@]}"; do
    # Iterate over each GPIO type
    for type in "${gpio_types[@]}"; do
        # Configure the GPIO pin
        echo "Configuring $pin as $type"
        python3 cli.py gpio-config --gpio=$pin --type=$type --resistor=GPIO_RESISTOR_PULL_UP
    done
    
    # Set the GPIO pin to high state
    echo "Writing high state to $pin"
    python3 cli.py gpio-write --gpio=$pin --state=true
    
    # Read back the GPIO pin state
    echo "Reading state from $pin"
    python3 cli.py gpio-read --gpio=$pin
done

# Adc
for channel in "${adc_channels[@]}"; do
    echo "Reading from $channel with a delay of $delay_ms ms"
    python3 cli.py adc-read --channel=$channel --delay-ms=$delay_ms
done

# python3 cli.py adc-read-all --delay-ms=$delay_ms

# Firmware files
# python3 cli.py upload-fw-file zephyr.hex
# python3 cli.py list-fw-files
# python3 cli.py delete-fw-file zephyr.hex

# J Link
python3 cli.py list-jlinks

# Dut
python3 cli.py dut-power-enable --enable=true
python3 cli.py dut-charge-power-enable --enable=true
python3 cli.py dut-power-enable --enable=false
python3 cli.py dut-charge-power-enable --enable=false
python3 cli.py dut-current-read
python3 cli.py dut-voltage-read
python3 cli.py dut-power-read
python3 cli.py altimeter-read
python3 cli.py accel-read
python3 cli.py accel-read-max-force
python3 cli.py eeprom-write 100 "Hello world!"
python3 cli.py eeprom-read 100 12
