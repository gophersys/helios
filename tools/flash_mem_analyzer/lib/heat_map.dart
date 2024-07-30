import 'package:flutter/material.dart';

class HeatMap extends StatelessWidget {
  final List<List<int>> data;
  final int blockSize;
  final int pageSize;
  final int memorySize;

  HeatMap(
      {required this.data,
      required this.blockSize,
      required this.pageSize,
      required this.memorySize});

  @override
  Widget build(BuildContext context) {
    int blocks = memorySize ~/ blockSize;
    int pagesPerBlock = blockSize ~/ pageSize;

    print("total of ${blocks}");

    return Container(
      padding: EdgeInsets.all(8.0),
      child: Column(
        children: List.generate(blocks, (blockIndex) {
          return Row(
            children: [
              Text('$blockIndex'),
              Row(
                children: List.generate(pagesPerBlock, (pageIndex) {
                  int dataIndex = blockIndex * pagesPerBlock + pageIndex;
                  int rowIndex = dataIndex ~/ pagesPerBlock;
                  int colIndex = dataIndex % pagesPerBlock;

                  return Container(
                    width: 10,
                    height: 10,
                    color: getColor(data[rowIndex][colIndex]),
                    margin: EdgeInsets.all(1.0),
                  );
                }),
              ),
            ],
          );
        }),
      ),
    );
  }

  Color getColor(int intensity) {
    int value = (255 * (intensity / 100)).clamp(0, 255).toInt();
    return Color.fromARGB(255, value, 0, 0);
  }
}
