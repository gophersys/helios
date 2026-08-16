//TODO: this document
# Zephyr DNSSEC Library Implementation Example

## Overview
This example demonstrates the implementation of CoreKinect's DNSSEC (DNS Security Extensions) library in the Zephyr RTOS environment. It showcases how to resolve domain names with DNSSEC validation using the Zephyr networking stack and TinyCrypt library for cryptographic operations.

## Requirements
- Zephyr RTOS environment set up.
- TinyCrypt library for cryptographic functions.
- A supported board (e.g., Nucleo H743ZI) or any other Zephyr-supported hardware platform.

## Build and Running
The example can be built and run using `west`, Zephyr's command-line tool. 

### Default Setup (Nucleo H743ZI)
For users with the Nucleo H743ZI board, the following `.vscode` tasks are provided for convenience:

- **West Build**: Builds the project.
- **West Clean Build**: Cleans and builds the project from scratch.
- **West Flash**: Flashes the built binary onto the board.

To use these tasks, select the desired task through the command paletter ***(CTRL+Shift+P) + Run Task***

### Other Boards
For other boards, use the standard Zephyr build and flash commands:
```bash
west build -p auto -b your_board_name
west flash
```
Replace your_board_name with the name of your board.

### Serial Terminal
To view the sample output, connect to the board's serial port using a terminal emulator (e.g., PuTTY, minicom) set to 115200 baud rate.

### Sample Output
Upon successful execution, you should see output similar to the following in your serial terminal:
```c
[00:00:10.457,000] <inf> app: IP Addr: 192.168.0.40
[00:00:10.458,000] <inf> app: Subnet: 255.255.255.0
[00:00:10.459,000] <inf> app: Router: 192.168.0.1
[00:00:10.459,000] <inf> app: Resolver [0]: 192.168.0.1
[00:00:10.726,000] <inf> dns_sec: DNS info record verified successfully
[00:00:10.727,000] <inf> app: Address was succesfully resolved with DNSSEC!
[00:00:10.728,000] <inf> app: Resolved IPv4 Addr: 52.126.32.170
```

### Kconfig Options
The project uses the following Kconfig options:
```c
config DNS_SEC_SAMPLE_HOST_URL
    string "Description of the configuration"
    default "sigma.blackohm.cloud"
```
Ensure to set DNS_SEC_SAMPLE_HOST_URL to the domain you wish to resolve using DNSSEC. This can be done in the project's prj.conf file.

### Additional Notes
This example assumes a basic familiarity with Zephyr and its build system.
Make sure your board is connected to a network capable of DNS resolution.
The example covers basic DNSSEC operations. For advanced usage, refer to the DNSSEC library documentation.