import 'package:flutter/material.dart';
import 'package:grpc/grpc.dart';
import 'package:mtib_cs_pi_protos/mtib-cs-pi.pbgrpc.dart'; // Ensure this import matches your project structure
import 'dart:io';

enum ServerStatus { idle, connecting, connected, failed }

class Server {
  final String address;
  final int port;
  ServerStatus status = ServerStatus.idle;

  Server(this.address, this.port);
}

class ServerCard extends StatelessWidget {
  final String serverName;
  final ServerStatus status;

  const ServerCard({Key? key, required this.serverName, required this.status})
      : super(key: key);

  @override
  Widget build(BuildContext context) {
    IconData iconData;
    Color iconColor;

    switch (status) {
      case ServerStatus.idle:
        iconData = Icons.lens;
        iconColor = Colors.grey;
        break;
      case ServerStatus.connecting:
        iconData = Icons.sync;
        iconColor = Colors.orange;
        break;
      case ServerStatus.connected:
        iconData = Icons.check_circle_outline;
        iconColor = Colors.green;
        break;
      case ServerStatus.failed:
        iconData = Icons.error_outline;
        iconColor = Colors.red;
        break;
    }

    return Card(
      child: ListTile(
        title: Text(serverName),
        trailing: Icon(iconData, color: iconColor),
      ),
      elevation: 4.0,
      margin: EdgeInsets.all(8),
    );
  }
}

class StartupPage extends StatefulWidget {
  @override
  _StartupPageState createState() => _StartupPageState();
}

class _StartupPageState extends State<StartupPage> {
  final List<Server> servers = [
    Server('control-plane', 12345),
    Server('slot-1', 12345),
    Server('slot-2', 12345),
    Server('slot-3', 12345),
    Server('slot-4', 12345),
    Server('slot-5', 12345),
  ];
  bool isChecking = false;

  void _startHealthChecks() async {
    setState(() {
      isChecking = true;
    });

    for (var server in servers) {
      setState(() {
        server.status = ServerStatus.connecting;
      });
      final isReachable = await isHostReachable(server.address, server.port);
      if (!isReachable) {
        print("${server.address} is not reachable.");
        setState(() {
          server.status = ServerStatus.failed;
        });
        continue;
      }

      final channel = ClientChannel(
        server.address,
        port: server.port,
        options:
            const ChannelOptions(credentials: ChannelCredentials.insecure()),
      );
      final stub = MtibCsPiClient(channel);

      try {
        final response = await stub.healthCheck(HealthCheckRequest());
        if (response.ok) {
          setState(() {
            server.status = ServerStatus.connected;
          });
        } else {
          setState(() {
            server.status = ServerStatus.failed;
          });
        }
      } catch (e) {
        print('Health check failed for ${server.address}: $e');
        setState(() {
          server.status = ServerStatus.failed;
        });
      } finally {
        await channel.shutdown();
      }
    }

    setState(() {
      isChecking = false;
    });
  }

  Future<bool> isHostReachable(String host, int port) async {
    try {
      final socket =
          await Socket.connect(host, port, timeout: Duration(seconds: 5));
      socket.destroy();
      return true;
    } on SocketException {
      return false;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text("Server Connection Status")),
      body: Padding(
        padding: const EdgeInsets.all(8.0),
        child: Column(
          children: [
            Expanded(
              child: ListView.builder(
                itemCount: servers.length,
                itemBuilder: (context, index) {
                  return ServerCard(
                    serverName: servers[index].address,
                    status: servers[index].status,
                  );
                },
              ),
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                ElevatedButton(
                  onPressed: isChecking ? null : _startHealthChecks,
                  child: Text('Connect'),
                ),
                ElevatedButton(
                  onPressed: () {
                    if (isChecking) {
                      // To implement: Cancel the ongoing
                      // Reset the servers' statuses to idle
                      for (var server in servers) {
                        server.status = ServerStatus.idle;
                      }
                      // Stop further checking by setting isChecking to false
                      setState(() {
                        isChecking = false;
                      });
                    }
                  },
                  child: Text('Cancel'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
