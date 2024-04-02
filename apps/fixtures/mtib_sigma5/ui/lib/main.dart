import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/app_state.dart';
import 'ui/pages/startup_page.dart';
import 'ui/pages/login_page.dart';
import 'ui/pages/home_page.dart';

void main() {
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (context) => AppState()),
      ],
      child: MaterialApp(
        title: 'Flutter Desktop App',
        initialRoute: '/',
        routes: {
          '/': (context) => StartupPage(),
          '/login': (context) => LoginPage(),
          '/home': (context) => HomePage(),
        },
      ),
    );
  }
}


// import 'package:flutter/material.dart';
// import 'package:grpc/grpc.dart';
// import 'package:mtib_cs_pi_protos/mtib-cs-pi.pbgrpc.dart';

// void main() {
//   runApp(const MyApp());
// }

// class MyApp extends StatelessWidget {
//   const MyApp({super.key});

//   // This widget is the root of your application.
//   @override
//   Widget build(BuildContext context) {
//     return MaterialApp(
//       title: 'Flutter Demo',
//       theme: ThemeData(
//         colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
//         useMaterial3: true,
//       ),
//       home: const MyHomePage(title: ''),
//     );
//   }
// }

// class MyHomePage extends StatefulWidget {
//   const MyHomePage({super.key, required this.title});
//   final String title;

//   @override
//   State<MyHomePage> createState() => _MyHomePageState();
// }

// class _MyHomePageState extends State<MyHomePage> {
//   String adcReading = '0';
//   late ClientChannel channel;
//   late MtibCsPiClient stub;

//   @override
//   void initState() {
//     super.initState();
//     // Initialize the gRPC channel and stub here
//     channel = ClientChannel(
//       'control-plane', // Your gRPC server address
//       port: 12345, // Your gRPC server port
//       options: const ChannelOptions(
//         credentials: ChannelCredentials.insecure(),
//       ),
//     );
//     stub = MtibCsPiClient(channel);
//   }

//   Future<void> readAdcValue() async {
//     try {
//       final response = await stub.adcRead(
//         AdcReadRequest()
//           ..channel = AdcChannel.ADC_CHANNEL_0
//           ..delayMs = 50,
//       );

//       if (response.success) {
//         setState(() {
//           adcReading = response.voltage.toString();
//         });
//       } else {
//         print('Error reading ADC: ${response.error}');
//       }
//     } catch (e) {
//       print('Caught error: $e');
//     }
//     // No need to shut down the channel after each request
//   }

//   @override
//   void dispose() {
//     // Shutdown the gRPC channel when the widget is disposed
//     channel.shutdown();
//     super.dispose();
//   }

//   @override
//   Widget build(BuildContext context) {
//     // Widget build method remains unchanged
//     return Scaffold(
//       appBar: AppBar(
//         backgroundColor: Theme.of(context).colorScheme.inversePrimary,
//         title: Text(widget.title),
//       ),
//       body: Center(
//         child: Column(
//           mainAxisAlignment: MainAxisAlignment.center,
//           children: <Widget>[
//             const Text('ADC Voltage Reading:'),
//             Text(
//               adcReading,
//               style: Theme.of(context).textTheme.headlineMedium,
//             ),
//           ],
//         ),
//       ),
//       floatingActionButton: FloatingActionButton(
//         onPressed: readAdcValue,
//         tooltip: 'Read ADC',
//         child: const Icon(Icons.add),
//       ),
//     );
//   }
// }
