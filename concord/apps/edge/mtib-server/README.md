# MTIB Server Application

## Overview

The MTIB Server is a gRPC ([gRPC](../../../libs/protocols/mtib/mtib.proto)) server that provides a network API for the MTIB hardware. It is written in Python and uses the different libraries to communicate with the hardware.

## Features

- ***GPIO control:*** Control the GPIO pins on the MTIB hardware.
- ***ADC control:*** Control the ADC pins on the MTIB hardware.
- ***Power control:*** Control the power to the MTIB hardware.
- ***Sensors:*** Read the sensors on the MTIB hardware.
- ***Motion control:*** Control the motion of the MTIB hardware.
- ***Firmware control:*** Control the firmware on the MTIB hardware.

## Hardware Revisions Supported

| Revision | Description | Support Status |
|----------|-------------|----------------|
| REV1.0 | The initial hardware revision of the MTIB hardware | Not supported by this server |
| REV1.1 | The first hardware revision of the MTIB hardware | Supported |
| REV1.2 | The second hardware revision of the MTIB hardware | Supported |