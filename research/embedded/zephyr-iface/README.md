# Zephyr Interface Library

## What does this library do?
This library provides an easy-to-use API to connect, send and recv data on communication interfaces. The goal of this library, is to abstract away the transport layer from the application, allowing users to write socket-like code but be able to user other physicial interfaces, such as UART.

The library does a CRC32 check on it's payloads, and if there's a mismatch a fatal error is thrown. This removes the responsability of data integrity checks at the application layer.

***Only UDP-like communication is currently supported for UART Sockets!***

## Why create this library?
At CoreKinect, we're constantly evolving and adapting new technologies in the embedded space. One of our key partnets Nordic Semiconductors makes hardware that is very useful to us, but that does not provide more advanced networking capabilities like Wi-Fi or Ethernet, and therefore lack a sockets API.

POSIX Sockets have been around for many years and have proven to be a meaningful abstraction layer between the application layer and the underlying hardware that is handling how this data gets from point A to point B.

We have a situation where we need our devs to quickly spin up a new test fixture or setup a prototype with one of these microcontrollers, but the most immediate interface is UART.

However, the UART API from Zephyr isn't the most straightforward. Nor can we do things like detect when a remote end isn't connected, or when it disconnects. This can be specially frustrating to someone who isn't be focused on getting a basic connection to work.

## Socket-like API

The aim of the API is to make obvious errors like timeout or connections closed obvious and easy to handle. The complexity of how these errors arise can then be abstracted away in the library implementation. The ***listen()*** function was not implemented (it's abstracted away inside of connect)

```c
bool iface_create(iface_t *p_iface);
bool iface_set_opt(iface_t *p_iface, iface_opt_t type, void *p_option, size_t option_size);
bool iface_connect(iface_t *p_iface, bool *timeout);
bool iface_accept(iface_t *p_iface, bool *timeout);
bool iface_send(const iface_t *p_iface, const void *p_buffer, const size_t buffer_size,
                uint16_t *p_send_count, bool *p_conn_closed, bool *p_timeout);
bool iface_recv(const iface_t *p_iface, void *p_buffer, const size_t buffer_size,
                uint16_t *p_recv_count, bool *p_conn_closed, bool *p_timeout);
bool iface_close(const iface_t *p_iface);
```
## Memory consumption
For UART sockets, it's a total of 


# How to include library into a project

1. Clone the submodule (this repo) into your project's directory, where you find it most appropiate for your architecture, in this example, it's being cloned into the root of a standard Zephyr app
```bash
git submodule add git@bitbucket.org:corekinect/iface.git
```

2. Add the library to your projects top level ***CMakeLists.txt***
```CMake
cmake_minimum_required(VERSION 3.20.0)

# Add the library at this level
list(APPEND ZEPHYR_EXTRA_MODULES
  ${CMAKE_CURRENT_SOURCE_DIR}/iface  
  )

find_package(Zephyr)
```

3. Add the right Kconfig option to your top level ***prj.conf***
```Kconfig
# Uart Sockets
CONFIG_CK_IFACE_LIB_UART=y

# TCP Sockets
CONFIG_CK_IFACE_LIB_UART=y
```
# Samples
Example implementations of servers and clients for UART sockets and TCP sockets can be found under **samples/**

# Implementation Details
## TCP Sockets
These functions implement the zephyr's BSD Sockets API, very straight forward as most all functions match the iface API.

## UART Sockets
Similar to a TCP/IP stack, a thread is in charge or handling multiple UART sockets. This logic works on the concept of "registered" and "unregistered" devices to enable the UART peripheral associated with an interface. 

The thread implements Zephyr's UART async API, which is a highly efficient and interrupt driven API. Therefore the CPU consumption of this thread is very 
minimal. The API uses a callback that tells use when data was sent or received on a specific interface. UART data is always received as a stream of bytes.

### Handling stream data
Because UART is a raw transport interface, there's not really a "protocol" per se running on top of it. Rather the user sends a raw array of bytes, and also receives a raw array of bytes. 

A small protocol was created to add enough functionality to create a reliable transport layer:
- **Start delimiter:** Which helps differentiate when a new packet begins.
- **Payload length:** Which helps determine the end of a packet. 
- **CRC32 on all the data:** Which helps to easily determine when a data corruption error has occurred.
Other fields also include a sequence number and packet types, but these are not being used right now (reserved for TCP-like implementation)

### Receiving data
When data is received on the UART callback, it's added to a ring buffer, and then packets are "assembled" from this ring buffer.

Assembling a packet consists of ensuring the entire payload was received, and a CRC32 was run on it to ensure data integrity. Only if it passes these checks, is this newly received packet added to a recv FIFO.

When the user calls ***iface_recv()*** we pop the first item on the queue and return the data. 

### Sending data
This one is more straightforward. We pack the user data + protocol header into a buffer, and tell the UART async API to send this data. If we don't get notified that the data was sent or that only some of the data was sent, we then signal the user that an error has occurred.

# Configuration Options
Below are some of the options you're most likely going to want to interact with. 

***All configuration options alongside their descriptions can be found in the Kconfig file in this repo.***

## Debugging
```Kconfig
# Set to level DBG (4) to see useful output from the UART sockets thread, such as state, register/unregister events, etc
CONFIG_CK_IFACE_LIB_STACK_DEBUG_LEVEL

# Set to level DBG (4) to see useful output regarding the raw data being received on the UART device, and how its being put into packets
CONFIG_CK_IFACE_LIB_ASSEMBLER_DEBUG_LEVEL
```

## Number of UART ports you'd like to use
```Kconfig
CONFIG_CK_IFACE_NUM_UART_SOCKETS
```
