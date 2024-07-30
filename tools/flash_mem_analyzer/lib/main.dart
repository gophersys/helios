import 'package:flutter/material.dart';
import 'heat_map.dart';

void main() {
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Heat Map Demo',
      theme: ThemeData(
        primarySwatch: Colors.blue,
      ),
      home: MyHomePage(),
    );
  }
}

class MyHomePage extends StatefulWidget {
  @override
  _MyHomePageState createState() => _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  final int blockSize = 64 * 2048; // 128 KB
  final int pageSize = 2048; // 2 KB
  final int memorySize = 1 * 1024 * 1024; // 1 MB
  late List<List<int>> data;

  @override
  void initState() {
    super.initState();
    int blocks = memorySize ~/ blockSize;
    int pagesPerBlock = blockSize ~/ pageSize;
    data = List.generate(blocks, (i) => List.generate(pagesPerBlock, (j) => 0));
  }

  void _updateHeatMap() {
    setState(() {
      int blocks = memorySize ~/ blockSize;
      int pagesPerBlock = blockSize ~/ pageSize;
      for (int i = 0; i < blocks; i++) {
        for (int j = 0; j < pagesPerBlock; j++) {
          data[i][j] = (data[i][j] + 10) % 100; // Simulate some changes
        }
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Heat Map Demo'),
      ),
      body: Center(
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SingleChildScrollView(
            scrollDirection: Axis.vertical,
            child: HeatMap(
              data: data,
              blockSize: blockSize,
              pageSize: pageSize,
              memorySize: memorySize,
            ),
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _updateHeatMap,
        tooltip: 'Update Heat Map',
        child: Icon(Icons.refresh),
      ),
    );
  }
}
