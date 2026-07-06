# Cipher Application Daemon
The cipher daemon is the program in charged of running a set of services related to the cipher networking protocol. The dameon, hereby after refered to as 'cipher-d', is structured into the following building blocks:

## Definitions
- **Encoded Packet**: Network packet in "Network Byte-Order", header + payload
- **Decoded Packet**: Network packet in "Host Byte-Order, header + payload
- **Hop**: The action of a network packet being routed from an incoming interface to an outgoing interface on the same host. 



# Daemon Threads
The daemon can run quite a high number of threads, so they're split up into logical groups below:

## Interfaces

### Transport Abstraction Layer
The protocol was designed to work over a stream-like transport layer. The most obvious case here is TCP sockets, but any transport interface can be used, **only if it guarantees the promises that TCP does for a single socket connection.** 

### Threads
Interfaces are build on top of this transport abstraction layer. Interfaces abstract away the connection management, sending and receiving of packets over the transport layer of choice. Interfaces are implemented as sets of 3 threads:
- **Connection (I-CT):** This thread takes care of calling ***connect()*** or ***accept()*** on the interface, exchanging protocol versions with the remote end, registering an unique ID, as well as taking care of disconnects and claim resources with ***close()***.
- **Send (I-ST):** This thread awaits on 2 queues, one for ***encoded packets*** that need to be routed from another interface, and another queue for ***decoded packets*** that need to be encoded. For both packet types, the thread will call ***send()***.
- **Recv (I-RT):** This thread awaits on ***recv()***, then attempts to decode the packet, and depending on the header type, adds the ***decoded packet*** to the right work queue.

## Service Discovery
### Threads
The protocol works on the notion of services. A device can route packets from one interface to another, allowing packets to "hop" between hosts and reach their final destination. 

- **Receiving (SD-RT):** Listens for new service advertisements from other nodes in the network. When a service advertisement is received, it updates the local service registry. This thread primarily processes incomig information.
- **Broadcasting (SD-B):** Responds to new connections by broadcasting the device's service list and any cached service lists from other devices that are within their allowable hop range. This thread is responsible for sending our information.

## Packet Router
These thread group will be responsible for routing a packet to the right interface if the hosts allows, taking into account hops, connection status, etc.

## Events
This thread group will be called any time an application event needs to be send out on the network, or an event was received on the network for the host, and has to be routed to the application callback provided

## Remote Procedure Calls
This thread group will be called any time a remote host invokes a remote procedure call in the host, which will in turn call the user defined callback, with the right input arguements, and then return back to the network the return value of the function.

# Heaps
### Network Packet 

# Registries

## Service Registry
The service registry is a centralized database (in-memory) that holds information about known services, their associated device IDs and hop counts. 